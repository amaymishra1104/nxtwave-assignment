"""Configuration module for Lesson Agent.

Loads environment variables, model specifications, temperatures, and paths.
Configurable via .env file or direct environment variables.
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable fallbacks."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    gemini_api_key: Optional[str] = None

    # Model Configuration (loaded from .env; no hardcoded static models)
    generator_model: str = "gemini-2.5-flash"
    judge_model: str = "gemini-2.5-pro"

    # Temperatures
    generator_temperature: float = 0.7
    judge_temperature: float = 0.2

    # Agent Loop Parameters
    max_retries: int = 2
    active_rules_limit: int = 5

    # Storage & File Paths
    database_path: Path = Path("data/memory.db")
    rubric_v1_path: Path = Path("data/rubric_v1.json")
    rubric_v2_proposed_path: Path = Path("data/rubric_v2_proposed.json")
    fact_pack_path: Path = Path("data/fact_pack.json")
    glossary_path: Path = Path("data/glossary.json")
    output_dir: Path = Path("outputs")


# Global singleton instance
settings = Settings()

