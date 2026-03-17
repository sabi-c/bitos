# Agent Interactive Forms — Design Document

**Date:** 2026-03-17
**Status:** Design
**Depends on:** ApprovalOverlay, ChatPanel voice pipeline, BackendClient SSE protocol

---

## 1. Problem

The agent sometimes needs structured input from the user mid-conversation — "What kind of task?", "Which priority?", "Should I send this?". Today the only mechanism is `request_approval`, which shows a simple overlay with 2-3 options and no way to provide freeform input. There is no way for the agent to ask a *sequence* of questions, and no way for the user to answer "something else" by voice.

This design introduces **Agent Interactive Forms**: a structured prompt system where the agent can present multi-choice questions (with an optional voice escape hatch), stack up to 3 questions, and collect all answers before continuing.

---

## 2. Server Protocol

### 2.1 New SSE event: `form_request`

The agent returns a structured block via tool_use. The server emits it as an SSE event during the chat stream, then blocks (same pattern as `approval_request`).

```json
{
  "form_request": {
    "id": "form_a1b2c3d4",
    "questions": [
      {
        "id": "q1",
        "text": "What kind of task?",
        "options": ["Work", "Personal", "Creative"]
      },
      {
        "id": "q2",
        "text": "Priority?",
        "options": ["High", "Medium", "Low"]
      }
    ]
  }
}
```

**Rules:**
- Max 3 questions per form.
- Max 3 explicit options per question (A, B, C). Option D ("Something else...") is always implicitly appended by the device.
- Question text max 80 chars (device truncates at 3 wrapped lines).
- Option text max 20 chars per option.

### 2.2 New tool definition: `request_user_input`

Added to the `TOOLS` list in `server/agent_tools.py`:

```python
{
    "name": "request_user_input",
    "description": (
        "Present structured questions to the user on their device. "
        "Use this when you need specific information to proceed — task type, "
        "priority, preferences, or confirmation with an edit option. "
        "Each question shows multiple-choice options. The user can also "
        "choose 'Something else' and speak a freeform answer. "
        "Max 3 questions, max 3 options each. Returns all answers."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "description": "List of questions to ask.",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The question text (max 80 chars).",
                        },
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "2-3 answer options (max 20 chars each).",
                            "maxItems": 3,
                            "minItems": 1,
                        },
                    },
                    "required": ["text", "options"],
                },
                "maxItems": 3,
                "minItems": 1,
            },
        },
        "required": ["questions"],
    },
}
```

### 2.3 Server-side blocking (same pattern as approval)

In `server/agent_tools.py`, add form request management alongside the existing approval system:

```
_pending_forms: dict[str, dict] = {}  # form_id -> {"event": Event, "answers": None}
_forms_lock = threading.Lock()
```

Functions: `create_form_request()`, `wait_for_form()`, `resolve_form()`.

In `server/llm_bridge.py`, when the model calls `request_user_input`:
1. Validate and clamp questions (max 3, max 3 options each).
2. Call `create_form_request()` to get `(form_id, sse_data)`.
3. `yield sse_data` so the SSE stream emits `form_request`.
4. `wait_for_form(form_id, timeout=120.0)` blocks the tool loop.
5. Return answers as tool_result JSON.

### 2.4 Device submission endpoint: `POST /chat/form`

```json
POST /chat/form
{
  "form_id": "form_a1b2c3d4",
  "answers": [
    {"question_id": "q1", "answer": "Work"},
    {"question_id": "q2", "answer": "Actually, it's a client deliverable for Friday"}
  ]
}
```

Added to `server/main.py` alongside `/chat/approval`. Calls `resolve_form()`.

### 2.5 Approval flows as a subset

Simple approval ("Should I send this email?" -> YES / NO / EDIT) maps directly to a single-question form:

```json
{
  "questions": [{
    "text": "Should I send this email?",
    "options": ["Yes", "No", "Edit"]
  }]
}
```

When "Edit" (or any freeform answer) is selected, the voice recording flow kicks in. This means `request_approval` can remain as-is for backward compatibility, while the new `request_user_input` handles richer cases. Over time, the agent can prefer `request_user_input` for all structured prompts.

---

## 3. Device-Side Architecture

### 3.1 New file: `device/overlays/form_overlay.py`

A new `FormOverlay` class, duck-typing with `ApprovalOverlay` / `AgentOverlay` so it can be hosted in `ScreenManager._active_banner`.

**Required interface (duck-type):**
- `dismissed: bool` property
- `tick(dt_ms: int) -> bool` — returns True while alive
- `handle_action(action: str) -> bool` — intercept gestures
- `render(surface: pygame.Surface) -> None` — draw on full screen

### 3.2 FormOverlay state machine

```
SHOWING_QUESTION
    |
    |-- SHORT_PRESS --> cycle selection (A -> B -> C -> D -> A)
    |-- TRIPLE_PRESS --> cycle selection backward (A -> D -> C -> B -> A)
    |-- DOUBLE_PRESS on A/B/C --> record answer, advance to next question
    |-- DOUBLE_PRESS on D ("Something else") --> transition to RECORDING
    |-- LONG_PRESS --> CANCELLED (dismiss entire form)
    |
RECORDING
    |
    |-- SHORT_PRESS / DOUBLE_PRESS --> stop recording, go to TRANSCRIBING
    |-- LONG_PRESS --> cancel recording, back to SHOWING_QUESTION (same question)
    |
TRANSCRIBING
    |
    |-- (automatic) on success --> CONFIRM_FREEFORM
    |-- (automatic) on failure --> RECORDING_ERROR
    |
RECORDING_ERROR
    |
    |-- SHORT_PRESS --> retry (back to RECORDING)
    |-- LONG_PRESS --> back to SHOWING_QUESTION
    |
CONFIRM_FREEFORM
    |  (shows transcribed text + "SEND" / "GO BACK")
    |
    |-- SHORT_PRESS --> toggle between SEND and GO BACK
    |-- DOUBLE_PRESS on SEND --> record answer, advance to next question
    |-- DOUBLE_PRESS on GO BACK --> back to SHOWING_QUESTION (same question)
    |-- LONG_PRESS --> back to SHOWING_QUESTION
    |
SUBMITTING (after final question answered)
    |
    |-- (automatic) POST /chat/form, then dismiss
    |
CANCELLED
    |
    |-- POST /chat/form with {"cancelled": true}, then dismiss
```

### 3.3 Internal data model

```python
@dataclass
class FormOverlay:
    form_id: str
    questions: list[dict]           # [{"id": "q1", "text": "...", "options": [...]}]
    client: BackendClient
    audio_pipeline: object | None
    led: object | None
    on_dismiss: Callable | None

    # Internal
    _current_question: int = 0      # index into questions[]
    _answers: list[dict] = []       # [{"question_id": "q1", "answer": "Work"}, ...]
    _selected_option: int = 0       # 0=A, 1=B, 2=C, 3=D (something else)
    _state: FormState = FormState.SHOWING_QUESTION
    _transcript: str = ""
    _confirm_selected: int = 0      # 0=SEND, 1=GO BACK
    _dismissed: bool = False
    _elapsed_ms: int = 0
    _timeout_ms: int = 120_000      # 2 min total timeout
```

### 3.4 Where it lives in the overlay stack

Wired up in `device/main.py` the same way as `ApprovalOverlay`:

```python
# In BackendClient._stream_chat_sse, handle "form_request" SSE events
# alongside "approval_request":
elif "form_request" in chunk:
    self._handle_form_request(chunk["form_request"])
```

```python
# In main.py:
def show_form_overlay(form_id, questions):
    overlay = FormOverlay(
        form_id=form_id,
        questions=questions,
        client=client,
        audio_pipeline=audio_pipeline,
        led=led,
        on_dismiss=lambda: screen_mgr.dismiss_banner(),
    )
    screen_mgr.show_banner(overlay)

client.on_form_request = show_form_overlay
```

---

## 4. Rendering (156px right panel or full-screen overlay)

The form renders as a **full-screen overlay** (like ApprovalOverlay), not inside the chat panel. This is simpler — the form captures all gestures, dims the background, and draws a centered card.

### 4.1 Question card layout (240x280 screen)

```
+----------------------------------+
|  (dim background, alpha 180)     |
|                                  |
|  +----------------------------+  |  card_x = SAFE_INSET (16)
|  | QUESTION 1/2          [DIM2] |  card_w = 208
|  |                              |
|  | What kind of task?     [WHITE]|  word-wrapped, max 3 lines, body font
|  |                              |
|  | ─────────────────────── [HAIRLINE]
|  |                              |
|  |   Work              [DIM1]   |  option A
|  | > Personal          [WHITE on WHITE rect] | option B (selected)
|  |   Creative          [DIM1]   |  option C
|  |   Something else... [DIM3]   |  option D (dimmer)
|  |                              |
|  | ─────────────────────── [HAIRLINE]
|  | TAP:next DBL:pick LONG:quit  |  hint font, DIM3
|  | ████████░░░░░░░░░░░░░░ [progress bar]
|  +----------------------------+  |
|                                  |
+----------------------------------+
```

**Selection rendering:**
- Selected option: WHITE background rectangle, BLACK text, `> ` prefix.
- Unselected A/B/C: DIM1 text, `  ` prefix.
- Option D: DIM3 text (visually distinct as escape hatch), `  ` prefix. When selected: same WHITE rect treatment but text stays dimmer than A-C.

**Option row height:** `max(22, font.get_height() + 8)` — same as ApprovalOverlay.

### 4.2 Recording state (within the same card)

When the user selects "Something else" and presses DOUBLE:

```
+----------------------------+
| QUESTION 1/2          [DIM2]|
|                             |
| What kind of task?   [WHITE]|
|                             |
| ──────────────────────      |
|                             |
|  ● REC 0:03          [RED]  |  pulsing red dot + timer (same as ChatPreviewPanel)
|                             |
|  Click to stop       [DIM3] |
|                             |
| ──────────────────────      |
| TAP:stop  LONG:cancel       |
+----------------------------+
```

### 4.3 Confirm freeform answer

After transcription succeeds:

```
+----------------------------+
| QUESTION 1/2          [DIM2]|
|                             |
| What kind of task?   [WHITE]|
|                             |
| ──────────────────────      |
|                             |
| "A client deliverable  |    |  WHITE text, word-wrapped, max 2 lines
|  for Friday"           |    |  with horizontal scroll if single-line overflow
|                             |
| ──────────────────────      |
|                             |
| > SEND             [selected]|
|   GO BACK          [DIM1]   |
|                             |
| TAP:next DBL:pick LONG:back |
+----------------------------+
```

**Horizontal text scroll for single-line overflow:** If the transcribed text fits on one line but exceeds the card width, the text renders with a negative x-offset that auto-scrolls (2px/frame) to reveal the full content, then pauses at the end. This matches the "typed out" feel requested. For multi-line text, standard word-wrap is used (max 2 lines, truncated with "..." if longer).

### 4.4 Question transitions

When an answer is recorded (DOUBLE_PRESS on an option or SEND):
1. Brief flash: selected option inverts (50ms, ~1 frame at 15fps).
2. `_current_question += 1`.
3. If more questions remain: reset `_selected_option = 0`, redraw with next question.
4. If final question: transition to SUBMITTING state.

No animation between questions — instant swap. The "QUESTION 1/2" -> "QUESTION 2/2" header change provides enough context.

---

## 5. Multi-Question Stacking

### 5.1 Answer accumulation

Answers are stored in `_answers: list[dict]` as each question is completed:

```python
self._answers.append({
    "question_id": self.questions[self._current_question]["id"],
    "answer": selected_text,  # option label or transcribed text
    "source": "option" | "voice",
})
```

### 5.2 Final submission

After the last question is answered:

1. State transitions to `SUBMITTING`.
2. Card shows "SENDING..." centered (like the LAUNCHING state in ChatPreviewPanel).
3. Background thread calls:
   ```python
   self.client.submit_form(self.form_id, self._answers)
   ```
4. On success: overlay dismisses. The server unblocks the tool loop, the agent receives all answers and continues generating its response. The chat panel picks up the streamed text as normal.
5. On failure: show error in card, SHORT_PRESS to retry, LONG_PRESS to cancel.

### 5.3 Typing out the combined response

On the final answer, before submitting, the form overlay:
1. Constructs a summary string from all answers:
   ```
   Task: Work | Priority: High
   ```
   or for voice answers:
   ```
   Task: "A client deliverable for Friday" | Priority: High
   ```
2. This summary is appended to the chat messages as a `user` message via the repository, so it appears in the chat history.
3. The overlay then submits and dismisses. The agent's continued response streams into the chat panel normally.

---

## 6. Integration with Existing Chat Flow

### 6.1 SSE stream handling in BackendClient

In `device/client/api.py`, `_stream_chat_sse()` already handles `approval_request` events. Add a parallel handler:

```python
elif "form_request" in chunk:
    self._handle_form_request(chunk["form_request"])
```

Where `_handle_form_request` calls `self.on_form_request(form_id, questions)` if wired up.

### 6.2 BackendClient new methods

```python
# New callback slot (same pattern as on_approval_request)
self.on_form_request = None  # Callable[[str, list[dict]], None]

def submit_form(self, form_id: str, answers: list[dict]) -> bool:
    """POST /chat/form — submit collected form answers."""
    resp = httpx.post(
        f"{self.base_url}/chat/form",
        json={"form_id": form_id, "answers": answers},
        timeout=10,
        headers=self._request_headers(),
    )
    resp.raise_for_status()
    return bool(resp.json().get("ok"))
```

### 6.3 Chat panel awareness

The ChatPanel itself does not need to know about forms. The form overlay is shown via `ScreenManager._active_banner`, which intercepts all gestures before they reach ChatPanel. When the form is dismissed, the agent's continued response arrives via the normal SSE stream and ChatPanel renders it with pagination/typewriter as usual.

The only interaction point: after the form submits, the combined answer summary is added to the chat message history so the user sees their answers in context.

---

## 7. Edge Cases

### 7.1 Recording fails (no audio, mic error, STT failure)

- Transition to `RECORDING_ERROR` state.
- Show error text in the card: "NO AUDIO DETECTED" or "DIDN'T CATCH THAT" (same copy as ChatPreviewPanel).
- SHORT_PRESS retries (back to RECORDING).
- LONG_PRESS goes back to SHOWING_QUESTION with the same question — the user can pick a predefined option instead.
- The form does not dismiss on recording failure.

### 7.2 User backs out entirely (LONG_PRESS from SHOWING_QUESTION)

- Form is cancelled.
- `POST /chat/form` with `{"form_id": "...", "cancelled": true}`.
- Server resolves the pending form with a "cancelled" result.
- The agent receives `{"cancelled": true}` as the tool_result and must handle gracefully (e.g., "No problem, let me know when you're ready.").
- Overlay dismisses. Chat continues normally.

### 7.3 Timeout (user ignores the form for 2 minutes)

- `tick()` increments `_elapsed_ms`. At 120,000ms, auto-cancel.
- Same cancellation flow as LONG_PRESS.
- Progress bar at bottom of card shows elapsed time (same as ApprovalOverlay).

### 7.4 Form arrives while another overlay is active

- `ScreenManager.show_banner()` replaces the current banner.
- If an ApprovalOverlay is active when a form_request arrives, the approval is replaced.
- This is acceptable because both are agent-initiated and the agent should not send both simultaneously. If it does, the form takes priority (it is the more structured interaction).

### 7.5 Form arrives when chat is not the active screen

- Same as approval_overlay: `main.py` calls `idle_mgr.wake()` to wake the display, then shows the banner overlay on top of whatever screen is active.
- The form overlay renders full-screen with a dimmed background, so it works on any screen.

### 7.6 Network failure during form submission

- `submit_form()` raises an exception.
- Card shows "SEND FAILED" with retry/cancel options.
- If network recovers, retry succeeds.
- If user cancels after failure, the server-side `wait_for_form()` will timeout after 120s and the agent receives "cancelled".

### 7.7 Single-option questions (approval shorthand)

- If a question has only 1 explicit option (e.g., "Confirm?" with just ["Yes"]), the device auto-appends "No" as option B and "Something else..." as option C.
- This prevents dead-end forms where the user has no way to decline.

### 7.8 Empty transcription

- If STT returns empty text, show "NO AUDIO DETECTED" error.
- User can retry or go back to option selection.
- Same handling as ChatPreviewPanel `_run_stt()`.

---

## 8. File Inventory

| File | Action | Description |
|------|--------|-------------|
| `device/overlays/form_overlay.py` | **NEW** | FormOverlay class with state machine, rendering, gesture handling |
| `device/overlays/__init__.py` | EDIT | Add `FormOverlay` to imports and `__all__` |
| `device/client/api.py` | EDIT | Add `on_form_request` callback, `submit_form()` method, handle `form_request` SSE events |
| `device/main.py` | EDIT | Wire `show_form_overlay` callback to client, import FormOverlay |
| `server/agent_tools.py` | EDIT | Add `request_user_input` tool definition, `create_form_request()`, `wait_for_form()`, `resolve_form()` functions, handle in `handle_tool_call()` |
| `server/llm_bridge.py` | EDIT | Handle `request_user_input` tool_use block (same pattern as `request_approval`) |
| `server/main.py` | EDIT | Add `POST /chat/form` endpoint |

---

## 9. Gesture Summary

| State | SHORT_PRESS | DOUBLE_PRESS | LONG_PRESS | TRIPLE_PRESS |
|-------|-------------|--------------|------------|--------------|
| SHOWING_QUESTION | Next option | Select option | Cancel form | Prev option |
| RECORDING | Stop recording | Stop recording | Cancel recording (back to question) | -- |
| TRANSCRIBING | (consumed) | (consumed) | Cancel (back to question) | -- |
| RECORDING_ERROR | Retry | -- | Back to question | -- |
| CONFIRM_FREEFORM | Toggle SEND/BACK | Confirm selection | Back to question | -- |
| SUBMITTING | (consumed) | (consumed) | (consumed) | -- |

---

## 10. Relationship to Existing `request_approval`

`request_approval` remains as a simpler, lighter-weight mechanism for binary choices. `request_user_input` is the richer system for multi-question flows. The agent can use either:

- **Simple confirmation:** `request_approval` with ["Yes", "No"] — shows the existing ApprovalOverlay.
- **Confirmation with edit:** `request_user_input` with one question and ["Yes", "No", "Edit"] — shows FormOverlay. "Edit" maps to "Something else..." (option D) with voice recording.
- **Multi-step intake:** `request_user_input` with 2-3 questions — shows FormOverlay with question stacking.

No migration needed. Both tools coexist. The system prompt can guide the agent on when to use each.
