from pydantic import BaseModel, Field, field_validator


class BranchRegisterRequest(BaseModel):
    install_token: str = Field(..., min_length=8, max_length=128)
    machine_id: str = Field(..., min_length=2, max_length=200)
    os_platform: str = Field(..., min_length=2, max_length=32)
    branch_name: str | None = Field(default=None, max_length=120)
    app_version: str | None = Field(default=None, max_length=40)
    pos_version: str | None = Field(default=None, max_length=40)

    @field_validator("install_token", "machine_id", "os_platform", "branch_name", "app_version", "pos_version")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        return stripped or None


class BranchInstallReportRequest(BaseModel):
    install_token: str = Field(..., min_length=8, max_length=128)
    status: str = Field(..., min_length=2, max_length=32)
    error: str | None = Field(default=None, max_length=500)
    app_version: str | None = Field(default=None, max_length=40)
    pos_version: str | None = Field(default=None, max_length=40)

    @field_validator("install_token", "status", "error", "app_version", "pos_version")
    @classmethod
    def strip_report_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
