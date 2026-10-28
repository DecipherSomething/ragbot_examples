"""Download everything the platform produced for a document.

The processed data, fetched with an API key and written to one folder:

    <out>/<uuid>/details.json      GET /api/v1/documents/api/details/{uuid}
    <out>/<uuid>/text.txt          GET /api/v1/raw-documents/{uuid}/text

The original upload is NOT fetched unless you ask for it with --with-file
(it can be hundreds of megabytes for a video):

    <out>/<uuid>/<original name>   GET /api/v1/documents/file/{uuid}

details.json is the JSON twin of the document view page: the record (title,
source, type, size, hash, status, summary, tags, notes, language, metadata,
timestamps), processing method and time (plus costs for admin keys), index
counts (chunks, embeddings, model), raw-text info, video-frame / PDF-page
counts, distributed job counts and evaluation counts.

Usage:
    export RAGBOT_API_KEY=sk_...
    export RAGBOT_BASE_URL=https://demo.deciphersomething.com/   # optional, this is the default
    python 06_download_entire_document.py <document_uuid> [<document_uuid> ...] [--out ./downloads]
    python 06_download_entire_document.py <document_uuid> --with-file   # also the original upload
"""

import argparse
import json
import os
import re
import sys
from urllib.parse import unquote

import requests

BASE_URL = os.environ.get(
    "RAGBOT_BASE_URL", "https://demo.deciphersomething.com/"
).rstrip("/")
API_KEY = os.environ["RAGBOT_API_KEY"]
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def _check(resp: requests.Response, what: str) -> requests.Response:
    """Turn the two common failures into readable messages."""
    if resp.status_code == 401:
        raise RuntimeError(
            f"{what}: API key refused. Check RAGBOT_API_KEY, or this deployment "
            "predates API-key access to this route (Oct 28, 2026)."
        )
    if resp.status_code == 404:
        raise RuntimeError(f"{what}: not found")
    resp.raise_for_status()
    return resp


def fetch_details(document_uuid: str) -> dict:
    resp = _check(
        requests.get(
            f"{BASE_URL}/api/v1/documents/api/details/{document_uuid}",
            headers=HEADERS,
            timeout=60,
        ),
        "details",
    )
    return resp.json()


def _filename_from_disposition(header: str | None) -> str | None:
    """Parse ``attachment; filename="a.pdf"; filename*=UTF-8''a.pdf``."""
    if not header:
        return None
    m = re.search(r"filename\*=(?:UTF-8|utf-8)''([^;]+)", header)
    if m:
        return unquote(m.group(1).strip())
    m = re.search(r'filename="?([^";]+)"?', header)
    return m.group(1).strip() if m else None


def _safe_name(name: str) -> str:
    name = os.path.basename(name or "").strip() or "document.bin"
    return re.sub(r"[^\w.\- ()\[\]]+", "_", name)


def download_file(document_uuid: str, folder: str, fallback_name: str) -> str | None:
    """Stream the original upload to disk. Returns the path, or None if the
    file is no longer stored on the server (the record can outlive it)."""
    with requests.get(
        f"{BASE_URL}/api/v1/documents/file/{document_uuid}",
        headers=HEADERS,
        stream=True,
        timeout=600,
    ) as resp:
        if resp.status_code == 404:
            print("  original file: not stored on the server (skipped)")
            return None
        _check(resp, "original file")
        name = _safe_name(
            _filename_from_disposition(resp.headers.get("Content-Disposition"))
            or fallback_name
        )
        path = os.path.join(folder, name)
        size = 0
        with open(path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
                size += len(chunk)
    print(f"  original file: {name} ({size:,} bytes)")
    return path


def download_text(document_uuid: str, folder: str) -> str | None:
    resp = requests.get(
        f"{BASE_URL}/api/v1/raw-documents/{document_uuid}/text",
        headers=HEADERS,
        timeout=120,
    )
    if resp.status_code == 404:
        print("  processed text: none stored (skipped)")
        return None
    _check(resp, "processed text")
    body = resp.json()
    path = os.path.join(folder, "text.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body["text"])
    print(f"  processed text: text.txt ({body['length']:,} characters)")
    return path


def download_document(document_uuid: str, out_dir: str, with_file: bool) -> str:
    folder = os.path.join(out_dir, document_uuid)
    os.makedirs(folder, exist_ok=True)

    details = fetch_details(document_uuid)
    record = details["document"]
    print(f"{document_uuid}: {record['title']}")
    print(
        f"  status {record['status']}, type {record['document_type']}, "
        f"{record['file_size'] or 0:,} bytes, uploaded {record['created_at']}"
    )
    idx = details["index"]
    media = details["media"]
    print(
        f"  index: {idx['text_chunks']} chunks, {idx['chunk_embeddings']} embeddings; "
        f"media: {media['video_frames']['count']} frames, {media['pdf_pages']['count']} pages"
    )

    with open(os.path.join(folder, "details.json"), "w", encoding="utf-8") as fh:
        json.dump(details, fh, indent=2, ensure_ascii=False)
    print("  details: details.json")

    if details["raw_text"]["available"]:
        download_text(document_uuid, folder)
    else:
        print("  processed text: none stored (skipped)")

    if with_file:
        download_file(document_uuid, folder, fallback_name=record.get("location") or "")

    return folder


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("document_ids", nargs="+", help="document UUID(s)")
    ap.add_argument(
        "--out", default="./downloads", help="output folder (default ./downloads)"
    )
    ap.add_argument(
        "--with-file",
        action="store_true",
        help="also download the original upload (off by default; videos are large)",
    )
    args = ap.parse_args()

    failures = 0
    for document_uuid in args.document_ids:
        try:
            folder = download_document(document_uuid, args.out, args.with_file)
            print(f"  -> {folder}\n")
        except Exception as e:  # keep going through the list
            failures += 1
            print(f"{document_uuid}: FAILED: {e}\n", file=sys.stderr)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
