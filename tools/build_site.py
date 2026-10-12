"""사이트 생성: kb/ 원본 → research/ 결과물

    python tools/build_site.py            # 생성
    python tools/build_site.py --check    # 생성 결과가 커밋된 파일과 같은지만 확인 (다르면 종료 코드 1)

원본(손으로 고치는 곳)과 결과물(고치지 않는 곳):
  kb/graph/{types,nodes,edges,sources}.json + tools/templates/a20_etch_knowledge_graph.html
      → research/a20_etch_knowledge_graph.html
  kb/snupal/{page,topics}.json → research/snupal_qna_knowledge.html   (tools/snupal_page.py)
  OES 페이지는 별도 비공개 저장소 데이터가 필요해 여기서 만들지 않는다 → tools/oes_page.py (CLAUDE.md 참고)
그 밖의 페이지(보고서·노트·3D·기록)는 HTML 자체가 원본이다.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import snupal_page  # noqa: E402

KB = ROOT / "kb"


def load(p):
    return json.loads((KB / p).read_text(encoding="utf-8"))


def js_list(rows):
    return "[\n" + ",\n".join("  " + json.dumps(r, ensure_ascii=False) for r in rows) + ",\n]"


def js_obj(d, multiline=True):
    if not multiline:
        return json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    return "{\n" + "".join(f"  {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)},\n" for k, v in d.items()) + "}"


def check_graph(types, nodes, edges, src):
    errs, ids = [], [n["id"] for n in nodes]
    idset = set(ids)
    if len(ids) != len(idset):
        errs.append("중복 노드 id: " + ", ".join(sorted({i for i in ids if ids.count(i) > 1})))
    for n in nodes:
        if n["type"] not in types["types"]:
            errs.append(f'{n["id"]}: 없는 분류 {n["type"]}')
        if n.get("area") not in types["area_labels"]:
            errs.append(f'{n["id"]}: 없는 영역 {n.get("area")}')
        errs += [f'{n["id"]}: 없는 출처 {k}' for k in n.get("src", []) if k not in src]
    for x in edges:
        for end in (x["from"], x["to"]):
            if end not in idset:
                errs.append(f'관계 {x["from"]}>{x["to"]}: 없는 노드 {end}')
    return errs


def build_graph():
    types, nodes, edges, src = load("graph/types.json"), load("graph/nodes.json"), load("graph/edges.json"), load("graph/sources.json")
    errs = check_graph(types, nodes, edges, src)
    if errs:
        raise SystemExit("그래프 원본 오류:\n  " + "\n  ".join(errs))
    blocks = {
        "TYPES": "{\n" + "".join(f"  {k}: {json.dumps(v, ensure_ascii=False)},\n" for k, v in types["types"].items()) + "}",
        "NODES": js_list([[n["id"], n["name"], n["en"], n["type"], n["desc"], n["etch"]] for n in nodes]),
        "EDGES": js_list([[x["from"], x["to"], x["label"]] for x in edges]),
        "SRC": js_obj({k: [v["title"], v["url"]] for k, v in src.items()}),
        "SOURCES": js_obj({n["id"]: n["src"] for n in nodes if n.get("src")}),
        "EDGE_SRC": js_obj({f'{x["from"]}>{x["to"]}': x["posts"] for x in edges if x.get("posts")}, False),
        "AREA_LABEL": js_obj(types["area_labels"], False),
        "AREA": js_obj({n["id"]: n["area"] for n in nodes}, False),
    }
    page = (ROOT / "tools/templates/a20_etch_knowledge_graph.html").read_text(encoding="utf-8")
    for k, v in blocks.items():
        page = page.replace(f"__KB_{k}__", v)
    if "__KB_" in page:
        raise SystemExit("템플릿에 채우지 못한 자리가 남음")
    print(f"그래프: 노드 {len(nodes)} · 관계 {len(edges)} · 출처 {len(src)}")
    return page


TARGETS = {
    "research/a20_etch_knowledge_graph.html": build_graph,
    "research/snupal_qna_knowledge.html": snupal_page.render,
}

if __name__ == "__main__":
    check = "--check" in sys.argv
    stale = []
    for rel, fn in TARGETS.items():
        out = ROOT / rel
        page = fn()
        if check:
            if not out.exists() or out.read_text(encoding="utf-8") != page:
                stale.append(rel)
        else:
            out.write_text(page, encoding="utf-8", newline="\n")
            print("written", rel)
    if check:
        print("최신 아님: " + ", ".join(stale) if stale else "모든 생성 결과가 최신")
        sys.exit(1 if stale else 0)
