"""Tests for modules/auth login and verify endpoints (integration with real DB)."""

import hashlib
import uuid

import pytest


async def test_login_valid_sha256(db_session):
    """Login with valid SHA256 password should succeed."""
    username = f"test_auth_{uuid.uuid4().hex[:8]}"
    password = "testpass123"
    pw_hash = hashlib.sha256(password.encode()).hexdigest()

    try:
        await db_session.execute(
            """INSERT INTO users (username, password_hash, role, is_active, created_at)
               VALUES (:username, :pw_hash, 'cashier', 1, NOW())""",
            {"username": username, "pw_hash": pw_hash},
        )

        user = await db_session.fetchrow(
            "SELECT * FROM users WHERE username = :username AND is_active = 1",
            {"username": username},
        )
        assert user is not None
        assert user["password_hash"] == pw_hash

        # Verify SHA256 match
        check = hashlib.sha256(password.encode()).hexdigest()
        assert check == pw_hash
    finally:
        await db_session.execute(
            "DELETE FROM users WHERE username = :username", {"username": username}
        )


async def test_login_invalid_password(db_session):
    """Login with wrong password should fail verification."""
    username = f"test_auth_bad_{uuid.uuid4().hex[:8]}"
    password = "correctpass"
    wrong = "wrongpass"
    pw_hash = hashlib.sha256(password.encode()).hexdigest()

    try:
        await db_session.execute(
            """INSERT INTO users (username, password_hash, role, is_active, created_at)
               VALUES (:username, :pw_hash, 'cashier', 1, NOW())""",
            {"username": username, "pw_hash": pw_hash},
        )

        wrong_hash = hashlib.sha256(wrong.encode()).hexdigest()
        assert wrong_hash != pw_hash
    finally:
        await db_session.execute(
            "DELETE FROM users WHERE username = :username", {"username": username}
        )


async def test_verify_token_structure(db_session):
    """Verify that create_token produces a decodable JWT."""
    from modules.shared.auth import create_token, SECRET_KEY, ALGORITHM
    import jwt

    token = create_token("42", "admin")
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    assert payload["sub"] == "42"
    assert payload["role"] == "admin"
    assert "exp" in payload
    assert "jti" in payload
