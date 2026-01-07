from __future__ import annotations
import json
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def _load_sa_info():
    """
    Aceita json_content tanto como dict (ideal) quanto como string (quando veio de """...""")
    """
    info = st.secrets["gcp_service_account"]["json_content"]
    if isinstance(info, str):
        info = json.loads(info)
    return info

def get_gspread_client():
    info = _load_sa_info()
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)

def open_db():
    client = get_gspread_client()
    return client.open("GestorObras_DB")

def ensure_financeiro_schema():
    db = open_db()
    ws = db.worksheet("Financeiro")

    header = ws.row_values(1)
    desired = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada", "Anexo"]

    if not header:
        ws.update("A1:G1", [desired])
        return

    missing = [c for c in desired if c not in header]
    if missing:
        new_header = header + missing
        last_col_letter = chr(64 + len(new_header))
        ws.update(f"A1:{last_col_letter}1", [new_header])

def ensure_obras_schema():
    db = open_db()
    ws = db.worksheet("Obras")

    header = ws.row_values(1)
    desired = ["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"]

    if not header:
        ws.update("A1:G1", [desired])
        return

    missing = [c for c in desired if c not in header]
    if missing:
        new_header = header + missing
        last_col_letter = chr(64 + len(new_header))
        ws.update(f"A1:{last_col_letter}1", [new_header])

def ensure_schema():
    ensure_obras_schema()
    ensure_financeiro_schema()
