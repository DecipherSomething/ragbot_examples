# ragBot Platform — API Developer Guide

This guide covers the programmatic API surface of the ragBot Platform: the endpoints
built for external integrations and service accounts, how to authenticate against
them, and the standard RAG workflows they enable. Runnable Python examples for each
workflow live in [`examples/api/`](examples/api/).

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

API keys belong to **service accounts**. A superuser creates one through the API, or in the web UI under **Admin → Users**:

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
| `GET /api/v1/documents/api/details/{document_uuid}` | **Everything** about one document as JSON: the record (title, source, file facts, status, stage, summary, tags, notes, language, metadata, cost group, timestamps, links), processing method/time (+ costs for admin callers), index counts (chunks, embeddings, model, vector size), raw-text availability, video-frame / PDF-page counts, MicroDC job counts, evaluation counts |
| `GET /api/v1/documents/file/{document_uuid}` | Download the original file (`?disposition=inline` to render in browser) |
| `GET /api/v1/documents/api/my-uploads` | Preview of the caller's own uploads: count, bytes, by status and type, plus the confirmation phrase the purge needs |
| `DELETE /api/v1/documents/api/my-uploads` | **Purge every document the caller uploaded** with all stored files (original, text, chunks, vectors, frames, pages, cache). Body `{"confirmation_phrase": "delete my uploads"}`. Only documents uploaded by this account; other users' and watcher-ingested documents are untouched. Irreversible |
| `GET /api/v1/raw-documents/{document_uuid}/text` | Download the **processed text** (parsed pages, video frame descriptions + transcript, image description) as `{document_id, text, length}` (plain or compressed storage, no flag needed); 404 until processing has stored it |
| `GET /api/v1/raw-documents/{document_uuid}/metadata` | Size/hash of the stored processed text without the text itself |
| `POST /api/v1/chat/api` | REST chat — synchronous RAG chat with session continuity and source citations |
| `POST /api/v1/chat/completions` | **OpenAI-compatible** Chat Completions — drop-in for the OpenAI SDK |
| `POST /api/v1/chat/feedback` | Thumbs up/down (+ optional comment) on an assistant answer from either chat endpoint |
| `GET /api/v1/external/search` | Corpus search (hybrid retrieval) — reduced mirror of the internal search-documents endpoint |
| `GET /api/v1/generated-docs/{file_id}/{filename}` | Download AI-generated documents (e.g. Word exports) |
| `GET /api/v1/external/stats` | Corpus/usage totals for integrations: `documents.total`/`by_type`, `storage.total_gb`, `index.text_chunks`, `usage.chat_sessions`/`chat_messages` (cached ≤60 s) |
| `GET /api/v1/system/platform/stats` | Full platform statistics (site-admin accounts only; a service-account key is refused with 403 — use `/external/stats`) |
| `GET /health` | Unauthenticated health/DB connectivity check (for probes and smoke tests) |

> **Session-cookie-only JSON APIs.** A larger JSON surface exists (search
> `/api/v1/search/api/*`, tags, document-sources, agents, prompt-templates,
> evaluations, the rest of raw-documents, LLM usage). These are clean REST APIs but currently
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
search. See [`examples/api/01_upload_document.py`](examples/api/01_upload_document.py).

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

See [`examples/api/02_chat.py`](examples/api/02_chat.py).

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
- Response: `sources` (documents cited), `session_id` and `message_id` (the
  stored assistant message — use it to send feedback) alongside the standard
  `choices`/`usage` fields. With the `openai` SDK, read extensions from
  `resp.model_extra` (e.g. `resp.model_extra["message_id"]`).

### Rating an answer

`POST /api/v1/chat/feedback` is the REST counterpart of the chat UI's 👍/👎
buttons, for either chat endpoint:

```bash
curl -X POST "$BASE_URL/api/v1/chat/feedback" \
  -H "Authorization: Bearer $RAGBOT_API_KEY" -H "Content-Type: application/json" \
  -d '{"message_id": 102, "feedback_type": "negative",
       "comment": "Cited the 2019 manual, not the current one"}'
```

- `message_id`: `message_id` from `/chat/completions`, or `assistant_message_id`
  from `/chat/api`.
- `feedback_type`: `positive` or `negative` (anything else → 422).
- `comment`: optional free-text feedback message (≤4000 chars).
- One vote per message: posting again replaces the vote; the comment is only
  replaced when a new one is sent.
- Returns the stored feedback row. 404 if the message doesn't exist or isn't in
  one of your sessions; 400 if it's a user (not assistant) message.
- Feedback shows up on the admin **Feedback** page and in the chat log viewer.

Streaming (`stream: true`) is not supported on this endpoint — responses are
synchronous. See [`examples/api/03_openai_compatible.py`](examples/api/03_openai_compatible.py).

---

## 6. Workflow: corpus search

`GET /api/v1/external/search` searches the document corpus directly — no LLM,
no chat session — using the same single-stage hybrid retrieval (vector +
keyword, no rerank) as the Search Documents page. It is a deliberately reduced
surface: retrieval mode and weights are fixed server-side.

| Query param | Default | Meaning |
|---|---|---|
| `query` | required | Search text |
| `limit` | `10` | Page size, 1–20 |
| `offset` | `0` | Results to skip (paging); `offset + limit` capped at 200 |
| `score` | `0.30` | Minimum combined score, 0–1 |

```bash
curl -sS -G "$BASE_URL/api/v1/external/search" \
  -H "Authorization: Bearer $API_KEY" \
  --data-urlencode "query=onboarding policy" \
  --data-urlencode "limit=5" \
  --data-urlencode "score=0.30"
```

`-G` turns the `--data-urlencode` pairs into URL query parameters (the
endpoint is a GET), and `--data-urlencode` handles spaces and special
characters in the query text. Pipe through `jq` to slim the output:

```bash
curl -sS -G "$BASE_URL/api/v1/external/search" \
  -H "Authorization: Bearer $API_KEY" \
  --data-urlencode "query=onboarding policy" \
| jq -r '.results[] | "\(.score)\t\(.document_id)\t\(.title)"'
```

The same call from Python:

```python
import requests

resp = requests.get(
    f"{BASE_URL}/api/v1/external/search",
    headers={"Authorization": f"Bearer {API_KEY}"},
    params={"query": "onboarding policy", "limit": 5},
)
resp.raise_for_status()
for hit in resp.json()["results"]:
    print(hit["score"], hit["document_id"], hit["title"])
```

Example response (`200 OK`, `application/json`):

```json
{
  "results": [
    {
      "document_id": "7f3c9a1e-52d4-4b8a-9c0e-2d6f8b41a973",
      "title": "Employee Onboarding Policy 2026",
      "filename": "onboarding-policy-2026.pdf",
      "score": 0.8123,
      "summary": "Company-wide onboarding policy covering the first-90-days checklist, IT provisioning, mandatory training, and manager responsibilities for new hires.",
      "tags": ["onboarding", "hr-policy", "training"]
    },
    {
      "document_id": "b2e714d0-9c3f-47a5-8e21-6a0d5c9f3b88",
      "title": "IT Equipment Request Guide",
      "filename": "it-equipment-guide.docx",
      "score": 0.4471,
      "summary": "How new employees request laptops, monitors, and software licenses, including approval workflow and delivery timelines.",
      "tags": ["it", "equipment", "new-hire"]
    }
  ],
  "query": "onboarding policy",
  "total_count": 2,
  "total_count_is_exact": true,
  "returned_count": 2,
  "offset": 0,
  "has_more": false,
  "duration_ms": 412
}
```

Field notes:

- `results` is sorted by `score` (combined hybrid retrieval score, rounded to
  4 decimals) descending; only documents at or above the `score` threshold
  appear. `returned_count` is the size of this page.
- `total_count` + `total_count_is_exact`: each request fetches a bounded
  window (`offset + limit + 1` ranked matches), never the full match set —
  an exact corpus-wide count of a vector-score threshold would require
  scanning every embedding. When the matches end inside the window,
  `total_count` is the exact total (`total_count_is_exact: true`); when the
  window fills, `total_count` is a floor — "at least N"
  (`total_count_is_exact: false`). Same convention as Elasticsearch's
  `total.relation: "gte"`.
- **Paging**: while `has_more` is true, request the next page with
  `offset = offset + returned_count` (same `query`/`score`). `offset +
  limit` is capped at 200 — past that, refine the query or raise `score`
  rather than paging deeper into relevance-ranked results. Each page re-runs
  the search, so results can shift if the corpus changes between pages.
- `summary` is the stored AI-generated document summary and may be an empty
  string for documents that have none; `tags` may be an empty list.
- `duration_ms` is server-side retrieval time for the request.

Use `document_id` with the document summary/download endpoints (§3) to fetch
full content. Rate-limited per account (shared with the chat endpoints);
`429` means back off and retry.

---

## 7. End-to-end example

[`examples/api/04_full_rag_workflow.py`](examples/api/04_full_rag_workflow.py)
chains the pieces into the canonical RAG loop:

1. Health-check the platform (`GET /health`).
2. Upload a document (`POST /documents/api/upload`).
3. Poll until processing completes (`GET /documents/api/summary/{uuid}`).
4. Ask questions about it (`POST /chat/api`), continuing one session across turns.
5. Print the cited sources for each answer.

[`examples/api/05_download_processed_content.py`](examples/api/05_download_processed_content.py)
is the ingest-only variant: upload, poll, then `GET /raw-documents/{uuid}/text`
and `GET /documents/api/details/{uuid}`, writing the processed text and the
full details document to disk.
Use `--document-id <uuid>` to fetch a document that was uploaded earlier.

[`examples/api/06_download_entire_document.py`](examples/api/06_download_entire_document.py)
is the export side: for each UUID given it writes `details.json`
(`GET /documents/api/details/{uuid}`) and `text.txt`
(`GET /raw-documents/{uuid}/text`) into `<out>/<uuid>/`. `--with-file` adds
the original upload (`GET /documents/file/{uuid}`, streamed, named from
`Content-Disposition`); it is off by default because videos are large. Missing
text or file is reported and skipped, not fatal.
Processing time depends on the file: a text PDF finishes in seconds, a
90-minute video can take over an hour, so the script's default wait is 4 hours.

---

## 8. Error handling conventions

| Code | Meaning |
|---|---|
| `401` | Missing/invalid API key (keys must start with `sk_`) or expired session |
| `403` | Authenticated but not permitted (e.g. viewer role, missing upload permission) |
| `404` | Resource not found *or* not owned by you (sessions are owner-scoped) |
| `413` | Upload exceeds the size limit |
| `429` | Chat rate limit exceeded — retry with backoff |

All error bodies follow FastAPI's `{"detail": "..."}` shape.
