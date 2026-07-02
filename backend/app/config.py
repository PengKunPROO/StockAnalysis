from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./stock.db"
    log_level: str = "INFO"
    diagnosis_llm_provider: str = "deepseek"
    diagnosis_llm_model: str = "deepseek-v4-pro"
    diagnosis_llm_api_key: str = ""
    diagnosis_llm_base_url: str = "https://api.deepseek.com/v1"
    diagnosis_max_tool_rounds: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
