"""Loads configuration from the .env file.

This is the single place credentials are read. Every other script imports
from here so the App Key / Secret never get hard-coded anywhere.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Read the .env file (if present) into environment variables.
load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_key: str
    app_secret: str
    callback_url: str
    token_path: str


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name!r}. "
            "Copy .env.example to .env and fill in your Schwab credentials."
        )
    return value


def load_settings() -> Settings:
    """Build a Settings object from environment variables."""
    return Settings(
        app_key=_require("SCHWAB_APP_KEY"),
        app_secret=_require("SCHWAB_APP_SECRET"),
        callback_url=_require("SCHWAB_CALLBACK_URL"),
        token_path=os.getenv("SCHWAB_TOKEN_PATH", "token.json"),
    )
