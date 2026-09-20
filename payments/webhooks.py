"""Provider webhook ingestion: verify, dedupe, apply.

Disabled by default: without a configured provider and webhook secret,
handle_webhook() refuses to run. When a provider IS configured, the flow is:

  1. verify_signature() — reject forged callbacks (constant-time compare)
  2. store.record_event() — idempotent log; duplicate deliveries are safe
  3. map the provider event type onto a payment status transition

Only event types we explicitly map can move money; anything else is logged
and ignored.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from .guards import assert_no_card_data

__all__ = ["SignatureRejected", "verify_signature", "handle_webhook"]


class SignatureRejected(ValueError):
    """The webhook signature did not verify: the callback is not trusted."""


def _stripe_verify(payload: bytes, signature: str, secret: str) -> bool:
    """Stripe's published webhook signature scheme (t=...,v1=...)."""
    try:
        parts = dict(p.split("=", 1) for p in signature.split(","))
        timestamp, v1 = parts["t"], parts["v1"]
    except (ValueError, KeyError):
        return False
    signed = f"{timestamp}.".encode() + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


def verify_signature(provider: str, payload: bytes, signature: str,
                     secret: str) -> bool:
    """True if the callback is authentically from the provider."""
    if not secret:
        raise SignatureRejected("no webhook secret configured")
    if provider == "stripe":
        return _stripe_verify(payload, signature, secret)
    raise NotImplementedError(
        f"no signature scheme implemented for provider {provider!r}"
    )


# provider event type -> (from-statuses allowed, to-status)
_EVENT_MAP = {
    "charge.succeeded": (("pending", "requires_action"), "succeeded"),
    "payment_intent.succeeded": (("pending", "requires_action"), "succeeded"),
    "charge.failed": (("pending", "requires_action"), "failed"),
    "payment_intent.payment_failed": (("pending", "requires_action"), "failed"),
    "charge.refunded": (("succeeded",), "refunded"),
    "charge.dispute.created": (("succeeded",), "disputed"),
}


def handle_webhook(store: Any, provider: str, payload: bytes, signature: str,
                   secret: str, actor: str = "webhook") -> dict:
    """Verify, log, and apply one provider callback. Returns a summary."""
    if not verify_signature(provider, payload, signature, secret):
        raise SignatureRejected("webhook signature verification failed")
    try:
        event = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("webhook payload is not valid JSON") from exc

    event_id = str(event.get("id", ""))
    event_type = str(event.get("type", ""))
    assert_no_card_data(event_id=event_id, event_type=event_type)
    if not event_id or not event_type:
        raise ValueError("webhook payload missing id/type")

    data_object = event.get("data", {}).get("object", {}) or {}
    charge_id = data_object.get("id")
    payment_id = None
    if charge_id:
        with store.conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM payments WHERE provider_charge_id = %s",
                (charge_id,),
            )
            found = cur.fetchone()
            payment_id = found["id"] if found else None

    logged = store.record_event(
        provider=provider,
        event_id=event_id,
        event_type=event_type,
        raw_payload=payload,
        payment_id=payment_id,
        actor=actor,
    )

    applied = None
    if not logged["duplicate"] and payment_id and event_type in _EVENT_MAP:
        from_allowed, to_status = _EVENT_MAP[event_type]
        with store.conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM payments WHERE id = %s", (payment_id,)
            )
            current = cur.fetchone()["status"]
        if current in from_allowed:
            applied = store.transition_payment(
                payment_id, to_status,
                provider_charge_id=charge_id, actor=actor,
            )

    return {
        "event_id": event_id,
        "event_type": event_type,
        "duplicate": logged["duplicate"],
        "payment_id": payment_id,
        "applied_transition": applied["status"] if applied else None,
    }
