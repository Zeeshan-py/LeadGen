"""Google Sheets credential validation and spreadsheet access helpers."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import google_auth_httplib2
import httplib2
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from lead_automation.sheets import SCOPES, SheetsLeadStore

from .config import Settings


GOOGLE_CREDENTIALS_MISSING_MESSAGE = (
    "Google Sheets is disabled because GOOGLE_SERVICE_ACCOUNT_JSON is missing. "
    "Set it to the complete service account JSON object to enable Google Sheets."
)


@dataclass
class GoogleSheetsValidation:
    status: str
    google_sheets: bool
    spreadsheet_access: bool
    code: str = ""
    message: str = ""
    credentials_source: str = ""
    spreadsheet_id_configured: bool = False
    service_account_email: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GoogleSheetsConfigError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_google_sheets(settings: Settings) -> dict[str, Any]:
    logger = _google_logger()
    result = _validate_google_sheets(settings, logger)
    logger.info("Google Sheets validation result: %s", result.to_dict())
    return result.to_dict()


def build_sheets_store(settings: Settings) -> SheetsLeadStore:
    credentials, source, _info = load_google_credentials(settings)
    _google_logger().info("Creating SheetsLeadStore using credentials source: %s", source)
    return SheetsLeadStore(
        spreadsheet_id=settings.google_sheets_spreadsheet_id,
        sheet_name=settings.google_sheets_sheet_name,
        credentials=credentials,
    )


def load_google_credentials(settings: Settings) -> tuple[Credentials, str, dict[str, Any]]:
    raw_credentials = settings.google_service_account_json.strip()
    if not raw_credentials:
        raise GoogleSheetsConfigError("missing_credentials", GOOGLE_CREDENTIALS_MISSING_MESSAGE)

    try:
        info = json.loads(raw_credentials)
    except json.JSONDecodeError as exc:
        raise GoogleSheetsConfigError(
            "invalid_json",
            "GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON. Paste the complete service account JSON object.",
        ) from exc
    if not isinstance(info, dict):
        raise GoogleSheetsConfigError(
            "invalid_json",
            "GOOGLE_SERVICE_ACCOUNT_JSON must contain a JSON object.",
        )

    try:
        credentials = Credentials.from_service_account_info(info, scopes=SCOPES)
    except (TypeError, ValueError) as exc:
        raise GoogleSheetsConfigError(
            "invalid_credentials",
            "GOOGLE_SERVICE_ACCOUNT_JSON could not be used as a Google service account credential.",
        ) from exc
    return credentials, "GOOGLE_SERVICE_ACCOUNT_JSON", info


def _validate_google_sheets(settings: Settings, logger: logging.Logger) -> GoogleSheetsValidation:
    if not settings.google_service_account_json.strip():
        logger.warning(
            "Google Sheets configuration error [missing_credentials]: %s",
            GOOGLE_CREDENTIALS_MISSING_MESSAGE,
        )
        return GoogleSheetsValidation(
            status="error",
            google_sheets=False,
            spreadsheet_access=False,
            code="missing_credentials",
            message=GOOGLE_CREDENTIALS_MISSING_MESSAGE,
            spreadsheet_id_configured=bool(
                settings.google_sheets_spreadsheet_id.strip()
            ),
        )

    if not settings.google_sheets_spreadsheet_id.strip():
        return GoogleSheetsValidation(
            status="error",
            google_sheets=False,
            spreadsheet_access=False,
            code="missing_spreadsheet_id",
            message="Google Sheets spreadsheet ID is missing. Set GOOGLE_SHEETS_SPREADSHEET_ID.",
            spreadsheet_id_configured=False,
        )

    try:
        credentials, source, info = load_google_credentials(settings)
        service = _build_service(credentials)
        service.spreadsheets().get(spreadsheetId=settings.google_sheets_spreadsheet_id).execute()
        return GoogleSheetsValidation(
            status="ok",
            google_sheets=True,
            spreadsheet_access=True,
            credentials_source=source,
            spreadsheet_id_configured=True,
            service_account_email=info.get("client_email", ""),
        )
    except GoogleSheetsConfigError as exc:
        logger.warning("Google Sheets configuration error [%s]: %s", exc.code, exc.message)
        return GoogleSheetsValidation(
            status="error",
            google_sheets=False,
            spreadsheet_access=False,
            code=exc.code,
            message=exc.message,
            spreadsheet_id_configured=True,
        )
    except HttpError as exc:
        code, message = _classify_http_error(exc)
        logger.exception("Google Sheets API error [%s]", code)
        return GoogleSheetsValidation(
            status="error",
            google_sheets=True,
            spreadsheet_access=False,
            code=code,
            message=message,
            spreadsheet_id_configured=True,
        )
    except Exception as exc:
        logger.exception("Unexpected Google Sheets validation error")
        return GoogleSheetsValidation(
            status="error",
            google_sheets=False,
            spreadsheet_access=False,
            code="validation_failed",
            message=f"Google Sheets validation failed: {exc}",
            spreadsheet_id_configured=True,
        )


def _build_service(credentials: Credentials):
    authorized_http = google_auth_httplib2.AuthorizedHttp(credentials, http=httplib2.Http(timeout=30))
    return build("sheets", "v4", http=authorized_http, cache_discovery=False)


def _classify_http_error(exc: HttpError) -> tuple[str, str]:
    status = getattr(exc.resp, "status", None)
    content = exc.content.decode("utf-8", errors="replace") if isinstance(exc.content, bytes) else str(exc.content)
    lowered = content.lower()
    if status == 403 and ("disabled" in lowered or "has not been used" in lowered):
        return (
            "api_disabled",
            "Google Sheets API appears to be disabled for this Google Cloud project. Enable the Google Sheets API.",
        )
    if status in {401, 403}:
        return (
            "no_spreadsheet_access",
            "No spreadsheet access. Share the spreadsheet with the service account email as an editor.",
        )
    if status == 404:
        return (
            "spreadsheet_not_found",
            "Spreadsheet was not found. Check GOOGLE_SHEETS_SPREADSHEET_ID and sharing permissions.",
        )
    return ("google_api_error", f"Google Sheets API returned HTTP {status}: {content}")


def _google_logger() -> logging.Logger:
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("leadforge.google")
    logger.setLevel(logging.INFO)
    log_path = str(logs_dir / "google.log")
    if not any(isinstance(handler, logging.FileHandler) and handler.baseFilename == str((logs_dir / "google.log").resolve()) for handler in logger.handlers):
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger
