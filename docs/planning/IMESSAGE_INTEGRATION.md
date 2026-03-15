# MSGS-RESEARCH-001 — iMessage (BlueBubbles) Integration Research

> Scope: research-only planning artifact for integrating BlueBubbles-backed iMessage into BITOS.
>
> Note: direct outbound access to BlueBubbles/Postman/Gist docs was blocked in this runtime (`curl` CONNECT 403). This report captures the integration plan and endpoint contracts that should be verified against the live docs before implementation.

## BlueBubbles API Endpoints We Need

Base convention used by BlueBubbles Server API:
- Base URL: `http(s)://<bluebubbles-host>:<port>/api/v1`
- Auth: `password` query param on API calls (see Authentication section)

### 1) List chats (with unread count)
- **Method:** `GET`
- **URL:** `/api/v1/chat/query`
- **Query params (expected):**
  - `password=<server_password>`
  - `limit=<int>` (optional)
  - `offset=<int>` (optional)
  - sort/filter params as supported by BlueBubbles query API
- **Needed response fields:**
  - `guid`
  - `displayName`
  - `hasUnreadMessage` (or unread indicator equivalent)
  - `lastMessage`/latest message metadata for snippet preview

Example:
```http
GET /api/v1/chat/query?password=...&limit=25&offset=0
```

### 2) Get messages for a chat (with pagination)
- **Method:** `GET`
- **URL:** `/api/v1/chat/{guid}/message`
- **Path params:**
  - `guid` = chat GUID
- **Query params (expected):**
  - `password=<server_password>`
  - `limit=<int>`
  - `offset=<int>` and/or time cursor params depending on BlueBubbles version
- **Needed response fields:**
  - `text`
  - `dateCreated`
  - `isFromMe`
  - sender/contact reference

Example:
```http
GET /api/v1/chat/iMessage;+;chat123/message?password=...&limit=50&offset=0
```

### 3) Send a message
- **Method:** `POST`
- **URL:** `/api/v1/message/text`
- **Query params:**
  - `password=<server_password>`
- **JSON body (expected):**
  - `chatGuid` (preferred when available)
  - `message` (text to send)
  - optionally `tempGuid` / `method` fields depending on server version

Example:
```http
POST /api/v1/message/text?password=...
Content-Type: application/json

{
  "chatGuid": "iMessage;+;chat123",
  "message": "On my way"
}
```

### 4) Register a webhook for new messages
- **Method:** `POST`
- **URL:** `/api/v1/webhook`
- **Query params:**
  - `password=<server_password>`
- **JSON body (expected):**
  - `url`: BITOS callback URL (publicly reachable from BlueBubbles host)
  - `events`: list including new-message/message-created event names
  - optionally auth header token metadata depending on BlueBubbles version

Example:
```http
POST /api/v1/webhook?password=...
Content-Type: application/json

{
  "url": "https://bitos-server.example.com/webhooks/imessage",
  "events": ["new-message"]
}
```

### 5) Get contact info
- **Method:** `GET`
- **URL:** `/api/v1/contact`
- **Query params (expected):**
  - `password=<server_password>`
  - lookup params such as `guid`, `address`, or search term depending on API variant
- **Needed response fields:**
  - contact display name
  - handles/phone/email

Example:
```http
GET /api/v1/contact?password=...&address=%2B15551234567
```

## Webhook Event Format

BlueBubbles webhook payloads are event-oriented. For new inbound messages, the effective structure is typically:

```json
{
  "event": "new-message",
  "data": {
    "guid": "...",
    "chatGuid": "iMessage;+;chat123",
    "text": "hey are you free later?",
    "dateCreated": 1710000000000,
    "isFromMe": false,
    "handle": {
      "address": "+15551234567"
    },
    "sender": "Alice"
  }
}
```

Fields BITOS should extract and normalize:
- `sender` → sender label fallback chain (`sender` → `handle.address` → "Unknown")
- `text` → message body/snippet
- `chatGuid` → conversation identifier
- `timestamp` → `dateCreated` normalized to epoch ms

## Authentication

BlueBubbles Server REST auth is password-based in common deployments:
- API calls include `password=<server_password>` as query param.
- No mandatory OAuth flow is required for local server-to-server calls.
- Some setups also use reverse-proxy auth or TLS termination externally.

Recommended BITOS handling:
- Store `BLUEBUBBLES_PASSWORD` server-side only.
- Never expose password to device clients.
- Support optional bearer/header secret for inbound webhook hardening at BITOS edge.

## Python Integration Pattern

```python
import requests

class BlueBubblesClient:
    def __init__(self, base_url: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.password = password

    def _params(self, extra: dict | None = None) -> dict:
        p = {"password": self.password}
        if extra:
            p.update(extra)
        return p

    def list_chats(self, limit: int = 25, offset: int = 0):
        r = requests.get(
            f"{self.base_url}/api/v1/chat/query",
            params=self._params({"limit": limit, "offset": offset}),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    def get_messages(self, chat_guid: str, limit: int = 50, offset: int = 0):
        r = requests.get(
            f"{self.base_url}/api/v1/chat/{chat_guid}/message",
            params=self._params({"limit": limit, "offset": offset}),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    def send_text(self, chat_guid: str, text: str):
        r = requests.post(
            f"{self.base_url}/api/v1/message/text",
            params=self._params(),
            json={"chatGuid": chat_guid, "message": text},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    def register_webhook(self, bitos_url: str):
        r = requests.post(
            f"{self.base_url}/api/v1/webhook",
            params=self._params(),
            json={
                "url": f"{bitos_url.rstrip('/')}/webhooks/imessage",
                "events": ["new-message"],
            },
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
```

Mapped calls requested in this task:
- `GET /api/v1/chat/query` → list chats
- `GET /api/v1/chat/{guid}/message` → chat messages
- `POST /api/v1/message/text` → send text
- `POST /api/v1/webhook` → register BITOS webhook

## BITOS Adapter Design

Proposed module: `server/integrations/bluebubbles_adapter.py`

```python
class BlueBubblesAdapter:
    def __init__(self, base_url: str, password: str): ...

    def get_conversations(self, limit: int = 25) -> list[dict]: ...
    def get_messages(self, chat_guid: str, limit: int = 50) -> list[dict]: ...
    def send_message(self, chat_guid: str, text: str) -> bool: ...  # Tier 1
    def register_webhook(self, bitos_url: str) -> bool: ...
```

Normalization target returned by adapter (BITOS-friendly):
- conversation:
  - `chat_id`, `title`, `snippet`, `timestamp`, `unread`
- message:
  - `message_id`, `chat_id`, `sender`, `text`, `timestamp`, `from_me`

Design fit with current codebase patterns:
- mirror `VikunjaAdapter` environment-driven constructor and mock-safe behavior;
- keep HTTP details isolated in adapter methods;
- return plain dict/list structures for easy use by FastAPI endpoints.

## Webhook Receiver Design

`server/main.py` proposal:
- Add endpoint: `POST /webhooks/imessage`
- Flow on new inbound message:
  1. Validate webhook authenticity (shared secret header + optional IP allowlist/Tailscale ACL).
  2. Parse event and reject non-message events early.
  3. Normalize to BITOS message schema (`chat_id`, `sender`, `text`, `timestamp`).
  4. Check if BITOS device is awake/connected:
     - if online: push event via current device channel (or queued notification envelope).
     - if offline: store in local cache for next poll/hydration.
  5. Return 200 quickly; move heavy work to background task.

Cache recommendation:
- small local rolling cache (SQLite table or in-memory + persisted queue) keyed by `chatGuid` + `message guid` for idempotency.

## Device UI Mapping

- `chat.guid` → `chat_id`
- `chat.displayName` → contact name/title
- `message.text` → snippet/body
- `message.dateCreated` → timestamp
- `chat.hasUnreadMessage` → unread badge state

Additional practical mappings:
- `message.isFromMe` → bubble alignment/style
- `handle.address` → fallback subtitle when display name absent

## Setup Steps (Mac mini)

1. Install BlueBubbles Server on the Mac mini (latest supported release).
2. Ensure Apple Messages is signed in with the desired Apple ID.
3. Grant required macOS permissions to BlueBubbles:
   - Full Disk Access
   - Accessibility
   - Automation / Messages access prompts
   - Notifications (optional but useful for debugging)
4. Configure BlueBubbles Server password and local server port.
5. Verify REST API responds locally on Mac (`/api/v1/ping`/health-equivalent).
6. Put Mac mini and BITOS server on same trusted network path:
   - Preferred: Tailscale on both hosts for stable private addressing.
   - Expose BlueBubbles over Tailscale IP/hostname; avoid open public internet.
7. Configure BITOS backend env vars:
   - `BLUEBUBBLES_BASE_URL`
   - `BLUEBUBBLES_PASSWORD`
8. Register BITOS webhook endpoint from adapter/bootstrap flow.
9. Send test iMessage and verify webhook receipt + UI reflection.

## Risks / Gotchas

- macOS/Apple updates can break automation hooks or private API behaviors.
- Message schema/event names may differ across BlueBubbles versions.
- If private API is required for certain features (typing indicators, read states), behavior may vary by setup.
- Webhook delivery can fail if callback endpoint is unreachable/NAT-blocked.
- Password-in-query auth is sensitive to log leakage if URLs are logged raw.
- Potential message duplication requires idempotent processing by message GUID.
- Rate limits are typically deployment-dependent (reverse proxy / host constraints) rather than strict cloud SaaS quotas.

## Recommended Approach

Cleanest integration path for BITOS architecture:

1. **Server adapter first**
   - Implement `BlueBubblesAdapter` in `server/integrations/` with strict normalization.
2. **Thin API endpoints in `server/main.py`**
   - Add chat list/message fetch/send endpoints that call adapter only.
3. **Webhook receiver with idempotent ingest**
   - `POST /webhooks/imessage` does minimal synchronous work + queue/cache handoff.
4. **Device pull + push hybrid**
   - Keep periodic fetch as baseline reliability, plus webhook-driven near-real-time updates.
5. **Security hardening from day one**
   - Tailscale-only transport, webhook shared secret, redact password query params in logs.

This approach matches existing BITOS patterns (adapter isolation, server-mediated device API) while minimizing coupling to BlueBubbles-specific payload details.
