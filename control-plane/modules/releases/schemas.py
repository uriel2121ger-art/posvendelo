from pydantic import BaseModel, Field, field_validator


class ReleaseCreateRequest(BaseModel):
    platform: str = Field(..., min_length=2, max_length=32)
    artifact: str = Field(..., min_length=2, max_length=64)
    version: str = Field(..., min_length=1, max_length=40)
    channel: str = Field(default="stable", min_length=2, max_length=32)
    target_ref: str = Field(..., min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("platform", "artifact", "version", "channel", "target_ref", "notes")
    @classmethod
    def strip_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ReleaseAssignmentRequest(BaseModel):
    branch_id: int = Field(..., ge=1)
    platform: str = Field(..., min_length=2, max_length=32)
    artifact: str = Field(..., min_length=2, max_length=64)
    channel: str = Field(default="stable", min_length=2, max_length=32)
    pinned_version: str | None = Field(default=None, max_length=40)

    @field_validator("platform", "artifact", "channel", "pinned_version")
    @classmethod
    def strip_assignment_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ReleasePublishRequest(BaseModel):
    platform: str = Field(..., min_length=2, max_length=32)
    artifact: str = Field(..., min_length=2, max_length=64)
    version: str = Field(..., min_length=1, max_length=40)
    channel: str = Field(default="stable", min_length=2, max_length=32)
    target_ref: str = Field(..., min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=500)
    source: str | None = Field(default="github-actions", max_length=80)

    @field_validator("platform", "artifact", "version", "channel", "target_ref", "notes", "source")
    @classmethod
    def strip_publish_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
