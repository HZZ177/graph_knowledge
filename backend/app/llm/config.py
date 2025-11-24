from pydantic import BaseModel


class LLMConfig(BaseModel):
    provider: str | None = None
    model_name: str
    base_url: str | None = None
    api_key: str
    temperature: float = 0.7
    max_tokens: int | None = None
