from __future__ import annotations

import pytest

from app.schemas.auth import (
    AdminUserCreateRequest,
    ChangePasswordRequest,
    RegisterRequest,
)


class TestRegisterRequest:
    def test_valid_username(self):
        req = RegisterRequest(username="testuser", password="password123")
        assert req.username == "testuser"

    def test_valid_username_with_underscores(self):
        req = RegisterRequest(username="test_user_01", password="password123")
        assert req.username == "test_user_01"

    def test_valid_username_with_hyphens(self):
        req = RegisterRequest(username="test-user", password="password123")
        assert req.username == "test-user"

    def test_username_too_short(self):
        with pytest.raises(Exception):
            RegisterRequest(username="a", password="password123")

    def test_password_too_short(self):
        with pytest.raises(Exception):
            RegisterRequest(username="testuser", password="12345")

    def test_username_with_spaces_raises(self):
        with pytest.raises(Exception):
            RegisterRequest(username="test user", password="password123")

    def test_username_with_special_chars_raises(self):
        with pytest.raises(Exception):
            RegisterRequest(username="test@user", password="password123")


class TestChangePasswordRequest:
    def test_valid(self):
        req = ChangePasswordRequest(old_password="old123456", new_password="new123456")
        assert req.old_password == "old123456"
        assert req.new_password == "new123456"

    def test_new_password_too_short(self):
        with pytest.raises(Exception):
            ChangePasswordRequest(old_password="old123456", new_password="12345")

    def test_empty_old_password(self):
        with pytest.raises(Exception):
            ChangePasswordRequest(old_password="", new_password="new123456")


class TestAdminUserCreateRequest:
    def test_default_role_is_user(self):
        req = AdminUserCreateRequest(username="newbie", password="password123")
        assert req.role == "user"

    def test_explicit_admin_role(self):
        req = AdminUserCreateRequest(username="admin2", password="password123", role="admin")
        assert req.role == "admin"

    def test_invalid_role_raises(self):
        with pytest.raises(Exception):
            AdminUserCreateRequest(username="bad", password="password123", role="superadmin")

    def test_short_password_raises(self):
        with pytest.raises(Exception):
            AdminUserCreateRequest(username="ok", password="12345")
