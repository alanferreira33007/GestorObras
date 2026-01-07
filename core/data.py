import pandas as pd
import streamlit as st
from core.sheets import ensure_schema


@st.cache_data(ttl=60)
def carregar_dados():
    db = ensure_schema()

    # ---- Obras
    ws_o = db.worksheet("Obras")
    vals_o = ws_o.get_all_values()
    if len(vals_o) >= 2:
        headers = vals_o[0]
        rows = vals_o[1:]
        df_o = pd.DataFrame(rows, columns=headers)
    else:
        df_o = pd.DataFrame(columns=["ID", "Cliente", "Status", "Valor Total", "Data Início", "Observações"])

    # normaliza colunas
    if "Valor Total" in df_o.columns:
        df_o["Valor Total"] = pd.to_numeric(df_o["Valor Total"], errors="coerce").fillna(0)

    # ---- Financeiro (com número da linha da planilha)
    ws_f = db.worksheet("Financeiro")
    vals_f = ws_f.get_all_values()
    if len(vals_f) >= 2:
        headers = vals_f[0]
        rows = vals_f[1:]
        df_f = pd.DataFrame(rows, columns=headers)
        df_f["_row"] = list(range(2, 2 + len(rows)))  # linha real na planilha

        # tipos
        if "Valor" in df_f.columns:
            df_f["Valor"] = pd.to_numeric(df_f["Valor"], errors="coerce").fillna(0)

        if "Data" in df_f.columns:
            df_f["Data_DT"] = pd.to_datetime(df_f["Data"], errors="coerce")
            df_f["Data_BR"] = df_f["Data_DT"].dt.strftime("%d/%m/%Y")
        else:
            df_f["Data_DT"] = pd.NaT
            df_f["Data_BR"] = ""

    else:
        df_f = pd.DataFrame(columns=["ID", "Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada", "Anexo", "_row", "Data_DT", "Data_BR"])

    return df_o, df_f


def clear_cache():
    st.cache_data.clear()
