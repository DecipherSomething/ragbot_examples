"""Upload a file, wait for ingestion, then download what the platform made of it.

The processed content of a document is its full extracted text (for a PDF the
parsed pages, for a video the per-frame descriptions and transcript, for an
image the vision description), plus the generated title, summary and tags.

1. Upload the file              POST /api/v1/documents/api/upload
2. Poll until processing ends   GET  /api/v1/documents/api/summary/{uuid}
3. Download the processed text  GET  /api/v1/raw-documents/{uuid}/text
4. Fetch every detail the platform holds about the document (record, index,
   media counts, raw-text info, jobs, evaluations)
                                GET  /api/v1/documents/api/details/{uuid}
5. Write <name>.txt (the text) and <name>.json (the details) next to the file

Usage:
    export RAGBOT_API_KEY=sk_...
    export RAGBOT_BASE_URL=https://demo.deciphersomething.com/   # optional, this is the default
    python 05_download_processed_content.py path/to/report.pdf
    python 05_download_processed_content.py --document-id <uuid>   # skip the upload
"""

import argparse
import json
import os
import sys
import time

import requests

BASE_URL = os.environ.get(
    "RAGBOT_BASE_URL", "https://demo.deciphersomething.com/"
).rstrip("/")
API_KEY = os.environ["RAGBOT_API_KEY"]
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def upload(path: str) -> str:
    """POST the file; the receipt's document_id is the UUID used everywhere else."""
    with open(path, "rb") as fh:
        resp = requests.post(
            f"{BASE_URL}/api/v1/documents/api/upload",
            headers=HEADERS,
            files={"document_file": (os.path.basename(path), fh)},
            timeout=600,  # large videos take a while to stream up
        )
    resp.raise_for_status()
    receipt = resp.json()
    print(f"uploaded {receipt['filename']} ({receipt['size']} bytes)")
    print(f"  document_id: {receipt['document_id']}")
    return receipt["document_id"]


def wait_until_processed(document_uuid: str, timeout_s: int, poll_s: int = 10) -> dict:
    """Poll the summary endpoint until the status is terminal.

    Video and large PDFs are processed by a distributed pipeline with no
    queue-time guarantee, so the timeout is generous and the poll is slow.
    """
    started = time.monotonic()
    deadline = started + timeout_s
    last_status = None
    while time.monotonic() < deadline:
        resp = requests.get(
            f"{BASE_URL}/api/v1/documents/api/summary/{document_uuid}",
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        summary = resp.json()
        status = summary["status"]
        if status == "completed":
            print(f"processed in {time.monotonic() - started:.0f}s: {summary['title']}")
            return summary
        if status == "failed":
            raise RuntimeError(f"processing failed for {document_uuid}")
        if status != last_status:
            print(f"  status: {status}")
            last_status = status
        time.sleep(poll_s)
    raise TimeoutError(f"{document_uuid} still {last_status} after {timeout_s}s")


def download_text(document_uuid: str) -> str:
    """Fetch the full processed text. 404 means the text was not stored."""
    url = f"{BASE_URL}/api/v1/raw-documents/{document_uuid}/text"
    resp = requests.get(url, headers=HEADERS, timeout=120)
    if resp.status_code == 401:
        raise RuntimeError(
            "raw-documents refused the API key: this deployment predates API-key "
            "access to processed text (Oct 28, 2026) and needs the new build."
        )
    if resp.status_code == 404:
        raise RuntimeError(
            f"no processed text stored for {document_uuid}: processing has not "
            "written it yet, or the document is metadata-only"
        )
    resp.raise_for_status()
    body = resp.json()
    print(f"downloaded {body['length']:,} characters of processed text")
    return body["text"]


def fetch_details(document_uuid: str) -> dict:
    """Everything the document view page knows, as one JSON document."""
    resp = requests.get(
        f"{BASE_URL}/api/v1/documents/api/details/{document_uuid}",
        headers=HEADERS,
        timeout=60,
    )
    if resp.status_code == 401:
        raise RuntimeError(
            "details endpoint refused the API key: this deployment predates "
            "the details API (Oct 28, 2026) and needs the new build."
        )
    resp.raise_for_status()
    details = resp.json()
    idx = details["index"]
    print(
        f"details: {idx['text_chunks']} chunks, "
        f"{idx['chunk_embeddings']} chunk embeddings, "
        f"{details['media']['video_frames']['count']} video frames, "
        f"{details['media']['pdf_pages']['count']} pdf pages"
    )
    return details


def save(base: str, details: dict, text: str) -> None:
    text_path = f"{base}.txt"
    json_path = f"{base}.json"
    with open(text_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(
            details,
            fh,
            indent=2,
            ensure_ascii=False,
        )
    print(f"wrote {text_path} and {json_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("file", nargs="?", help="file to upload")
    ap.add_argument(
        "--document-id", help="download an already-processed document instead"
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=4 * 3600,
        help="seconds to wait for processing (default 4h; videos can be slow)",
    )
    ap.add_argument(
        "--out",
        help="output path without extension (default: next to the uploaded file, "
        "or ./<document_id> with --document-id)",
    )
    args = ap.parse_args()
    if not args.file and not args.document_id:
        sys.exit("give a file to upload or --document-id")

    document_uuid = args.document_id or upload(args.file)
    summary = wait_until_processed(document_uuid, args.timeout)
    text = download_text(document_uuid)
    details = fetch_details(document_uuid)

    base = args.out or (os.path.splitext(args.file)[0] if args.file else document_uuid)
    save(base, details, text)

    print()
    print(f"title:   {summary['title']}")
    print(f"tags:    {', '.join(summary['tags']) or '-'}")
    print(f"summary: {summary['summary'][:300]}")
    print(f"text:    {text[:300].strip()!r}")


if __name__ == "__main__":
    main()
