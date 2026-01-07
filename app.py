import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- 1. CONFIGURAÇÃO DE ALTO NÍVEL ---
st.set_page_config(
    page_title="Gestor Obras | Enterprise",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CSS CUSTOMIZADO (VISUAL PROFISSIONAL) ---
st.markdown("""
    <style>
        /* Fundo geral e fontes */
        .main {
            background-color: #f8f9fa;
        }
        h1, h2, h3 {
            font-family: 'Segoe UI', sans-serif;
            color: #2c3e50;
        }
        
        /* Cards de Métricas (KPIs) com sombra e borda arredondada */
        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            transition: transform 0.2s;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 8px rgba(0,0,0,0.1);
        }

        /* Ajuste do Menu Lateral */
        section[data-testid="stSidebar"] {
            background-color: #262730;
        }
        
        /* Remover elementos desnecessários do Streamlit */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. BACKEND ROBUSTO (CONEXÃO E CACHE) ---
@st.cache_resource
def conectar_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # strict=False essencial para evitar erros de formatação no segredo
        json_creds = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json_creds, scope)
        client = gspread.authorize(creds)
        sheet = client.open("GestorObras_DB")
        return sheet
    except Exception as e:
        st.error(f"⚠️ Falha Crítica na Nuvem: {e}")
        return None

def carregar_dados():
    sheet = conectar_google_sheets()
    if sheet is None:
        return None, pd.DataFrame(), pd.DataFrame()

    try:
        # Carregar Obras
        try:
            ws_obras = sheet.worksheet("Obras")
        except:
            ws_obras = sheet.add_worksheet(title="Obras", rows="100", cols="20")
            ws_obras.append_row(["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"])
        
        df_obras = pd.DataFrame(ws_obras.get_all_records())
        # Limpeza de dados numéricos
        if not df_obras.empty:
            df_obras['Valor Total'] = pd.to_numeric(df_obras['Valor Total'], errors='coerce').fillna(0)

        # Carregar Financeiro
        try:
            ws_fin = sheet.worksheet("Financeiro")
        except:
            ws_fin = sheet.add_worksheet(title="Financeiro", rows="500", cols="20")
            ws_fin.append_row(["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"])
        
        df_financeiro = pd.DataFrame(ws_fin.get_all_records())
        if not df_financeiro.empty:
            df_financeiro['Valor'] = pd.to_numeric(df_financeiro['Valor'], errors='coerce').fillna(0)
            df_financeiro['Data'] = pd.to_datetime(df_financeiro['Data'], errors='coerce').dt.date

        return sheet, df_obras, df_financeiro

    except Exception as e:
        st.error(f"Erro no Processamento de Dados: {e}")
        return sheet, pd.DataFrame(), pd.DataFrame()

def salvar_dado(sheet, aba, nova_linha_dict):
    ws = sheet.worksheet(aba)
    ws.append_row(list(nova_linha_dict.values()))

# --- 4. INTERFACE (FRONTEND) ---
sheet, df_obras, df_financeiro = carregar_dados()

# Sidebar de Navegação Premium
with st.sidebar:
    st.markdown("## 🏗️ Gestor **PRO**")
    st.caption("Sistema Integrado de Gestão")
    st.markdown("---")
    
    menu = st.radio(
        "MENU PRINCIPAL", 
        ["📊 Dashboard Executivo", "📁 Gestão de Obras", "💸 Fluxo de Caixa", "⚙️ Configurações"],
    )
    
    st.markdown("---")
    if sheet:
        st.success("✅ Banco de Dados: Online")
    else:
        st.error("❌ Banco de Dados: Offline")

# --- LÓGICA DAS PÁGINAS ---

if menu == "📊 Dashboard Executivo":
    st.markdown("### 📊 Visão Estratégica")
    
    if not df_obras.empty:
        # CÁLCULOS DE KPI
        total_contratos = df_obras["Valor Total"].sum()
        
        if not df_financeiro.empty and 'Tipo' in df_financeiro.columns
