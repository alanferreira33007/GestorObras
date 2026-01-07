import json
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from core.constants import FIN_HEADERS, OBRAS_HEADERS, ORC_HEADERS


def obter_conector():
    creds_json = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope))


def get_db():
    client = obter_conector()
    return client.open("GestorObras_DB")


def ensure_worksheet(db, title: str, rows=1000, cols=20):
    try:
        return db.worksheet(title)
    except Exception:
        return db.add_worksheet(title=title, rows=str(rows), cols=str(cols))


def ensure_headers(ws, required_headers: list[str]):
    # garante que a primeira linha tenha todos os headers necessários
    row1 = ws.row_values(1)
    if not row1:
        ws.update("A1", [required_headers])
        return

    current = row1
    changed = False
    for h in required_headers:
        if h not in current:
            current.append(h)
            changed = True
    if changed:
        ws.update("A1", [current])


def ensure_schema():
    db = get_db()
    ws_fin = ensure_worksheet(db, "Financeiro", rows=3000, cols=30)
    ws_obr = ensure_worksheet(db, "Obras", rows=1000, cols=20)
    ws_orc = ensure_worksheet(db, "Orcamento", rows=1000, cols=10)

    ensure_headers(ws_fin, FIN_HEADERS)
    ensure_headers(ws_obr, OBRAS_HEADERS)
    ensure_headers(ws_orc, ORC_HEADERS)

    return db
