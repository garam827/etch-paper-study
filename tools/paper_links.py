"""레퍼런스 논문 ↔ 요약 연결 (원본: kb/papers/papers.json)

    python tools/paper_links.py apply <페이지.html> ...   # 논문 링크 뒤에 "요약" 링크를 넣는다(이미 있으면 그대로)
    python tools/paper_links.py oes                       # OES 페이지에 반영 (oes_page.py도 저장 전에 같은 처리를 한다)
    python tools/paper_links.py check                     # 공개 페이지의 논문 링크마다 요약 링크가 붙어 있는지 확인

손으로 쓰는 페이지(보고서·노트)는 apply로, 생성 페이지(그래프·OES)는 각 생성 도구가 이 모듈을 불러 같은 링크를 만든다.
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = "research/papers.html"
SKIP = {"data", "ledger", "source", "merge_src", "node_modules", ".git", "tools", "kb", ".claude", "history", "docs"}
ANCHOR = re.compile(r'<a href="(https?://[^"]+)"([^>]*)>(.*?)</a>(\s*<a class="psum"[^>]*>요약</a>)?', re.S)
STYLE = "font-size:12px;font-weight:600;background:#eef2ff;border-radius:999px;padding:0 7px;text-decoration:none;white-space:nowrap"
# 검증 근거 링크만 모은 생성 페이지는 대상이 아니다
NOT_CITING = {"research/claims_status.html"}


def papers():
    return json.loads((ROOT / "kb/papers/papers.json").read_text(encoding="utf-8"))["papers"]


def matcher():
    rows = [(m.lower(), p["id"]) for p in papers() for m in p["match"]]

    def find(url):
        u = url.lower()
        ids = {pid for m, pid in rows if m in u}
        return ids.pop() if len(ids) == 1 else None
    return find


def href_from(page_rel, pid):
    """page_rel(사이트 루트 기준 경로)에서 요약 앵커로 가는 상대 경로"""
    return Path(os.path.relpath(PAGE, Path(page_rel).parent)).as_posix() + "#" + pid


def summary_link(page_rel, pid):
    return f'<a class="psum" href="{href_from(page_rel, pid)}" style="{STYLE}">요약</a>'


def apply_html(text, page_rel, find=None):
    find = find or matcher()

    def rep(m):
        pid = find(m.group(1))
        if not pid:
            return m.group(0)
        return f'<a href="{m.group(1)}"{m.group(2)}>{m.group(3)}</a> {summary_link(page_rel, pid)}'
    return ANCHOR.sub(rep, text)


def missing(text, page_rel, find=None):
    find = find or matcher()
    body = re.sub(r"<script\b.*?</script>", "", text, flags=re.S)
    return [m.group(1) for m in ANCHOR.finditer(body) if find(m.group(1)) and not m.group(4)]


def public_pages():
    return [p for p in ROOT.rglob("*.html") if not (set(p.relative_to(ROOT).parts[:-1]) & SKIP)
            and p.relative_to(ROOT).as_posix() not in NOT_CITING | {PAGE}]


def link_oes(page):
    """OES 페이지(tools/oes_page.py 생성): 정적 표의 논문 링크 + 스크립트가 그리는 조합 표 출처 링크에 요약을 붙인다."""
    find = matcher()
    page = apply_html(page, "research/oes_etch_chemistry.html", find)
    js_a = '<a href="${esc(SRC[s][1])}" target="_blank" rel="noopener">${esc(SRC[s][0])}</a>'
    if js_a in page and "const PSUM" not in page:
        m = re.search(r"const SRC = (\{.*?\});\n", page)
        src = json.loads(m.group(1))
        psum = {k: pid for k, v in src.items() if (pid := find(v[1]))}
        page = page.replace(m.group(0), m.group(0) + "const PSUM = " + json.dumps(psum, separators=(",", ":")) + ";\n", 1)
        page = page.replace(js_a, js_a + '${PSUM[s] ? ` <a class="psum" href="papers.html#${PSUM[s]}" style="' + STYLE + '">요약</a>` : ""}')
    return page


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    find = matcher()
    if cmd == "apply":
        for a in args:
            p = (ROOT / a).resolve()
            rel = p.relative_to(ROOT).as_posix()
            t = p.read_text(encoding="utf-8")
            n = apply_html(t, rel, find)
            if n != t:
                p.write_text(n, encoding="utf-8", newline="")
            print(rel, "요약 링크", n.count('class="psum"'))
    elif cmd == "oes":
        p = ROOT / "research/oes_etch_chemistry.html"
        p.write_text(link_oes(p.read_text(encoding="utf-8")), encoding="utf-8", newline="")
        print("OES 요약 링크 반영")
    elif cmd == "check":
        bad = [(p.relative_to(ROOT).as_posix(), u) for p in public_pages() for u in missing(p.read_text(encoding="utf-8"), p.relative_to(ROOT).as_posix(), find)]
        print(f"논문 링크 요약 연결: 빠진 곳 {len(bad)}건")
        for r, u in bad:
            print("  ", r, u)
        sys.exit(1 if bad else 0)
