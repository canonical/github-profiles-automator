"""Helpers for running the unit tests."""

import base64


def as_base64(text: str) -> str:
    """Return the same string as Base64-encoded text."""
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")
