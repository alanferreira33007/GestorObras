import streamlit as st
from streamlit_option_menu import option_menu

from core.data import carregar_dados
from core.sheets import ensure_schema

from pages import investimentos, caixa, insumos, projetos, orcamento


st.set_page_config(page_title="GESTOR PRO | Master", layout="wide")

st.markdown("""
<style>
.stApp { background-color: #F8F9FA; color:#1A1C1E; font-family: Inter, sans-serif; }
[data-testid="stMetric"] { background:#fff; border:1px solid #E9ECEF; border-radius:12px; padding:18px !important; }
div.stButton > button { background:#2D6A4F !important; color:#fff !important; border-radius:8px !important; font-weight:700 !important; height:44px; }
header, footer, #MainMenu {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

ensure_schema()

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.form("login"):
            st.markdown("<h2 style='text-align:center; color:#2D6A4F;'>GESTOR PRO</h2>", unsafe_allow_html=True)
            pwd = st.text_input("Senha de Acesso", type="password")
            if st.form_submit_button("Acessar"):
                if pwd == st.secrets["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
else:
    df_obras, df_fin = carregar_dados()

    lista_obras = []
    if not df_obras.empty and "Cliente" in df_obras.columns:
        lista_obras = df_obras["Cliente"].astype(str).tolist()

    with st.sidebar:
        sel = option_menu(
            "GESTOR PRO",
            ["Investimentos", "Caixa", "Insumos", "Orçamento", "Projetos"],
            icons=["graph-up-arrow", "wallet2", "cart-check", "bullseye", "building"],
            default_index=0,
        )
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

    if sel == "Investimentos":
        investimentos.render(df_obras, df_fin, lista_obras)
    elif sel == "Caixa":
        caixa.render(df_obras, df_fin, lista_obras)
    elif sel == "Insumos":
        insumos.render(df_obras, df_fin, lista_obras)
    elif sel == "Orçamento":
        orcamento.render(df_obras, df_fin, lista_obras)
    elif sel == "Projetos":
        projetos.render(df_obras, df_fin, lista_obras)
