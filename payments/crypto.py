"""AES-256-GCM envelope encryption for PII columns.

The 32-byte key comes from the PAYMENTS_ENC_KEY environment variable
(base64-encoded). That variable is populated from the Secure Vault at
deploy time. The key is never committed, never logged, and never sent
anywhere — this module refuses to operate without it.

Ciphertext layout: nonce (12 bytes) || AES-GCM ciphertext+tag.
"""

from __future__ import annotations

import base64
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_ENV_VAR = "PAYMENTS_ENC_KEY"
_NONCE_LEN = 12
_KEY_LEN = 32


def load_key() -> bytes:
    """Return the 32-byte data key, or raise (fail closed, no PII w/o key)."""
    raw = os.environ.get(_ENV_VAR)
    if not raw:
        raise RuntimeError(
            f"{_ENV_VAR} is not set: refusing to handle PII without an "
            "encryption key. Populate it from the Secure Vault at deploy."
        )
    try:
        key = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise RuntimeError(f"{_ENV_VAR} is not valid base64") from exc
    if len(key) != _KEY_LEN:
        raise RuntimeError(f"{_ENV_VAR} must decode to 32 bytes (AES-256)")
    return key


def generate_key_b64() -> str:
    """Generate a fresh 32-byte key, base64-encoded.

    Print it ONCE and store it in the Secure Vault immediately. It must
    never be written to a file, chat log, or repository.
    """
    return base64.b64encode(secrets.token_bytes(_KEY_LEN)).decode("ascii")


def encrypt(plaintext: str, *, key: bytes | None = None) -> bytes:
    """Encrypt a PII string for storage in a BYTEA column."""
    aesgcm = AESGCM(key or load_key())
    nonce = secrets.token_bytes(_NONCE_LEN)
    return nonce + aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)


def decrypt(token: bytes, *, key: bytes | None = None) -> str:
    """Decrypt a BYTEA column value back to a string."""
    token = bytes(token)
    if len(token) <= _NONCE_LEN:
        raise ValueError("ciphertext too short")
    aesgcm = AESGCM(key or load_key())
    return aesgcm.decrypt(token[:_NONCE_LEN], token[_NONCE_LEN:], None).decode("utf-8")


def rotate(token: bytes, *, old_key: bytes, new_key: bytes) -> bytes:
    """Re-encrypt a stored value under a new key (for key rotation)."""
    return encrypt(decrypt(token, key=old_key), key=new_key)
