from __future__ import annotations

import pandas as pd
import streamlit as st

from core.sheets import open_db, ensure_schema


def _ensure_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Garante que o DataFrame tenha as colunas esperadas."""
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols]


@st.cache_data(ttl=10)
def carregar_dados():
    """
    Retorna:
      df_obras: planilha Obras
      df_fin:   planilha Financeiro (com Data_DT e Data_BR)
    """
    # garante header e colunas mínimas no Sheets
    ensure_schema()

    db = open_db()

    # ---------------- Obras ----------------
    obras_cols = ["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"]
    try:
        ws_o = db.worksheet("Obras")
        records_o = ws_o.get_all_records()
        df_obras = pd.DataFrame(records_o)
    except Exception:
        df_obras = pd.DataFrame(columns=obras_cols)

    df_obras = _ensure_cols(df_obras, obras_cols)

    # normalizações
    df_obras["Valor Total"] = pd.to_numeric(df_obras["Valor Total"], errors="coerce").fillna(0)

    # ---------------- Financeiro ----------------
    fin_cols = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada", "Anexo"]
    try:
        ws_f = db.worksheet("Financeiro")
        records_f = ws_f.get_all_records()
        df_fin = pd.DataFrame(records_f)
    except Exception:
        df_fin = pd.DataFrame(columns=fin_cols)

    df_fin = _ensure_cols(df_fin, fin_cols)

    # normalizações
    df_fin["Valor"] = pd.to_numeric(df_fin["Valor"], errors="coerce").fillna(0)
    df_fin["Data_DT"] = pd.to_datetime(df_fin["Data"], errors="coerce")
    df_fin["Data_BR"] = df_fin["Data_DT"].dt.strftime("%d/%m/%Y")

    # evita NaN em texto
    for c in ["Data", "Tipo", "Categoria", "Descrição", "Obra Vinculada", "Anexo"]:
        df_fin[c] = df_fin[c].fillna("").astype(str)

    return df_obras, df_fin
