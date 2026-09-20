"""Read-only forum data layer for the Lampy console.

Tries the live forum PostgreSQL (same FORUM_DB_* env vars the forum app
uses); when the database is unreachable it falls back to clearly labeled
demo fixtures so the /forum pages still render.

Nothing here writes to the database — posting stays in the forum app.
"""

import os
import socket

DB_HOST = os.environ.get("FORUM_DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("FORUM_DB_PORT", "5432"))
DB_NAME = os.environ.get("FORUM_DB_NAME", "forum")
DB_USER = os.environ.get("FORUM_DB_USER", "forum")
DB_PASS = os.environ.get("FORUM_DB_PASS", "")


def _conninfo():
    return (
        "host=%s port=%d dbname=%s user=%s password=%s connect_timeout=4"
        % (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS)
    )


def probe():
    """True if something answers on the forum DB port."""
    try:
        socket.create_connection((DB_HOST, DB_PORT), timeout=3).close()
        return True
    except OSError:
        return False


def live_query(sql, params=()):
    """Run a read query against the live DB. Raises on any failure."""
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(_conninfo(), row_factory=dict_row) as conn:
        return conn.execute(sql, params).fetchall()


# ----------------------------------------------------------------------------
# Demo fixtures (used only while the database is not provisioned)
# ----------------------------------------------------------------------------

_FIX_CATS = [
    {"id": 1, "name": "General", "description": "General discussion",
     "thread_count": 2, "post_count": 5},
    {"id": 2, "name": "Book discussions", "description": "One thread per book or section",
     "thread_count": 1, "post_count": 3},
    {"id": 3, "name": "Site feedback", "description": "Bugs, typos, and suggestions for the site",
     "thread_count": 0, "post_count": 0},
]

_FIX_THREADS = {
    1: [
        {"id": 1, "title": "Welcome to the Lampy forum", "username": "musey",
         "is_moderator_post": True, "post_count": 3,
         "last_post_at": "2026-09-20 10:00:00+00", "is_locked": False},
        {"id": 2, "title": "Where should Book 0 discussion go?",
         "username": "kit", "is_moderator_post": False, "post_count": 2,
         "last_post_at": "2026-09-20 09:12:00+00", "is_locked": False},
    ],
    2: [
        {"id": 3, "title": "Volume 0 — first impressions", "username": "kit",
         "is_moderator_post": False, "post_count": 3,
         "last_post_at": "2026-09-20 08:40:00+00", "is_locked": False},
    ],
    3: [],
}

_FIX_POSTS = {
    1: [
        {"id": 1, "username": "musey", "is_moderator_post": True,
         "created_at": "2026-09-20 10:00:00+00",
         "body": "Hello — I'm Musey, the moderator here. Keep threads on "
                 "topic, be kind, and flag anything that looks like spam. "
                 "I'll be reading along."},
        {"id": 2, "username": "kit", "is_moderator_post": False,
         "created_at": "2026-09-20 10:05:00+00",
         "body": "Testing the forum link from the console. This is a demo "
                 "post shown while the database is not yet provisioned."},
        {"id": 3, "username": "musey", "is_moderator_post": True,
         "created_at": "2026-09-20 10:07:00+00",
         "body": "Noted — demo mode confirmed. Carry on."},
    ],
    2: [
        {"id": 4, "username": "kit", "is_moderator_post": False,
         "created_at": "2026-09-20 09:12:00+00",
         "body": "Should Book 0 get its own board, or live under Book discussions?"},
        {"id": 5, "username": "musey", "is_moderator_post": True,
         "created_at": "2026-09-20 09:20:00+00",
         "body": "Book discussions works for now — one thread per book. "
                 "We can split it out if it gets busy."},
    ],
    3: [
        {"id": 6, "username": "kit", "is_moderator_post": False,
         "created_at": "2026-09-20 08:40:00+00",
         "body": "Volume 0 reads clean. The exact-vs-conditional status "
                 "discipline is doing real work."},
        {"id": 7, "username": "musey", "is_moderator_post": True,
         "created_at": "2026-09-20 08:44:00+00",
         "body": "Agreed — and thank you for the kind words about the status labels."},
        {"id": 8, "username": "kit", "is_moderator_post": False,
         "created_at": "2026-09-20 08:50:00+00",
         "body": "One typo candidate on the vol0 page, filing under Site feedback next."},
    ],
}

_FIX_MUSEY = {"username": "musey", "email": "musey@lampy.local",
              "is_admin": True, "present": False}


def _fixture_thread(tid):
    for _cat, threads in _FIX_THREADS.items():
        for t in threads:
            if t["id"] == tid:
                cat_id = _cat
                cat = next(c for c in _FIX_CATS if c["id"] == cat_id)
                return {"id": t["id"], "title": t["title"],
                        "username": t["username"], "cat_name": cat["name"],
                        "category_id": cat_id, "is_locked": t["is_locked"]}
    return None


# ----------------------------------------------------------------------------
# Public API — each returns (payload, live: bool)
# ----------------------------------------------------------------------------

def get_overview():
    """(categories, latest_threads, live)."""
    try:
        cats = live_query(
            """SELECT c.id, c.name, c.description,
                      COUNT(DISTINCT t.id) AS thread_count,
                      COUNT(p.id) AS post_count
               FROM categories c
               LEFT JOIN threads t ON t.category_id = c.id
               LEFT JOIN posts p ON p.thread_id = t.id
               GROUP BY c.id ORDER BY c.sort_order, c.name""")
        latest = live_query(
            """SELECT t.id, t.title, t.created_at, u.username,
                      c.name AS cat_name,
                      (SELECT COUNT(*) FROM posts p WHERE p.thread_id = t.id)
                        AS post_count,
                      (SELECT MAX(p.created_at) FROM posts p
                        WHERE p.thread_id = t.id) AS last_post_at
               FROM threads t
               JOIN users u ON u.id = t.user_id
               JOIN categories c ON c.id = t.category_id
               ORDER BY last_post_at DESC NULLS LAST LIMIT 15""")
        for r in latest:
            r["is_moderator_post"] = (r["username"] == "musey")
        return cats, latest, True
    except Exception:
        latest = []
        for _cat, threads in _FIX_THREADS.items():
            latest.extend(threads)
        return _FIX_CATS, latest, False


def get_category(cat_id):
    """(category, threads, live) — category is None when missing."""
    try:
        rows = live_query(
            "SELECT id, name, description FROM categories WHERE id = %s",
            (cat_id,))
        if not rows:
            return None, [], True
        threads = live_query(
            """SELECT t.id, t.title, t.created_at, t.is_locked, u.username,
                      (SELECT COUNT(*) FROM posts p WHERE p.thread_id = t.id)
                        AS post_count,
                      (SELECT MAX(p.created_at) FROM posts p
                        WHERE p.thread_id = t.id) AS last_post_at
               FROM threads t JOIN users u ON u.id = t.user_id
               WHERE t.category_id = %s
               ORDER BY last_post_at DESC NULLS LAST""", (cat_id,))
        for r in threads:
            r["is_moderator_post"] = (r["username"] == "musey")
        return rows[0], threads, True
    except Exception:
        cat = next((c for c in _FIX_CATS if c["id"] == cat_id), None)
        return cat, _FIX_THREADS.get(cat_id, []), False


def get_thread(thread_id):
    """(thread, posts, live) — thread is None when missing."""
    try:
        rows = live_query(
            """SELECT t.id, t.title, t.is_locked, t.category_id,
                      c.name AS cat_name, u.username
               FROM threads t
               JOIN categories c ON c.id = t.category_id
               JOIN users u ON u.id = t.user_id
               WHERE t.id = %s""", (thread_id,))
        if not rows:
            return None, [], True
        posts = live_query(
            """SELECT p.id, p.body, p.created_at, u.username
               FROM posts p JOIN users u ON u.id = p.user_id
               WHERE p.thread_id = %s ORDER BY p.id ASC""", (thread_id,))
        for p in posts:
            p["is_moderator_post"] = (p["username"] == "musey")
        return rows[0], posts, True
    except Exception:
        th = _fixture_thread(thread_id)
        return th, _FIX_POSTS.get(thread_id, []), False


def get_recent_posts(limit=10):
    """Recent posts for the moderation queue. (posts, live)."""
    try:
        rows = live_query(
            """SELECT p.id, p.body, p.created_at, u.username, t.title,
                      t.id AS thread_id
               FROM posts p
               JOIN users u ON u.id = p.user_id
               JOIN threads t ON t.id = p.thread_id
               ORDER BY p.id DESC LIMIT %s""", (limit,))
        for p in rows:
            p["is_moderator_post"] = (p["username"] == "musey")
        return rows, True
    except Exception:
        posts = []
        for tid, plist in _FIX_POSTS.items():
            th = _fixture_thread(tid)
            for p in plist:
                q = dict(p)
                q["thread_id"] = tid
                q["title"] = th["title"] if th else ""
                posts.append(q)
        posts.sort(key=lambda p: p["id"], reverse=True)
        return posts[:limit], False


def get_musey_status():
    """Musey moderator account status. Dict with `present` bool."""
    try:
        rows = live_query(
            "SELECT username, email, is_admin FROM users "
            "WHERE username = 'musey'")
        if rows:
            r = rows[0]
            return {"username": r["username"], "email": r["email"],
                    "is_admin": r["is_admin"], "present": True}
        return {"username": "musey", "email": "musey@lampy.local",
                "is_admin": False, "present": False}
    except Exception:
        return dict(_FIX_MUSEY)


def get_table_counts():
    """Row counts for the database page. {} when the DB is unreachable."""
    try:
        out = {}
        for tbl in ("users", "categories", "threads", "posts",
                    "forum_events"):
            n = live_query("SELECT COUNT(*) AS n FROM %s" % tbl)[0]["n"]
            out[tbl] = n
        return out
    except Exception:
        return {}
