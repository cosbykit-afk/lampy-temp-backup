"""Card-data guards: make it structurally impossible to store a PAN.

No table in the payments database has a column for a full card number,
CVV, or PIN — and these guards reject card-like values in code too, so a
bug or a confused provider payload cannot smuggle one in through a text
field (e.g. provider_token or an audit detail string).

Fail-closed rule: anything that looks like a 13–19 digit number passing
the Luhn check is treated as a PAN and refused.
"""

from __future__ import annotations

import re

__all__ = ["CardDataRejected", "looks_like_pan", "assert_no_card_data"]


class CardDataRejected(ValueError):
    """Raised when a value looks like card data and must not be stored."""


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = ord(ch) - 48
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def looks_like_pan(value: object) -> bool:
    """True if the value looks like a primary account number (card number)."""
    if not isinstance(value, str):
        return False
    digits = re.sub(r"\D", "", value)
    return (
        13 <= len(digits) <= 19
        and digits.isdigit()
        and not (len(set(digits)) == 1)  # all-same-digit is not a real PAN
        and _luhn_ok(digits)
    )


def assert_no_card_data(**fields: object) -> None:
    """Reject the call if any field value looks like card data.

    Walk nested mappings/sequences as well, so a provider payload dict
    cannot hide a PAN one level down.
    """
    seen: set[int] = set()

    def walk(value: object, name: str) -> None:
        if id(value) in seen:
            return
        seen.add(id(value))
        if isinstance(value, str):
            if looks_like_pan(value):
                raise CardDataRejected(
                    f"refusing to store card-like data in field {name!r}"
                )
        elif isinstance(value, dict):
            for k, v in value.items():
                walk(v, f"{name}.{k}")
        elif isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                walk(v, f"{name}[{i}]")

    for name, value in fields.items():
        walk(value, name)
