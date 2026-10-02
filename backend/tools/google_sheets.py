"""
Google Sheets integration — secure live data access.
Credentials never reach the LLM.
"""
from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict, List, Optional

import structlog
from config import settings

logger = structlog.get_logger(__name__)


def _get_credentials():
    """Load Google credentials from env — never hard-coded."""
    if settings.GOOGLE_SERVICE_ACCOUNT_JSON_B64:
        json_str = base64.b64decode(settings.GOOGLE_SERVICE_ACCOUNT_JSON_B64).decode()
        return json.loads(json_str)
    elif settings.GOOGLE_SERVICE_ACCOUNT_FILE and os.path.exists(settings.GOOGLE_SERVICE_ACCOUNT_FILE):
        with open(settings.GOOGLE_SERVICE_ACCOUNT_FILE) as f:
            return json.load(f)
    else:
        raise ValueError("Google service account credentials not configured.")


class GoogleSheetsClient:
    """
    Secure Google Sheets connector.
    Always fetches LIVE data — does not cache stale spreadsheet state.
    """

    def _get_client(self):
        from google.oauth2.service_account import Credentials
        import gspread

        creds_dict = _get_credentials()
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly",
            ],
        )
        return gspread.authorize(creds)

    def get_sheet_as_records(
        self,
        sheet_id: str,
        worksheet_index: int = 0,
    ) -> List[Dict[str, Any]]:
        """Fetch all rows as list of dicts (header row = keys)."""
        if not settings.GOOGLE_SHEETS_ENABLED:
            raise ValueError("Google Sheets integration is not enabled.")

        gc = self._get_client()
        spreadsheet = gc.open_by_key(sheet_id)
        worksheet = spreadsheet.get_worksheet(worksheet_index)
        records = worksheet.get_all_records()
        logger.info("sheets.fetched", sheet_id=sheet_id, rows=len(records))
        return records

    def get_sheet_as_dataframe(self, sheet_id: str, worksheet_index: int = 0):
        import pandas as pd
        records = self.get_sheet_as_records(sheet_id, worksheet_index)
        return pd.DataFrame(records)


# Singleton
gsheets_client = GoogleSheetsClient()
