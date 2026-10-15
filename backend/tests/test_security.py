from __future__ import annotations

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_and_verify():
    encoded = hash_password("correct-horse-battery-77")
    assert encoded.startswith("pbkdf2_sha256$")
    assert verify_password("correct-horse-battery-77", encoded)
    assert not verify_password("wrong-password", encoded)


def test_short_password_rejected():
    try:
        hash_password("tiny")
    except ValueError as exc:
        assert "12 characters" in str(exc)
    else:
        raise AssertionError("short password was accepted")


def test_token_signature_rejects_tampering():
    token = create_access_token(user_id="u1", organization_id="o1", role="admin", secret_key="long-test-secret", expires_seconds=60)
    assert decode_access_token(token, "long-test-secret")["sub"] == "u1"
    body, sig = token.split(".")
    replacement = "A" if body[0] != "A" else "B"
    assert decode_access_token(replacement + body[1:] + "." + sig, "long-test-secret") is None


def test_expired_token_rejected():
    token = create_access_token(user_id="u1", organization_id="o1", role="admin", secret_key="long-test-secret", expires_seconds=-1)
    assert decode_access_token(token, "long-test-secret") is None


def test_wrong_secret_rejected():
    token = create_access_token(user_id="u1", organization_id="o1", role="admin", secret_key="secret-a", expires_seconds=60)
    assert decode_access_token(token, "secret-b") is None
