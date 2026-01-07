import streamlit as st

st.set_page_config(page_title="GESTOR PRO", layout="wide")

st.markdown("""
<style>
.stApp { background-color: #F8F9FA; color: #1A1C1E; font-family: 'Inter', sans-serif; }
[data-testid="stMetric"] { background-color: #FFFFFF; border: 1px solid #E9ECEF; border-radius: 12px; padding: 20px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
div.stButton > button { background-color: #2D6A4F !important; color: white !important; border-radius: 6px !important; font-weight: 600 !important; width: 100%; height: 45px; }
header, footer, #MainMenu {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

st.title("🏗️ GESTOR PRO")
st.caption("Escolha uma página no menu lateral (Caixa, Insumos, Investimentos, Orçamento, Projetos).")
