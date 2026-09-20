"""Auth hardening tests for the db-console. No live database needed.

Run from db-console/ with the forum venv:
    CONSOLE_DEV=1 FORUM_SECRET_KEY=test-key \
    ~/workspace/forum/venv/bin/python -m unittest discover -s tests -t . -v
"""

import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CONSOLE_DIR = os.path.dirname(HERE)

os.environ.setdefault("FORUM_SECRET_KEY", "test-key-for-auth-tests")
os.environ["CONSOLE_DEV"] = "1"
sys.path.insert(0, CONSOLE_DIR)

import app as console_app  # noqa: E402
import auth  # noqa: E402
import security  # noqa: E402


def set_session(client, **values):
    with client.session_transaction() as s:
        for k, v in values.items():
            s[k] = v


class HardeningTests(unittest.TestCase):
    def setUp(self):
        console_app.login_limiter.reset()
        self.client = console_app.app.test_client()
        self._orig_verify = auth.verify_login

    def tearDown(self):
        auth.verify_login = self._orig_verify
        console_app.login_limiter.reset()

    # ------------------------------------------------- secret key handling
    def test_refuses_to_start_without_secret(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("FORUM_SECRET_KEY", "CONSOLE_DEV")}
        p = subprocess.run(
            [sys.executable, "app.py"], cwd=CONSOLE_DIR, env=env,
            capture_output=True, text=True, timeout=120)
        self.assertNotEqual(p.returncode, 0,
                            "app must not start without a secret key")
        self.assertIn("FORUM_SECRET_KEY", p.stderr)

    def test_env_secret_is_used(self):
        key = os.environ["FORUM_SECRET_KEY"]
        self.assertTrue(key)
        self.assertEqual(console_app.app.secret_key, key)

    def test_no_hardcoded_fallback_key(self):
        self.assertNotIn("dev-only-change-me",
                         open(os.path.join(CONSOLE_DIR, "app.py")).read())

    # ------------------------------------------------------- cookie config
    def test_session_cookie_flags(self):
        cfg = console_app.app.config
        self.assertTrue(cfg["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(cfg["SESSION_COOKIE_SAMESITE"], "Lax")

    def test_login_page_sets_httponly_cookie(self):
        r = self.client.get("/login")
        self.assertEqual(r.status_code, 200)
        cookie = r.headers.get("Set-Cookie", "")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

    # ----------------------------------------------------------------- CSRF
    def test_login_form_has_csrf_field(self):
        html = self.client.get("/login").get_data(as_text=True)
        self.assertIn('name="csrf_token"', html)

    def test_login_rejects_missing_csrf(self):
        r = self.client.post("/login",
                             data={"username": "x", "password": "y"})
        self.assertEqual(r.status_code, 400)

    def test_login_rejects_bad_csrf(self):
        set_session(self.client, _csrf_token="real-token")
        r = self.client.post("/login", data={
            "username": "x", "password": "y", "csrf_token": "wrong"})
        self.assertEqual(r.status_code, 400)

    def _csrf_post(self, **form):
        set_session(self.client, _csrf_token="tok123")
        form["csrf_token"] = "tok123"
        return self.client.post("/login", data=form)

    def test_bad_credentials_401(self):
        auth.verify_login = lambda u, p: None
        r = self._csrf_post(username="nobody", password="wrong")
        self.assertEqual(r.status_code, 401)
        self.assertIn("Invalid username or password",
                      r.get_data(as_text=True))

    def test_db_unreachable_503_not_500(self):
        # No monkeypatch: real verify_login fails closed without a database.
        r = self._csrf_post(username="musey", password="password")
        self.assertEqual(r.status_code, 503)
        self.assertIn("account database unreachable",
                      r.get_data(as_text=True))

    # ---------------------------------------------------------- rate limit
    def test_rate_limit_locks_out_after_five_failures(self):
        auth.verify_login = lambda u, p: None
        statuses = [self._csrf_post(username="u", password="w").status_code
                    for _ in range(6)]
        self.assertEqual(statuses[:5], [401] * 5)
        self.assertEqual(statuses[5], 429)
        r = self._csrf_post(username="u", password="w")
        self.assertIn("Retry-After", r.headers)

    def test_success_resets_rate_limit(self):
        auth.verify_login = lambda u, p: None
        for _ in range(4):
            self._csrf_post(username="u", password="w")
        # a success clears the counter
        auth.verify_login = lambda u, p: {"id": 1, "username": "u",
                                          "is_admin": False}
        r = self._csrf_post(username="u", password="right")
        self.assertEqual(r.status_code, 302)
        auth.verify_login = lambda u, p: None
        # fresh client (logged out): four more failures are still fine
        self.client = console_app.app.test_client()
        for _ in range(4):
            self.assertEqual(
                self._csrf_post(username="u", password="w").status_code, 401)

    # --------------------------------------------------------------- logout
    def test_logout_get_not_allowed(self):
        self.assertEqual(self.client.get("/logout").status_code, 405)

    def test_logout_post_clears_session(self):
        set_session(self.client, console_user={"id": 1, "username": "u",
                                               "is_admin": False})
        r = self.client.post("/logout")
        self.assertEqual(r.status_code, 302)
        with self.client.session_transaction() as s:
            self.assertNotIn("console_user", s)

    # ----------------------------------------------------- musey-review CSRF
    def _admin(self):
        set_session(self.client,
                    console_user={"id": 1, "username": "musey",
                                  "is_admin": True},
                    _csrf_token="tok123")

    def test_musey_review_rejects_missing_csrf(self):
        self._admin()
        r = self.client.post("/forum/musey-review", json={"body": "hi"})
        self.assertEqual(r.status_code, 403)

    def test_musey_review_accepts_header_csrf(self):
        self._admin()
        # Empty body: 400 from the handler proves the CSRF gate passed.
        r = self.client.post("/forum/musey-review", json={"body": ""},
                             headers={"X-CSRF-Token": "tok123"})
        self.assertEqual(r.status_code, 400)

    def test_musey_review_still_admin_gated(self):
        set_session(self.client,
                    console_user={"id": 2, "username": "pleb",
                                  "is_admin": False},
                    _csrf_token="tok123")
        r = self.client.post("/forum/musey-review", json={"body": "hi"},
                             headers={"X-CSRF-Token": "tok123"})
        self.assertEqual(r.status_code, 403)

    # ------------------------------------------------------- login redirect
    def test_next_redirect_restricted_to_relative_paths(self):
        set_session(self.client, _csrf_token="tok123")
        auth.verify_login = lambda u, p: {"id": 1, "username": "u",
                                          "is_admin": True}
        r = self.client.post("/login", data={
            "username": "u", "password": "p", "csrf_token": "tok123",
            "next": "//evil.example/phish"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].startswith("/"))
        self.assertNotIn("evil.example", r.headers["Location"])


if __name__ == "__main__":
    unittest.main()
