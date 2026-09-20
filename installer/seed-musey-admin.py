#!/usr/bin/env python3
"""Create (or repair) the Musey admin account in the forum database.

Idempotent: safe to run repeatedly. Ensures a user named ``musey`` exists
with ``is_admin = TRUE``. If the user already exists, the existing password
is left alone unless --reset-password is passed.

Password handling — read carefully:
  * If MUSEY_PASSWORD is set in the environment, that password is used.
  * Otherwise a 32-character random password is generated and printed ONCE
    to stdout for the operator to record (password manager, vault, etc.).
  * The plaintext password is never written to disk, never logged, and never
    stored anywhere by this script. Only the werkzeug hash goes into the
    database, exactly as the forum's own /register route would store it.

Usage (run from any host that can reach the database):
    FORUM_DB_HOST=db FORUM_DB_PORT=5432 FORUM_DB_NAME=forum \\
    FORUM_DB_USER=forum FORUM_DB_PASS=<deploy-time password> \\
    [MUSEY_PASSWORD=<chosen password>] \\
    python3 seed-musey-admin.py [--dry-run] [--reset-password]

  --dry-run         validate everything and show what would happen; touches
                    no database.
  --reset-password  if the musey user already exists, set a new password
                    (from MUSEY_PASSWORD or freshly generated) instead of
                    keeping the old one.

Prerequisites: schema.sql must already be applied (the script refuses to
run if the users table is missing), and psycopg (v3) + werkzeug installed.
"""

import argparse
import os
import re
import secrets
import string
import sys

# Same validation the forum app enforces (app.py USERNAME_RE/EMAIL_RE).
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MUSEY_USERNAME = "musey"
MUSEY_EMAIL = "musey@lampy.local"


def db_kwargs():
    return {
        "host": os.environ.get("FORUM_DB_HOST", "127.0.0.1"),
        "port": int(os.environ.get("FORUM_DB_PORT", "5432")),
        "dbname": os.environ.get("FORUM_DB_NAME", "forum"),
        "user": os.environ.get("FORUM_DB_USER", "forum"),
        "password": os.environ.get("FORUM_DB_PASS", "forum_dev_only"),
    }


def new_password():
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secrets.choice(alphabet) for _ in range(32))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reset-password", action="store_true")
    args = ap.parse_args()

    if not USERNAME_RE.match(MUSEY_USERNAME):
        sys.exit("FATAL: seed username fails the forum's username rule")
    if not EMAIL_RE.match(MUSEY_EMAIL) or len(MUSEY_EMAIL) > 254:
        sys.exit("FATAL: seed email fails the forum's email rule")

    from werkzeug.security import check_password_hash, generate_password_hash

    supplied = os.environ.get("MUSEY_PASSWORD", "")
    password = supplied if supplied else new_password()
    if len(password) < 8:
        sys.exit("FATAL: MUSEY_PASSWORD must be at least 8 characters")
    pw_hash = generate_password_hash(password)
    # Prove the hash round-trips before touching the database.
    assert check_password_hash(pw_hash, password)

    if args.dry_run:
        print("dry-run: would upsert user "
              f"username={MUSEY_USERNAME} email={MUSEY_EMAIL} is_admin=TRUE")
        print("dry-run: password source = "
              + ("MUSEY_PASSWORD (operator-chosen)" if supplied else "generated"))
        print("dry-run: hash verified to round-trip; no database touched")
        return 0

    try:
        import psycopg
    except ImportError:
        sys.exit("FATAL: psycopg (v3) is required: pip install \"psycopg[binary]\"")

    kw = db_kwargs()
    try:
        conn = psycopg.connect(**kw)
    except Exception as e:
        sys.exit(f"FATAL: could not connect to the database: {e}")
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'users'"
            )
            if not cur.fetchone():
                sys.exit("FATAL: users table missing — apply schema.sql first")

            cur.execute(
                "SELECT id, password_hash, is_admin FROM users WHERE username = %s",
                (MUSEY_USERNAME,),
            )
            row = cur.fetchone()

            if row is None:
                cur.execute(
                    "INSERT INTO users (username, email, password_hash, is_admin) "
                    "VALUES (%s, %s, %s, TRUE) RETURNING id",
                    (MUSEY_USERNAME, MUSEY_EMAIL, pw_hash),
                )
                uid = cur.fetchone()[0]
                # Mirror the app's register(): record the registration event.
                cur.execute(
                    "INSERT INTO forum_events (event_type, user_id) "
                    "VALUES ('user_registered', %s)",
                    (uid,),
                )
                created = True
            else:
                uid, old_hash, was_admin = row
                if args.reset_password:
                    cur.execute(
                        "UPDATE users SET password_hash = %s, is_admin = TRUE "
                        "WHERE id = %s",
                        (pw_hash, uid),
                    )
                elif not was_admin:
                    cur.execute(
                        "UPDATE users SET is_admin = TRUE WHERE id = %s", (uid,)
                    )
                created = False

            cur.execute(
                "SELECT username, email, is_admin FROM users WHERE id = %s", (uid,)
            )
            uname, email, is_admin = cur.fetchone()
        conn.commit()

    print(f"OK: user '{uname}' <{email}> id={uid} "
          f"is_admin={is_admin} ({'created' if created else 'already existed'})")
    if created or args.reset_password:
        print()
        print("=" * 64)
        print("MUSEY'S FORUM PASSWORD — RECORD IT NOW. It is shown once and")
        print("is not stored anywhere by this script.")
        print("=" * 64)
        print(password)
        print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
