from pydantic_settings import BaseSettings, SettingsConfigDict

from pydantic_settings import BaseSettings, SettingsConfigDict

from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "APIForge AI"
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///./apiforge.db"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        import os
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            self.SQLALCHEMY_DATABASE_URI = db_url
            
    REDIS_URL: str = ""

    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    GROQ_API_KEY_1: Optional[str] = None
    GROQ_API_KEY_2: Optional[str] = None
    E2B_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore")

settings = Settings()
