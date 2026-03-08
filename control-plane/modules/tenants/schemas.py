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
