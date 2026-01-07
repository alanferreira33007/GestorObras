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
st.set_page_config(page_title="Gestor Obras | Elite Edition", layout="wide", initial_sidebar_state="expanded")

# --- 2. CSS CUSTOMIZADO (DESIGN PREMIUM DARK) ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        
        /* Base e Fundo */
        .stApp { background-color: #0b0e14; color: #ffffff; font-family: 'Inter', sans-serif; }
        
        /* Cards de Métricas Estilizados */
        div[data-testid="stMetric"] {
            background: linear-gradient(145deg, #161b22, #0d1117);
            border: 1px solid #30363d;
            border-radius: 16px;
            padding: 25px !important;
            box-shadow: 0 8px 16px rgba(0,0,0,0.4);
        }
        
        /* Botões Estilo "Elite" (Verde Esmeralda) */
        div.stButton > button, div[data-testid="stForm"] button {
            background: linear-gradient(90deg, #10b981, #059669) !important;
            color: white !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 800 !important;
            text-transform: uppercase;
            letter-spacing: 1px;
            height: 48px;
            transition: 0.3s all;
        }
        div.stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(16, 185, 129, 0.3);
        }

        /* Tabelas e Dataframes */
        .stDataFrame { border: 1px solid #30363d; border-radius: 12px; }

        /* Sidebar Customizada */
        [data-testid="stSidebar"] { background-color: #0d1117 !important; border-right: 1px solid #30363d; }
        
        #MainMenu, footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. CONTROLE DE ACESSO ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center;'>🏗️ GESTOR PRO</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #8b949e;'>Painel Administrativo de Elite</p>", unsafe_allow_html=True)
        with st.form("login"):
            pwd = st.text_input("CHAVE DE ACESSO", type="password")
            if st.form_submit_button("DESBLOQUEAR SISTEMA"):
                if pwd == st.secrets["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else: st.error("Chave inválida.")
else:
    # --- 4. BACKEND INTEGRADO ---
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

    # --- 5. NAVEGAÇÃO PREMIUM ---
    with st.sidebar:
        st.markdown("<div style='padding: 20px 0; text-align: center;'><h2 style='color: #10b981;'>GESTOR PRO</h2></div>", unsafe_allow_html=True)
        sel = option_menu(
            None, ["Insights", "Obras", "Financeiro", "Relatórios"],
            icons=['cpu', 'building-gear', 'bank', 'file-earmark-medical'],
            menu_icon="cast", default_index=0,
            styles={
                "container": {"background-color": "transparent"},
                "nav-link": {"color": "#8b949e", "font-size": "14px", "text-align": "left", "margin": "8px", "border-radius": "10px"},
                "nav-link-selected": {"background-color": "#10b981", "color": "white", "font-weight": "800"},
            }
        )
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("🚪 LOGOUT"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- 6. TELAS ---
    if sel == "Insights":
        st.markdown("<h1 style='letter-spacing: -1px;'>📊 Dashboard de Elite</h1>", unsafe_allow_html=True)
        
        if not df_obras.empty:
            obra = st.selectbox("Selecione a Unidade de Análise", ["Faturamento Global"] + df_obras['Cliente'].tolist())
            
            df_v = df_fin.copy()
            valor_contrato = df_obras['Valor Total'].sum()
            
            if obra != "Faturamento Global":
                df_v = df_fin[df_fin['Obra Vinculada'] == obra]
                valor_contrato = df_obras[df_obras['Cliente'] == obra]['Valor Total'].sum()
            
            ent = df_v[df_v['Tipo'].str.contains('Entrada', na=False)]['Valor'].sum()
            sai = df_v[df_v['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
            saldo = ent - sai
            
            # Cards de Métricas com Design Moderno
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("RECEITA", f"R$ {ent:,.2f}")
            c2.metric("CUSTOS", f"R$ {sai:,.2f}", delta_color="inverse")
            c3.metric("RESULTADO", f"R$ {saldo:,.2f}")
            progresso = (sai / valor_contrato * 100) if valor_contrato > 0 else 0
            c4.metric("CONSUMO CONTRATO", f"{progresso:.1f}%")

            st.markdown("<br>", unsafe_allow_html=True)
            
            # Gráfico de Evolução Profissional
            col_g1, col_g2 = st.columns([2, 1])
            with col_g1:
                df_ev = df_v[df_v['Tipo'].str.contains('Saída', na=False)].sort_values('Data')
                fig = px.area(df_ev, x='Data', y='Valor', title="Fluxo de Desembolso Mensal",
                              color_discrete_sequence=['#10b981'])
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                                  font=dict(color="#8b949e"), margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig, use_container_width=True)
            
            with col_g2:
                # Gauge Chart (Velocímetro) de Lucratividade
                lucratividade = (saldo / ent * 100) if ent > 0 else 0
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = lucratividade,
                    title = {'text': "Margem de Lucro (%)", 'font': {'size': 14, 'color': "#8b949e"}},
                    gauge = {
                        'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "#8b949e"},
                        'bar': {'color': "#10b981"},
                        'bgcolor': "#161b22",
                        'borderwidth': 2,
                        'bordercolor': "#30363d",
                        'steps': [
                            {'range': [0, 20], 'color': '#ef4444'},
                            {'range': [20, 50], 'color': '#f59e0b'}],
                    }
                ))
                fig_gauge.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color="#8b949e"), height=250, margin=dict(l=20, r=20, t=30, b=20))
                st.plotly_chart(fig_gauge, use_container_width=True)

    elif sel == "Obras":
        st.markdown("<h1>📁 Gerenciamento de Projetos</h1>", unsafe_allow_html=True)
        tab_o1, tab_o2 = st.tabs(["📝 Cadastrar Novo Contrato", "🔍 Consultar Portfólio"])
        
        with tab_o1:
            with st.form("new_o_pro"):
                c1, c2 = st.columns(2)
                cli = c1.text_input("Nome do Cliente/Obra")
                val = c2.number_input("Valor Total do Contrato", min_value=0.0, step=1000.0)
                if st.form_submit_button("🚀 REGISTRAR PROJETO NO SISTEMA"):
                    get_client().open("GestorObras_DB").worksheet("Obras").append_row([len(df_obras)+1, cli, "", "Ativo", val, str(date.today()), ""])
                    st.cache_data.clear()
                    st.success(f"Obra {cli} cadastrada com sucesso!")
                    st.rerun()
        
        with tab_o2:
            st.dataframe(df_obras, use_container_width=True, hide_index=True)

    elif sel == "Financeiro":
        st.markdown("<h1>💸 Centro de Custos</h1>", unsafe_allow_html=True)
        tab_f1, tab_f2 = st.tabs(["💰 Novo Lançamento", "📄 Extrato Consolidado"])
        
        with tab_f1:
            with st.form("new_f_pro"):
                c1, c2 = st.columns(2)
                tipo = c1.selectbox("Natureza da Operação", ["Saída (Despesa)", "Entrada (Receita)"])
                obra_v = c1.selectbox("Vincular à Unidade", df_obras['Cliente'].tolist() if not df_obras.empty else ["Geral"])
                desc = c2.text_input("Descrição Detalhada")
                valor = c2.number_input("Valor da Transação", min_value=0.0, step=10.0)
                if st.form_submit_button("✅ EFETIVAR LANÇAMENTO"):
                    get_client().open("GestorObras_DB").worksheet("Financeiro").append_row([str(date.today()), tipo, "Geral", desc, valor, obra_v])
                    st.cache_data.clear()
                    st.rerun()
        
        with tab_f2:
            st.dataframe(df_fin.sort_values('Data', ascending=False), use_container_width=True, hide_index=True)

    elif sel == "Relatórios":
        st.markdown("<h1>📄 Inteligência Documental</h1>", unsafe_allow_html=True)
        st.markdown("""
            <div style='padding: 40px; border: 1px dashed #30363d; border-radius: 20px; text-align: center; background-color: #161b22;'>
                <h3 style='color: #10b981;'>Relatórios de Medição e Prestação de Contas</h3>
                <p>O sistema processa automaticamente os dados do Dashboard para gerar PDFs técnicos.</p>
            </div>
        """, unsafe_allow_html=True)
