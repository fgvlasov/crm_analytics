# -*- coding: utf-8 -*-
"""HMAC helpers for LeadIntel signed requests."""

import hashlib
import hmac
import time


def sign_payload(method: str, path: str, timestamp: str, raw_body: bytes, secret: str) -> str:
    body_hash = hashlib.sha256(raw_body).hexdigest()
    payload = f"{method.upper()}\n{path}\n{timestamp}\n{body_hash}"
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_signature(
    method: str,
    path: str,
    timestamp: str,
    raw_body: bytes,
    signature: str,
    secret: str,
    max_skew_seconds: int = 300,
) -> bool:
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(int(time.time()) - ts) > max_skew_seconds:
        return False
    expected = sign_payload(method, path, timestamp, raw_body, secret)
    return hmac.compare_digest(expected, signature or "")
