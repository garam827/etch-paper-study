"""서울대 플라즈마 응용 연구실(SNU PAL) 질문·답변 게시판 수집 → SQLite.

대상: https://snupal.snu.ac.kr/qna/list/  (robots.txt: 전체 허용)
저장: data/snupal/snupal.db  + data/snupal/raw/*.html  (로컬 보관, 공개 저장소에 올리지 않음)

- 목록 페이지에서 글 번호·문서 ID·제목·작성일·조회수를 읽고, 문서마다 본문·댓글(답변)을 저장한다.
- 이미 받은 문서는 건너뛴다(이어받기). 요청 사이 1초 쉰다.

사용법:
    python tools/snupal_crawl.py list      # 목록 전체 수집
    python tools/snupal_crawl.py docs      # 아직 안 받은 문서 수집
    python tools/snupal_crawl.py stats
"""
import re
import sqlite3
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "snupal"
RAW = DATA / "raw"
DB = DATA / "snupal.db"
BASE = "https://snupal.snu.ac.kr/qna"
UA = {"User-Agent": "Mozilla/5.0 (etch-paper-study; personal study crawler, 1 req/s)"}
DELAY = 1.0

SCHEMA = """
create table if not exists posts(
  doc_id integer primary key, list_no integer, url text, title text, category text,
  author text, date text, views integer, question_text text, question_html text,
  n_comments integer, fetched_at text);
create table if not exists comments(
  comment_id integer primary key autoincrement, doc_id integer, depth integer, ord integer,
  author text, created text, text text, html text,
  unique(doc_id, ord));
"""


def db():
    DATA.mkdir(parents=True, exist_ok=True); RAW.mkdir(exist_ok=True)
    c = sqlite3.connect(DB); c.executescript(SCHEMA); return c


def get(url):
    for attempt in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=30)
            if r.status_code == 200:
                r.encoding = "utf-8"; return r.text
            print("HTTP", r.status_code, url)
        except requests.RequestException as e:
            print("ERR", type(e).__name__, url)
        time.sleep(5 * (attempt + 1))
    return None


def crawl_list():
    c = db(); page, seen = 1, 0
    while True:
        html = get(f"{BASE}/list/?pageid={page}")
        if not html: break
        s = BeautifulSoup(html, "html.parser")
        rows = s.select("ul.board_body > li")
        new = 0
        for li in rows:
            a = li.select_one(".subject a")
            no = li.select_one(".uid")
            if not a or not no: continue
            m = re.search(r"/document/(\d+)/", a["href"])
            if not m: continue
            no_txt = no.get_text(strip=True)
            c.execute("""insert into posts(doc_id, list_no, url, title, author, date, views) values(?,?,?,?,?,?,?)
                         on conflict(doc_id) do update set list_no=excluded.list_no, title=excluded.title, views=excluded.views""",
                      (int(m.group(1)), int(no_txt) if no_txt.isdigit() else None, f"{BASE}/document/{m.group(1)}/",
                       a.get_text(" ", strip=True), (li.select_one(".kboard-author-name") or a).get_text(strip=True),
                       (li.select_one(".date") or a).get_text(strip=True),
                       int(re.sub(r"\D", "", (li.select_one(".view") or a).get_text()) or 0)))
            new += 1
        c.commit(); seen += new
        print(f"page {page}: {new} rows (누적 {seen})", flush=True)
        if new == 0: break
        page += 1; time.sleep(DELAY)
    print("목록 완료:", c.execute("select count(*) from posts").fetchone()[0])


def text_of(el):
    for br in el.find_all(["br"]): br.replace_with("\n")
    parts = [p.get_text(" ", strip=True) for p in el.find_all(["p", "li", "h1", "h2", "h3", "h4", "pre", "td"])] or [el.get_text("\n", strip=True)]
    t = "\n".join(x for x in parts if x)
    return t if t.strip() else el.get_text("\n", strip=True)


def parse_doc(doc_id, html):
    s = BeautifulSoup(html, "html.parser")
    cat = s.select_one(".kboard-header .detail-category1 .detail-value, .kboard-header .detail-category1 .detail-name")
    cats = [x.get_text(strip=True) for x in s.select(".kboard-header .cate .detail-attr div:not(.detail-name)")]
    title = s.select_one(".kboard-header h1.tit")
    cv = s.select_one(".kboard-content .content-view")
    comments = []

    def walk(ul, depth):
        for li in ul.find_all("li", class_="kboard-comments-item", recursive=False):
            body = li.select_one(":scope > .comments-list-content")
            comments.append({
                "depth": depth, "author": li.get("data-username"),
                "created": (li.select_one(":scope > .comments-list-create") or li).get_text(strip=True)[:16],
                "text": text_of(body) if body else "", "html": str(body) if body else ""})
            sub = li.select_one(":scope > .comments-list > ul")
            if sub: walk(sub, depth + 1)

    top = s.select_one(".kboard-comments-wrap > .comments-list > ul")
    if top: walk(top, 0)
    return {
        "title": title.get_text(" ", strip=True) if title else None,
        "category": (cats[0] if cats else (cat.get_text(strip=True) if cat else None)),
        "question_text": text_of(cv) if cv else "", "question_html": str(cv) if cv else "",
        "comments": comments,
    }


def crawl_docs():
    c = db()
    todo = [r[0] for r in c.execute("select doc_id from posts where fetched_at is null order by doc_id")]
    print("받을 문서:", len(todo), flush=True)
    for k, d in enumerate(todo, 1):
        raw = RAW / f"{d}.html"
        if raw.exists():
            html = raw.read_text(encoding="utf-8")
        else:
            html = get(f"{BASE}/document/{d}/")
            if not html: continue
            raw.write_text(html, encoding="utf-8"); time.sleep(DELAY)
        p = parse_doc(d, html)
        c.execute("""update posts set title=coalesce(?,title), category=?, question_text=?, question_html=?, n_comments=?,
                     fetched_at=datetime('now') where doc_id=?""",
                  (p["title"], p["category"], p["question_text"], p["question_html"], len(p["comments"]), d))
        c.execute("delete from comments where doc_id=?", (d,))
        for i, cm in enumerate(p["comments"]):
            c.execute("insert into comments(doc_id, depth, ord, author, created, text, html) values(?,?,?,?,?,?,?)",
                      (d, cm["depth"], i, cm["author"], cm["created"], cm["text"], cm["html"]))
        c.commit()
        if k % 25 == 0 or k == len(todo): print(f"{k}/{len(todo)}", flush=True)


def stats():
    c = db()
    q = lambda s: c.execute(s).fetchall()
    print("글:", q("select count(*), sum(fetched_at is not null) from posts")[0])
    print("댓글:", q("select count(*) from comments")[0][0], "/ 댓글 없는 글:", q("select count(*) from posts where n_comments=0")[0][0])
    print("분류:", q("select category, count(*) from posts group by 1 order by 2 desc"))
    print("답변자:", q("select author, count(*) from comments group by 1 order by 2 desc limit 8"))
    print("기간:", q("select min(date), max(date) from posts")[0])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"list": crawl_list, "docs": crawl_docs, "stats": stats}[sys.argv[1]]()
