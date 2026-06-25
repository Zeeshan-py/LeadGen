from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "LeadForge AI"
    environment: str = "development"
    database_url: str = Field(
        default="postgresql+psycopg://leadforge:leadforge@localhost:5432/leadforge",
        validation_alias="DATABASE_URL",
    )
    frontend_origin: str = Field(default="http://localhost:3000", validation_alias="FRONTEND_ORIGIN")
    public_backend_url: str = Field(default="http://localhost:8000", validation_alias="PUBLIC_BACKEND_URL")

    apify_api_token: str = Field(default="", validation_alias="APIFY_API_TOKEN")
    apify_actor_id: str = Field(default="compass/crawler-google-places", validation_alias="APIFY_ACTOR_ID")
    apify_web_actor_id: str = Field(default="apify/website-content-crawler", validation_alias="APIFY_WEB_ACTOR_ID")

    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", validation_alias="GEMINI_MODEL")
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")

    google_sheets_spreadsheet_id: str = Field(default="", validation_alias="GOOGLE_SHEETS_SPREADSHEET_ID")
    google_sheets_sheet_name: str = Field(default="LeadForgeLeads", validation_alias="GOOGLE_SHEETS_SHEET_NAME")
    google_service_account_file: Path = Field(
        default=Path("./service-account.json"),
        validation_alias="GOOGLE_SERVICE_ACCOUNT_FILE",
    )
    google_service_account_json: str = Field(default="", validation_alias="GOOGLE_SERVICE_ACCOUNT_JSON")

    gmail_client_id: str = Field(default="", validation_alias="GMAIL_CLIENT_ID")
    gmail_client_secret: str = Field(default="", validation_alias="GMAIL_CLIENT_SECRET")
    gmail_refresh_token: str = Field(default="", validation_alias="GMAIL_REFRESH_TOKEN")
    gmail_sender_email: str = Field(default="", validation_alias="GMAIL_SENDER_EMAIL")
    gmail_reply_sync_interval_seconds: int = Field(default=60, validation_alias="GMAIL_REPLY_SYNC_INTERVAL_SECONDS")
    auto_reply_enabled: bool = Field(default=True, validation_alias="AUTO_REPLY_ENABLED")
    auto_reply_body: str = Field(
        default=(
            "Hi,\n\n"
            "Thanks for getting back to me. I received your reply and will close this outreach on my side.\n\n"
            "Best,"
        ),
        validation_alias="AUTO_REPLY_BODY",
    )

    fetch_timeout_seconds: int = Field(default=20, validation_alias="LEAD_FETCH_TIMEOUT_SECONDS")
    max_website_pages: int = Field(default=5, validation_alias="LEAD_MAX_WEBSITE_PAGES")
    enable_contact_discovery: bool = Field(default=True, validation_alias="ENABLE_CONTACT_DISCOVERY")
    contact_discovery_results: int = Field(default=8, validation_alias="CONTACT_DISCOVERY_RESULTS")
    default_lead_limit: int = Field(default=50, validation_alias="DEFAULT_LEAD_LIMIT")
    enable_screenshot_capture: bool = Field(default=True, validation_alias="ENABLE_SCREENSHOT_CAPTURE")
    screenshots_dir: Path = Field(default=Path("./storage/screenshots"), validation_alias="SCREENSHOTS_DIR")

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://") and "+psycopg" not in value:
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value

    def require_generation_credentials(self) -> None:
        missing = [
            name
            for name, value in {
                "APIFY_API_TOKEN": self.apify_api_token,
            }.items()
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Missing required lead generation environment variables: {joined}")

    def require_gmail_credentials(self) -> None:
        missing = [
            name
            for name, value in {
                "GMAIL_CLIENT_ID": self.gmail_client_id,
                "GMAIL_CLIENT_SECRET": self.gmail_client_secret,
                "GMAIL_REFRESH_TOKEN": self.gmail_refresh_token,
            }.items()
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Missing required Gmail environment variables: {joined}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
