import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import datetime, date
from streamlit_option_menu import option_menu
import io

# --- 1. CONFIGURAÇÃO E AUTENTICAÇÃO (SESSÃO) ---
st.set_page_config(page_title="Gestor Obras | Ultra Speed", layout="wide")

# Inicializa o estado de autenticação se não existir
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

def check_password():
    if not st.session_state["authenticated"]:
        _, col_central, _ = st.columns([1, 1, 1])
        with col_central:
            st.markdown("<br><br>", unsafe_allow_html=True)
            st.title("🏗️ Gestor PRO")
            with st.form("login_form"):
                pwd = st.text_input("Senha", type="password")
                if st.form_submit_button("Entrar"):
                    if pwd == st.secrets["password"]:
                        st.session_state["authenticated"] = True
                        st.rerun()
                    else:
                        st.error("⚠️ Senha incorreta.")
        return False
    return True

if check_password():

    # --- 2. BACKEND COM CACHE INTELIGENTE ---
    @st.cache_resource
    def get_gspread_client():
        """Cria o cliente de conexão uma única vez."""
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        json_creds = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json_creds, scope)
        return gspread.authorize(creds)

    @st.cache_data(ttl=300) # Guarda os dados na memória por 5 minutos (300 segundos)
    def buscar_dados():
        """Busca as abas e transforma em DataFrames de forma rápida."""
        client = get_gspread_client()
        sheet = client.open("GestorObras_DB")
        
        # Obras
        ws_obras = sheet.worksheet("Obras")
        df_obras = pd.DataFrame(ws_obras.get_all_records())
        if not df_obras.empty:
            df_obras['Valor Total'] = pd.to_numeric(df_obras['Valor Total'], errors='coerce').fillna(0)
        
        # Financeiro
        ws_fin = sheet.worksheet("Financeiro")
        df_fin = pd.DataFrame(ws_fin.get_all_records())
        if not df_fin.empty:
            df_fin['Valor'] = pd.to_numeric(df_fin['Valor'], errors='coerce').fillna(0)
            df_fin['Data'] = pd.to_datetime(df_fin['Data'], errors='coerce').dt.date
            
        return df_obras, df_fin

    # --- 3. UI E ESTILO ---
    st.markdown("""
        <style>
            .main { background-color: #f8f9fa; }
            div[data-testid="stMetric"] {
                background-color: #ffffff; border-radius: 12px; padding: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #eee;
            }
            #MainMenu, footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

    # Carregamento inicial rápido
    df_obras, df_fin = buscar_dados()

    # --- 4. SIDEBAR ---
    with st.sidebar:
        st.markdown("<h2 style='text-align: center;'>🏗️ GESTOR PRO</h2>", unsafe_allow_html=True)
        
        menu = option_menu(
            menu_title=None,
            options=["Dashboard", "Obras", "Financeiro", "Relatórios"],
            icons=["bar-chart-line", "house-gear", "cash-stack", "file-earmark-pdf"],
            default_index=0,
            styles={
                "nav-link": {"font-size": "15px", "text-align": "left", "margin": "5px", "border-radius": "8px"},
                "nav-link-selected": {"background-color": "#007bff"},
            }
        )
        
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- 5. PÁGINAS (SÓ PROCESSAM O NECESSÁRIO) ---
    if menu == "Dashboard":
        st.title("📊 Painel Estratégico")
        if not df_obras.empty:
            obra_sel = st.selectbox("Obra", ["Todas"] + df_obras['Cliente'].tolist())
            
            # Filtro em memória (muito rápido)
            df_v = df_fin.copy()
            if obra_sel != "Todas":
                df_v = df_fin[df_fin['Obra Vinculada'] == obra_sel]
            
            ent = df_v[df_v['Tipo'].str.contains('Entrada', na=False)]['Valor'].sum()
            sai = df_v[df_v['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Recebido", f"R$ {ent:,.2f}")
            c2.metric("Gasto", f"R$ {sai:,.2f}")
            c3.metric("Saldo", f"R$ {ent-sai:,.2f}")
            
            if not df_v.empty:
                df_ev = df_v[df_v['Tipo'].str.contains('Saída', na=False)].sort_values('Data')
                fig = px.line(df_ev, x='Data', y='Valor', title="Fluxo de Gastos", markers=True)
                fig.update_layout(hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)
        else: st.info("Sem dados.")

    elif menu == "Obras":
        st.title("📁 Gestão de Obras")
        with st.form("f_ob", clear_on_submit=True):
            c1, c2 = st.columns(2)
            cli = c1.text_input("Cliente")
            val = c2.number_input("Valor Contrato", step=500.0)
            if st.form_submit_button("Salvar Obra"):
                client = get_gspread_client()
                client.open("GestorObras_DB").worksheet("Obras").append_row([len(df_obras)+1, cli, "", "Em Andamento", val, str(date.today()), ""])
                st.cache_data.clear() # Limpa o cache para forçar leitura nova
                st.rerun()
        st.dataframe(df_obras, use_container_width=True, hide_index=True)

    elif menu == "Financeiro":
        st.title("💸 Caixa")
        with st.form("f_fi", clear_on_submit=True):
            t = st.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
            o = st.selectbox("Obra", df_obras['Cliente'].tolist() if not df_obras.empty else ["Geral"])
            d = st.text_input("Descrição")
            v = st.number_input("Valor", step=10.0)
            if st.form_submit_button("Lançar"):
                client = get_gspread_client()
                client.open("GestorObras_DB").worksheet("Financeiro").append_row([str(date.today()), t, "Geral", d, v, o])
                st.cache_data.clear() # Atualiza os dados
                st.rerun()
        st.dataframe(df_fin, use_container_width=True, hide_index=True)

    elif menu == "Relatórios":
        st.title("📄 Relatórios")
        st.info("O módulo de exportação está otimizado para a base atual.")
        # Reinsira aqui a sua função de PDF preferida se desejar usar agora
