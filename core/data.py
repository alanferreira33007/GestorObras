from __future__ import annotations
import pandas as pd
import streamlit as st
from core.sheets import open_db, ensure_schema

@st.cache_data(ttl=10)
def carregar_dados():
    ensure_schema()
    db = open_db()

    # Obras
    ws_o = db.worksheet("Obras")
    df_obras = pd.DataFrame(ws_o.get_all_records())
    if not df_obras.empty:
        if "Valor Total" in df_obras.columns:
            df_obras["Valor Total"] = pd.to_numeric(df_obras["Valor Total"], errors="coerce").fillna(0)

    # Financeiro
    ws_f = db.worksheet("Financeiro")
    df_fin = pd.DataFrame(ws_f.get_all_records())
    if df_fin.empty:
        df_fin = pd.DataFrame(columns=["Data","Tipo","Categoria","Descrição","Valor","Obra Vinculada","Anexo"])

    # tipos
    if "Valor" in df_fin.columns:
        df_fin["Valor"] = pd.to_numeric(df_fin["Valor"], errors="coerce").fillna(0)

    if "Data" in df_fin.columns:
        df_fin["Data_DT"] = pd.to_datetime(df_fin["Data"], errors="coerce")
        df_fin["Data_BR"] = df_fin["Data_DT"].dt.strftime("%d/%m/%Y")

    # garante coluna Anexo
    if "Anexo" not in df_fin.columns:
        df_fin["Anexo"] = ""

    return df_obras, df_fin
