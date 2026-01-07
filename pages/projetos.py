import streamlit as st
from datetime import date

from core.data import carregar_dados
from core.formatters import fmt_moeda
from core.sheets import open_db

st.title("📁 Projetos (Obras)")

df_obras, _ = carregar_dados()

with st.form("f_obra", clear_on_submit=True):
    n_obra = st.text_input("Nome da Obra (Cliente)")
    end = st.text_input("Endereço", value="")
    status = st.selectbox("Status", ["Planejamento", "Em Construção", "Concluída"])
    vgv = st.number_input("VGV (Valor Total)", format="%.2f", step=100.0)
    prazo = st.text_input("Prazo", value="A definir")

    if st.form_submit_button("CADASTRAR OBRA"):
        try:
            db = open_db()
            ws = db.worksheet("Obras")
            novo_id = (len(df_obras) + 1) if not df_obras.empty else 1

            ws.append_row([
                novo_id,
                n_obra,
                end,
                status,
                float(vgv),
                date.today().strftime("%Y-%m-%d"),
                prazo
            ])

            st.cache_data.clear()
            st.success("Obra cadastrada!")
            st.rerun()

        except Exception as e:
            st.error(f"Erro ao cadastrar: {e}")

st.divider()
st.subheader("📌 Obras cadastradas")

if df_obras.empty:
    st.info("Nenhuma obra cadastrada.")
else:
    df_show = df_obras[["Cliente","Status","Valor Total"]].copy()
    df_show["Valor Total"] = df_show["Valor Total"].apply(fmt_moeda)
    st.dataframe(df_show, use_container_width=True, hide_index=True)
