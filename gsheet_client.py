from typing import Any, Dict, List, Optional
import json
import logging
import streamlit as st
import datetime
import decimal

import gspread
from google.oauth2.service_account import Credentials

# -------------------------------------------------
# Logger
# -------------------------------------------------
logger = logging.getLogger("gsheet_client")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# -------------------------------------------------
# Google Sheet setup
# -------------------------------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_NAME = "MS Form Temp Table"      # Google Sheet file name
WORKSHEET_NAME = "Sheet1"        # Tab name


# @st.cache_resource
def get_worksheet():
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)

    sheet = client.open(SHEET_NAME)
    ws = sheet.worksheet(WORKSHEET_NAME)
    return ws

def _get_all_rows(ws):
    rows = ws.get_all_values()
    if len(rows) < 2:
        return []

    header = [h.strip() for h in rows[0]]
    data_rows = rows[1:]

    return [dict(zip(header, r)) for r in data_rows]

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def make_json_safe(obj):
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_safe(v) for v in obj]
    elif isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    elif isinstance(obj, decimal.Decimal):
        return float(obj)
    return obj


def _now():
    return datetime.datetime.utcnow().isoformat()


def _find_row(ws, activity_id: str) -> Optional[int]:
    records = _get_all_rows(ws)
    for idx, row in enumerate(records, start=2):
        if row.get("activity_id") == activity_id:
            return idx
    return None


# -------------------------------------------------
# CORE FUNCTIONS (same names as before)
# -------------------------------------------------
def upsert_activity(activity_id: str, user_id: str, payload: Dict[str, Any], status: str = "draft"):
    try:
        ws = get_worksheet()

        clean_payload = make_json_safe(payload)
        json_data = json.dumps(clean_payload, ensure_ascii=False)

        row_idx = _find_row(ws, activity_id)

        row_data = [
            activity_id,
            user_id,
            status,
            json_data,
            _now(),
        ]

        if row_idx:
            ws.update(f"A{row_idx}:E{row_idx}", [row_data])
        else:
            ws.append_row(row_data)

        return True, {
            "activity_id": activity_id,
            "user_id": user_id,
            "status": status,
            "data": clean_payload,
        }

    except Exception as e:
        logger.exception("upsert_activity failed")
        return False, None


def get_activity(activity_id: str) -> Optional[Dict]:
    try:
        ws = get_worksheet()
        records = _get_all_rows(ws)

        for row in records:
            if row["activity_id"] == activity_id:
                row["data"] = json.loads(row["data"]) if row.get("data") else {}
                return row

        return None

    except Exception:
        logger.exception("get_activity failed")
        return None


def list_all_activities():
    ws = get_worksheet()
    rows = ws.get_all_values()

    if not rows:
        return []

    header = rows[0]
    data_rows = rows[1:]

    out = []
    for r in data_rows:
        row = dict(zip(header, r))

        try:
            row["data"] = json.loads(row["data"]) if row.get("data") else {}
        except json.JSONDecodeError:
            logger.error(
                f"Invalid JSON in activity_id={row.get('activity_id')}"
            )
            row["data"] = {}  # or continue to skip

        out.append(row)

    return out


def list_activities_for_user(user_id: str, status: Optional[str] = None, limit: int = 200):
    ws = get_worksheet()
    records = _get_all_rows(ws)

    out = []
    for r in records:
        if r["user_id"] != user_id:
            continue
        if status and r["status"] != status:
            continue

        try:
            r["data"] = json.loads(r["data"]) if r.get("data") else {}
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in row activity_id={r.get('activity_id')}")
            r["data"] = {}  # or skip row

        out.append(r)

    return out[:limit]


def list_submitted_activities(limit: int = 500):
    ws = get_worksheet()
    records = _get_all_rows(ws)

    out = []
    for r in records:
        if r["status"] != "submitted":
            continue

        try:
            r["data"] = json.loads(r["data"]) if r.get("data") else {}
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in row activity_id={r.get('activity_id')}")
            r["data"] = {}

        out.append(r)

    return out[:limit]


def mark_status(activity_id: str, status: str, verifier: Optional[str] = None, comment: Optional[str] = None) -> bool:
    try:
        ws = get_worksheet()
        row_idx = _find_row(ws, activity_id)
        if not row_idx:
            return False

        ws.update(f"C{row_idx}", status)
        ws.update(f"E{row_idx}", _now())
        return True

    except Exception:
        logger.exception("mark_status failed")
        return False


def delete_activity(activity_id: str) -> bool:
    try:
        ws = get_worksheet()
        row_idx = _find_row(ws, activity_id)
        if not row_idx:
            return False

        ws.delete_rows(row_idx)
        return True

    except Exception:
        logger.exception("delete_activity failed")
        return False


# -------------------------------------------------
# Convenience helpers (unchanged)
# -------------------------------------------------
def submit_activity(activity_id: str, user_id: str) -> bool:
    return mark_status(activity_id, "submitted")


def mark_verified(activity_id: str, verifier: str, comment: Optional[str] = None) -> bool:
    return mark_status(activity_id, "verified")

