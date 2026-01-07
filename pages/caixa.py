import streamlit as st
from datetime import date
import pandas as pd

from core.data import carregar_dados
from core.formatters import fmt_moeda
from core.sheets import open_db
from core.drive import upload_to_drive

st.title("💸 Caixa")

df_obras, df_fin = carregar_dados()
obras_list = df_obras["Cliente"].dropna().unique().tolist() if not df_obras.empty else ["Geral"]

with st.form("f_caixa", clear_on_submit=True):
    c1, c2 = st.columns(2)
    dt_input = c1.date_input("Data", value=date.today(), format="DD/MM/YYYY")
    tp_input = c2.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])

    c3, c4 = st.columns(2)
    cat_input = c3.text_input("Categoria", value="Geral")
    ob_input = c4.selectbox("Obra Vinculada", obras_list)

    vl_input = st.number_input("Valor (R$)", format="%.2f", step=0.01)
    ds_input = st.text_input("Descrição")

    uploaded = st.file_uploader("📎 Anexar nota (PDF/foto)", type=["pdf", "png", "jpg", "jpeg"])

    if st.form_submit_button("REGISTRAR LANÇAMENTO"):
        anexo_url = ""
        try:
            if uploaded is not None:
                file_bytes = uploaded.getvalue()
                mime_type = uploaded.type or "application/octet-stream"
                _, anexo_url = upload_to_drive(uploaded.name, file_bytes, mime_type)

            db = open_db()
            ws = db.worksheet("Financeiro")

            ws.append_row([
                dt_input.strftime("%Y-%m-%d"),
                tp_input,
                cat_input,
                ds_input,
                float(vl_input),
                ob_input,
                anexo_url
            ])

            st.cache_data.clear()
            st.success("Lançamento realizado!")
            st.rerun()

        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

st.divider()
st.subheader("📜 Histórico")

if df_fin.empty:
    st.info("Sem lançamentos ainda.")
else:
    df_display = df_fin.copy()
    cols = ["Data_BR", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada", "Anexo"]
    for c in cols:
        if c not in df_display.columns:
            df_display[c] = ""

    df_display["Valor"] = df_display["Valor"].apply(fmt_moeda)
    if "Data_DT" in df_display.columns:
        df_display = df_display.sort_values("Data_DT", ascending=False)

    df_display = df_display[cols].copy()
    df_display.columns = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra", "Anexo"]

    st.dataframe(df_display, use_container_width=True, hide_index=True)
