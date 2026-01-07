import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import datetime, date
from streamlit_option_menu import option_menu

# --- 1. CONFIGURAÇÃO (FORÇAR TEMA DARK) ---
st.set_page_config(page_title="Gestor PRO | Final Fix", layout="wide")

# --- 2. CSS AGRESSIVO PARA BOTÕES E CONTRASTE ---
st.markdown("""
    <style>
        /* Fundo e Texto Geral */
        .stApp {
            background-color: #0f172a !important;
            color: #FFFFFF !important;
        }

        /* 🟢 BOTÕES: FORÇAR VERDE COM TEXTO BRANCO 🟢 */
        /* Aplicar em todos os botões, inclusive dentro de forms */
        div.stButton > button, div[data-testid="stForm"] button {
            background-color: #28a745 !important;
            color: #FFFFFF !important;
            border: 2px solid #28a745 !important;
            font-weight: bold !important;
            font-size: 16px !important;
            text-transform: uppercase !important;
            width: 100% !important;
            height: 45px !important;
            opacity: 1 !important;
            visibility: visible !important;
        }

        /* Garantir que o texto do botão seja branco mesmo no HOVER */
        div.stButton > button:hover, div[data-testid="stForm"] button:hover {
            background-color: #218838 !important;
            color: #FFFFFF !important;
            border-color: #FFFFFF !important;
        }

        /* ⚪ CORREÇÃO DE INPUTS (ONDE ESCREVE) ⚪ */
        input, select, textarea {
            color: #FFFFFF !important;
            background-color: #1e293b !important;
        }

        /* Labels (Nomes dos campos) */
        label {
            color: #FFFFFF !important;
            font-weight: bold !important;
        }

        /* Tabelas */
        [data-testid="stTable"] {
            color: #FFFFFF !important;
            background-color: #1e293b !important;
        }
        
        /* Sidebar */
        [data-testid="stSidebar"] {
            background-color: #1e293b !important;
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
        st.markdown("<h1 style='text-align: center; color: white;'>🏗️ GESTOR PRO</h1>", unsafe_allow_html=True)
        with st.form("login"):
            # O Enter vai funcionar aqui
            pwd = st.text_input("SENHA DE ACESSO", type="password")
            if st.form_submit_button("ENTRAR NO SISTEMA"):
                if pwd == st.secrets["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else: st.error("Senha incorreta.")
else:
    # --- 4. BACKEND ---
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

    # --- 5. MENU LATERAL ---
    with st.sidebar:
        st.markdown("<h3 style='text-align: center; color: #3b82f6;'>GESTOR PRO</h3>", unsafe_allow_html=True)
        sel = option_menu(
            None, ["Insights", "Obras", "Financeiro", "Relatórios"],
            icons=['graph-up-arrow', 'building', 'currency-dollar', 'file-pdf'],
            menu_icon="cast", default_index=0,
            styles={
                "container": {"background-color": "#1e293b"},
                "nav-link": {"color": "white", "font-size": "14px", "text-align": "left"},
                "nav-link-selected": {"background-color": "#3b82f6"},
            }
        )
        st.markdown("---")
        if st.button("🚪 SAIR"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- 6. CONTEÚDO ---
    if sel == "Insights":
        st.title("📊 Painel de Desempenho")
        if not df_obras.empty:
            obra = st.selectbox("Filtrar Obra", ["Todas"] + df_obras['Cliente'].tolist())
            df_v = df_fin.copy()
            if obra != "Todas": df_v = df_fin[df_fin['Obra Vinculada'] == obra]
            
            ent = df_v[df_v['Tipo'].str.contains('Entrada', na=False)]['Valor'].sum()
            sai = df_v[df_v['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("FATURAMENTO", f"R$ {ent:,.2f}")
            c2.metric("GASTOS", f"R$ {sai:,.2f}")
            c3.metric("LUCRO", f"R$ {ent-sai:,.2f}")
            
            st.markdown("<br>", unsafe_allow_html=True)
            df_ev = df_v[df_v['Tipo'].str.contains('Saída', na=False)].sort_values('Data')
            fig = px.area(df_ev, x='Data', y='Valor', title="Fluxo de Custos", template="plotly_dark")
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)

    elif sel == "Obras":
        st.title("📁 Projetos")
        col1, col2 = st.columns([1, 2])
        with col1:
            with st.form("new_o"):
                st.write("### Cadastrar Obra")
                cli = st.text_input("Cliente")
                val = st.number_input("Valor", step=1000.0)
                if st.form_submit_button("SALVAR OBRA"):
                    get_client().open("GestorObras_DB").worksheet("Obras").append_row([len(df_obras)+1, cli, "", "Ativa", val, str(date.today()), ""])
                    st.cache_data.clear()
                    st.rerun()
        with col2:
            st.dataframe(df_obras, use_container_width=True)

    elif sel == "Financeiro":
        st.title("💸 Caixa")
        col1, col2 = st.columns([1, 2])
        with col1:
            with st.form("new_f"):
                st.write("### Lançamento")
                tipo = st.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
                obra_v = st.selectbox("Obra", df_obras['Cliente'].tolist() if not df_obras.empty else ["Geral"])
                desc = st.text_input("Descrição")
                valor = st.number_input("Valor", step=10.0)
                if st.form_submit_button("LANÇAR AGORA"):
                    get_client().open("GestorObras_DB").worksheet("Financeiro").append_row([str(date.today()), tipo, "Geral", desc, valor, obra_v])
                    st.cache_data.clear()
                    st.rerun()
        with col2:
            st.dataframe(df_fin.sort_values('Data', ascending=False), use_container_width=True)

    elif sel == "Relatórios":
        st.title("📄 Relatórios")
        st.write("Relatórios disponíveis conforme dados do Dashboard.")
