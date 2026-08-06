"""Use the ragBot Platform as a drop-in replacement for the OpenAI Chat API.

Shows both plain-requests usage and (if installed) the official `openai` SDK
pointed at the platform. The response follows the OpenAI schema plus two RAG
extensions: `sources` (cited documents) and `session_id`.

Usage:
    export RAGBOT_API_KEY=sk_...
    export RAGBOT_BASE_URL=https://demo.deciphersomething.com/   # optional, this is the default
    python 03_openai_compatible.py
"""

import os

import requests

BASE_URL = os.environ.get("RAGBOT_BASE_URL", "https://demo.deciphersomething.com/")
API_KEY = os.environ["RAGBOT_API_KEY"]

QUESTION = "What are the key points in the most recently uploaded document?"


def with_requests() -> None:
    resp = requests.post(
        f"{BASE_URL}/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": "rag-model",  # informational only
            "messages": [{"role": "user", "content": QUESTION}],
        },
    )
    resp.raise_for_status()
    data = resp.json()

    print("== via requests ==")
    print(data["choices"][0]["message"]["content"])
    print(f"tokens: {data['usage']['total_tokens']}")
    for src in data.get("sources") or []:
        print(f"  source: {src.get('title', src)}")


def with_openai_sdk() -> None:
    try:
        from openai import OpenAI
    except ImportError:
        print(
            "\n(openai package not installed — skipping SDK demo; pip install openai)"
        )
        return

    client = OpenAI(base_url=f"{BASE_URL}/api/v1", api_key=API_KEY)
    resp = client.chat.completions.create(
        model="rag-model",
        messages=[{"role": "user", "content": QUESTION}],
    )
    print("\n== via openai SDK ==")
    print(resp.choices[0].message.content)


if __name__ == "__main__":
    with_requests()
    with_openai_sdk()
