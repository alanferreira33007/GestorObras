import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import datetime, date
from streamlit_option_menu import option_menu

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestor PRO | Alta Visibilidade", layout="wide")

# --- 2. CSS DE ALTO CONTRASTE ---
st.markdown("""
    <style>
        /* Fundo Grafite Profundo */
        .stApp {
            background: #0f172a;
            color: #FFFFFF !important;
        }
        
        /* Forçar TUDO que é texto para Branco ou Azul Claro */
        h1, h2, h3, h4, h5, h6, p, label, .stMarkdown {
            color: #FFFFFF !important;
            font-family: 'Inter', sans-serif;
        }

        /* Ajuste da Barra Lateral */
        [data-testid="stSidebar"] {
            background-color: #1e293b !important;
            border-right: 2px solid #334155;
        }
        
        /* Ajuste de Inputs (onde você escreve) */
        .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div>div {
            background-color: #1e293b !important;
            color: #FFFFFF !important;
            border: 1px solid #3b82f6 !important;
        }

        /* MÉTRICAS (KPIs) - Fundo mais escuro com borda brilhante para destacar o texto branco */
        div[data-testid="stMetric"] {
            background: #1e293b !important;
            border: 2px solid #334155 !important;
            border-radius: 12px;
            padding: 20px;
        }
        
        /* Texto das Métricas */
        div[data-testid="stMetricValue"] > div {
            color: #FFFFFF !important;
            font-weight: 800 !important;
        }
        
        /* Tabelas (Dataframes) - Forçar visibilidade das células */
        .stDataFrame div[data-testid="stTable"] td {
            color: #FFFFFF !important;
        }
        
        /* Botão Primário */
        .stButton>button {
            background: #2563eb !important;
            color: #FFFFFF !important;
            font-weight: bold;
            border: none;
            width: 100%;
        }

        #MainMenu, footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. LÓGICA DE LOGIN ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center;'>🏗️ GESTOR PRO</h1>", unsafe_allow_html=True)
        with st.form("login"):
            pwd = st.text_input("Senha de Acesso", type="password")
            if st.form_submit_button("ENTRAR"):
                if pwd == st.secrets["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else: st.error("Senha Incorreta")
else:
    # --- 4. DATA BACKEND ---
    @st.cache_resource
    def get_client():
        json_creds = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
        return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(json_creds, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]))

    @st.cache_data(ttl=60)
    def load_data():
        try:
            client = get_client()
            db = client.open("GestorObras_DB")
            df_o = pd.DataFrame(db.worksheet("Obras").get_all_records())
            df_f = pd.DataFrame(db.worksheet("Financeiro").get_all_records())
            df_o['Valor Total'] = pd.to_numeric(df_o['Valor Total'], errors='coerce').fillna(0)
            df_f['Valor'] = pd.to_numeric(df_f['Valor'], errors='coerce').fillna(0)
            df_f['Data'] = pd.to_datetime(df_f['Data'], errors='coerce').dt.date
            return df_o, df_f
        except: return pd.DataFrame(), pd.DataFrame()

    df_obras, df_fin = load_data()

    # --- 5. NAVEGAÇÃO LATERAL ---
    with st.sidebar:
        st.markdown("<h3 style='text-align: center; color: #3b82f6 !important;'>MENU PRINCIPAL</h3>", unsafe_allow_html=True)
        sel = option_menu(
            None, ["Insights", "Obras", "Financeiro", "Relatórios"],
            icons=['graph-up-arrow', 'building', 'currency-dollar', 'file-pdf'],
            menu_icon="cast", default_index=0,
            styles={
                "container": {"background-color": "#1e293b"},
                "nav-link": {"color": "#FFFFFF", "font-size": "14px", "text-align": "left", "margin": "5px"},
                "nav-link-selected": {"background-color": "#3b82f6", "font-weight": "bold"},
            }
        )
        if st.button("SAIR"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- 6. TELAS ---
    if sel == "Insights":
        st.markdown("<h1 style='color: #FFFFFF !important;'>📊 Dashboard de Desempenho</h1>", unsafe_allow_html=True)
        
        if not df_obras.empty:
            obra = st.selectbox("Escolha a Obra", ["Todas"] + df_obras['Cliente'].tolist())
            df_v = df_fin.copy()
            if obra != "Todas": df_v = df_fin[df_fin['Obra Vinculada'] == obra]
            
            e = df_v[df_v['Tipo'].str.contains('Entrada', na=False)]['Valor'].sum()
            s = df_v[df_v['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("FATURAMENTO", f"R$ {e:,.2f}")
            c2.metric("GASTOS", f"R$ {s:,.2f}")
            c3.metric("RESULTADO", f"R$ {e-s:,.2f}")
            
            st.markdown("<br>", unsafe_allow_html=True)
            df_ev = df_v[df_v['Tipo'].str.contains('Saída', na=False)].sort_values('Data')
            fig = px.area(df_ev, x='Data', y='Valor', title="Evolução Financeira", template="plotly_dark")
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("Cadastre dados para visualizar.")

    elif sel == "Obras":
        st.markdown("<h1>📁 Gestão de Projetos</h1>", unsafe_allow_html=True)
        col1, col2 = st.columns([1, 2])
        with col1:
            with st.form("new_o"):
                st.write("### Nova Obra")
                cli = st.text_input("Cliente")
                val = st.number_input("Valor", step=1000.0)
                if st.form_submit_button("SALVAR"):
                    get_client().open("GestorObras_DB").worksheet("Obras").append_row([len(df_obras)+1, cli, "", "Ativa", val, str(date.today()), ""])
                    st.cache_data.clear()
                    st.rerun()
        with col2:
            st.write("### Lista de Contratos")
            st.dataframe(df_obras, use_container_width=True)

    elif sel == "Financeiro":
        st.markdown("<h1>💸 Movimentação de Caixa</h1>", unsafe_allow_html=True)
        col1, col2 = st.columns([1, 2])
        with col1:
            with st.form("new_f"):
                st.write("### Lançamento")
                tipo = st.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
                obra_v = st.selectbox("Obra", df_obras['Cliente'].tolist() if not df_obras.empty else ["Geral"])
                desc = st.text_input("Descrição")
                valor = st.number_input("Valor", step=10.0)
                if st.form_submit_button("LANÇAR"):
                    get_client().open("GestorObras_DB").worksheet("Financeiro").append_row([str(date.today()), tipo, "Geral", desc, valor, obra_v])
                    st.cache_data.clear()
                    st.rerun()
        with col2:
            st.write("### Histórico")
            st.dataframe(df_fin.sort_values('Data', ascending=False), use_container_width=True)

    elif sel == "Relatórios":
        st.markdown("<h1>📄 Documentos e Exportação</h1>", unsafe_allow_html=True)
        st.info("Selecione a obra no Dashboard para visualizar os dados consolidados para o relatório.")
