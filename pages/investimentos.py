import streamlit as st
import plotly.express as px
import pandas as pd
from core.formatters import fmt_moeda


def render(df_obras: pd.DataFrame, df_fin: pd.DataFrame, lista_obras: list[str]):
    st.markdown("### 📊 Performance e ROI por Obra")

    if not lista_obras:
        st.info("Cadastre uma obra para iniciar a análise.")
        return

    obra_sel = st.selectbox("Selecione a obra", lista_obras)

    df_match = df_obras[df_obras["Cliente"].astype(str).str.strip() == str(obra_sel).strip()]
    if df_match.empty:
        st.warning("Obra não encontrada. Verifique se o nome está igual ao cadastrado na aba Obras.")
        return

    obra_row = df_match.iloc[0]
    vgv = float(obra_row.get("Valor Total", 0) or 0)

    df_v = df_fin[df_fin["Obra Vinculada"].astype(str).str.strip() == str(obra_sel).strip()].copy()

    custos = df_v[df_v["Tipo"].astype(str).str.contains("Saída", case=False, na=False)]["Valor"].sum()
    lucro = vgv - custos
    roi = (lucro / custos * 100) if custos > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("V
