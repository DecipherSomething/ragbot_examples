# ragBot Platform — API Examples

Runnable Python examples for the platform's developer API. Full endpoint
reference: [docs/guides/API_DEVELOPER_GUIDE.md](../../docs/guides/API_DEVELOPER_GUIDE.md).

## Setup

All examples authenticate with a **service-account API key** (`sk_...`) sent as a
Bearer token. A superuser issues keys via `POST /api/v1/service-accounts/`.

```bash
export RAGBOT_API_KEY=sk_your_key_here
export RAGBOT_BASE_URL=https://demo.deciphersomething.com/   # optional, this is the default, Make sure you point to your ragBot deployment
pip install requests                            # openai optional, for example 03
```

## Examples

| Script | Workflow |
|---|---|
| `01_upload_document.py` | Upload a file, poll until ingestion completes, print the generated summary |
| `02_chat.py` | Multi-turn REST chat with session continuity and source citations |
| `03_openai_compatible.py` | Use the platform as an OpenAI Chat Completions drop-in (raw HTTP and `openai` SDK) |
| `04_full_rag_workflow.py` | End-to-end: health check → upload → wait → chat about the document |

```bash
python 01_upload_document.py report.pdf
python 02_chat.py "What documents do you have about onboarding?"
python 03_openai_compatible.py
python 04_full_rag_workflow.py report.pdf "What is this document about?"
```
