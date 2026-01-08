# db.py
import streamlit as st
import gspread
import json
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from utils import ensure_cols

OBRAS_COLS = ["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"]
FIN_COLS = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]


@st.cache_resource
def obter_db():
    creds = json.loads(st.secrets["gcp_service_account"]["json_content"])
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds, scope))
    return client.open("GestorObras_DB")


@st.cache_data(ttl=10)
def carregar_dados():
    db = obter_db()

    ws_o = db.worksheet("Obras")
    df_o = pd.DataFrame(ws_o.get_all_records())
    df_o = ensure_cols(df_o, OBRAS_COLS)
    df_o["Valor Total"] = pd.to_numeric(df_o["Valor Total"], errors="coerce").fillna(0)

    ws_f = db.worksheet("Financeiro")
    df_f = pd.DataFrame(ws_f.get_all_records())
    df_f = ensure_cols(df_f, FIN_COLS)
    df_f["Valor"] = pd.to_numeric(df_f["Valor"], errors="coerce").fillna(0)
    df_f["Data_DT"] = pd.to_datetime(df_f["Data"], errors="coerce")

    return df_o, df_f
