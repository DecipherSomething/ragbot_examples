"""End-to-end RAG workflow against the ragBot Platform API.

1. Health-check the platform.
2. Upload a document.
3. Poll until ingestion (parse -> chunk -> embed -> summarize) completes.
4. Chat about the document across a multi-turn session.
5. Show which sources each answer cited.

Usage:
    export RAGBOT_API_KEY=sk_...
    export RAGBOT_BASE_URL=https://demo.deciphersomething.com/   # optional, this is the default
    python 04_full_rag_workflow.py path/to/document.pdf "What is this document about?"
"""

import os
import sys
import time

import requests

BASE_URL = os.environ.get("RAGBOT_BASE_URL", "https://demo.deciphersomething.com/")
API_KEY = os.environ["RAGBOT_API_KEY"]
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def check_health() -> None:
    resp = requests.get(f"{BASE_URL}/health", timeout=5)
    resp.raise_for_status()
    body = resp.json()
    print(f"platform status: {body.get('status', 'unknown')}")
    if body.get("status") != "healthy":
        print(f"  warning — health payload: {body}")


def upload(path: str) -> str:
    with open(path, "rb") as fh:
        resp = requests.post(
            f"{BASE_URL}/api/v1/documents/api/upload",
            headers=HEADERS,
            files={"document_file": (os.path.basename(path), fh)},
        )
    resp.raise_for_status()
    receipt = resp.json()
    print(f"uploaded {receipt['filename']} -> document_id {receipt['document_id']}")
    return receipt["document_id"]


def wait_until_processed(
    document_uuid: str, timeout_s: int = 600, poll_s: int = 5
) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        resp = requests.get(
            f"{BASE_URL}/api/v1/documents/api/summary/{document_uuid}", headers=HEADERS
        )
        resp.raise_for_status()
        summary = resp.json()
        if summary["status"] == "completed":
            print(f"processing complete: {summary['title']}")
            return summary
        if summary["status"] == "failed":
            raise RuntimeError(f"Processing failed for {document_uuid}")
        time.sleep(poll_s)
    raise TimeoutError(f"Still pending after {timeout_s}s")


def ask(message: str, session_guid: str | None = None) -> dict:
    payload = {"message": message}
    if session_guid:
        payload["session_guid"] = session_guid
    resp = requests.post(f"{BASE_URL}/api/v1/chat/api", headers=HEADERS, json=payload)
    resp.raise_for_status()
    reply = resp.json()

    print(f"\nQ: {message}")
    print(f"A: {reply['assistant_message']}")
    for src in reply.get("sources") or []:
        print(f"   [source] {src.get('title') or src.get('location') or src}")
    return reply


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <file> [question]")
    path = sys.argv[1]
    question = sys.argv[2] if len(sys.argv) > 2 else "What is this document about?"

    check_health()
    doc_uuid = upload(path)
    wait_until_processed(doc_uuid)

    # Multi-turn chat: reuse the session_guid so turn 2 has turn 1's context.
    first = ask(question)
    ask(
        "List three key takeaways as bullet points.", session_guid=first["session_guid"]
    )


if __name__ == "__main__":
    main()
