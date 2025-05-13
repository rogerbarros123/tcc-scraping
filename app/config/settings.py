import os
from pathlib import Path
from pydantic import HttpUrl, Field
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
  """Configuration settings for the application."""
  # Base URLs
  # Logging configuration
  LOG_LEVEL: Optional[str] = Field(default="WARNING")
  MILVUS_URL: str
  MISTRAL_API_KEY: str
  OPENAI_API_KEY: str
  class Config:
      env_file = Path(__file__).resolve().parent.parent.parent / ".env"
      env_file_encoding = 'utf-8'
      case_sensitive = True

# Create a settings instance
settings = Settings()