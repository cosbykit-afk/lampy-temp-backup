"""Data-access layer for the Lampy payments database.

Every value that reaches the database goes through parameterized queries
(no string interpolation of values, ever). PII is encrypted via crypto.py
before INSERT and decrypted after SELECT. Card-like values are rejected
by guards.py before they can be stored.

Connection settings come from PAYMENTS_DB_* environment variables; the
password and encryption key are injected from the Secure Vault at deploy.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any

import psycopg
from psycopg.rows import dict_row

from . import crypto
from .guards import assert_no_card_data

__all__ = ["PaymentsStore", "VALID_PURPOSES", "VALID_TRANSITIONS"]

VALID_PURPOSES = ("donation", "membership", "other")

# Allowed status transitions. Money must never move backwards silently:
# succeeded -> refunded/disputed only, never back to pending.
VALID_TRANSITIONS = {
    "pending": ("requires_action", "succeeded", "failed"),
    "requires_action": ("succeeded", "failed"),
    "succeeded": ("refunded", "disputed"),
    "failed": (),
    "refunded": (),
    "disputed": ("refunded",),
}


def _conninfo() -> str:
    return (
        "host={host} port={port} dbname={name} user={user} password={pw}".format(
            host=os.environ.get("PAYMENTS_DB_HOST", "127.0.0.1"),
            port=os.environ.get("PAYMENTS_DB_PORT", "5432"),
            name=os.environ.get("PAYMENTS_DB_NAME", "lampy_payments"),
            user=os.environ.get("PAYMENTS_DB_USER", "payments_app"),
            pw=os.environ.get("PAYMENTS_DB_PASSWORD", ""),
        )
    )


class PaymentsStore:
    """Thin, audited wrapper around the payments database."""

    def __init__(self, conn: Any):
        self.conn = conn

    # ------------------------------------------------------------ lifecycle
    @classmethod
    def connect(cls) -> "PaymentsStore":
        conn = psycopg.connect(_conninfo(), row_factory=dict_row)
        return cls(conn)

    def close(self) -> None:
        self.conn.close()

    # ---------------------------------------------------------------- audit
    def _audit(
        self,
        actor: str,
        action: str,
        target_id: Any = None,
        detail: str | None = None,
    ) -> None:
        assert_no_card_data(actor=actor, action=action, detail=detail or "")
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO payment_access_audit (actor, action, target_id, detail)"
                " VALUES (%s, %s, %s, %s)",
                (actor, action, target_id, detail),
            )
        self.conn.commit()

    # ------------------------------------------------------------- customers
    def create_customer(
        self,
        external_ref: str,
        email: str,
        name: str | None = None,
        country: str | None = None,
        actor: str = "system",
    ) -> dict:
        """Create (or fetch, idempotently) a customer. PII is encrypted."""
        assert_no_card_data(external_ref=external_ref, email=email, name=name or "")
        if country is not None and not re.fullmatch(r"[A-Z]{2}", country):
            raise ValueError("country must be a 2-letter ISO code")
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO customers (external_ref, email_enc, name_enc, country)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (external_ref) DO UPDATE
                    SET email_enc = EXCLUDED.email_enc,
                        name_enc  = EXCLUDED.name_enc,
                        country   = EXCLUDED.country,
                        deleted_at = NULL
                RETURNING id, external_ref, country, created_at
                """,
                (
                    external_ref,
                    crypto.encrypt(email),
                    crypto.encrypt(name) if name else None,
                    country,
                ),
            )
            row = cur.fetchone()
        self.conn.commit()
        self._audit(actor, "upsert_customer", row["id"])
        return dict(row)

    def get_customer(self, customer_id: str, actor: str) -> dict | None:
        """Fetch and decrypt a customer. Every read is audit-logged."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, external_ref, email_enc, name_enc, country,"
                "       created_at, deleted_at FROM customers WHERE id = %s",
                (customer_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        self._audit(actor, "read_customer", row["id"])
        return {
            "id": row["id"],
            "external_ref": row["external_ref"],
            "email": crypto.decrypt(row["email_enc"]),
            "name": crypto.decrypt(row["name_enc"]) if row["name_enc"] else None,
            "country": row["country"],
            "created_at": row["created_at"],
            "deleted_at": row["deleted_at"],
        }

    # ------------------------------------------------------- payment methods
    def attach_payment_method(
        self,
        customer_id: str,
        provider: str,
        provider_token: str,
        brand: str | None = None,
        last4: str | None = None,
        exp_month: int | None = None,
        exp_year: int | None = None,
        actor: str = "system",
    ) -> dict:
        """Attach an opaque provider token. Anything card-like is refused."""
        assert_no_card_data(provider_token=provider_token, brand=brand or "")
        if last4 is not None and not re.fullmatch(r"[0-9]{4}", last4):
            raise ValueError("last4 must be exactly four digits")
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payment_methods
                    (customer_id, provider, provider_token, brand, last4,
                     exp_month, exp_year)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (provider, provider_token) DO UPDATE
                    SET revoked_at = NULL
                RETURNING id, customer_id, provider, brand, last4,
                          exp_month, exp_year, created_at
                """,
                (
                    customer_id,
                    provider,
                    provider_token,
                    brand,
                    last4,
                    exp_month,
                    exp_year,
                ),
            )
            row = cur.fetchone()
        self.conn.commit()
        self._audit(actor, "attach_payment_method", row["id"])
        return dict(row)

    # --------------------------------------------------------------- payments
    def create_payment(
        self,
        customer_id: str,
        idempotency_key: str,
        purpose: str,
        amount_cents: int,
        currency: str,
        provider: str,
        actor: str = "system",
    ) -> dict:
        """Create a payment idempotently: same key -> same record, no double charge."""
        assert_no_card_data(idempotency_key=idempotency_key)
        if purpose not in VALID_PURPOSES:
            raise ValueError(f"purpose must be one of {VALID_PURPOSES}")
        if amount_cents <= 0:
            raise ValueError("amount_cents must be positive")
        if not re.fullmatch(r"[A-Z]{3}", currency or ""):
            raise ValueError("currency must be a 3-letter ISO code")
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payments
                    (customer_id, idempotency_key, purpose, amount_cents,
                     currency, provider)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING id, customer_id, purpose, amount_cents, currency,
                          status, provider, provider_charge_id,
                          created_at, updated_at
                """,
                (
                    customer_id,
                    idempotency_key,
                    purpose,
                    amount_cents,
                    currency,
                    provider,
                ),
            )
            row = cur.fetchone()
            if row is None:  # duplicate key: return the existing record
                cur.execute(
                    "SELECT id, customer_id, purpose, amount_cents, currency,"
                    "       status, provider, provider_charge_id,"
                    "       created_at, updated_at FROM payments"
                    " WHERE idempotency_key = %s",
                    (idempotency_key,),
                )
                row = cur.fetchone()
        self.conn.commit()
        self._audit(actor, "create_payment", row["id"],
                    f"{purpose} {amount_cents} {currency}")
        return dict(row)

    def transition_payment(
        self,
        payment_id: str,
        to_status: str,
        provider_charge_id: str | None = None,
        actor: str = "system",
    ) -> dict:
        """Move a payment through its lifecycle; illegal moves are refused."""
        assert_no_card_data(provider_charge_id=provider_charge_id or "")
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM payments WHERE id = %s", (payment_id,)
            )
            row = cur.fetchone()
            if row is None:
                raise KeyError(f"unknown payment {payment_id}")
            from_status = row["status"]
            if to_status not in VALID_TRANSITIONS.get(from_status, ()):
                raise ValueError(
                    f"illegal transition {from_status} -> {to_status}"
                )
            cur.execute(
                """
                UPDATE payments
                   SET status = %s,
                       provider_charge_id = COALESCE(%s, provider_charge_id)
                 WHERE id = %s
                RETURNING id, status, provider_charge_id, updated_at
                """,
                (to_status, provider_charge_id, payment_id),
            )
            updated = cur.fetchone()
        self.conn.commit()
        self._audit(actor, "transition_payment", payment_id,
                    f"{from_status} -> {to_status}")
        return dict(updated)

    # ----------------------------------------------------------------- events
    def record_event(
        self,
        provider: str,
        event_id: str,
        event_type: str,
        raw_payload: bytes,
        payment_id: str | None = None,
        actor: str = "webhook",
    ) -> dict:
        """Log a provider webhook event idempotently.

        Only the SHA-256 of the raw payload is stored — never the payload
        itself — so card data cannot accumulate here. Duplicate deliveries
        (same provider + event_id) are acknowledged without double-applying.
        """
        assert_no_card_data(event_id=event_id, event_type=event_type)
        payload_hash = hashlib.sha256(raw_payload).hexdigest()
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payment_events
                    (payment_id, provider, event_id, event_type, payload_hash)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (provider, event_id) DO NOTHING
                RETURNING id, received_at
                """,
                (payment_id, provider, event_id, event_type, payload_hash),
            )
            row = cur.fetchone()
        self.conn.commit()
        inserted = row is not None
        if inserted:
            self._audit(actor, "webhook_event", payment_id,
                        f"{provider}:{event_type}")
        return {"duplicate": not inserted,
                "event_row_id": row["id"] if row else None}
