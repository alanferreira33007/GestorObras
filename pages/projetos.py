import streamlit as st
import pandas as pd
from datetime import date
from core.sheets import get_db
from core.data import clear_cache
from core.formatters import fmt_moeda
from core.constants import STATUS_PADRAO

def render(df_obras: pd.DataFrame):
    st.markdown("### 📁 Gestão de Obras")

    with st.form("f_obra", clear_on_submit=True):
        c1, c2 = st.columns(2)
        cliente = c1.text_input("Cliente / Nome da Obra")
        endereco = c2.text_input("Endereço")

        c3, c4, c5 = st.columns(3)
        status = c3.selectbox("Status", STATUS_PADRAO)
        vgv = c4.number_input("Valor Total (VGV)", format="%.2f", step=1000.0, min_value=0.0)
        prazo = c5.text_input("Prazo", value="A definir")

        if st.form_submit_button("CADASTRAR OBRA"):
            db = get_db()
            ws = db.worksheet("Obras")

            max_id = pd.to_numeric(df_obras["ID"], errors="coerce").max() if not df_obras.empty else None
            novo_id = int(max_id) + 1 if pd.notna(max_id) else 1

            ws.append_row(
                [
                    novo_id,
                    cliente.strip(),
                    endereco.strip(),
                    status,
                    float(vgv),
                    date.today().strftime("%Y-%m-%d"),
                    prazo.strip(),
                ],
                value_input_option="USER_ENTERED",
            )
            clear_cache()
            st.success("Obra cadastrada!")
            st.rerun()

    if not df_obras.empty:
        df_view = df_obras[["Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"]].copy()
        df_view["Valor Total"] = df_view["Valor Total"].apply(fmt_moeda)
        st.dataframe(df_view, use_container_width=True, hide_index=True)
