"""POSVENDELO - Auth Module Schemas"""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=4, max_length=200)

    @field_validator("username")
    @classmethod
    def strip_username(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("username no puede estar vacío")
        return stripped


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str = "cashier"
    branch_id: int | None = None


class SetupOwnerRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8)
    name: Optional[str] = None


class PairTokenRequest(BaseModel):
    branch_id: int = Field(default=1, ge=1)
    terminal_id: int = Field(default=1, ge=1)
    device_label: str | None = Field(default=None, max_length=120)


class PairRequest(BaseModel):
    pairing_token: str = Field(..., min_length=8, max_length=128)
    device_id: str = Field(..., min_length=3, max_length=200)
    device_name: str | None = Field(default=None, max_length=160)
    platform: str | None = Field(default=None, max_length=80)
    app_version: str | None = Field(default=None, max_length=80)
    hardware_fingerprint: str | None = Field(default=None, max_length=255)
