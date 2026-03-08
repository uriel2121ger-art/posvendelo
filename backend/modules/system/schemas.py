from pydantic import BaseModel, Field


class RestorePlanRequest(BaseModel):
    backup_file: str = Field(..., min_length=1, max_length=255)
