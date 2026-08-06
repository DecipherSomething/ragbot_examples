"""Chat with the ragBot Platform via the REST chat API.

Runs a small multi-turn conversation: the session_guid returned by the first
call is passed back on later turns so the assistant keeps conversation history.

Usage:
    export RAGBOT_API_KEY=sk_...
    export RAGBOT_BASE_URL=https://demo.deciphersomething.com/   # optional, this is the default
    python 02_chat.py "What documents do you have about onboarding?"
"""

import os
import sys

import requests

BASE_URL = os.environ.get("RAGBOT_BASE_URL", "https://demo.deciphersomething.com/")
API_KEY = os.environ["RAGBOT_API_KEY"]
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def chat(message: str, session_guid: str | None = None) -> dict:
    """Send one chat turn. Omit session_guid to start a new session."""
    payload = {"message": message}
    if session_guid:
        payload["session_guid"] = session_guid

    resp = requests.post(f"{BASE_URL}/api/v1/chat/api", headers=HEADERS, json=payload)
    if resp.status_code == 429:
        raise RuntimeError("Rate limit exceeded — wait a minute and retry")
    resp.raise_for_status()
    return resp.json()


def print_turn(reply: dict) -> None:
    print(f"\nassistant ({reply['time_taken']:.1f}s, route={reply['route']}):")
    print(reply["assistant_message"])
    if reply.get("sources"):
        print("\nsources:")
        for src in reply["sources"]:
            title = src.get("title") or src.get("location") or str(src)
            print(f"  - {title}")


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else "What documents are available?"

    # Turn 1 — new session
    reply = chat(question)
    print(f"session: {reply['session_title']} ({reply['session_guid']})")
    print_turn(reply)

    # Turn 2 — same session, so "that" resolves against the previous answer
    followup = chat(
        "Summarize that in one sentence.", session_guid=reply["session_guid"]
    )
    print_turn(followup)


if __name__ == "__main__":
    main()
