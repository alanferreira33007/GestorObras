import streamlit as st
import pandas as pd
from datetime import date
from core.sheets import get_db
from core.data import clear_cache
from core.formatters import fmt_moeda
from core.constants import CATEGORIAS_PADRAO

def render(df_obras: pd.DataFrame, df_fin: pd.DataFrame, lista_obras: list[str]):
    st.markdown("### 💸 Lançamento Financeiro")

    with st.form("f_caixa", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        dt_input = c1.date_input("Data", value=date.today(), format="DD/MM/YYYY")
        tp_input = c2.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
        cat_input = c3.selectbox("Categoria", CATEGORIAS_PADRAO)

        c4, c5 = st.columns(2)
        ob_input = c4.selectbox("Obra Vinculada", lista_obras if lista_obras else ["Geral"])
        vl_input = c5.number_input("Valor R$", format="%.2f", step=0.01, min_value=0.0)

        ds_input = st.text_input("Descrição")

        if st.form_submit_button("REGISTRAR LANÇAMENTO"):
            db = get_db()
            db.worksheet("Financeiro").append_row(
                [
                    dt_input.strftime("%Y-%m-%d"),
                    tp_input,
                    cat_input,
                    ds_input,
                    float(vl_input),
                    ob_input,
                ],
                value_input_option="USER_ENTERED",
            )
            clear_cache()
            st.success("Lançamento realizado!")
            st.rerun()

    if not df_fin.empty:
        st.markdown("#### Histórico de Lançamentos")
        df_display = df_fin[["Data_BR", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]].copy()
        df_display = df_display.assign(_dt=df_fin["Data_DT"]).sort_values("_dt", ascending=False).drop(columns="_dt")
        df_display["Valor"] = df_display["Valor"].apply(fmt_moeda)
        df_display.columns = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra"]
        st.dataframe(df_display, use_container_width=True, hide_index=True)
