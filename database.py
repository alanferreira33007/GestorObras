import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

OBRAS_COLS = ["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"]
FIN_COLS   = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]

def ensure_cols(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]

@st.cache_resource
def obter_db():
    creds_json = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope))
    return client.open("GestorObras_DB")

@st.cache_data(ttl=10)
def carregar_dados():
    try:
        db = obter_db()
        # Carrega Obras
        ws_o = db.worksheet("Obras")
        df_o = pd.DataFrame(ws_o.get_all_records())
        df_o = ensure_cols(df_o, OBRAS_COLS)
        df_o["ID"] = pd.to_numeric(df_o["ID"], errors="coerce")
        df_o["Valor Total"] = pd.to_numeric(df_o["Valor Total"], errors="coerce").fillna(0)

        # Carrega Financeiro
        ws_f = db.worksheet("Financeiro")
        df_f = pd.DataFrame(ws_f.get_all_records())
        df_f = ensure_cols(df_f, FIN_COLS)
        df_f["Valor"] = pd.to_numeric(df_f["Valor"], errors="coerce").fillna(0)
        df_f["Data_DT"] = pd.to_datetime(df_f["Data"], errors="coerce")
        df_f["Data_BR"] = df_f["Data_DT"].dt.strftime("%d/%m/%Y")
        
        return df_o, df_f
    except Exception as e:
        st.error(f"Erro de Conexão: {e}")
        return pd.DataFrame(columns=OBRAS_COLS), pd.DataFrame(columns=FIN_COLS)
