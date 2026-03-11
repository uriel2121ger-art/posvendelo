from pydantic import BaseModel, Field, field_validator


class CloudRegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=200)
    password: str = Field(..., min_length=8, max_length=200)
    full_name: str | None = Field(default=None, max_length=120)
    business_name: str | None = Field(default=None, max_length=120)
    branch_name: str = Field(default="Sucursal Principal", min_length=2, max_length=120)
    branch_slug: str | None = Field(default=None, min_length=2, max_length=80)
    link_code: str | None = Field(default=None, min_length=4, max_length=32)
    install_token: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("password", "full_name", "business_name", "branch_name", "branch_slug", "link_code", "install_token")
    @classmethod
    def strip_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email:
            raise ValueError("Correo inválido")
        return email


class CloudLoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=200)
    password: str = Field(..., min_length=8, max_length=200)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email:
            raise ValueError("Correo inválido")
        return email

    @field_validator("password")
    @classmethod
    def strip_password(cls, value: str) -> str:
        return value.strip()


class CloudRegisterBranchRequest(BaseModel):
    branch_name: str = Field(..., min_length=2, max_length=120)
    branch_slug: str | None = Field(default=None, min_length=2, max_length=80)
    release_channel: str = Field(default="stable", min_length=2, max_length=32)

    @field_validator("branch_name", "branch_slug", "release_channel")
    @classmethod
    def strip_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class CloudLinkNodeRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=32)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class CloudPasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=8, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=200)

    @field_validator("current_password", "new_password")
    @classmethod
    def strip_passwords(cls, value: str) -> str:
        return value.strip()


class CloudPasswordForgotRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=200)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email:
            raise ValueError("Correo inválido")
        return email


class CloudPasswordResetRequest(BaseModel):
    reset_token: str = Field(..., min_length=12, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=200)

    @field_validator("reset_token", "new_password")
    @classmethod
    def strip_reset_fields(cls, value: str) -> str:
        return value.strip()


class CloudEmailChangeRequest(BaseModel):
    password: str = Field(..., min_length=8, max_length=200)
    new_email: str = Field(..., min_length=5, max_length=200)

    @field_validator("password")
    @classmethod
    def strip_password(cls, value: str) -> str:
        return value.strip()

    @field_validator("new_email")
    @classmethod
    def normalize_new_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email:
            raise ValueError("Correo inválido")
        return email


class CloudPushTokenRequest(BaseModel):
    platform: str = Field(..., min_length=2, max_length=32)
    push_token: str = Field(..., min_length=8, max_length=1000)
    device_label: str | None = Field(default=None, max_length=120)

    @field_validator("platform", "push_token", "device_label")
    @classmethod
    def strip_push_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class CloudRemoteRequestCreate(BaseModel):
    branch_id: int = Field(..., ge=1)
    request_type: str = Field(..., min_length=2, max_length=64)
    payload: dict = Field(default_factory=dict)
    approval_mode: str = Field(default="local_confirmation", min_length=2, max_length=64)
    idempotency_key: str | None = Field(default=None, max_length=120)
    expires_in_minutes: int | None = Field(default=1440, ge=5, le=10080)

    @field_validator("request_type", "approval_mode", "idempotency_key")
    @classmethod
    def strip_request_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class CloudRemoteRequestAck(BaseModel):
    status: str = Field(..., min_length=2, max_length=64)
    result: dict = Field(default_factory=dict)

    @field_validator("status")
    @classmethod
    def strip_status(cls, value: str) -> str:
        return value.strip()
