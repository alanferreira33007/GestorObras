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
            sai = df_v[df_v['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Recebido", f"R$ {ent:,.2f}")
            c2.metric("Desembolsado", f"R$ {sai:,.2f}")
            c3.metric("Saldo Líquido", f"R$ {ent-sai:,.2f}")
            c4.metric("Margem", f"{((ent-sai)/ent*100 if ent>0 else 0):.1f}%")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if not df_v.empty:
                fig = px.area(df_v[df_v['Tipo'].str.contains('Saída', na=False)].sort_values('Data'), 
                              x='Data', y='Valor', title="Fluxo de Saída (Custos)", 
                              color_discrete_sequence=['#2563eb'])
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(family="Inter"))
                st.plotly_chart(fig, use_container_width=True)
        else: st.info("👋 Bem-vindo! Comece cadastrando uma obra na aba lateral.")

    elif menu == "Obras":
        st.markdown("<h1 class='page-title'>📁 Gestão de Projetos</h1>", unsafe_allow_html=True)
        st.markdown("<p class='page-subtitle'>Gerencie novos contratos e visualize o status atual.</p>", unsafe_allow_html=True)
        
        col_form, col_list = st.columns([1, 1.5])
        with col_form:
            with st.form("f_ob", clear_on_submit=True):
                st.markdown("**Cadastrar Novo Contrato**")
                cli = st.text_input("Nome do Cliente", placeholder="Ex: Residencial Alvorada")
                val = st.number_input("Valor do Contrato (R$)", min_value=0.0, step=1000.0)
                status = st.selectbox("Status Inicial", ["Planejamento", "Em Andamento", "Finalizada"])
                if st.form_submit_button("🚀 Salvar Obra", use_container_width=True):
                    client = get_client()
                    client.open("GestorObras_DB").worksheet("Obras").append_row([len(df_obras)+1, cli, "", status, val, str(date.today()), ""])
                    st.cache_data.clear()
                    st.rerun()
        
        with col_list:
            st.markdown("**Projetos Ativos**")
            st.dataframe(df_obras[['Cliente', 'Status', 'Valor Total']], use_container_width=True, hide_index=True)

    elif menu == "Financeiro":
        st.markdown("<h1 class='page-title'>💸 Controle de Caixa</h1>", unsafe_allow_html=True)
        st.markdown("<p class='page-subtitle'>Registre cada centavo que entra ou sai dos seus projetos.</p>", unsafe_allow_html=True)
        
        col_f, col_t = st.columns([1, 2])
        with col_f:
            with st.form("f_fi", clear_on_submit=True):
                st.markdown("**Novo Lançamento**")
                t = st.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
                o = st.selectbox("Obra Vinculada", df_obras['Cliente'].tolist() if not df_obras.empty else ["Geral"])
                desc = st.text_input("Descrição", placeholder="Ex: Compra de Vergalhões")
                v = st.number_input("Valor", min_value=0.0, step=10.0)
                if st.form_submit_button("💾 Confirmar Lançamento", use_container_width=True):
                    client = get_client()
                    client.open("GestorObras_DB").worksheet("Financeiro").append_row([str(date.today()), t, "Geral", desc, v, o])
                    st.cache_data.clear()
                    st.rerun()
        
        with col_t:
            st.markdown("**Extrato de Lançamentos**")
            st.dataframe(df_fin.sort_values('Data', ascending=False), use_container_width=True, hide_index=True)

    elif menu == "Relatórios":
        st.markdown("<h1 class='page-title'>📄 Relatórios Inteligentes</h1>", unsafe_allow_html=True)
        st.markdown("<p class='page-subtitle'>Gere documentos técnicos em PDF para clientes ou sócios.</p>", unsafe_allow_html=True)
        
        with st.container(border=True):
            if not df_obras.empty:
                o_rep = st.selectbox("Escolha o projeto para exportação:", df_obras['Cliente'].tolist())
                st.markdown("---")
                c1, c2 = st.columns(2)
                c1.button("📄 Gerar Relatório de Medição", use_container_width=True)
                c2.button("📊 Exportar Fluxo de Caixa (Excel)", use_container_width=True)
            else: st.warning("Cadastre dados para habilitar relatórios.")
