from pydantic import BaseModel, Field, field_validator


class TenantCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    slug: str = Field(..., min_length=2, max_length=80)

    @field_validator("name", "slug")
    @classmethod
    def strip_fields(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Campo requerido")
        return stripped


class TenantOnboardRequest(TenantCreateRequest):
    branch_name: str = Field(default="Sucursal Principal", min_length=2, max_length=120)
    branch_slug: str | None = Field(default=None, min_length=2, max_length=80)
    release_channel: str = Field(default="stable", min_length=2, max_length=32)
    license_type: str = Field(default="trial", pattern="^(trial|monthly|perpetual)$")
    license_status: str = Field(default="active", pattern="^(active|grace|expired|revoked)$")
    grace_days: int = Field(default=0, ge=0, le=365)
    max_branches: int | None = Field(default=None, ge=1, le=1000)
    max_devices: int | None = Field(default=None, ge=1, le=10000)
    notes: str | None = Field(default=None, max_length=1000)
