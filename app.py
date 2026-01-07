import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import datetime, date
from streamlit_option_menu import option_menu

# --- 1. CONFIGURAÇÃO DE ALTO NÍVEL ---
st.set_page_config(page_title="Gestor PRO | Ultra Premium", layout="wide")

# --- 2. CSS AVANÇADO (CUSTOM UI) ---
st.markdown("""
    <style>
        /* Fundo Geral Dark */
        .stApp {
            background: radial-gradient(circle at top left, #1e293b, #0f172a);
            color: #f8fafc;
        }
        
        /* Títulos e Textos */
        h1, h2, h3, p { font-family: 'Inter', sans-serif; color: #f8fafc !important; }
        
        /* Sidebar Customizada */
        [data-testid="stSidebar"] {
            background-color: rgba(15, 23, 42, 0.9) !important;
            border-right: 1px solid rgba(255, 255, 255, 0.1);
        }

        /* Estilo dos Cards de Métricas (Glassmorphism) */
        div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 20px;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
        }
        div[data-testid="stMetric"]:hover {
            border: 1px solid #3b82f6;
            transform: translateY(-5px);
            background: rgba(59, 130, 246, 0.05);
        }

        /* Botões Estilizados */
        .stButton>button {
            background: linear-gradient(90deg, #2563eb, #3b82f6);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 10px 20px;
            font-weight: 600;
            width: 100%;
            transition: all 0.3s;
        }
        .stButton>button:hover {
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.5);
            transform: scale(1.02);
        }

        /* Tabelas e Dataframes */
        .stDataFrame {
            background: rgba(255, 255, 255, 0.02);
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        #MainMenu, footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. LOGICA DE ACESSO ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

def login_screen():
    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div style='text-align: center; padding: 30px; border-radius: 20px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);'>
                <h1 style='font-size: 40px;'>🏗️</h1>
                <h2 style='margin-bottom: 0;'>GESTOR PRO</h2>
                <p style='color: #94a3b8;'>Engineering Intelligence</p>
            </div>
        """, unsafe_allow_html=True)
        with st.form("login"):
            pwd = st.text_input("Acesso Administrativo", type="password")
            if st.form_submit_button("DESBLOQUEAR SISTEMA"):
                if pwd == st.secrets["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else: st.error("Chave incorreta.")

if not st.session_state["authenticated"]:
    login_screen()
else:
    # --- 4. DATA BACKEND ---
    @st.cache_resource
    def get_sheet_client():
        json_creds = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
        return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(json_creds, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]))

    @st.cache_data(ttl=300)
    def load_data():
        try:
            client = get_sheet_client()
            db = client.open("GestorObras_DB")
            df_o = pd.DataFrame(db.worksheet("Obras").get_all_records())
            df_f = pd.DataFrame(db.worksheet("Financeiro").get_all_records())
            df_o['Valor Total'] = pd.to_numeric(df_o['Valor Total'], errors='coerce').fillna(0)
            df_f['Valor'] = pd.to_numeric(df_f['Valor'], errors='coerce').fillna(0)
            df_f['Data'] = pd.to_datetime(df_f['Data'], errors='coerce').dt.date
            return df_o, df_f
        except: return pd.DataFrame(), pd.DataFrame()

    df_obras, df_fin = load_data()

    # --- 5. NAVEGAÇÃO ---
    with st.sidebar:
        st.markdown("<h2 style='text-align: center; letter-spacing: 2px;'>GESTOR</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; font-size: 10px; color: #3b82f6;'>ENTERPRISE v9.0</p>", unsafe_allow_html=True)
        
        sel = option_menu(
            None, ["Insights", "Projetos", "Caixa", "Docs"],
            icons=['lightning-charge', 'stack', 'safe2', 'file-pdf'],
            default_index=0,
            styles={
                "container": {"background-color": "transparent"},
                "nav-link": {"color": "#94a3b8", "font-size": "14px", "text-align": "left", "margin": "10px", "border-radius": "12px"},
                "nav-link-selected": {"background-color": "#2563eb", "color": "white", "font-weight": "bold"},
            }
        )
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        if st.button("LOGOUT"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- 6. TELAS ---
    if sel == "Insights":
        st.markdown("<h1 style='font-size: 2.5rem; font-weight: 800;'>📊 Insights do Negócio</h1>", unsafe_allow_html=True)
        
        if not df_obras.empty:
            obra = st.selectbox("Filtro de Unidade", ["Consolidado"] + df_obras['Cliente'].tolist())
            df_v = df_fin.copy()
            if obra != "Consolidado": df_v = df_fin[df_fin['Obra Vinculada'] == obra]
            
            e = df_v[df_v['Tipo'].str.contains('Entrada', na=False)]['Valor'].sum()
            s = df_v[df_v['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("FATURAMENTO", f"R$ {e:,.2f}", delta="Bruto")
            c2.metric("CUSTOS OPERACIONAIS", f"R$ {s:,.2f}", delta="- Negativo", delta_color="inverse")
            c3.metric("LUCRO LÍQUIDO", f"R$ {e-s:,.2f}", delta=f"{((e-s)/e*100 if e>0 else 0):.1f}% Margem")
            
            st.markdown("<br>", unsafe_allow_html=True)
            col_g1, col_g2 = st.columns([2, 1])
            
            with col_g1:
                df_ev = df_v[df_v['Tipo'].str.contains('Saída', na=False)].sort_values('Data')
                fig = px.area(df_ev, x='Data', y='Valor', title="Evolução de Custos", color_discrete_sequence=['#3b82f6'])
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))
                st.plotly_chart(fig, use_container_width=True)
            
            with col_g2:
                fig_pie = px.pie(df_obras, names='Status', values='Valor Total', hole=0.7, title="Distribuição de Status")
                fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"), showlegend=False)
                st.plotly_chart(fig_pie, use_container_width=True)

    elif sel == "Projetos":
        st.markdown("<h1>📁 Portfólio de Obras</h1>", unsafe_allow_html=True)
        col_in, col_ls = st.columns([1, 2])
        with col_in:
            with st.form("new_o"):
                st.markdown("### Novo Contrato")
                cli = st.text_input("Cliente")
                val = st.number_input("Valor R$", step=1000.0)
                if st.form_submit_button("REGISTRAR OBRA"):
                    get_sheet_client().open("GestorObras_DB").worksheet("Obras").append_row([len(df_obras)+1, cli, "", "Ativa", val, str(date.today()), ""])
                    st.cache_data.clear()
                    st.rerun()
        with col_ls:
            st.dataframe(df_obras, use_container_width=True)

    elif sel == "Caixa":
        st.markdown("<h1>💸 Movimentação Financeira</h1>", unsafe_allow_html=True)
        col_f, col_t = st.columns([1, 2])
        with col_f:
            with st.form("new_f"):
                st.markdown("### Lançamento")
                tipo = st.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
                obra_v = st.selectbox("Obra", df_obras['Cliente'].tolist() if not df_obras.empty else ["Geral"])
                desc = st.text_input("Descrição")
                valor = st.number_input("Valor", step=10.0)
                if st.form_submit_button("LANÇAR NO CAIXA"):
                    get_sheet_client().open("GestorObras_DB").worksheet("Financeiro").append_row([str(date.today()), tipo, "Geral", desc, valor, obra_v])
                    st.cache_data.clear()
                    st.rerun()
        with col_t:
            st.dataframe(df_fin.sort_values('Data', ascending=False), use_container_width=True)

    elif sel == "Docs":
        st.markdown("<h1>📄 Central de Documentos</h1>", unsafe_allow_html=True)
        st.markdown("<div style='padding: 50px; border: 1px dashed rgba(255,255,255,0.2); border-radius: 20px; text-align: center;'>Selecione uma obra para gerar o relatório consolidado em PDF.</div>", unsafe_allow_html=True)
