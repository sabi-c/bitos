# MAIL-RESEARCH-001 — Gmail MCP Integration Research

> Scope: research-only planning artifact for integrating Gmail via the already-connected remote MCP server at `https://gmail.mcp.claude.com/mcp`.
>
> Runtime note: outbound web access from this environment is blocked (HTTP CONNECT 403), so Gmail MCP tool argument schemas could not be live-introspected. The call patterns below are based on the local Anthropic SDK types in this repo runtime and MCP protocol conventions.

## Approach

Unlike iMessage (which requires a separately hosted BlueBubbles server), Gmail uses the existing MCP connection.
The BITOS FastAPI server should call Gmail MCP tools through the Anthropic Messages API using MCP tool-use blocks.

## How BITOS server calls Gmail MCP

BITOS already has an Anthropic client abstraction (`server/llm_bridge.py`).
For Gmail MCP, the reliable pattern is:

1. Provide the remote MCP server in `mcp_servers`.
2. Enable MCP tool usage with a `tools` entry of type `mcp_toolset`.
3. Prompt Claude normally.
4. Handle `mcp_tool_use` blocks and (if needed) send follow-up `mcp_tool_result` blocks in a second turn.

### Recommended Anthropic pattern (remote MCP via Claude)

```python
from anthropic import Anthropic

client = Anthropic(api_key=ANTHROPIC_API_KEY)

response = client.beta.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1000,
    mcp_servers=[
        {
            "type": "url",
            "name": "gmail",
            "url": "https://gmail.mcp.claude.com/mcp",
            # optional depending on connector requirements:
            # "authorization_token": "..."
        }
    ],
    tools=[
        {
            "type": "mcp_toolset",
            "mcp_server_name": "gmail",
        }
    ],
    messages=[
        {
            "role": "user",
            "content": "Search my inbox for unread emails from Joaquin"
        }
    ],
)

for block in response.content:
    if block.type == "mcp_tool_use":
        print(block.server_name, block.name, block.input)
```

> The `computer_20241022` tool type in the example prompt is for Computer Use, not Gmail MCP. For Gmail, use `mcp_servers` + `mcp_toolset`.

### JSON block formats used by Anthropic for MCP

Model-emitted MCP tool call (`mcp_tool_use`):

```json
{
  "type": "mcp_tool_use",
  "id": "toolu_...",
  "server_name": "gmail",
  "name": "gmail_search_messages",
  "input": {
    "query": "is:unread newer_than:7d"
  }
}
```

Client follow-up result block (`mcp_tool_result`) when returning tool output to the model:

```json
{
  "type": "mcp_tool_result",
  "tool_use_id": "toolu_...",
  "content": "{\"messages\":[...]}"
}
```

## Direct MCP call vs Claude-mediated call

### A) Recommended for BITOS: Claude-mediated (above)
- Pros: one existing Anthropic integration path, model can reason over tool output inline.
- Cons: tool schemas are mediated through Anthropic request format.

### B) Direct MCP from Python (without Claude)
Yes, possible in principle, but **not via ad-hoc raw HTTP endpoint calls**.
Correct pattern is an MCP client implementing protocol methods (`initialize`, `tools/list`, `tools/call`) over a supported transport (typically streamable HTTP or stdio depending on server).

High-level direct-MCP sequence:
1. Open MCP transport session to `https://gmail.mcp.claude.com/mcp`.
2. `initialize` handshake.
3. `tools/list` to discover exact schemas.
4. `tools/call` for operations (search/read/draft/etc).

Because BITOS already uses Claude and because this environment cannot reach the remote server, the practical integration plan should prefer Claude-mediated MCP tool calling.

## Gmail MCP Tool Signatures

Confirmed available tools:
- `gmail_search_messages`
- `gmail_read_message`
- `gmail_read_thread`
- `gmail_create_draft`
- `gmail_list_labels`
- `gmail_list_drafts`
- `gmail_get_profile`

Since live introspection is blocked here, below are **working assumptions** aligned with common Gmail query/thread/draft workflows. Implementation should first run `tools/list` against the connected Gmail MCP to lock exact argument names and response shapes.

### gmail_search_messages
Likely input:
```json
{
  "query": "is:unread in:inbox",
  "max_results": 10,
  "label_ids": ["INBOX"]
}
```
Likely output:
```json
{
  "messages": [
    {
      "id": "msg_123",
      "thread_id": "thr_abc",
      "snippet": "Can you resend the invoice...",
      "subject": "Invoice follow-up",
      "from": "Joaquin <joaquin@company.com>",
      "date": "2026-03-14T14:21:00Z",
      "label_ids": ["INBOX", "UNREAD"]
    }
  ],
  "next_page_token": null
}
```

### gmail_read_thread
Likely input:
```json
{
  "thread_id": "thr_abc"
}
```
Likely output:
```json
{
  "thread": {
    "id": "thr_abc",
    "messages": [
      {
        "id": "msg_1",
        "from": "Joaquin <joaquin@company.com>",
        "to": ["you@example.com"],
        "subject": "Invoice follow-up",
        "date": "2026-03-14T14:21:00Z",
        "snippet": "Can you resend...",
        "text_body": "Can you resend the PDF?",
        "label_ids": ["INBOX", "UNREAD"]
      }
    ]
  }
}
```

### gmail_create_draft
Likely input:
```json
{
  "to": ["joaquin@company.com"],
  "subject": "Re: Invoice follow-up",
  "body": "Absolutely — attaching the updated invoice.",
  "thread_id": "thr_abc"
}
```
Likely output:
```json
{
  "draft_id": "dr_456",
  "message_id": "msg_789",
  "thread_id": "thr_abc"
}
```

## BITOS Email Adapter Design

Proposed module: `server/integrations/gmail_adapter.py`

```python
class GmailAdapter:
    def get_inbox(self, limit=10) -> list[dict]:
        """Unread emails, newest first"""

    def get_thread(self, thread_id: str) -> list[dict]:
        """Full conversation thread"""

    def draft_reply(self, thread_id: str, voice_transcript: str) -> str:
        """Claude drafts a reply using thread context"""

    def create_draft(self, to: str, subject: str, body: str) -> str:
        """Creates Gmail draft, returns draft_id"""
        """Tier 1 — confirm before calling"""

    def send_draft(self, draft_id: str) -> bool:
        """Sends existing draft"""
        """Tier 2 — full review before calling"""
```

Normalization target (BITOS-friendly):
- inbox row: `thread_id`, `preview`, `sender`, `subject`, `timestamp`, `unread`
- thread message: `message_id`, `thread_id`, `from`, `to`, `subject`, `timestamp`, `body_text`, `labels`

## Device UI Mapping

Map Gmail fields to BITOS email panel:
- `thread.id` → `thread_id`
- `thread.snippet` → preview text
- `message.from` → sender label
- `message.subject` → subject line
- `message.date` → timestamp
- `UNREAD` label → unread badge

## Permission Tier Mapping

- Read email = Tier 0 (always ok)
- Create draft = Tier 1 (confirm)
- Send = Tier 2 (full review, must see full draft)

## Key Differences from iMessage

- No separate server process (BlueBubbles not needed)
- Drafts can be saved and reviewed before sending
- Thread model vs flat message model
- Subject lines are first-class
- Reply vs Reply All vs Forward distinction
- Gmail labels (multiple states) vs iMessage read/unread simplicity

## Mock Data

Use realistic inbox mock data for development/testing:

```json
[
  {
    "thread_id": "thr_work_001",
    "sender": "Joaquin Rivera <joaquin@acmefinance.com>",
    "subject": "Invoice #4821 missing attachment",
    "preview": "Hey — can you resend the PDF for #4821?",
    "timestamp": "2026-03-14T09:12:00Z",
    "unread": true,
    "labels": ["INBOX", "UNREAD", "CATEGORY_UPDATES"]
  },
  {
    "thread_id": "thr_personal_001",
    "sender": "Anthony <anthony@gmail.com>",
    "subject": "Sunday family lunch",
    "preview": "Can everyone do 1pm this Sunday?",
    "timestamp": "2026-03-13T21:05:00Z",
    "unread": false,
    "labels": ["INBOX", "CATEGORY_PERSONAL"]
  },
  {
    "thread_id": "thr_opportunity_001",
    "sender": "Priya Shah <priya@venturetalent.io>",
    "subject": "Advisory opportunity in AI tooling",
    "preview": "Would you be open to a short intro call next week?",
    "timestamp": "2026-03-14T07:40:00Z",
    "unread": true,
    "labels": ["INBOX", "UNREAD", "CATEGORY_PRIMARY"]
  },
  {
    "thread_id": "thr_work_002",
    "sender": "Accounts Payable <ap@vendorco.com>",
    "subject": "Payment confirmation for March retainer",
    "preview": "Payment has been processed and will settle in 1-2 days.",
    "timestamp": "2026-03-12T16:33:00Z",
    "unread": false,
    "labels": ["INBOX", "CATEGORY_UPDATES"]
  }
]
```

## Risks

- Gmail MCP OAuth token expiry handling
- Gmail API / connector rate limits
- Large threads (100+ messages) require pagination and lazy loading
- HTML-heavy emails need robust text extraction/cleanup
- Attachments should be referenced in metadata only (no automatic download)

## Setup (nothing to install)

Gmail MCP is already connected.

Verify:
1. `https://gmail.mcp.claude.com/mcp` is allowed in BITOS server MCP connections.
2. Anthropic request path includes the Gmail MCP server (`mcp_servers`) and enabled toolset (`mcp_toolset`).
3. No new local packages or OS-level permissions are required for this research scope.
