import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from streamlit_option_menu import option_menu

# --- 1. CONFIGURAÇÃO DE ALTO NÍVEL ---
st.set_page_config(page_title="GESTOR PRO | Signature Edition", layout="wide", initial_sidebar_state="expanded")

# --- 2. CSS SIGNATURE (O ACABAMENTO DE LUXO) ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap');
        
        /* Fundo e Tipografia */
        .stApp { 
            background: linear-gradient(135deg, #0f172a 0%, #020617 100%); 
            color: #f8fafc; 
            font-family: 'Plus Jakarta Sans', sans-serif; 
        }
        
        /* Efeito de Vidro na Sidebar */
        [data-testid="stSidebar"] {
            background-color: rgba(15, 23, 42, 0.7) !important;
            backdrop-filter: blur(15px);
            border-right: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        /* Cards de Métricas Estilo Premium */
        div[data-testid="stMetric"] {
            background: rgba(30, 41, 59, 0.5);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 25px !important;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        }
        
        /* Botões Signature (Verde Neon Profissional) */
        div.stButton > button, div[data-testid="stForm"] button {
            background: linear-gradient(135deg, #22c55e 0%, #15803d 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 12px !important;
            font-weight: 700 !important;
            letter-spacing: 0.5px;
            height: 50px;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        div.stButton > button:hover {
            transform: scale(1.02);
            box-shadow: 0 0 20px rgba(34, 197, 94, 0.4);
        }

        /* Inputs Estilizados */
        input, select, textarea, div[data-baseweb="select"] {
            background-color: #1e293b !important;
            border-radius: 10px !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            color: white !important;
        }

        /* Títulos de Página */
        .main-title {
            font-size: 38px;
            font-weight: 800;
            background: linear-gradient(90deg, #f8fafc, #94a3b8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 30px;
        }
        
        #MainMenu, footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. AUTENTICAÇÃO ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

def screen_login():
    _, col, _ = st.columns([1, 1.3, 1])
    with col:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div style='text-align: center; padding: 40px; border-radius: 30px; background: rgba(30,41,59,0.5); border: 1px solid rgba(255,255,255,0.1);'>
                <h1 style='color: white; margin-bottom: 0;'>GESTOR PRO</h1>
                <p style='color: #94a3b8;'>Signature Access</p>
            </div>
        """, unsafe_allow_html=True)
        with st.form("login"):
            pwd = st.text_input("PASSWORD", type="password")
            if st.form_submit_button("AUTHENTICATE"):
                if pwd == st.secrets["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else: st.error("Acesso Negado")

if not st.session_state["authenticated"]:
    screen_login()
else:
    # --- 4. DATA ENGINE ---
    @st.cache_resource
    def get_connector():
        creds_dict = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
        return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]))

    @st.cache_data(ttl=60)
    def load_elite_data():
        try:
            client = get_connector()
            sheet = client.open("GestorObras_DB")
            df_o = pd.DataFrame(sheet.worksheet("Obras").get_all_records())
            df_f = pd.DataFrame(sheet.worksheet("Financeiro").get_all_records())
            df_o['Valor Total'] = pd.to_numeric(df_o['Valor Total'], errors='coerce').fillna(0)
            df_f['Valor'] = pd.to_numeric(df_f['Valor'], errors='coerce').fillna(0)
            df_f['Data'] = pd.to_datetime(df_f['Data'], errors='coerce').dt.date
            return df_o, df_f
        except: return pd.DataFrame(), pd.DataFrame()

    df_obras, df_fin = load_elite_data()

    # --- 5. NAVEGAÇÃO LATERAL (OPTION MENU) ---
    with st.sidebar:
        st.markdown("<div style='text-align: center; margin-bottom: 30px;'><h1 style='color: #22c55e; font-size: 24px;'>GESTOR PRO</h1></div>", unsafe_allow_html=True)
        sel = option_menu(
            None, ["Insights", "Projetos", "Fluxo de Caixa", "Relatórios"],
            icons=['command', 'layout-text-sidebar-reverse', 'wallet2', 'journal-text'],
            menu_icon="cast", default_index=0,
            styles={
                "container": {"background-color": "transparent"},
                "nav-link": {"color": "#94a3b8", "font-size": "15px", "text-align": "left", "margin": "10px", "border-radius": "12px", "padding": "12px"},
                "nav-link-selected": {"background-color": "#22c55e", "color": "white", "font-weight": "700"},
            }
        )
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("🚪 LOGOUT"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- 6. TELAS ---
    if sel == "Insights":
        st.markdown("<h1 class='main-title'>📈 Inteligência de Negócio</h1>", unsafe_allow_html=True)
        
        if not df_obras.empty:
            obra_sel = st.selectbox("Unidade de Negócio", ["Consolidado"] + df_obras['Cliente'].tolist())
            
            df_v = df_fin.copy()
            if obra_sel != "Consolidado":
                df_v = df_fin[df_fin['Obra Vinculada'] == obra_sel]
            
            e = df_v[df_v['Tipo'].str.contains('Entrada', na=False)]['Valor'].sum()
            s = df_v[df_v['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
            
            c1, c2, c3 = st.columns(3)
            with c1: st.metric("RECEITA BRUTA", f"R$ {e:,.2f}")
            with c2: st.metric("CUSTOS TOTAIS", f"R$ {s:,.2f}")
            with c3: st.metric("MARGEM LÍQUIDA", f"R$ {e-s:,.2f}")
            
            st.markdown("<br>", unsafe_allow_html=True)
            col_left, col_right = st.columns([2, 1])
            
            with col_left:
                df_ev = df_v[df_v['Tipo'].str.contains('Saída', na=False)].sort_values('Data')
                fig = px.area(df_ev, x='Data', y='Valor', title="Evolução de Desembolso", color_discrete_sequence=['#22c55e'])
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="#f8fafc"))
                st.plotly_chart(fig, use_container_width=True)
            
            with col_right:
                # Indicador de Performance (Bullet)
                st.markdown("<div style='background: rgba(30,41,59,0.5); padding: 20px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.1);'>", unsafe_allow_html=True)
                st.write("📊 Saúde Financeira")
                perc = (e-s)/e*100 if e > 0 else 0
                st.progress(max(min(perc/100, 1.0), 0.0))
                st.write(f"Margem: {perc:.1f}%")
                st.markdown("</div>", unsafe_allow_html=True)

    elif sel == "Projetos":
        st.markdown("<h1 class='main-title'>📁 Portfólio de Obras</h1>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["📝 Novo Projeto", "🔍 Lista de Obras"])
        
        with t1:
            with st.form("new_signature_o"):
                c1, c2 = st.columns(2)
                cli = c1.text_input("Identificação do Cliente")
                val = c2.number_input("Valor de Contrato (R$)", step=1000.0)
                if st.form_submit_button("REGISTRAR NA BASE SIGNATURE"):
                    get_connector().open("GestorObras_DB").worksheet("Obras").append_row([len(df_obras)+1, cli, "", "Ativo", val, str(date.today()), ""])
                    st.cache_data.clear()
                    st.rerun()
        
        with t2:
            st.dataframe(df_obras, use_container_width=True, hide_index=True)

    elif sel == "Fluxo de Caixa":
        st.markdown("<h1 class='main-title'>💸 Movimentação Financeira</h1>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["💰 Lançar Operação", "🧾 Extrato Detalhado"])
        
        with t1:
            with st.form("new_signature_f"):
                c1, c2 = st.columns(2)
                tipo = c1.selectbox("Tipo de Operação", ["Saída (Despesa)", "Entrada"])
                obra_v = c1.selectbox("Obra Referência", df_obras['Cliente'].tolist() if not df_obras.empty else ["Geral"])
                desc = c2.text_input("Descrição / Finalidade")
                valor = c2.number_input("Valor da Transação", step=10.0)
                if st.form_submit_button("EFETIVAR LANÇAMENTO"):
                    get_connector().open("GestorObras_DB").worksheet("Financeiro").append_row([str(date.today()), tipo, "Geral", desc, valor, obra_v])
                    st.cache_data.clear()
                    st.rerun()
        
        with t2:
            st.dataframe(df_fin.sort_values('Data', ascending=False), use_container_width=True, hide_index=True)

    elif sel == "Relatórios":
        st.markdown("<h1 class='main-title'>📄 Central de Inteligência</h1>", unsafe_allow_html=True)
        st.markdown("""
            <div style='background: rgba(30,41,59,0.5); padding: 50px; border-radius: 30px; text-align: center; border: 1px dashed rgba(255,255,255,0.2);'>
                <h2 style='color: #22c55e;'>Geração de Relatório Consolidado</h2>
                <p>O sistema está pronto para compilar as métricas selecionadas no Dashboard em um documento técnico PDF.</p>
            </div>
        """, unsafe_allow_html=True)
