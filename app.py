import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import datetime, date
from streamlit_option_menu import option_menu

# --- 1. CONFIGURAÇÃO DE UI CORPORATIVA ---
st.set_page_config(page_title="GESTOR PRO | Enterprise", layout="wide", initial_sidebar_state="expanded")

# --- 2. CSS CORPORATIVO (LIMPO E PROFISSIONAL) ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        /* Fundo Limpo */
        .stApp {
            background-color: #F8F9FA;
            color: #1A1C1E;
            font-family: 'Inter', sans-serif;
        }

        /* Sidebar Profissional */
        [data-testid="stSidebar"] {
            background-color: #FFFFFF !important;
            border-right: 1px solid #E9ECEF;
        }

        /* Cards de Métricas (Estilo Dashboard Financeiro) */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #E9ECEF;
            border-radius: 12px;
            padding: 20px !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        }

        /* Botão de Ação (Verde Corporativo - Estilo Excel/WhatsApp) */
        div.stButton > button, div[data-testid="stForm"] button {
            background-color: #2D6A4F !important;
            color: white !important;
            border: none !important;
            border-radius: 6px !important;
            font-weight: 600 !important;
            height: 42px;
            width: 100%;
            transition: 0.2s;
        }
        div.stButton > button:hover {
            background-color: #1B4332 !important;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }

        /* Tabelas */
        [data-testid="stDataFrame"] {
            border: 1px solid #E9ECEF !important;
            border-radius: 8px !important;
        }

        /* Customização de Títulos */
        .section-title {
            color: #212529;
            font-weight: 700;
            font-size: 24px;
            margin-bottom: 20px;
        }
        
        header, footer, #MainMenu {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. LOGICA DE ACESSO ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div style='text-align: center; padding: 30px; background: white; border-radius: 15px; border: 1px solid #E9ECEF;'>
                <h2 style='color: #2D6A4F;'>GESTOR PRO</h2>
                <p style='color: #6C757D;'>Painel de Gestão de Engenharia</p>
            </div>
        """, unsafe_allow_html=True)
        with st.form("login"):
            pwd = st.text_input("Senha", type="password")
            if st.form_submit_button("Acessar Painel"):
                if pwd == st.secrets["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else: st.error("Acesso não autorizado.")
else:
    # --- 4. BACKEND ---
    @st.cache_data(ttl=60)
    def load_data():
        try:
            creds_dict = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
            client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]))
            sheet = client.open("GestorObras_DB")
            df_o = pd.DataFrame(sheet.worksheet("Obras").get_all_records())
            df_f = pd.DataFrame(sheet.worksheet("Financeiro").get_all_records())
            df_o['Valor Total'] = pd.to_numeric(df_o['Valor Total'], errors='coerce').fillna(0)
            df_f['Valor'] = pd.to_numeric(df_f['Valor'], errors='coerce').fillna(0)
            df_f['Data'] = pd.to_datetime(df_f['Data'], errors='coerce').dt.date
            return df_o, df_f, client
        except: return pd.DataFrame(), pd.DataFrame(), None

    df_obras, df_fin, connector = load_data()

    # --- 5. NAVEGAÇÃO LATERAL CLEAN ---
    with st.sidebar:
        st.markdown("<h3 style='text-align:center; color:#2D6A4F;'>GESTOR PRO</h3>", unsafe_allow_html=True)
        sel = option_menu(
            None, ["Dashboard", "Gestão de Obras", "Financeiro", "Relatórios"],
            icons=['house', 'building', 'wallet2', 'file-text'],
            menu_icon="cast", default_index=0,
            styles={
                "container": {"background-color": "#FFFFFF"},
                "nav-link": {"color": "#495057", "font-size": "14px", "text-align": "left", "margin": "5px"},
                "nav-link-selected": {"background-color": "#E9F5EE", "color": "#2D6A4F", "font-weight": "600"},
            }
        )
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- 6. PÁGINAS ---
    if sel == "Dashboard":
        st.markdown("<h1 class='section-title'>📊 Visão Geral do Negócio</h1>", unsafe_allow_html=True)
        
        if not df_obras.empty:
            obra_sel = st.selectbox("Filtrar por Obra", ["Consolidado de Obras"] + df_obras['Cliente'].tolist())
            
            df_v = df_fin.copy()
            if obra_sel != "Consolidado de Obras":
                df_v = df_fin[df_fin['Obra Vinculada'] == obra_sel]
            
            ent = df_v[df_v['Tipo'].str.contains('Entrada', na=False)]['Valor'].sum()
            sai = df_v[df_v['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Receitas Totais", f"R$ {ent:,.2f}")
            c2.metric("Despesas Totais", f"R$ {sai:,.2f}")
            c3.metric("Saldo Líquido", f"R$ {ent-sai:,.2f}")

            st.markdown("<br>", unsafe_allow_html=True)
            
            col_left, col_right = st.columns([2, 1])
            with col_left:
                df_ev = df_v[df_v['Tipo'].str.contains('Saída', na=False)].sort_values('Data')
                fig = px.line(df_ev, x='Data', y='Valor', title="Evolução de Custos", color_discrete_sequence=['#2D6A4F'])
                fig.update_layout(plot_bgcolor='white', paper_bgcolor='white')
                st.plotly_chart(fig, use_container_width=True)
            
            with col_right:
                st.markdown("##### Status da Carteira")
                fig_pie = px.pie(df_obras, names='Status', hole=0.5, color_discrete_sequence=['#2D6A4F', '#A4C3B2', '#E9F5EE'])
                fig_pie.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_pie, use_container_width=True)

    elif sel == "Gestão de Obras":
        st.markdown("<h1 class='section-title'>📁 Projetos e Contratos</h1>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["Novo Cadastro", "Lista de Projetos"])
        
        with tab1:
            with st.form("new_o"):
                c1, c2 = st.columns(2)
                cli = c1.text_input("Cliente / Obra")
                val = c2.number_input("Valor do Contrato", step=1000.0)
                if st.form_submit_button("Cadastrar Obra"):
                    connector.open("GestorObras_DB").worksheet("Obras").append_row([len(df_obras)+1, cli, "", "Em Andamento", val, str(date.today()), ""])
                    st.cache_data.clear()
                    st.rerun()
        
        with tab2:
            st.dataframe(df_obras, use_container_width=True, hide_index=True)

    elif sel == "Financeiro":
        st.markdown("<h1 class='section-title'>💸 Fluxo de Caixa</h1>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["Lançamento Manual", "Extrato Geral"])
        
        with tab1:
            with st.form("new_f"):
                c1, c2 = st.columns(2)
                tipo = c1.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
                obra_v = c1.selectbox("Vincular Obra", df_obras['Cliente'].tolist() if not df_obras.empty else ["Geral"])
                desc = c2.text_input("Descrição")
                valor = c2.number_input("Valor R$", step=10.0)
                if st.form_submit_button("Lançar"):
                    connector.open("GestorObras_DB").worksheet("Financeiro").append_row([str(date.today()), tipo, "Geral", desc, valor, obra_v])
                    st.cache_data.clear()
                    st.rerun()
        
        with tab2:
            st.dataframe(df_fin.sort_values('Data', ascending=False), use_container_width=True, hide_index=True)

    elif sel == "Relatórios":
        st.markdown("<h1 class='section-title'>📄 Relatórios e Documentos</h1>", unsafe_allow_html=True)
        st.info("Utilize os filtros do Dashboard para exportar os dados consolidados.")
