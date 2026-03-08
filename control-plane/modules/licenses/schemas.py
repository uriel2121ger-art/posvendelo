from pydantic import BaseModel, Field, field_validator


class LicenseResolveRequest(BaseModel):
    install_token: str = Field(..., min_length=8, max_length=128)
    machine_id: str | None = Field(default=None, max_length=200)
    os_platform: str | None = Field(default=None, max_length=32)
    app_version: str | None = Field(default=None, max_length=40)
    pos_version: str | None = Field(default=None, max_length=40)

    @field_validator("install_token", "machine_id", "os_platform", "app_version", "pos_version")
    @classmethod
    def strip_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class LicenseActivateRequest(LicenseResolveRequest):
    pass


class LicenseRefreshRequest(LicenseResolveRequest):
    pass


class LicenseRevokeRequest(BaseModel):
    license_id: int = Field(..., gt=0)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class LicenseIssueRequest(BaseModel):
    tenant_id: int = Field(..., gt=0)
    license_type: str = Field(..., pattern="^(trial|monthly|perpetual)$")
    status: str = Field(default="active", pattern="^(active|grace|expired|revoked)$")
    valid_from: str | None = Field(default=None, max_length=40)
    valid_until: str | None = Field(default=None, max_length=40)
    support_until: str | None = Field(default=None, max_length=40)
    trial_started_at: str | None = Field(default=None, max_length=40)
    trial_expires_at: str | None = Field(default=None, max_length=40)
    grace_days: int = Field(default=0, ge=0, le=60)
    max_branches: int | None = Field(default=None, ge=1, le=1000)
    max_devices: int | None = Field(default=None, ge=1, le=10000)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator(
        "license_type",
        "status",
        "valid_from",
        "valid_until",
        "support_until",
        "trial_started_at",
        "trial_expires_at",
        "notes",
    )
    @classmethod
    def strip_values(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
