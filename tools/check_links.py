"""공개 사이트의 내부 링크 검사: href/src가 가리키는 파일과 #앵커가 있는지 확인한다.

    python tools/check_links.py        # 문제가 있으면 목록을 출력하고 종료 코드 1

외부 링크(http…)는 검사하지 않는다(사이트 밖 상태에 따라 흔들림). 비공개 폴더(data/ ledger/ source/ merge_src/)는 대상이 아니다.
"""
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
SKIP = {"data", "ledger", "source", "merge_src", "node_modules", ".git", "tools", "kb", ".claude"}
ATTR = re.compile(r'\b(?:href|src)\s*=\s*"([^"]+)"')
ID = re.compile(r'\bid\s*=\s*"([^"]+)"')

pages = [p for p in ROOT.rglob("*.html") if not (set(p.relative_to(ROOT).parts[:-1]) & SKIP)]
ids = {}


def anchors(p):
    if p not in ids:
        ids[p] = set(ID.findall(p.read_text(encoding="utf-8", errors="replace")))
    return ids[p]


bad = []
for page in pages:
    text = page.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"<script\b[^>]*>.*?</script>", lambda m: m.group(0) if 'src="' in m.group(0)[:200] else "", text, flags=re.S)
    for url in ATTR.findall(text):
        if url.startswith(("http:", "https:", "mailto:", "data:", "javascript:")) or "${" in url:
            continue
        u = urlsplit(url)
        target = page if not u.path else (page.parent / unquote(u.path)).resolve()
        if target.is_dir():
            target = target / "index.html"
        rel = page.relative_to(ROOT).as_posix()
        if not target.exists():
            bad.append(f"{rel}: 없는 파일 {url}")
        elif u.fragment and "=" not in u.fragment and target.suffix == ".html" and unquote(u.fragment) not in anchors(target):
            # 그래프 노드 앵커(#노드id)는 페이지 안 스크립트가 처리하므로 원본 노드 목록으로 확인
            if target.name == "a20_etch_knowledge_graph.html" and f'["{unquote(u.fragment)}",' in target.read_text(encoding="utf-8"):
                continue
            bad.append(f"{rel}: 없는 앵커 {url}")

print(f"페이지 {len(pages)}개 검사, 문제 {len(bad)}건")
for b in bad:
    print("  " + b)
sys.exit(1 if bad else 0)
