import streamlit as st
import pandas as pd
from core.sheets import get_db
from core.constants import OBRAS_COLS, FIN_COLS

def ensure_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]

@st.cache_data(ttl=10)
def load_data():
    db = get_db()

    ws_o = db.worksheet("Obras")
    df_o = pd.DataFrame(ws_o.get_all_records())
    if df_o.empty:
        df_o = pd.DataFrame(columns=OBRAS_COLS)
    df_o = ensure_cols(df_o, OBRAS_COLS)
    df_o["ID"] = pd.to_numeric(df_o["ID"], errors="coerce")
    df_o["Valor Total"] = pd.to_numeric(df_o["Valor Total"], errors="coerce").fillna(0)

    ws_f = db.worksheet("Financeiro")
    df_f = pd.DataFrame(ws_f.get_all_records())
    if df_f.empty:
        df_f = pd.DataFrame(columns=FIN_COLS)
    df_f = ensure_cols(df_f, FIN_COLS)
    df_f["Valor"] = pd.to_numeric(df_f["Valor"], errors="coerce").fillna(0)
    df_f["Data_DT"] = pd.to_datetime(df_f["Data"], errors="coerce")
    df_f["Data_BR"] = df_f["Data_DT"].dt.strftime("%d/%m/%Y")
    df_f.loc[df_f["Data_DT"].isna(), "Data_BR"] = ""

    return df_o, df_f

def obras_list(df_obras: pd.DataFrame) -> list[str]:
    if df_obras.empty or "Cliente" not in df_obras.columns:
        return []
    return (
        df_obras["Cliente"]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .unique()
        .tolist()
    )

def clear_cache():
    st.cache_data.clear()
