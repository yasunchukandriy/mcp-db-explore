"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings loaded from environment variables with MCP_ prefix."""

    model_config = {"env_prefix": "MCP_"}

    database_url: str = "postgresql://postgres:postgres@localhost:5432/explorer"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    query_timeout_seconds: int = 10
    max_rows: int = 100
    pool_min_size: int = 2
    pool_max_size: int = 10


settings = Settings()
