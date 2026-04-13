from pydantic import BaseModel, Field


class HumanizeRequest(BaseModel):
    text: str = Field(..., min_length=50)
    strength: str = Field("medium", pattern="^(light|medium|aggressive)$")
    tone: str = Field(
        "general", pattern="^(general|academic|casual|blog|professional)$"
    )
    max_iterations: int = Field(3, ge=1, le=5)
    target_score: float = Field(0.35, ge=0.0, le=1.0)
    mode: str = Field("sentence", pattern="^(full|sentence)$")
    candidates_per_sentence: int = Field(3, ge=1, le=5)
    preserve_citations: bool = Field(
        True,
        description="Keep citations, quotes, code blocks, and LaTeX exactly as written.",
    )


class ModelSelectRequest(BaseModel):
    model: str
