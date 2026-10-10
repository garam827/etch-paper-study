"""학술 메타데이터 검색 (OpenAlex · Crossref · arXiv).

실제로 존재하는 논문만 후보로 삼기 위한 도구. 결과는 JSON 목록으로 출력하며,
각 항목은 출처 API가 돌려준 메타데이터 그대로다 (요약·추측 없음).

사용법:
    python tools/lit_search.py "selective SiGe etch nanosheet" [--n 10] [--from 2018] [--src openalex,crossref,arxiv]

필드: source, title, authors(앞 3명), venue, year, doi, url, cited_by, oa_url, type
"""
import argparse
import json
import sys
import urllib.parse
import xml.etree.ElementTree as ET

import requests

UA = {"User-Agent": "etch-paper-study/1.0 (literature search; mailto:none)"}
T = 25


def openalex(q, n, y0):
    p = {"search": q, "per-page": n, "sort": "relevance_score:desc"}
    if y0:
        p["filter"] = f"from_publication_date:{y0}-01-01"
    r = requests.get("https://api.openalex.org/works", params=p, headers=UA, timeout=T)
    r.raise_for_status()
    out = []
    for w in r.json().get("results", []):
        loc = (w.get("primary_location") or {}).get("source") or {}
        oa = (w.get("open_access") or {}).get("oa_url")
        out.append({
            "source": "openalex", "title": w.get("title"),
            "authors": [a["author"]["display_name"] for a in w.get("authorships", [])[:3]],
            "venue": loc.get("display_name"), "year": w.get("publication_year"),
            "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
            "url": w.get("id"), "cited_by": w.get("cited_by_count"), "oa_url": oa, "type": w.get("type"),
        })
    return out


def crossref(q, n, y0):
    p = {"query.bibliographic": q, "rows": n,
         "select": "DOI,title,author,container-title,issued,is-referenced-by-count,type,URL"}
    if y0:
        p["filter"] = f"from-pub-date:{y0}"
    r = requests.get("https://api.crossref.org/works", params=p, headers=UA, timeout=T)
    r.raise_for_status()
    out = []
    for w in r.json()["message"]["items"]:
        yr = ((w.get("issued") or {}).get("date-parts") or [[None]])[0][0]
        out.append({
            "source": "crossref", "title": (w.get("title") or [None])[0],
            "authors": [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in w.get("author", [])[:3]],
            "venue": (w.get("container-title") or [None])[0], "year": yr, "doi": w.get("DOI"),
            "url": w.get("URL"), "cited_by": w.get("is-referenced-by-count"), "oa_url": None, "type": w.get("type"),
        })
    return out


def arxiv(q, n, y0):
    url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        {"search_query": f"all:{q}", "max_results": n, "sortBy": "relevance"})
    r = requests.get(url, headers=UA, timeout=T)
    r.raise_for_status()
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    out = []
    for e in ET.fromstring(r.text).findall("a:entry", ns):
        yr = int(e.findtext("a:published", "0000", ns)[:4])
        if y0 and yr < y0:
            continue
        doi = e.find("x:doi", ns)
        out.append({
            "source": "arxiv", "title": " ".join(e.findtext("a:title", "", ns).split()),
            "authors": [a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)[:3]],
            "venue": "arXiv", "year": yr, "doi": doi.text if doi is not None else None,
            "url": e.findtext("a:id", "", ns), "cited_by": None,
            "oa_url": e.findtext("a:id", "", ns).replace("/abs/", "/pdf/"), "type": "preprint",
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--from", dest="y0", type=int)
    ap.add_argument("--src", default="openalex,crossref,arxiv")
    a = ap.parse_args()
    res, errors, seen = [], {}, set()
    for name in a.src.split(","):
        try:
            for w in {"openalex": openalex, "crossref": crossref, "arxiv": arxiv}[name](a.query, a.n, a.y0):
                key = (w["doi"] or w["title"] or "").lower()
                if key and key not in seen:
                    seen.add(key)
                    res.append(w)
        except Exception as e:  # 한 API가 실패해도 나머지 결과는 낸다
            errors[name] = str(e)[:200]
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps({"query": a.query, "results": res, "errors": errors}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
