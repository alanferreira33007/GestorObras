import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import datetime, date
from streamlit_option_menu import option_menu

# --- 1. CONFIGURAÇÃO DE UI RADICAL ---
st.set_page_config(page_title="GESTOR PRO | Architect", layout="wide", initial_sidebar_state="collapsed")

# --- 2. CSS DE ALTO NÍVEL (CONSTRUINDO O APP DO ZERO) ---
st.markdown("""
    <style>
        /* Importação de Fonte Google */
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
        
        /* Fundo e Container Principal */
        .stApp {
            background-color: #050505;
            color: #E0E0E0;
            font-family: 'Outfit', sans-serif;
        }

        /* Removendo Padding Desnecessário */
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 0rem !important;
        }

        /* ESTILIZAÇÃO DOS WIDGETS (CARDS) */
        .metric-card {
            background: rgba(20, 20, 20, 0.8);
            border: 1px solid #222;
            border-radius: 20px;
            padding: 24px;
            text-align: left;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5);
            transition: 0.4s;
        }
        .metric-card:hover {
            border-color: #10b981;
            transform: translateY(-5px);
        }

        /* BOTÕES DE AÇÃO (ULTRA MODERNOS) */
        div.stButton > button, div[data-testid="stForm"] button {
            background: #10b981 !important;
            color: #000 !important;
            border: none !important;
            border-radius: 12px !important;
            font-weight: 700 !important;
            font-size: 14px !important;
            letter-spacing: 1px;
            height: 48px;
            text-transform: uppercase;
            box-shadow: 0 0 20px rgba(16, 185, 129, 0.2);
        }
        div.stButton > button:hover {
            background: #34d399 !important;
            box-shadow: 0 0 30px rgba(16, 185, 129, 0.4);
        }

        /* TABELAS E DATAFRAMES */
        [data-testid="stDataFrame"] {
            background: #0A0A0A !important;
            border: 1px solid #222 !important;
            border-radius: 15px !important;
        }

        /* SIDEBAR CUSTOMIZADA */
        [data-testid="stSidebar"] {
            background-color: #000000 !important;
            border-right: 1px solid #111;
        }
        
        /* Ocultar elementos nativos do Streamlit */
        header, footer, #MainMenu {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. LOGICA DE ACESSO ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("<br><br><br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div style='background: #0A0A0A; padding: 50px; border-radius: 30px; border: 1px solid #222; text-align: center;'>
                <h1 style='color: #10b981; font-weight: 800; font-size: 40px;'>GESTOR PRO</h1>
                <p style='color: #666;'>SISTEMA DE GESTÃO DE OBRAS DE ELITE</p>
            </div>
        """, unsafe_allow_html=True)
        with st.form("login"):
            pwd = st.text_input("PASSWORD", type="password")
            if st.form_submit_button("AUTHENTICATE"):
                if pwd == st.secrets["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else: st.error("Acesso Negado")
else:
    # --- 4. BACKEND ---
    @st.cache_data(ttl=60)
    def load_elite_data():
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

    df_obras, df_fin, connector = load_elite_data()

    # --- 5. MENU DE NAVEGAÇÃO SUPERIOR (DENTRO DA SIDEBAR) ---
    with st.sidebar:
        st.markdown("<h2 style='text-align:center; color:#10b981;'>CONTROL</h2>", unsafe_allow_html=True)
        sel = option_menu(
            None, ["Insights", "Projetos", "Financeiro", "Relatórios"],
            icons=['cpu-fill', 'grid-3x3-gap-fill', 'wallet-fill', 'file-earmark-text-fill'],
            menu_icon="cast", default_index=0,
            styles={
                "container": {"background-color": "transparent"},
                "nav-link": {"color": "#666", "font-size": "14px", "text-align": "left", "margin": "10px", "border-radius": "10px"},
                "nav-link-selected": {"background-color": "#111", "color": "#10b981", "font-weight": "800", "border": "1px solid #10b981"},
            }
        )
        if st.button("LOGOUT"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- 6. PÁGINAS ---
    if sel == "Insights":
        st.markdown("<h1 style='font-weight: 800; font-size: 42px;'>ESTATÍSTICAS REAIS</h1>", unsafe_allow_html=True)
        
        if not df_obras.empty:
            # Widget de Seleção Moderno
            obra_sel = st.selectbox("Unidade de Negócio", ["Consolidado Global"] + df_obras['Cliente'].tolist())
            
            df_v = df_fin.copy()
            if obra_sel != "Consolidado Global":
                df_v = df_fin[df_fin['Obra Vinculada'] == obra_sel]
            
            ent = df_v[df_v['Tipo'].str.contains('Entrada', na=False)]['Valor'].sum()
            sai = df_v[df_v['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
            
            # GRID DE MÉTRICAS CUSTOMIZADAS
            m1, m2, m3 = st.columns(3)
            with m1:
                st.markdown(f"<div class='metric-card'><small>TOTAL RECEBIDO</small><br><h2 style='color:#10b981;'>R$ {ent:,.2f}</h2></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='metric-card'><small>CUSTO OPERACIONAL</small><br><h2 style='color:#EF4444;'>R$ {sai:,.2f}</h2></div>", unsafe_allow_html=True)
            with m3:
                st.markdown(f"<div class='metric-card'><small>MARGEM LÍQUIDA</small><br><h2 style='color:#3B82F6;'>R$ {ent-sai:,.2f}</h2></div>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            
            # Gráficos com Estilo Glassmorphism
            col_left, col_right = st.columns([2, 1])
            with col_left:
                df_ev = df_v[df_v['Tipo'].str.contains('Saída', na=False)].sort_values('Data')
                fig = px.area(df_ev, x='Data', y='Valor', title="Evolução de Gastos", color_discrete_sequence=['#10b981'])
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="#666"))
                st.plotly_chart(fig, use_container_width=True)
            
            with col_right:
                st.markdown("<div class='metric-card' style='height: 380px;'>", unsafe_allow_html=True)
                st.write("📊 STATUS DOS PROJETOS")
                fig_pie = px.pie(df_obras, names='Status', hole=0.7, color_discrete_sequence=['#10b981', '#3B82F6', '#EF4444'])
                fig_pie.update_layout(showlegend=False, paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_pie, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

    elif sel == "Projetos":
        st.markdown("<h1 style='font-weight: 800;'>CONTROLE DE OBRAS</h1>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["[ NOVO REGISTRO ]", "[ LISTA DE ATIVOS ]"])
        
        with tab1:
            with st.form("new_o_pro"):
                c1, c2 = st.columns(2)
                cli = c1.text_input("IDENTIFICAÇÃO DO PROJETO")
                val = c2.number_input("VALOR TOTAL DO CONTRATO", step=1000.0)
                if st.form_submit_button("REGISTRAR PROJETO"):
                    connector.open("GestorObras_DB").worksheet("Obras").append_row([len(df_obras)+1, cli, "", "Ativo", val, str(date.today()), ""])
                    st.cache_data.clear()
                    st.rerun()
        
        with tab2:
            st.dataframe(df_obras, use_container_width=True, hide_index=True)

    elif sel == "Financeiro":
        st.markdown("<h1 style='font-weight: 800;'>CONTROLE DE CAIXA</h1>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["[ LANÇAR MOVIMENTAÇÃO ]", "[ HISTÓRICO DE EXTRATO ]"])
        
        with tab1:
            with st.form("new_f_pro"):
                c1, c2 = st.columns(2)
                tipo = c1.selectbox("TIPO", ["Saída (Despesa)", "Entrada"])
                obra_v = c1.selectbox("OBRA", df_obras['Cliente'].tolist() if not df_obras.empty else ["Geral"])
                desc = c2.text_input("DESCRIÇÃO")
                valor = c2.number_input("VALOR", step=10.0)
                if st.form_submit_button("EFETUAR LANÇAMENTO"):
                    connector.open("GestorObras_DB").worksheet("Financeiro").append_row([str(date.today()), tipo, "Geral", desc, valor, obra_v])
                    st.cache_data.clear()
                    st.rerun()
        
        with tab2:
            st.dataframe(df_fin.sort_values('Data', ascending=False), use_container_width=True, hide_index=True)

    elif sel == "Relatórios":
        st.markdown("<h1 style='font-weight: 800;'>CENTRAL DE RELATÓRIOS</h1>", unsafe_allow_html=True)
        st.markdown("""
            <div style='background: #0A0A0A; padding: 100px; border-radius: 30px; border: 1px dashed #222; text-align: center;'>
                <h3 style='color: #10b981;'>GERADOR DE PDF TÉCNICO</h3>
                <p style='color: #666;'>O sistema está pronto para compilar os dados do Dashboard.</p>
            </div>
        """, unsafe_allow_html=True)
