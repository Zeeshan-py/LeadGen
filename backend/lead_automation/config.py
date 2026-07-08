"""Configuration model for lead automation providers and limits."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    apify_api_token: str
    apify_actor_id: str
    spreadsheet_id: str
    sheet_name: str
    service_account_json: str
    coverage_file: Path
    anthropic_api_key: str
    fetch_timeout_seconds: int
    max_website_pages: int


def load_settings() -> Settings:
    return Settings(
        apify_api_token=require_env("APIFY_API_TOKEN"),
        apify_actor_id=os.environ.get("APIFY_ACTOR_ID", "compass/crawler-google-places"),
        spreadsheet_id=require_env("GOOGLE_SHEETS_SPREADSHEET_ID"),
        sheet_name=os.environ.get("GOOGLE_SHEETS_SHEET_NAME", "MossLeads"),
        service_account_json=os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", ""),
        coverage_file=Path(
            os.environ.get("LEAD_COVERAGE_FILE", "./coverage/canada_moss_coverage.json")
        ),
        anthropic_api_key=require_env("ANTHROPIC_API_KEY"),
        fetch_timeout_seconds=int(os.environ.get("LEAD_FETCH_TIMEOUT_SECONDS", "20")),
        max_website_pages=int(os.environ.get("LEAD_MAX_WEBSITE_PAGES", "5")),
    )


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value
    raise ValueError(f"Missing required environment variable: {name}")
