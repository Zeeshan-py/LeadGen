from __future__ import annotations

from typing import Any

import httplib2
import google_auth_httplib2
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from .models import PlaceLead

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

COLUMNS = [
    "dedupe_key",
    "business_name",
    "lead_segment",
    "owner_or_contact",
    "email",
    "phone",
    "website",
    "google_maps_url",
    "coverage_market",
    "search_query",
    "pages_scraped",
    "enrichment_status",
    "facebook",
    "instagram",
    "linkedin",
    "youtube",
    "x_twitter",
    "tiktok",
    "whatsapp",
]


class SheetsLeadStore:
    def __init__(
        self,
        spreadsheet_id: str = "",
        sheet_name: str = "",
        credentials: Credentials | None = None,
        service_account_info: dict[str, Any] | None = None,
    ) -> None:
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        if credentials is not None:
            creds = credentials
        elif service_account_info is not None:
            creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        else:
            raise ValueError("Google Sheets credentials were not provided.")
        authorized_http = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http(timeout=60))
        self._service = build("sheets", "v4", http=authorized_http, cache_discovery=False)
        self._rows_cache: list[list[str]] | None = None
        self._ensure_tab_exists()

    def existing_dedupe_keys(self) -> set[str]:
        rows = self._rows()
        if len(rows) < 2:
            return set()
        try:
            idx = COLUMNS.index("dedupe_key")
            return {row[idx] for row in rows[1:] if len(row) > idx and row[idx]}
        except (ValueError, IndexError):
            return set()

    def upsert_leads(self, leads: list[PlaceLead]) -> None:
        if not leads:
            return
        rows = self._ensure_header(self._rows())
        existing_keys: dict[str, int] = {}
        if len(rows) > 1:
            try:
                idx = COLUMNS.index("dedupe_key")
                for i, row in enumerate(rows[1:], start=2):
                    if len(row) > idx and row[idx]:
                        existing_keys[row[idx]] = i
            except (ValueError, IndexError):
                pass

        updates: list[dict[str, Any]] = []
        appends: list[list[str]] = []

        for lead in leads:
            key = lead.dedupe_key()
            row_data = _lead_to_row(lead)
            if key in existing_keys:
                row_num = existing_keys[key]
                range_str = f"'{self.sheet_name}'!A{row_num}:{_col_letter(len(COLUMNS))}{row_num}"
                updates.append({"range": range_str, "values": [row_data]})
            else:
                appends.append(row_data)

        if updates:
            self._service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"valueInputOption": "USER_ENTERED", "data": updates},
            ).execute()

        if appends:
            self._service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"'{self.sheet_name}'!A1",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": appends},
            ).execute()
        self._rows_cache = None

    def replace_leads(self, leads: list[PlaceLead]) -> None:
        self._clear_sheet()
        self._ensure_header([])
        if leads:
            self._service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"'{self.sheet_name}'!A1",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [_lead_to_row(l) for l in leads]},
            ).execute()
        self._rows_cache = None

    def _ensure_header(self, rows: list[list[str]]) -> list[list[str]]:
        if not rows or rows[0] != COLUMNS:
            self._service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"'{self.sheet_name}'!A1",
                valueInputOption="USER_ENTERED",
                body={"values": [COLUMNS]},
            ).execute()
            rows = [COLUMNS, *rows[1:]] if rows else [COLUMNS]
            self._rows_cache = rows
        return rows

    def _ensure_tab_exists(self) -> None:
        meta = self._service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
        if self.sheet_name not in existing:
            self._service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": self.sheet_name}}}]},
            ).execute()

    def _clear_sheet(self) -> None:
        self._service.spreadsheets().values().clear(
            spreadsheetId=self.spreadsheet_id,
            range=f"'{self.sheet_name}'",
            body={},
        ).execute()
        self._rows_cache = []

    def _read_all_rows(self) -> list[list[str]]:
        result = self._service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"'{self.sheet_name}'",
        ).execute()
        return result.get("values", [])

    def _rows(self) -> list[list[str]]:
        if self._rows_cache is None:
            self._rows_cache = self._read_all_rows()
        return self._rows_cache


def _lead_to_row(lead: PlaceLead) -> list[str]:
    return [
        lead.dedupe_key(),
        lead.business_name,
        lead.lead_segment,
        lead.owner_or_contact,
        lead.primary_email(),
        lead.primary_phone(),
        lead.website,
        lead.google_maps_url,
        lead.coverage_market,
        lead.search_query,
        str(lead.pages_scraped),
        lead.enrichment_status,
        lead.social_links.get("facebook", ""),
        lead.social_links.get("instagram", ""),
        lead.social_links.get("linkedin", ""),
        lead.social_links.get("youtube", ""),
        lead.social_links.get("x_twitter", ""),
        lead.social_links.get("tiktok", ""),
        lead.social_links.get("whatsapp", ""),
    ]


def _col_letter(n: int) -> str:
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result
