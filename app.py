import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import datetime, date
from streamlit_option_menu import option_menu
import io

# --- 1. CONFIGURAÇÃO E AUTENTICAÇÃO ---
st.set_page_config(page_title="Gestor Obras | Enterprise", layout="wide")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

def check_password():
    if not st.session_state["authenticated"]:
        _, col_central, _ = st.columns([1, 1.2, 1])
        with col_central:
            st.markdown("<br><br><br>", unsafe_allow_html=True)
            with st.container():
                st.markdown("""
                    <div style='background-color: white; padding: 40px; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); border: 1px solid #f0f0f0;'>
                        <h2 style='text-align: center; color: #1e3a8a;'>🏗️ GESTOR PRO</h2>
                        <p style='text-align: center; color: #64748b;'>Painel Administrativo</p>
                    </div>
                """, unsafe_allow_html=True)
                with st.form("login_form"):
                    pwd = st.text_input("Senha de Acesso", type="password", placeholder="••••••••")
                    if st.form_submit_button("Acessar Sistema", use_container_width=True):
                        if pwd == st.secrets["password"]:
                            st.session_state["authenticated"] = True
                            st.rerun()
                        else: st.error("⚠️ Senha inválida")
        return False
    return True

if check_password():
    # --- 2. BACKEND E CACHE ---
    @st.cache_resource
    def get_client():
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        json_creds = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
        return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(json_creds, scope))

    @st.cache_data(ttl=300)
    def load_data():
        client = get_client()
        sheet = client.open("GestorObras_DB")
        df_obras = pd.DataFrame(sheet.worksheet("Obras").get_all_records())
        df_fin = pd.DataFrame(sheet.worksheet("Financeiro").get_all_records())
        
        if not df_obras.empty:
            df_obras['Valor Total'] = pd.to_numeric(df_obras['Valor Total'], errors='coerce').fillna(0)
        if not df_fin.empty:
            df_fin['Valor'] = pd.to_numeric(df_fin['Valor'], errors='coerce').fillna(0)
            df_fin['Data'] = pd.to_datetime(df_fin['Data'], errors='coerce').dt.date
        return df_obras, df_fin

    # --- 3. ESTILIZAÇÃO CSS (INTERFACE MODERNA) ---
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
            html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
            
            .stApp { background-color: #fcfcfd; }
            
            /* Estilo dos Cards de Formulário */
            [data-testid="stForm"] {
                background-color: white !important;
                border: 1px solid #ebedef !important;
                border-radius: 15px !important;
                padding: 30px !important;
                box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
            }
            
            /* Títulos das Páginas */
            .page-title { color: #1e293b; font-weight: 700; font-size: 28px; margin-bottom: 5px; }
            .page-subtitle { color: #64748b; font-size: 16px; margin-bottom: 25px; }
            
            /* Métricas Customizadas */
            div[data-testid="stMetric"] {
                background-color: white;
                border: 1px solid #f1f5f9;
                border-radius: 12px;
                padding: 15px;
                transition: transform 0.2s;
            }
            div[data-testid="stMetric"]:hover { transform: translateY(-3px); }
        </style>
    """, unsafe_allow_html=True)

    df_obras, df_fin = load_data()

    # --- 4. SIDEBAR ---
    with st.sidebar:
        st.markdown("<div style='padding: 20px 0;'><h2 style='text-align: center; color: #1e3a8a;'>🏗️ GESTOR</h2></div>", unsafe_allow_html=True)
        menu = option_menu(
            None, ["Dashboard", "Obras", "Financeiro", "Relatórios"],
            icons=['grid-1x2', 'briefcase', 'wallet2', 'file-earmark-bar-graph'],
            menu_icon="cast", default_index=0,
            styles={
                "nav-link": {"font-size": "14px", "text-align": "left", "margin": "8px", "border-radius": "10px", "font-weight": "500"},
                "nav-link-selected": {"background-color": "#2563eb"},
            }
        )
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- 5. CONTEÚDO ---
    if menu == "Dashboard":
        st.markdown("<h1 class='page-title'>📊 Dashboard Executivo</h1>", unsafe_allow_html=True)
        st.markdown("<p class='page-subtitle'>Resumo financeiro e progresso das obras em tempo real.</p>", unsafe_allow_html=True)
        
        if not df_obras.empty:
            obra_sel = st.selectbox("Selecione uma obra para análise:", ["Todas as Obras"] + df_obras['Cliente'].tolist())
            
            df_v = df_fin.copy()
            if obra_sel != "Todas as Obras":
                df_v = df_fin[df_fin['Obra Vinculada'] == obra_sel]
            
            ent = df_v[df_v['Tipo'].str.contains('Entrada', na=False)]['Valor'].sum()
            sai = df_v[df_v['Tipo'].str.contains('
