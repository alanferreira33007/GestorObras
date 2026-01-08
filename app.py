import streamlit as st
import pandas as pd
from datetime import date
from streamlit_option_menu import option_menu

# Nossas peças separadas
from database import carregar_dados, salvar_financeiro, salvar_obra
from relatorios import fmt_moeda, gerar_relatorio_investimentos_pdf, download_pdf_one_click

# Configuração de página
st.set_page_config(page_title="GESTOR PRO | Business Intelligence", layout="wide")

# --- ESTILIZAÇÃO CUSTOMIZADA (CSS) ---
st.markdown("""
<style>
    /* Estilização da Barra Lateral */
    [data-testid="stSidebar"] {
        background-color: #1B4332; /* Verde muito escuro */
        color: white;
    }
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    /* Estilização do Menu de Opções */
    .nav-link {
        font-weight: 500;
        border-radius: 8px !important;
        margin: 5px 0px;
    }
    .nav-link-selected {
        background-color: #2D6A4F !important; /* Verde destaque */
    }
    /* Card de Usuário no topo da Sidebar */
    .user-card {
        padding: 15px;
        background-color: rgba(255,255,255,0.1);
        border-radius: 10px;
        margin-bottom: 20px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# --- LOGIN (Simplificado) ---
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if not st.session_state["authenticated"]:
    # ... (mesmo código de login anterior)
    st.title("🔐 Acesso Gestor Pro")
    pwd = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if pwd == st.secrets["password"]:
            st.session_state["authenticated"] = True
            st.rerun()
    st.stop()

# --- CARREGAMENTO DE DADOS ---
df_obras, df_fin = carregar_dados()
lista_obras = df_obras["Cliente"].unique().tolist()

# --- BARRA LATERAL (SIDEBAR) MELHORADA ---
with st.sidebar:
    # 1. Cabeçalho com Logo/Ícone
    st.markdown('<div class="user-card">', unsafe_allow_html=True)
    st.image("https://cdn-icons-png.flaticon.com/512/3095/3095147.png", width=70) # Ícone de Construção
    st.markdown("### GESTOR PRO")
    st.markdown("<small>ADMINISTRADOR</small>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 2. Menu de Navegação
    sel = option_menu(
        menu_title=None, # Título oculto para ficar mais limpo
        options=["Investimentos", "Caixa", "Projetos"], 
        icons=["graph-up-arrow", "wallet2", "building-gear"], 
        menu_icon="cast", 
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "#D8F3DC", "font-size": "18px"}, 
            "nav-link": {"font-size": "16px", "text-align": "left", "margin":"0px"},
            "nav-link-selected": {"background-color": "#2D6A4F"},
        }
    )
    
    st.divider()
    
    # 3. Informações de Status (Rodapé da Sidebar)
    with st.container():
        st.caption("🛰️ **Status do Sistema**")
        st.success("Conectado ao Cloud DB")
        st.caption(f"📅 Data: {date.today().strftime('%d/%m/%Y')}")
    
    st.divider()
    
    # 4. Botão de Sair com visual discreto
    if st.button("🚪 Encerrar Sessão", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()

# --- CONTEÚDO DAS TELAS (Telas de Investimento, Caixa e Projetos...) ---
if sel == "Investimentos":
    st.title("📊 Painel de Performance")
    # ... (Resto do código do Dashboard anterior)
    st.info(f"Visualizando dados sincronizados: {len(df_fin)} registros.")

elif sel == "Caixa":
    st.title("💸 Gestão de Fluxo")
    # ... (Resto do código do Caixa anterior)

elif sel == "Projetos":
    st.title("🏗️ Gestão de Portfólio")
    # ... (Resto do código de Projetos anterior)
