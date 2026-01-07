import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA (PRIMEIRA COISA A RODAR) ---
st.set_page_config(
    page_title="Gestor de Obras Pro",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILO CUSTOMIZADO (CSS) ---
# Remove marcas d'água do Streamlit e ajusta espaçamentos
st.markdown("""
    <style>
        .reportview-container { margin-top: -2em; }
        #MainMenu {visibility: hidden;}
        .stDeployButton {display:none;}
        footer {visibility: hidden;}
        .stDecoration {display:none;}
    </style>
""", unsafe_allow_html=True)

# --- CONEXÃO SEGURA (BACKEND) ---
@st.cache_resource
def conectar_google_sheets():
    """Conecta ao Google Sheets e faz cache da conexão para não recarregar toda hora."""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # strict=False para evitar erros de quebra de linha no segredo
        json_creds = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json_creds, scope)
        client = gspread.authorize(creds)
        sheet = client.open("GestorObras_DB")
        return sheet
    except Exception as e:
        st.error(f"⚠️ Erro Crítico na Conexão: {e}")
        return None

def carregar_dados():
    sheet = conectar_google_sheets()
    if sheet is None:
        return None, pd.DataFrame(), pd.DataFrame()

    try:
        # Tenta carregar ou criar aba Obras
        try:
            ws_obras = sheet.worksheet("Obras")
        except:
            ws_obras = sheet.add_worksheet(title="Obras", rows="100", cols="20")
            ws_obras.append_row(["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"])

        # Tenta carregar ou criar aba Financeiro
        try:
            ws_fin = sheet.worksheet("Financeiro")
        except:
            ws_fin = sheet.add_worksheet(title="Financeiro", rows="100", cols="20")
            ws_fin.append_row(["ID", "Obra ID", "Descrição", "Tipo", "Valor", "Data"])

        # Carrega Dataframes e converte tipos numéricos
        df_obras = pd.DataFrame(ws_obras.get_all_records())
        df_financeiro = pd.DataFrame(ws_fin.get_all_records())

        # Tratamento de erro caso a planilha esteja vazia (apenas cabeçalho)
        if not df_obras.empty:
            # Garante que 'Valor Total' seja número. Remove 'R$' e ',' se houver erro de digitação manual
            df_obras['Valor Total'] = pd.to_numeric(df_obras['Valor Total'], errors='coerce').fillna(0)
            
        return sheet, df_obras, df_financeiro

    except Exception as e:
        st.error(f"Erro ao processar dados: {e}")
        return sheet, pd.DataFrame(), pd.DataFrame()

def salvar_obra(sheet, nova_obra):
    ws = sheet.worksheet("Obras")
    ws.append_row(list(nova_obra.values()))

# --- INTERFACE DO USUÁRIO (FRONTEND) ---

# 1. Carregamento de Dados
sheet, df_obras, df_financeiro = carregar_dados()

# 2. Sidebar (Menu Lateral)
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2666/2666505.png", width=50)
    st.title("Gestor Obras")
    st.markdown("---")
    
    menu = st.radio(
        "Navegação", 
        ["📊 Dashboard", "➕ Nova Obra", "📁 Consultar Base", "💰 Financeiro"]
    )
    
    st.markdown("---")
    st.caption("v2.0 - Professional Edition")
    if sheet:
        st.markdown(f"[🔗 Acessar Planilha]({sheet.url})")

# 3. Lógica das Páginas
if menu == "📊 Dashboard":
    st.title("📊 Painel de Controle")
    st.markdown("Visão geral estratégica dos projetos.")

    if not df_obras.empty:
        # KPI Cards (Métricas no topo)
        total_obras = len(df_obras)
        valor_total = df_obras["Valor Total"].sum()
        obras_ativas = len(df_obras[df_obras["Status"] == "Em Andamento"])

        col1, col2, col3 = st.columns(3)
        col1.metric("Projetos Totais", total_obras, delta="Cadastrados")
        col2.metric("Valor em Carteira", f"R$ {valor_total:,.2f}", delta="Contratos")
        col3.metric("Obras em Andamento", obras_ativas, delta="Ativas", delta_color="normal")

        st.markdown("---")

        # Gráficos Lado a Lado
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Distribuição por Status")
            fig_pie = px.pie(df_obras, names='Status', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with c2:
            st.subheader("Maiores Contratos")
            df_top = df_obras.nlargest(5, 'Valor Total')
            fig_bar = px.bar(df_top, x='Cliente', y='Valor Total', text_auto='.2s', color='Valor Total')
            st.plotly_chart(fig_bar, use_container_width=True)

    else:
        st.warning("⚠️ Nenhuma obra cadastrada para gerar indicadores.")

elif menu == "➕ Nova Obra":
    st.title("📝 Cadastro de Projetos")
    st.markdown("Preencha os dados abaixo para iniciar um novo controle.")
    
    with st.container(border=True):
        with st.form("form_obra", clear_on_submit=True):
            # Layout em Colunas (Grid)
            col_a, col_b = st.columns(2)
            
            with col_a:
                cliente = st.text_input("Nome do Cliente / Proprietário")
                endereco = st.text_input("Localização da Obra")
                data_inicio = st.date_input("Data de Início", datetime.now())
            
            with col_b:
                valor = st.number_input("Valor do Contrato (R$)", min_value=0.0, step=1000.0, format="%.2f")
                status = st.selectbox("Status Atual", ["Planejamento", "Em Andamento", "Paralisada", "Concluída"])
                prazo = st.text_input("Prazo Estimado (ex: 6 meses)")

            st.markdown("---")
            submitted = st.form_submit_button("💾 Salvar Projeto", type="primary")

            if submitted:
                if not cliente:
                    st.error("O nome do cliente é obrigatório.")
                else:
                    nova_obra = {
                        "ID": len(df_obras) + 1,
                        "Cliente": cliente,
                        "Endereço": endereco,
                        "Status": status,
                        "Valor Total": valor,
                        "Data Início": str(data_inicio),
                        "Prazo": prazo
                    }
                    salvar_obra(sheet, nova_obra)
                    st.toast(f"✅ Obra de {cliente} cadastrada com sucesso!", icon="🎉")

elif menu == "📁 Consultar Base":
    st.title("📁 Base de Dados de Obras")
    
    if not df_obras.empty:
        # Filtro rápido
        filtro = st.text_input("🔍 Buscar cliente ou endereço...", "")
        
        if filtro:
            df_display = df_obras[df_obras.apply(lambda row: row.astype(str).str.contains(filtro, case=False).any(), axis=1)]
        else:
            df_display = df_obras

        # Tabela Profissional
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Valor Total": st.column_config.NumberColumn(
                    "Valor Contrato",
                    format="R$ %.2f"
                ),
                "Status": st.column_config.SelectboxColumn(
                    "Status",
                    width="medium",
                    options=["Planejamento", "Em Andamento", "Concluída", "Paralisada"],
                ),
                "ID": st.column_config.TextColumn("ID", width="small")
            }
        )
    else:
        st.info("Nenhum dado encontrado.")

elif menu == "💰 Financeiro":
    st.title("💰 Gestão Financeira")
    st.info("🚧 Módulo em desenvolvimento. Aqui você lançará notas fiscais e pagamentos.")
