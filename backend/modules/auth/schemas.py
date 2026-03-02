"""TITAN POS - Auth Module Schemas"""

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
