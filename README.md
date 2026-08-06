# ragBot Platform — API Developer Guide

This guide covers the programmatic API surface of the ragBot Platform: the endpoints
built for external integrations and service accounts, how to authenticate against
them, and the standard RAG workflows they enable. Runnable Python examples for each
workflow live in [`examples/api/`](../../examples/api/).

All endpoints are mounted under the versioned prefix **`/api/v1`**.

---

## 1. Authentication

The platform supports two authentication modes:

| Mode | Mechanism | Intended for |
|---|---|---|
| **API key** | `Authorization: Bearer sk_...` header | Service accounts, external systems, scripts |
| **Session cookie** | JWT cookie set by `POST /api/v1/auth/login` | Browser UI |

Developer-facing endpoints use *flexible authentication*: they try the API key
first, then fall back to the session cookie. Anything documented in this guide
works with a plain API key — no cookies or CSRF handling required.

```python
headers = {"Authorization": f"Bearer {RAGBOT_API_KEY}"}
```

### Getting an API key

API keys belong to **service accounts**. A superuser creates one via, or via the web using admin->Users:

```
POST /api/v1/service-accounts/
{"username": "my-integration", "email": "integration@example.com", ...}
```

The response contains the raw `api_key` (prefix `sk_`) **exactly once** — the
database stores only a hash, so save it immediately. Lost keys are replaced with:

```
POST /api/v1/service-accounts/{user_id}/regenerate-api-key
```

---

## 2. API-key-capable endpoints (the developer surface)

These accept `Bearer sk_...` keys and return JSON:

| Method & Path | Purpose |
|---|---|
| `POST /api/v1/documents/api/upload` | Upload a document for ingestion (multipart, field `document_file`) |
| `GET /api/v1/documents/api/summary/{document_uuid}` | Document metadata + processing **status** (`pending` / `completed` / `failed`) |
| `GET /api/v1/documents/file/{document_uuid}` | Download the original file (`?disposition=inline` to render in browser) |
| `POST /api/v1/chat/api` | REST chat — synchronous RAG chat with session continuity and source citations |
| `POST /api/v1/chat/completions` | **OpenAI-compatible** Chat Completions — drop-in for the OpenAI SDK |
| `GET /api/v1/generated-docs/{file_id}/{filename}` | Download AI-generated documents (e.g. Word exports) |
| `GET /api/v1/system/platform/stats` | Platform-level statistics |
| `GET /health` | Unauthenticated health/DB connectivity check (for probes and smoke tests) |

> **Session-cookie-only JSON APIs.** A larger JSON surface exists (search
> `/api/v1/search/api/*`, tags, document-sources, agents, prompt-templates,
> evaluations, raw-documents, LLM usage). These are clean REST APIs but currently
> require a browser session cookie (`get_current_user`), not an API key. If you
> need one of them from a service account, that endpoint must first be switched to
> flexible auth.

---

## 3. Workflow: upload a document

Upload is a two-step, asynchronous flow: the upload returns immediately with a
`pending` status, then a background pipeline (parsing, chunking, embedding,
summarization) processes the file.

**1. Upload** — multipart POST, file field is named `document_file`:

```python
import requests

resp = requests.post(
    f"{BASE_URL}/api/v1/documents/api/upload",
    headers={"Authorization": f"Bearer {API_KEY}"},
    files={"document_file": ("report.pdf", open("report.pdf", "rb"), "application/pdf")},
)
resp.raise_for_status()
doc = resp.json()
# {"id": 42, "document_id": "<uuid>", "status": "pending",
#  "message": "...", "filename": "report.pdf", "size": 123456}
```

Errors: `400` unsupported file type (the message lists allowed extensions),
`413` file too large, `403` account lacks upload permission.

**2. Poll for completion** — the summary endpoint reports processing status:

```python
resp = requests.get(
    f"{BASE_URL}/api/v1/documents/api/summary/{doc['document_id']}",
    headers={"Authorization": f"Bearer {API_KEY}"},
)
status = resp.json()["status"]   # "pending" → "completed" | "failed"
```

Once `completed`, the document is chunked, embedded, and retrievable by chat and
search. See [`examples/api/01_upload_document.py`](../../examples/api/01_upload_document.py).

---

## 4. Workflow: chat with the AI (REST)

`POST /api/v1/chat/api` runs the full RAG workflow (routing, retrieval,
generation) and returns a synchronous JSON response.

**Request** (`RestChatRequest`):

```json
{
  "message": "What does the Q3 report say about revenue?",
  "session_guid": "optional — omit to start a new session",
  "excluded_document_ids": [12, 15]
}
```

**Response** (`RestChatResponse`):

```json
{
  "session_guid": "…",
  "session_title": "…",
  "user_message_id": 101,
  "assistant_message_id": 102,
  "assistant_message": "…",
  "sources": [{"…": "documents cited by the answer"}],
  "time_taken": 2.31,
  "route": "rag"
}
```

- **Session continuity:** pass the returned `session_guid` back on the next turn
  to continue the same conversation with history.
- **Rate limiting:** requests are limited per user per minute
  (`AGENT_RATE_LIMIT_PER_USER`); a `429` means back off and retry.

See [`examples/api/02_chat.py`](../../examples/api/02_chat.py).

---

## 5. Workflow: OpenAI-compatible chat

`POST /api/v1/chat/completions` implements the OpenAI Chat Completions schema, so
the platform can act as a drop-in replacement for OpenAI-style clients — including
the official `openai` Python SDK:

```python
from openai import OpenAI

client = OpenAI(
    base_url=f"{BASE_URL}/api/v1",      # SDK appends /chat/completions
    api_key=RAGBOT_API_KEY,             # your sk_ service-account key
)
resp = client.chat.completions.create(
    model="rag-model",                  # informational
    messages=[{"role": "user", "content": "Summarize our onboarding docs."}],
)
print(resp.choices[0].message.content)
```

Non-standard RAG extensions:

- Request: `rag_options` (optional dict) for retrieval tuning.
- Response: `sources` (documents cited) and `session_id` alongside the standard
  `choices`/`usage` fields.

Streaming (`stream: true`) is not supported on this endpoint — responses are
synchronous. See [`examples/api/03_openai_compatible.py`](../../examples/api/03_openai_compatible.py).

---

## 6. End-to-end example

[`examples/api/04_full_rag_workflow.py`](../../examples/api/04_full_rag_workflow.py)
chains the pieces into the canonical RAG loop:

1. Health-check the platform (`GET /health`).
2. Upload a document (`POST /documents/api/upload`).
3. Poll until processing completes (`GET /documents/api/summary/{uuid}`).
4. Ask questions about it (`POST /chat/api`), continuing one session across turns.
5. Print the cited sources for each answer.

---

## 7. Error handling conventions

| Code | Meaning |
|---|---|
| `401` | Missing/invalid API key (keys must start with `sk_`) or expired session |
| `403` | Authenticated but not permitted (e.g. viewer role, missing upload permission) |
| `404` | Resource not found *or* not owned by you (sessions are owner-scoped) |
| `413` | Upload exceeds the size limit |
| `429` | Chat rate limit exceeded — retry with backoff |

All error bodies follow FastAPI's `{"detail": "..."}` shape.
