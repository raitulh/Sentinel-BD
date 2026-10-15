from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any


PBKDF2_ITERATIONS = 310_000


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters long")
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64encode(salt)}${_b64encode(derived)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_encoded, expected_encoded = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        rounds_int = int(rounds)
        if rounds_int < 100_000 or rounds_int > 2_000_000:
            return False
        salt = _b64decode(salt_encoded)
        expected = _b64decode(expected_encoded)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds_int)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, base64.binascii.Error):
        return False


def create_access_token(*, user_id: str, organization_id: str, role: str, secret_key: str, expires_seconds: int) -> str:
    now = int(time.time())
    payload = {
        "iss": "sentinel-bd",
        "typ": "access",
        "sub": user_id,
        "org": organization_id,
        "role": role,
        "iat": now,
        "exp": now + expires_seconds,
        "jti": secrets.token_urlsafe(12),
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(secret_key.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64encode(signature)}"


def decode_access_token(token: str, secret_key: str) -> dict[str, Any] | None:
    try:
        body, signature = token.split(".", 1)
        expected_sig = hmac.new(secret_key.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected_sig, _b64decode(signature)):
            return None
        payload = json.loads(_b64decode(body))
        now = int(time.time())
        if payload.get("iss") != "sentinel-bd" or payload.get("typ") != "access":
            return None
        if not isinstance(payload.get("exp"), int) or payload["exp"] <= now:
            return None
        if not all(isinstance(payload.get(k), str) and payload.get(k) for k in ("sub", "org", "role")):
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError, base64.binascii.Error):
        return None
