"""jev(TypeSafe) 판단 API 호출 도구.

사용법:
    python tools/ask_jev.py questions.json          # {"state": "...", "questions": {...}}
    echo '{...}' | python tools/ask_jev.py -

API 키는 프로젝트 루트 .env 의 TYPESAFE_API_KEY 에서 읽는다. 키 값은 절대 출력하지 않는다.
"""
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.local")

ENDPOINT = "https://api.typesafe.ai/v1/systemone"


def ask_jev(state: str, questions: dict) -> dict:
    api_key = os.getenv("TYPESAFE_API_KEY")
    if not api_key:
        raise RuntimeError("TYPESAFE_API_KEY 가 .env 에 없습니다.")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": "jev-latest", "state": state, "questions": questions}
    response = requests.post(ENDPOINT, headers=headers, json=payload, timeout=60)
    if not response.ok:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
    return response.json()


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "-"
    raw = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8")
    req = json.loads(raw)
    result = ask_jev(req["state"], req["questions"])
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
