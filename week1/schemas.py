from pydantic import BaseModel, Field


class GenerationRequest(BaseModel):
    prompt: str = Field(..., description="The input prompt to generate text from.")
    max_new_tokens: int = Field(
        default=256,
        ge=1,
        le=2048,
        description="Maximum number of new tokens to generate."
    )
    temperature: float = Field(
        default=0.7,
        ge=0.01,
        le=2.0,
        description="Sampling temperature. Lower is more deterministic."
    )


class GenerationResponse(BaseModel):
    generated_text: str = Field(..., description="The model's generated output.")
    model_used: str = Field(..., description="The model ID used for inference.")
    tokens_generated: int = Field(..., description="Estimated number of tokens generated.")
    processing_time_ms: float = Field(..., description="End-to-end processing time in milliseconds.")
