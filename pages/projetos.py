import streamlit as st
from datetime import date, datetime
from core.sheets import get_db
from core.data import clear_cache
from core.formatters import fmt_moeda


def render(df_obras, df_fin, lista_obras):
    st.markdown("### 📁 Projetos — Obras")

    with st.form("f_obra", clear_on_submit=True):
        n_obra = st.text_input("Nome da Casa/Lote")
        v_obra = st.number_input("Preço de Venda Pretendido (VGV)", format="%.2f", min_value=0.0, step=1000.0)
        status = st.selectbox("Status", ["Planejamento", "Em Construção", "Finalizada"], index=1)
        if st.form_submit_button("CADASTRAR OBRA"):
            if not n_obra.strip():
                st.error("Informe o nome da obra.")
                st.stop()

            db = get_db()
            ws = db.worksheet("Obras")
            new_id = str(int(datetime.now().timestamp() * 1000))

            ws.append_row(
                [new_id, n_obra, status, float(v_obra), date.today().strftime("%Y-%m-%d"), ""],
                value_input_option="USER_ENTERED",
            )
            clear_cache()
            st.success("Obra cadastrada!")
            st.rerun()

    if df_obras.empty:
        st.info("Nenhuma obra cadastrada.")
        return

    df_show = df_obras.copy()
    if "Valor Total" in df_show.columns:
        df_show["Valor Total"] = df_show["Valor Total"].apply(fmt_moeda)
    cols = [c for c in ["Cliente", "Status", "Valor Total", "Data Início"] if c in df_show.columns]
    st.dataframe(df_show[cols], use_container_width=True, hide_index=True)
