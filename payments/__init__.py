"""Lampy payments package: the "firewall database" layer.

Card data never reaches this code: checkout is hosted by the payment
provider, and only opaque tokens are stored. See README.md for the full
threat model and deploy checklist.
"""

from .crypto import decrypt, encrypt, generate_key_b64, load_key, rotate
from .guards import CardDataRejected, assert_no_card_data, looks_like_pan
from .store import PaymentsStore, VALID_PURPOSES, VALID_TRANSITIONS
from .webhooks import SignatureRejected, handle_webhook, verify_signature

__all__ = [
    "decrypt",
    "encrypt",
    "generate_key_b64",
    "load_key",
    "rotate",
    "CardDataRejected",
    "assert_no_card_data",
    "looks_like_pan",
    "PaymentsStore",
    "VALID_PURPOSES",
    "VALID_TRANSITIONS",
    "SignatureRejected",
    "handle_webhook",
    "verify_signature",
]
