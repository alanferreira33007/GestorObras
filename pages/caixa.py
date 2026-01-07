import streamlit as st
import pandas as pd
from datetime import date
from core.sheets import get_db
from core.data import clear_cache
from core.formatters import fmt_moeda
from core.constants import CATEGORIAS_PADRAO


MESES = [
    ("Todos", "Todos"),
    (1, "01 - Jan"),
    (2, "02 - Fev"),
    (3, "03 - Mar"),
    (4, "04 - Abr"),
    (5, "05 - Mai"),
    (6, "06 - Jun"),
    (7, "07 - Jul"),
    (8, "08 - Ago"),
    (9, "09 - Set"),
    (10, "10 - Out"),
    (11, "11 - Nov"),
    (12, "12 - Dez"),
]


def _filtrar_periodo(df: pd.DataFrame, ano_sel: str, mes_sel):
    df2 = df.copy()
    df2 = df2.dropna(subset=["Data_DT"])

    if ano_sel != "Todos":
        ano_int = int(ano_sel)
        df2 = df2[df2["Data_DT"].dt.year == ano_int]

    if mes_sel != "Todos":
        mes_int = int(mes_sel)
        df2 = df2[df2["Data_DT"].dt.month == mes_int]

    return df2


def render(df_obras: pd.DataFrame, df_fin: pd.DataFrame, lista_obras: list[str]):
    st.markdown("### 💸 Lançamento Financeiro")

    # ---------- FORM LANÇAMENTO ----------
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

    # ---------- HISTÓRICO + FILTRO ----------
    if df_fin.empty:
        return

    st.markdown("#### Histórico de Lançamentos")

    # opções de ano (com base nos dados)
    df_temp = df_fin.dropna(subset=["Data_DT"]).copy()
    anos = sorted(df_temp["Data_DT"].dt.year.dropna().astype(int).unique().tolist())
    op_anos = ["Todos"] + [str(a) for a in anos]

    with st.expander("📅 Filtros (Ano/Mês)", expanded=False):
        f1, f2 = st.columns(2)
        ano_sel = f1.selectbox("Ano", op_anos, index=0)
        mes_label = f2.selectbox("Mês", [m[1] for m in MESES], index=0)

        # traduz label de mês para número
        mes_sel = "Todos"
        for num, lab in MESES:
            if lab == mes_label:
                mes_sel = num
                break

    df_filtrado = _filtrar_periodo(df_fin, ano_sel, mes_sel)

    # tabela
    df_display = df_filtrado[["Data_BR", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]].copy()
    df_display = df_display.assign(_dt=df_filtrado["Data_DT"]).sort_values("_dt", ascending=False).drop(columns="_dt")
    df_display["Valor"] = df_display["Valor"].apply(fmt_moeda)
    df_display.columns = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra"]

    st.dataframe(df_display, use_container_width=True, hide_index=True)
