"""Unit tests for the payments package. No live database required.

Run:  ~/workspace/forum-stack/payments/.venv/bin/python -m unittest discover -s tests -v
"""

import base64
import hashlib
import hmac
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

os.environ["PAYMENTS_ENC_KEY"] = base64.b64encode(os.urandom(32)).decode()

from payments import crypto  # noqa: E402
from payments.guards import (  # noqa: E402
    CardDataRejected,
    assert_no_card_data,
    looks_like_pan,
)
from payments.store import PaymentsStore  # noqa: E402
from payments.webhooks import (  # noqa: E402
    SignatureRejected,
    handle_webhook,
    verify_signature,
)

TEST_PAN = "4242424242424242"  # Luhn-valid test card number (Stripe docs)


# ------------------------------------------------------------------ fakes
class FakeCursor:
    def __init__(self, queue):
        self.queue = queue
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        return self.queue.pop(0) if self.queue else None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConn:
    def __init__(self, rows):
        self.queue = list(rows)
        self.cursors = []
        self.commits = 0

    def cursor(self):
        cur = FakeCursor(self.queue)
        self.cursors.append(cur)
        return cur

    def commit(self):
        self.commits += 1

    def all_queries(self):
        return [q for c in self.cursors for q, _ in c.executed]

    def all_params(self):
        return [p for c in self.cursors for _, p in c.executed]


def make_store(rows):
    return PaymentsStore(FakeConn(rows))


# ------------------------------------------------------------------- crypto
class CryptoTests(unittest.TestCase):
    def test_round_trip(self):
        ct = crypto.encrypt("kit@example.com")
        self.assertIsInstance(ct, bytes)
        self.assertNotIn(b"kit@example.com", ct)
        self.assertEqual(crypto.decrypt(ct), "kit@example.com")

    def test_nondeterministic(self):
        self.assertNotEqual(crypto.encrypt("x"), crypto.encrypt("x"))

    def test_missing_key_fails_closed(self):
        saved = os.environ.pop("PAYMENTS_ENC_KEY")
        try:
            with self.assertRaises(RuntimeError):
                crypto.encrypt("x")
        finally:
            os.environ["PAYMENTS_ENC_KEY"] = saved

    def test_short_key_rejected(self):
        saved = os.environ["PAYMENTS_ENC_KEY"]
        os.environ["PAYMENTS_ENC_KEY"] = base64.b64encode(b"short").decode()
        try:
            with self.assertRaises(RuntimeError):
                crypto.encrypt("x")
        finally:
            os.environ["PAYMENTS_ENC_KEY"] = saved

    def test_rotate(self):
        old = base64.b64decode(os.environ["PAYMENTS_ENC_KEY"])
        new = os.urandom(32)
        ct = crypto.encrypt("secret", key=old)
        ct2 = crypto.rotate(ct, old_key=old, new_key=new)
        self.assertEqual(crypto.decrypt(ct2, key=new), "secret")

    def test_tampered_ciphertext_rejected(self):
        ct = bytearray(crypto.encrypt("secret"))
        ct[-1] ^= 0xFF
        with self.assertRaises(Exception):
            crypto.decrypt(bytes(ct))


# ------------------------------------------------------------------- guards
class GuardTests(unittest.TestCase):
    def test_luhn_valid_pan_detected(self):
        self.assertTrue(looks_like_pan(TEST_PAN))
        self.assertTrue(looks_like_pan("4242 4242 4242 4242"))
        self.assertTrue(looks_like_pan("4242-4242-4242-4242"))

    def test_non_pans_ignored(self):
        self.assertFalse(looks_like_pan("4242"))                 # last4 only
        self.assertFalse(looks_like_pan("pm_1AbC2dEfGhIjKlMn"))  # provider token
        self.assertFalse(looks_like_pan("cus_12345"))
        self.assertFalse(looks_like_pan("1111111111111111"))     # all same digit
        self.assertFalse(looks_like_pan("1234567890123"))        # fails Luhn
        self.assertFalse(looks_like_pan(None))
        self.assertFalse(looks_like_pan(4242424242424242))       # not a string

    def test_assert_rejects_nested(self):
        with self.assertRaises(CardDataRejected):
            assert_no_card_data(token="pm_ok",
                                payload={"nested": [TEST_PAN]})
        # clean values pass silently
        assert_no_card_data(token="pm_ok", last4="4242")


# -------------------------------------------------------------------- store
class StoreTests(unittest.TestCase):
    def test_create_customer_encrypts_pii(self):
        store = make_store([{"id": "c1", "external_ref": "ext1",
                             "country": "US", "created_at": "t"}])
        store.create_customer("ext1", "kit@example.com", name="Kit",
                              country="US", actor="test")
        params = store.conn.all_params()
        insert_params = params[0]
        # email/name stored as ciphertext bytes, never plaintext
        self.assertIsInstance(insert_params[1], bytes)
        self.assertIsInstance(insert_params[2], bytes)
        for p in params:
            for v in (p or ()):
                if isinstance(v, str):
                    self.assertNotIn("kit@example.com", v)
        # values are bound parameters, not interpolated into SQL
        for q in store.conn.all_queries():
            self.assertNotIn("kit@example.com", q)
            self.assertIn("%s", q)
        # audit row was written
        self.assertTrue(any("payment_access_audit" in q
                            for q in store.conn.all_queries()))

    def test_create_customer_rejects_pan_email(self):
        store = make_store([])
        with self.assertRaises(CardDataRejected):
            store.create_customer("ext1", TEST_PAN, actor="test")

    def test_attach_payment_method_rejects_pan(self):
        store = make_store([])
        with self.assertRaises(CardDataRejected):
            store.attach_payment_method("c1", "stripe", TEST_PAN,
                                        last4="4242", actor="test")

    def test_attach_payment_method_validates_last4(self):
        store = make_store([])
        with self.assertRaises(ValueError):
            store.attach_payment_method("c1", "stripe", "pm_abc",
                                        last4="4242424242424242", actor="test")

    def test_create_payment_idempotent(self):
        # first INSERT hits ON CONFLICT -> fetchone None -> falls back to SELECT
        existing = {"id": "p1", "customer_id": "c1", "purpose": "donation",
                    "amount_cents": 500, "currency": "USD", "status": "pending",
                    "provider": "stripe", "provider_charge_id": None,
                    "created_at": "t", "updated_at": "t"}
        store = make_store([None, existing])
        row = store.create_payment("c1", "key-123", "donation", 500, "USD",
                                   "stripe", actor="test")
        self.assertEqual(row["id"], "p1")  # same record, no double charge
        self.assertIn("ON CONFLICT (idempotency_key)", store.conn.all_queries()[0])

    def test_create_payment_validates(self):
        store = make_store([])
        with self.assertRaises(ValueError):
            store.create_payment("c1", "k", "bribe", 500, "USD", "stripe")
        with self.assertRaises(ValueError):
            store.create_payment("c1", "k", "donation", -5, "USD", "stripe")
        with self.assertRaises(ValueError):
            store.create_payment("c1", "k", "donation", 500, "US", "stripe")

    def test_illegal_transition_refused(self):
        store = make_store([{"status": "failed"}])
        with self.assertRaises(ValueError):
            store.transition_payment("p1", "succeeded", actor="test")

    def test_legal_transition(self):
        store = make_store(
            [{"status": "pending"},
             {"id": "p1", "status": "succeeded",
              "provider_charge_id": "ch_1", "updated_at": "t"}])
        row = store.transition_payment("p1", "succeeded",
                                       provider_charge_id="ch_1", actor="test")
        self.assertEqual(row["status"], "succeeded")

    def test_record_event_hashes_payload(self):
        raw = b'{"id":"evt_1","card":"' + TEST_PAN.encode() + b'"}'
        store = make_store([{"id": 7, "received_at": "t"}])
        out = store.record_event("stripe", "evt_1", "charge.succeeded",
                                 raw, payment_id="p1")
        self.assertFalse(out["duplicate"])
        params = store.conn.all_params()[0]
        self.assertEqual(params[4], hashlib.sha256(raw).hexdigest())
        # raw payload bytes never bound as a parameter
        for p in store.conn.all_params():
            for v in (p or ()):
                self.assertNotEqual(v, raw)

    def test_record_event_duplicate(self):
        store = make_store([None])  # ON CONFLICT DO NOTHING -> no row
        out = store.record_event("stripe", "evt_1", "charge.succeeded",
                                 b"{}", payment_id="p1")
        self.assertTrue(out["duplicate"])
        self.assertIsNone(out["event_row_id"])


# ----------------------------------------------------------------- webhooks
class WebhookTests(unittest.TestCase):
    SECRET = "whsec_test"

    def _signed(self, payload: bytes):
        ts = "1492774577"
        v1 = hmac.new(self.SECRET.encode(), ts.encode() + b"." + payload,
                      hashlib.sha256).hexdigest()
        return f"t={ts},v1={v1}"

    def test_verify_ok(self):
        payload = b'{"id":"evt_1"}'
        self.assertTrue(verify_signature("stripe", payload,
                                        self._signed(payload), self.SECRET))

    def test_verify_tampered(self):
        payload = b'{"id":"evt_1"}'
        sig = self._signed(payload)
        self.assertFalse(verify_signature("stripe", b'{"id":"evt_2"}',
                                         sig, self.SECRET))

    def test_verify_no_secret_fails_closed(self):
        with self.assertRaises(SignatureRejected):
            verify_signature("stripe", b"{}", "t=1,v1=abc", "")

    def test_verify_unknown_provider(self):
        with self.assertRaises(NotImplementedError):
            verify_signature("acme", b"{}", "sig", self.SECRET)

    def test_handle_webhook_applies_transition(self):
        payload = (b'{"id":"evt_1","type":"charge.succeeded",'
                   b'"data":{"object":{"id":"ch_1"}}}')
        store = make_store([
            {"id": "p1"},                                  # lookup by charge id
            {"id": 7, "received_at": "t"},                 # event insert
            {"status": "pending"},                        # pre-transition read
            {"status": "pending"},                        # transition read
            {"id": "p1", "status": "succeeded",            # transition update
             "provider_charge_id": "ch_1", "updated_at": "t"},
        ])
        out = handle_webhook(store, "stripe", payload,
                             self._signed(payload), self.SECRET)
        self.assertEqual(out["payment_id"], "p1")
        self.assertFalse(out["duplicate"])
        self.assertEqual(out["applied_transition"], "succeeded")

    def test_handle_webhook_duplicate_safe(self):
        payload = (b'{"id":"evt_1","type":"charge.succeeded",'
                   b'"data":{"object":{"id":"ch_1"}}}')
        store = make_store([
            {"id": "p1"},
            None,  # duplicate event: nothing inserted
        ])
        out = handle_webhook(store, "stripe", payload,
                             self._signed(payload), self.SECRET)
        self.assertTrue(out["duplicate"])
        self.assertIsNone(out["applied_transition"])

    def test_handle_webhook_bad_signature(self):
        store = make_store([])
        with self.assertRaises(SignatureRejected):
            handle_webhook(store, "stripe", b"{}", "t=1,v1=nope", self.SECRET)


if __name__ == "__main__":
    unittest.main()
