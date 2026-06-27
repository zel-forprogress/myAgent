from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="Username")
    password: str = Field(..., min_length=1, description="Password")


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=100, description="Username")
    password: str = Field(..., min_length=6, max_length=128, description="Password (6-128 characters)")

    @field_validator("username")
    @classmethod
    def username_must_be_alphanumeric(cls, v: str) -> str:
        v = v.strip()
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, underscores and hyphens")
        return v


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=128, description="New password (6-128 characters)")


class AdminUserCreateRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(default="user", pattern=r"^(admin|user)$")


class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    created_at: str


class UserListItem(BaseModel):
    id: str
    username: str
    role: str
    created_at: str


class UserListResponse(BaseModel):
    users: List[UserListItem]
    total: int


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
