from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestHashPassword:
    def test_returns_different_hashes_for_same_password(self):
        h1 = hash_password("test123")
        h2 = hash_password("test123")
        assert h1 != h2

    def test_hash_contains_salt_and_digest(self):
        h = hash_password("password")
        parts = h.split("$")
        assert len(parts) == 2
        assert len(parts[0]) == 32  # 16 hex bytes → 32 hex chars
        assert len(parts[1]) == 64  # SHA-256 hex digest


class TestVerifyPassword:
    def test_correct_password_returns_true(self):
        h = hash_password("mypassword")
        assert verify_password("mypassword", h) is True

    def test_incorrect_password_returns_false(self):
        h = hash_password("correct")
        assert verify_password("wrong", h) is False

    def test_empty_hash_returns_false(self):
        assert verify_password("anything", "") is False

    def test_malformed_hash_returns_false(self):
        assert verify_password("anything", "noseparator") is False

    def test_tampered_hash_returns_false(self):
        h = hash_password("secret")
        salt, digest = h.split("$", 1)
        tampered_digest = "0" * 64
        assert verify_password("secret", f"{salt}${tampered_digest}") is False

    def test_verify_uses_constant_time_comparison(self):
        h = hash_password("secret")
        assert verify_password("secret", h) is True


class TestCreateAccessToken:
    def test_token_contains_correct_claims(self):
        user = MagicMock()
        user.id = "user-1"
        user.username = "alice"
        user.role = "admin"

        token = create_access_token(user)
        payload = decode_access_token(token)

        assert payload["sub"] == "user-1"
        assert payload["username"] == "alice"
        assert payload["role"] == "admin"
        assert "exp" in payload

    def test_token_is_valid_jwt(self):
        user = MagicMock()
        user.id = "u1"
        user.username = "bob"
        user.role = "user"

        token = create_access_token(user)
        payload = decode_access_token(token)

        assert isinstance(payload, dict)
        assert payload["sub"] == "u1"


class TestDecodeAccessToken:
    def test_roundtrip_token(self):
        user = MagicMock()
        user.id = "u2"
        user.username = "charlie"
        user.role = "user"

        token = create_access_token(user)
        decoded = decode_access_token(token)

        assert decoded["sub"] == "u2"
        assert decoded["username"] == "charlie"
        assert decoded["role"] == "user"
