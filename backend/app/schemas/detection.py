from pydantic import BaseModel, Field


class DetectRequest(BaseModel):
    text: str = Field(..., min_length=50)
