import streamlit as st
import pandas as pd
from datetime import date
from streamlit_option_menu import option_menu

# Importando nossas funções
from database import carregar_dados, salvar_financeiro, salvar_obra
from relatorios import fmt_moeda, gerar_relatorio_investimentos_pdf, download_pdf_one_click

# Configuração de página
st.set_page_config(page_title="GESTOR PRO | Business Intelligence", layout="wide")

# --- NOVO LAYOUT CSS (MINIMALISTA) ---
st.markdown("""
<style>
    /* Fundo do app e da sidebar */
    .stApp { background-color: #FBFBFB; }
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E6E8EB;
    }
    
    /* Ajuste de fontes e textos */
    h1, h2, h3 { color: #1E293B !important; font-family: 'Inter', sans-serif; }
    .stMarkdown { color: #475569; }

    /* Estilização do Menu Lateral */
    .nav-link {
        font-size: 15px !important;
        color: #64748B !important;
        padding: 10px 15px !important;
        border-radius: 6px !important;
    }
    .nav-link:hover {
        background-color: #F1F5F9 !important;
        color: #1E293B !important;
    }
    .nav-link-selected {
        background-color: #E2E8F0 !important;
        color: #0F172A !important;
        font-weight: 600 !important;
    }

    /* Cards de Métricas */
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    }
</style>
""", unsafe_allow_html=True)

# --- LOGIN ---
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if not st.session_state["authenticated"]:
    # ... (Mantenha seu código de login aqui)
    st.stop()

# --- CARREGAMENTO ---
df_obras, df_fin = carregar_dados()
lista_obras = df_obras["Cliente"].unique().tolist()

# --- SIDEBAR MINIMALISTA ---
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    # Título discreto e elegante
    st.markdown("<h2 style='text-align: center; font-size: 22px;'>🏗️ Gestor Pro</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94A3B8; font-size: 12px;'>Versão 2.0 Corporate</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Menu com visual de "sistema nativo"
    sel = option_menu(
        menu_title=None,
        options=["Investimentos", "Caixa", "Projetos"], 
        icons=["bar-chart-steps", "wallet2", "stack"], 
        default_index=0,
        styles={
            "container": {"padding": "5px", "background-color": "transparent"},
            "icon": {"color": "#64748B", "font-size": "18px"}, 
            "nav-link": {"margin":"5px 0px"},
            "nav-link-selected": {"background-color": "#F1F5F9", "color": "#1E293B"},
        }
    )
    
    st.vfill() # Empurra o conteúdo abaixo para o fundo
    
    # Rodapé da Sidebar
    st.markdown("---")
    st.caption("👤 **Usuário:** Administrador")
    if st.button("Sair do Sistema", use_container_width=True, type="secondary"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- CONTEÚDO ---
if sel == "Investimentos":
    st.subheader("📊 Análise de Performance")
    # ... (Restante do seu dashboard)
elif sel == "Caixa":
    st.subheader("💸 Fluxo Financeiro")
    # ... (Restante do seu caixa)
elif sel == "Projetos":
    st.subheader("🏗️ Gestão de Obras")
    # ... (Restante dos seus projetos)
