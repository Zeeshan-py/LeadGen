"""Runtime configuration for the LeadForge backend.

Settings are loaded from environment variables and optional .env files. This
module owns deployment defaults and validation for integrations, database
connectivity, frontend origins, authentication, and AI/provider credentials.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
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
    public_backend_url: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("PUBLIC_URL", "PUBLIC_BACKEND_URL"),
    )
    jwt_secret_key: str = Field(default="", validation_alias=AliasChoices("JWT_SECRET_KEY", "SESSION_SECRET"))
    jwt_issuer: str = Field(default="leadforge", validation_alias="JWT_ISSUER")
    access_token_minutes: int = Field(default=15, validation_alias="ACCESS_TOKEN_MINUTES")
    refresh_token_days: int = Field(default=30, validation_alias="REFRESH_TOKEN_DAYS")
    session_refresh_token_days: int = Field(default=1, validation_alias="SESSION_REFRESH_TOKEN_DAYS")
    password_reset_token_minutes: int = Field(default=30, validation_alias="PASSWORD_RESET_TOKEN_MINUTES")
    auth_cookie_secure: bool | None = Field(default=None, validation_alias="AUTH_COOKIE_SECURE")
    auth_cookie_domain: str = Field(default="", validation_alias="AUTH_COOKIE_DOMAIN")
    admin_email: str = Field(default="", validation_alias="ADMIN_EMAIL")
    admin_password: str = Field(default="", validation_alias="ADMIN_PASSWORD")
    google_oauth_client_id: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_CLIENT_ID"),
    )
    google_oauth_client_secret: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_CLIENT_SECRET"),
    )
    google_oauth_redirect_uri: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_OAUTH_REDIRECT_URI", "GOOGLE_REDIRECT_URI"),
    )
    github_oauth_client_id: str = Field(default="", validation_alias="GITHUB_OAUTH_CLIENT_ID")
    github_oauth_client_secret: str = Field(default="", validation_alias="GITHUB_OAUTH_CLIENT_SECRET")
    github_oauth_redirect_uri: str = Field(default="", validation_alias="GITHUB_OAUTH_REDIRECT_URI")
    database_pool_size: int = Field(default=5, validation_alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, validation_alias="DATABASE_MAX_OVERFLOW")
    frontend_static_dir: Path = Field(default=Path("./frontend"), validation_alias="FRONTEND_STATIC_DIR")

    apify_api_token: str = Field(default="", validation_alias="APIFY_API_TOKEN")
    apify_actor_id: str = Field(default="compass/crawler-google-places", validation_alias="APIFY_ACTOR_ID")
    apify_web_actor_id: str = Field(default="apify/website-content-crawler", validation_alias="APIFY_WEB_ACTOR_ID")

    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", validation_alias="GEMINI_MODEL")
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")

    google_sheets_spreadsheet_id: str = Field(default="", validation_alias="GOOGLE_SHEETS_SPREADSHEET_ID")
    google_sheets_sheet_name: str = Field(default="LeadForgeLeads", validation_alias="GOOGLE_SHEETS_SHEET_NAME")
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

    @field_validator("frontend_origin")
    @classmethod
    def normalize_frontend_origin(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("admin_email")
    @classmethod
    def normalize_admin_email(cls, value: str) -> str:
        return value.strip().lower()

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

    def validate_production(self) -> None:
        if self.environment.lower() != "production":
            return
        missing = [
            name
            for name, value in {
                "JWT_SECRET_KEY": self.jwt_secret_key,
                "ADMIN_EMAIL": self.admin_email,
                "ADMIN_PASSWORD": self.admin_password,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Production configuration is incomplete: " + ", ".join(missing)
            )

    @property
    def secure_auth_cookies(self) -> bool:
        if self.auth_cookie_secure is not None:
            return self.auth_cookie_secure
        return self.environment.lower() == "production"

    def oauth_redirect_uri(self, provider: str) -> str:
        if provider == "google" and self.google_oauth_redirect_uri:
            return self.google_oauth_redirect_uri
        if provider == "github" and self.github_oauth_redirect_uri:
            return self.github_oauth_redirect_uri
        return f"{self.public_backend_url.rstrip('/')}/auth/{provider}/callback"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
