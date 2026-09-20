#!/usr/bin/env python3
"""Lampy console prototype — DigitalOcean-docs-style web UI.

Mock content: the R Theory rewrite site, rendered dynamically from its HTML
files at startup (titles, headings, per-page CSS scoped to the article
column, links rewritten to console routes, static assets served locally).

Layout: top bar with a Google-style search box, left side-panel navigation
(volumes -> books), right "On this page" table of contents.

/database probes the forum PostgreSQL (FORUM_DB_* env) and shows a pending
panel until the database is provisioned (Windows bring-up ~2026-09-23).

Run:
    R_THEORY_DIR=~/workspace/r-theory-rewrite \
    ~/workspace/forum/venv/bin/python app.py
Serves on 127.0.0.1:5001 (localhost only — add auth before exposing).
"""

import html as ihtml
import os
import re
import socket

from flask import Flask, abort, jsonify, render_template, request, \
    send_from_directory, session

import forum_data
import musey_moderation
import auth

CONTENT_ROOT = os.path.abspath(os.path.expanduser(
    os.environ.get("R_THEORY_DIR", "~/workspace/r-theory-rewrite")))

app = Flask(__name__)
app.secret_key = os.environ.get("FORUM_SECRET_KEY", "")
if not app.secret_key:
    # Dev-only fallback: sessions won't survive restarts and aren't secure.
    app.secret_key = "dev-only-change-me"


@app.context_processor
def _inject_console_user():
    return {"console_user": auth.current_console_user()}

# ----------------------------------------------------------------------------
# Page loading: discover index.html files, then extract + normalize each page
# ----------------------------------------------------------------------------

def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def discover():
    """slug -> directory ('' for the site root)."""
    slugs = {}
    root_index = os.path.join(CONTENT_ROOT, "index.html")
    if os.path.isfile(root_index):
        slugs["index"] = ""
    for entry in sorted(os.listdir(CONTENT_ROOT)):
        p = os.path.join(CONTENT_ROOT, entry)
        if os.path.isdir(p) and os.path.isfile(os.path.join(p, "index.html")):
            slugs[entry] = entry
    return slugs


SLUGS = discover()


def scope_css(css):
    """Prefix every selector with .rtheory-doc so a page's embedded styles
    cannot leak into the console chrome. :root and body become .rtheory-doc."""
    css = re.sub(r":root\b", ".rtheory-doc", css)

    def prefix(m):
        out = []
        for s in m.group(1).split(","):
            s = s.strip()
            if not s or s.startswith("@") or s.startswith(".rtheory-doc"):
                out.append(s)
            elif s == "body":
                out.append(".rtheory-doc")
            else:
                out.append(".rtheory-doc " + s)
        return ", ".join(out) + "{"

    return re.sub(r"([^{}]+)\{", prefix, css)


def fix_url(url, d):
    """Rewrite a page-relative URL to a console route or a static file."""
    if not url or url.startswith(("#", "/")):
        return url
    if re.match(r"(?i)^[a-z][a-z0-9+.-]*:", url):
        return url  # http:, https:, mailto:, data:, ...
    if url in ("..", "../"):
        return "/"
    if url.startswith("../"):
        rest = url[3:]
        if rest.startswith("#"):
            return "/" + rest
        cand = rest.split("/")[0]
        if cand in SLUGS:
            return "/page/" + cand
        return "/rtheory-files/" + rest
    cand = url.split("/")[0]
    if url.endswith("/") and cand in SLUGS:
        return "/page/" + cand
    base = "rtheory-files/" + (d + "/" if d else "")
    return "/" + base + url


ATTR_RE = re.compile(r'''(href|src)=(?:"([^"]*)"|'([^']*)')''')


def rewrite_attrs(body, d):
    def repl(m):
        attr = m.group(1)
        url = m.group(2) if m.group(2) is not None else m.group(3)
        q = '"' if m.group(2) is not None else "'"
        return "%s=%s%s%s" % (attr, q, fix_url(url, d), q)

    return ATTR_RE.sub(repl, body)


def add_heading_ids(body):
    """Ensure every h2/h3 has an id; collect (level, id, text) for the TOC."""
    headings = []
    counter = 0

    def repl(m):
        nonlocal counter
        level, attrs, inner = m.group(1), m.group(2), m.group(3)
        text = ihtml.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
        mid = re.search(r'id="([^"]+)"', attrs)
        hid = mid.group(1) if mid else None
        if not hid:
            counter += 1
            hid = "toc-h%s-%d" % (level, counter)
            attrs = attrs + ' id="%s"' % hid
        if level in ("2", "3") and text:
            headings.append((level, hid, text))
        return "<h%s%s>%s</h%s>" % (level, attrs, inner, level)

    body = re.sub(r"<h([23])((?:\s[^>]*)?)>(.*?)</h\1>",
                  repl, body, flags=re.S | re.I)
    return body, headings


def load_page(slug, d):
    path = os.path.join(CONTENT_ROOT, d, "index.html") if d \
        else os.path.join(CONTENT_ROOT, "index.html")
    raw = _read(path)

    title_m = re.search(r"<title>(.*?)</title>", raw, re.S | re.I)
    title = ihtml.unescape(title_m.group(1)).strip() if title_m else slug

    css_m = re.search(r"<style>(.*?)</style>", raw, re.S | re.I)
    css = scope_css(css_m.group(1)) if css_m else ""

    body_m = re.search(r"<body[^>]*>(.*)</body>", raw, re.S | re.I)
    body = body_m.group(1) if body_m else raw
    # The injected site nav is replaced by the console's side panel;
    # page scripts (e.g. Desmos embeds) are dropped — PNG fallbacks remain.
    body = re.sub(r'<nav class="sitenav".*?</nav>', "", body, flags=re.S | re.I)
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S | re.I)
    body = rewrite_attrs(body, d)
    body, headings = add_heading_ids(body)

    text = ihtml.unescape(
        re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))).strip()
    return {"slug": slug, "dir": d, "title": title, "css": css,
            "body": body, "headings": headings, "text": text}


PAGES = {slug: load_page(slug, d) for slug, d in SLUGS.items()}

# ----------------------------------------------------------------------------
# Navigation: volumes -> books (DigitalOcean tutorial-series style)
# ----------------------------------------------------------------------------

VOLUMES = [
    ("Volume 0 — Exact Witnesses", ["vol0", "book20", "book21", "book22"]),
    ("Volume I — Books 0–6",
     ["book%d" % n for n in range(0, 7)]),
    ("Volume II — Books 7–13",
     ["book%d" % n for n in range(7, 14)]),
    ("Volume III — Books 14–16",
     ["book%d" % n for n in range(14, 17)]),
    ("Volume IV — Books 17–19",
     ["vol4"] + ["book%d" % n for n in range(17, 20)]),
    ("Appendices", ["tables", "e8"]),
]

SHORT_LABELS = {"vol0": "Overview", "vol4": "Overview",
                "tables": "Tables", "e8": "E8 notes", "index": "Home"}


def short_label(slug, title):
    if slug in SHORT_LABELS:
        return SHORT_LABELS[slug]
    m = re.match(r"(Book \d+)\s*[—–-]", title)
    if m:
        return m.group(1)
    return title.split("—")[0].strip()[:40]


def nav_items():
    nav = []
    for vtitle, slugs in VOLUMES:
        items = []
        for slug in slugs:
            if slug not in PAGES:
                continue
            items.append({"slug": slug,
                          "label": short_label(slug, PAGES[slug]["title"]),
                          "title": PAGES[slug]["title"],
                          "url": "/page/" + slug})
        if items:
            nav.append({"title": vtitle, "items": items})
    return nav


NAV_ITEMS = nav_items()

# ----------------------------------------------------------------------------
# Search
# ----------------------------------------------------------------------------

def snippet(text, terms, width=220):
    low = text.lower()
    hits = [low.find(t) for t in terms if t in low]
    pos = min(hits) if hits else 0
    start = max(0, pos - 80)
    end = min(len(text), pos + width)
    s = ihtml.escape(text[start:end].strip())
    for t in sorted(set(terms), key=len, reverse=True):
        s = re.sub(r"(?i)" + re.escape(ihtml.escape(t)),
                   r"<mark>\g<0></mark>", s)
    return ("…" if start > 0 else "") + s + ("…" if end < len(text) else "")


def run_search(q):
    terms = [t.lower() for t in re.findall(r"\w+", q)]
    ranked = []
    for slug, p in PAGES.items():
        score = 0.0
        tl = p["title"].lower()
        hl = " ".join(h[2] for h in p["headings"]).lower()
        bl = p["text"].lower()
        for t in terms:
            if t in tl:
                score += 10
            if t in hl:
                score += 5
            score += min(bl.count(t), 20) * 0.5
        if score > 0:
            ranked.append((score, slug))
    ranked.sort(reverse=True)
    return [(PAGES[slug], snippet(PAGES[slug]["text"], terms))
            for score, slug in ranked[:25]]

# ----------------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------------

@app.get("/")
def home():
    return render_template("page.html", section="docs", nav=NAV_ITEMS,
                           active="index", page=PAGES["index"],
                           is_home=True)


@app.get("/page/<slug>")
def page(slug):
    if slug not in PAGES:
        abort(404)
    return render_template("page.html", section="docs", nav=NAV_ITEMS,
                           active=slug, page=PAGES[slug], is_home=False)


@app.get("/search")
def search():
    q = request.args.get("q", "").strip()
    results = run_search(q) if q else []
    return render_template("search.html", section="docs", nav=NAV_ITEMS,
                           active="index", q=q, results=results)


@app.get("/database")
def database():
    host = os.environ.get("FORUM_DB_HOST", "127.0.0.1")
    port = int(os.environ.get("FORUM_DB_PORT", "5432"))
    dbname = os.environ.get("FORUM_DB_NAME", "forum")
    user = os.environ.get("FORUM_DB_USER", "forum")
    reachable, err = False, ""
    try:
        socket.create_connection((host, port), timeout=3).close()
        reachable = True
    except Exception as e:  # refused / timeout / unreachable
        err = "%s: %s" % (type(e).__name__, e)
    counts = forum_data.get_table_counts() if reachable else {}
    musey = forum_data.get_musey_status()
    return render_template("database.html", section="database", nav=NAV_ITEMS,
                           active="index", host=host, port=port, dbname=dbname,
                           user=user, reachable=reachable, err=err,
                           counts=counts, musey=musey)


@app.get("/rtheory-files/<path:fname>")
def rtheory_files(fname):
    return send_from_directory(CONTENT_ROOT, fname)


# ----------------------------------------------------------------------------
# Forum — read-only view of the forum database, with Musey as moderator
# ----------------------------------------------------------------------------

def _forum_nav():
    cats, _latest, _live = forum_data.get_overview()
    return [{"slug": "forum", "label": c["name"], "title": c["name"],
             "url": "/forum/category/%d" % c["id"]} for c in cats]


@app.get("/forum")
def forum_index():
    cats, latest, live = forum_data.get_overview()
    return render_template("forum_index.html", section="forum",
                           forum_nav=_forum_nav(), cats=cats, latest=latest,
                           live=live, musey=forum_data.get_musey_status())


@app.get("/forum/category/<int:cat_id>")
def forum_category(cat_id):
    cat, threads, live = forum_data.get_category(cat_id)
    if cat is None:
        abort(404)
    return render_template("forum_category.html", section="forum",
                           forum_nav=_forum_nav(), cat=cat, threads=threads,
                           live=live)


@app.get("/forum/thread/<int:thread_id>")
def forum_thread(thread_id):
    th, posts, live = forum_data.get_thread(thread_id)
    if th is None:
        abort(404)
    return render_template("forum_thread.html", section="forum",
                           forum_nav=_forum_nav(), th=th, posts=posts,
                           live=live)


@app.get("/forum/moderate")
@auth.admin_required
def forum_moderate():
    posts, live = forum_data.get_recent_posts(limit=10)
    ok, models = musey_moderation.ollama_available()
    return render_template("forum_moderate.html", section="forum",
                           forum_nav=_forum_nav(), posts=posts, live=live,
                           ollama_ok=ok, ollama_models=models,
                           reviews=musey_moderation.recent_reviews(),
                           musey_model=musey_moderation.MODEL)


@app.post("/forum/musey-review")
@auth.admin_required
def forum_musey_review():
    data = request.get_json(force=True, silent=True) or {}
    post_id = data.get("post_id")
    username = data.get("username", "")
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"verdict": "ERROR",
                        "error": "empty post body"}), 400
    result = musey_moderation.review_post(body)
    entry = musey_moderation.log_review(post_id, username, body, result)
    return jsonify(entry)


@app.errorhandler(404)
def not_found(e):
    return render_template("search.html", section="docs", nav=NAV_ITEMS,
                           active="index", q="", results=[],
                           notice="Page not found."), 404


# ----------------------------------------------------------------------------
# Logon — credentials verified against the forum database's users table
# ----------------------------------------------------------------------------

@app.get("/login")
def login():
    if auth.current_console_user():
        return redirect("/forum/moderate")
    return render_template("login.html", section="forum",
                           forum_nav=_forum_nav(),
                           next=request.args.get("next", ""), error="")


@app.post("/login")
def login_post():
    if auth.current_console_user():
        return redirect("/forum/moderate")
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    nxt = request.form.get("next", "") or "/forum/moderate"
    if not (nxt.startswith("/") and not nxt.startswith("//")):
        nxt = "/forum/moderate"  # relative-path redirects only
    error = ""
    try:
        user = auth.verify_login(username, password)
    except RuntimeError as e:
        user, error = None, str(e)
    if user is None and not error:
        error = "Invalid username or password."
    if error:
        return render_template("login.html", section="forum",
                               forum_nav=_forum_nav(), next=nxt, error=error)
    session["console_user"] = user
    return redirect(nxt)


@app.get("/logout")
def logout():
    session.pop("console_user", None)
    return redirect("/forum")


if __name__ == "__main__":
    print("Lampy console: %d pages loaded from %s" % (len(PAGES), CONTENT_ROOT))
    app.run(host="127.0.0.1", port=5001)
