from __future__ import annotations
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_gspread_client():
    info = st.secrets["gcp_service_account"]["json_content"]
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)

def open_db():
    client = get_gspread_client()
    return client.open("GestorObras_DB")

def ensure_financeiro_schema():
    """
    Garante que a aba Financeiro tem as colunas:
    Data | Tipo | Categoria | Descrição | Valor | Obra Vinculada | Anexo
    """
    db = open_db()
    ws = db.worksheet("Financeiro")

    header = ws.row_values(1)
    desired = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada", "Anexo"]

    if not header:
        ws.update("A1:G1", [desired])
        return

    # adiciona colunas faltantes ao final
    missing = [c for c in desired if c not in header]
    if missing:
        new_header = header + missing
        ws.update(f"A1:{chr(64+len(new_header))}1", [new_header])

def ensure_obras_schema():
    """
    Garante a aba Obras com colunas básicas.
    """
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
        ws.update(f"A1:{chr(64+len(new_header))}1", [new_header])

def ensure_schema():
    ensure_obras_schema()
    ensure_financeiro_schema()
