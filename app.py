import streamlit as st
from database import carregar_dados, obter_db
from relatorios import gerar_relatorio_investimentos_pdf, fmt_moeda
from streamlit_option_menu import option_menu
from datetime import date

# Configuração da Página
st.set_page_config(page_title="GESTOR PRO", layout="wide")

# LOGIN (Simplificado)
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    pwd = st.text_input("Senha", type="password")
    if st.button("Acessar"):
        if pwd == st.secrets["password"]:
            st.session_state["authenticated"] = True
            st.rerun()
    st.stop()

# CARREGAR DADOS (Vem do database.py)
df_obras, df_fin = carregar_dados()

# MENU
with st.sidebar:
    sel = option_menu("GESTOR PRO", ["Investimentos", "Caixa", "Projetos"])

if sel == "Investimentos":
    st.title("📊 Performance por Obra")
    # ... aqui entra o resto do seu código de visualização ...
    st.write("Dados carregados com sucesso!")
