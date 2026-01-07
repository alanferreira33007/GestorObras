import streamlit as st
from streamlit_option_menu import option_menu

from core.auth import ensure_auth, login_screen
from core.data import load_data, obras_list
from pages import investimentos, caixa, insumos, projetos

# --- 1) CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="GESTOR PRO | Modular", layout="wide")

# --- 2) CSS (SEU ESTILO) ---
st.markdown("""
<style>
    .stApp { background-color: #F8F9FA; color: #1A1C1E; font-family: 'Inter', sans-serif; }
    [data-testid="stMetric"] { background-color: #FFFFFF; border: 1px solid #E9ECEF; border-radius: 12px; padding: 20px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
    div.stButton > button { background-color: #2D6A4F !important; color: white !important; border-radius: 6px !important; font-weight: 600 !important; width: 100%; height: 45px; }
    .alert-card { background-color: #FFFFFF; border-left: 5px solid #E63946; padding: 20px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
    header, footer, #MainMenu {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- 3) AUTENTICAÇÃO ---
ensure_auth()
if not st.session_state["authenticated"]:
    login_screen()
    st.stop()

# --- 4) CARREGAMENTO DE DADOS ---
df_obras, df_fin = load_data()
lista_obras = obras_list(df_obras)

# --- 5) MENU LATERAL ---
with st.sidebar:
    sel = option_menu(
        "GESTOR PRO",
        ["Investimentos", "Caixa", "Insumos", "Projetos"],
        icons=["graph-up-arrow", "wallet2", "cart-check", "building"],
        default_index=0,
    )
    if st.button("Sair"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- 6) ROTAS (TELAS) ---
if sel == "Investimentos":
    investimentos.render(df_obras, df_fin, lista_obras)

elif sel == "Caixa":
    caixa.render(df_obras, df_fin, lista_obras)

elif sel == "Insumos":
    insumos.render(df_fin)

elif sel == "Projetos":
    projetos.render(df_obras)
