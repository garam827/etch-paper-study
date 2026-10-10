"""출처 실재 확인: DOI가 실제로 해석되고 제목이 맞는지, URL이 열리는지 검사.

사용법:
    python tools/check_refs.py ledger.json        # 주장 장부의 모든 sources 검사
    python tools/check_refs.py --doi 10.1109/... --title "기대 제목"
    python tools/check_refs.py --url https://...

판정: ok / title_mismatch / not_found / unreachable / paywalled(열리지만 403·401)
"""
import argparse
import difflib
import json
import sys
from pathlib import Path

import requests

UA = {"User-Agent": "etch-paper-study/1.0 (reference check)"}


def norm(s):
    return " ".join("".join(c.lower() if c.isalnum() else " " for c in (s or "")).split())


def check_doi(doi, title=None):
    try:
        r = requests.get(f"https://api.crossref.org/works/{doi}", headers=UA, timeout=25)
    except requests.RequestException as e:
        return {"doi": doi, "status": "unreachable", "detail": str(e)[:120]}
    if r.status_code == 404:
        # Crossref에 없는 DOI(DataCite 등)는 doi.org 해석으로 재확인
        try:
            h = requests.head(f"https://doi.org/{doi}", headers=UA, timeout=25, allow_redirects=False)
            if h.status_code in (301, 302, 303, 307, 308):
                return {"doi": doi, "status": "ok", "detail": "doi.org 해석됨 (Crossref 외)"}
        except requests.RequestException:
            pass
        return {"doi": doi, "status": "not_found"}
    m = r.json()["message"]
    real = (m.get("title") or [""])[0]
    yr = ((m.get("issued") or {}).get("date-parts") or [[None]])[0][0]
    out = {"doi": doi, "real_title": real, "venue": (m.get("container-title") or [None])[0], "year": yr}
    if title:
        a, b = norm(title), norm(real)
        # 부제를 뺀 짧은 제목도 인정 (한쪽이 다른 쪽에 통째로 들어 있으면 일치)
        sim = 1.0 if a and b and (a in b or b in a) else difflib.SequenceMatcher(None, a, b).ratio()
        out["title_similarity"] = round(sim, 2)
        out["status"] = "ok" if sim >= 0.8 else "title_mismatch"
    else:
        out["status"] = "ok"
    return out


def check_url(url):
    # stream·HEAD 요청에 응답하지 않는 서버가 있어 일반 GET, 시간 초과 시 한 번 재시도
    for attempt in (1, 2):
        try:
            r = requests.get(url, headers=UA, timeout=25, allow_redirects=True)
            code = r.status_code
            break
        except requests.RequestException as e:
            if attempt == 2:
                return {"url": url, "status": "unreachable", "detail": str(e)[:120]}
    st = "ok" if code < 400 else "paywalled" if code in (401, 402, 403) else "not_found" if code in (404, 410) else "unreachable"
    return {"url": url, "status": st, "http": code}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger", nargs="?")
    ap.add_argument("--doi"); ap.add_argument("--title"); ap.add_argument("--url")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.doi:
        print(json.dumps(check_doi(a.doi, a.title), ensure_ascii=False, indent=1)); return
    if a.url:
        print(json.dumps(check_url(a.url), ensure_ascii=False, indent=1)); return
    led = json.loads(Path(a.ledger).read_text(encoding="utf-8"))
    res, bad = {}, 0
    for s in led.get("sources", []):
        r = check_doi(s["doi"], s.get("title")) if s.get("doi") else check_url(s["url"]) if s.get("url") else {"status": "no_locator"}
        res[s["id"]] = r
        bad += r["status"] not in ("ok", "paywalled")
    print(json.dumps({"checked": len(res), "problems": bad, "results": res}, ensure_ascii=False, indent=1))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
