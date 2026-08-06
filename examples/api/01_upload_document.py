"""Upload a document to the ragBot Platform and wait for processing to finish.

Usage:
    export RAGBOT_API_KEY=sk_...
    export RAGBOT_BASE_URL=https://demo.deciphersomething.com/   # optional, this is the default
    python 01_upload_document.py path/to/report.pdf
"""

import os
import sys
import time

import requests

BASE_URL = os.environ.get("RAGBOT_BASE_URL", "https://demo.deciphersomething.com/")
API_KEY = os.environ["RAGBOT_API_KEY"]
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def upload_document(path: str) -> dict:
    """POST the file and return the upload receipt (document_id is the UUID)."""
    with open(path, "rb") as fh:
        resp = requests.post(
            f"{BASE_URL}/api/v1/documents/api/upload",
            headers=HEADERS,
            files={"document_file": (os.path.basename(path), fh)},
        )
    resp.raise_for_status()
    return resp.json()


def wait_for_processing(
    document_uuid: str, timeout_s: int = 600, poll_s: int = 5
) -> dict:
    """Poll the summary endpoint until status leaves 'pending'."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        resp = requests.get(
            f"{BASE_URL}/api/v1/documents/api/summary/{document_uuid}",
            headers=HEADERS,
        )
        resp.raise_for_status()
        summary = resp.json()
        if summary["status"] != "pending":
            return summary
        print(f"  still processing... (status={summary['status']})")
        time.sleep(poll_s)
    raise TimeoutError(f"Document {document_uuid} still pending after {timeout_s}s")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <file>")

    receipt = upload_document(sys.argv[1])
    print(f"Uploaded: {receipt['filename']} ({receipt['size']} bytes)")
    print(f"  document_id: {receipt['document_id']}  status: {receipt['status']}")

    summary = wait_for_processing(receipt["document_id"])
    print(f"\nProcessing finished with status: {summary['status']}")
    print(f"  title:   {summary['title']}")
    print(f"  tags:    {summary['tags']}")
    print(f"  summary: {summary['summary'][:300]}")


if __name__ == "__main__":
    main()
