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
        
        # --- CORREÇÃO AQUI (Adicionado o :) ---
        if not df_financeiro.empty and 'Tipo' in df_financeiro.columns:
            total_gasto = df_financeiro[df_financeiro['Tipo'].str.contains('Saída', case=False, na=False)]['Valor'].sum()
        else:
            total_gasto = 0
            
        lucro_estimado = total_contratos - total_gasto
        
        # DEFINIÇÃO DE CORES SEMÂNTICAS
        cores_status = {
            "Concluída": "#2ecc71",      # Verde
            "Em Andamento": "#f1c40f",   # Amarelo
            "Planejamento": "#3498db",   # Azul
            "Paralisada": "#e74c3c"      # Vermelho
        }

        # KPI CARDS
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Faturamento Contratado", f"R$ {total_contratos:,.2f}", delta="Total Obras")
        c2.metric("Despesas Totais", f"R$ {total_gasto:,.2f}", delta="- Saídas", delta_color="inverse")
        c3.metric("Saldo de Caixa", f"R$ {lucro_estimado:,.2f}", delta="Margem")
        c4.metric("Obras Ativas", len(df_obras[df_obras['Status'] == 'Em Andamento']), "Projetos")

        st.markdown("---")

        # GRÁFICOS AVANÇADOS
        g1, g2 = st.columns([2, 1])
        
        with g1:
            st.subheader("Evolução Financeira por Obra")
            if not df_obras.empty:
                fig_bar = px.bar(
                    df_obras, 
                    x='Cliente', 
                    y='Valor Total', 
                    color='Status',
                    color_discrete_map=cores_status,
                    text_auto='.2s',
                    title="Valor dos Contratos por Cliente"
                )
                fig_bar.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_bar, use_container_width=True)
        
        with g2:
            st.subheader("Status dos Projetos")
            status_counts = df_obras['Status'].value_counts()
            
            # Gráfico de Rosca
            fig_pie = px.pie(
                values=status_counts.values, 
                names=status_counts.index, 
                color=status_counts.index,
                color_discrete_map=cores_status,
                hole=0.6
            )
            fig_pie.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_pie, use_container_width=True)

    else:
        st.info("👋 Bem-vindo! Comece cadastrando sua primeira obra no menu lateral.")

elif menu == "📁 Gestão de Obras":
    tab1, tab2 = st.tabs(["📝 Novo Cadastro", "🔍 Consultar Base"])
    
    with tab1:
        st.markdown("#### Cadastrar Nova Obra")
        with st.form("form_obra_pro", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                cliente = st.text_input("Nome do Cliente / Projeto")
                endereco = st.text_input("Localização")
                data_ini = st.date_input("Data de Início", datetime.now())
            with col_b:
                valor = st.number_input("Valor do Contrato (R$)", min_value=0.0, step=1000.0)
                status = st.selectbox("Status", ["Planejamento", "Em Andamento", "Concluída", "Paralisada"])
                prazo = st.text_input("Prazo de Entrega")
            
            if st.form_submit_button("🚀 Lançar Projeto no Sistema", type="primary"):
                nova_obra = {
                    "ID": len(df_obras) + 1,
                    "Cliente": cliente,
                    "Endereço": endereco,
                    "Status": status,
                    "Valor Total
