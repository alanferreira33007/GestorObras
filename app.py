import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURAÇÃO DE ALTO NÍVEL ---
st.set_page_config(
    page_title="Gestor Obras | Enterprise",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CSS CUSTOMIZADO (VISUAL PROFISSIONAL & LEGÍVEL) ---
st.markdown("""
    <style>
        /* Fundo principal (Cinza bem claro para descanso dos olhos) */
        .main {
            background-color: #f4f6f9;
        }
        
        /* Fontes Corporativas */
        h1, h2, h3 {
            font-family: 'Segoe UI', sans-serif;
            color: #2c3e50;
        }
        
        /* BARRA LATERAL (CORRIGIDA: Fundo Branco para Alto Contraste) */
        section[data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: 1px solid #e0e0e0;
        }
        
        /* Cards de Métricas (KPIs) */
        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }

        /* Limpeza visual */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. BACKEND (CONEXÃO) ---
@st.cache_resource
def conectar_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        json_creds = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json_creds, scope)
        client = gspread.authorize(creds)
        return client.open("GestorObras_DB")
    except Exception as e:
        st.error(f"⚠️ Erro de Conexão: {e}")
        return None

def carregar_dados():
    sheet = conectar_google_sheets()
    if sheet is None:
        return None, pd.DataFrame(), pd.DataFrame()

    try:
        # Aba Obras
        try:
            ws_obras = sheet.worksheet("Obras")
        except:
            ws_obras = sheet.add_worksheet(title="Obras", rows="100", cols="20")
            ws_obras.append_row(["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"])
        
        df_obras = pd.DataFrame(ws_obras.get_all_records())
        if not df_obras.empty:
            df_obras['Valor Total'] = pd.to_numeric(df_obras['Valor Total'], errors='coerce').fillna(0)

        # Aba Financeiro
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
        st.error(f"Erro ao ler dados: {e}")
        return sheet, pd.DataFrame(), pd.DataFrame()

def salvar_dado(sheet, aba, linha):
    ws = sheet.worksheet(aba)
    ws.append_row(list(linha.values()))

# --- 4. INTERFACE ---
sheet, df_obras, df_financeiro = carregar_dados()

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2666/2666505.png", width=50)
    st.markdown("## Gestor **PRO**")
    st.markdown("---")
    menu = st.radio("MENU PRINCIPAL", ["📊 Dashboard", "📁 Obras", "💸 Financeiro", "⚙️ Config"])
    st.markdown("---")
    if sheet: st.success("Banco de Dados: Online ✅")

# --- LÓGICA ---
if menu == "📊 Dashboard":
    st.markdown("### 📊 Visão Estratégica")
    if not df_obras.empty:
        total_contratos = df_obras["Valor Total"].sum()
        
        if not df_financeiro.empty and 'Tipo' in df_financeiro.columns:
            total_gasto = df_financeiro[df_financeiro['Tipo'].str.contains('Saída', case=False, na=False)]['Valor'].sum()
        else:
            total_gasto = 0
            
        c1, c2, c3 = st.columns(3)
        c1.metric("Faturamento", f"R$ {total_contratos:,.2f}")
        c2.metric("Despesas", f"R$ {total_gasto:,.2f}")
        c3.
