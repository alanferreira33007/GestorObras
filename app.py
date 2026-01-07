import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURAÇÃO DE ALTO NÍVEL ---
st.set_page_config(
    page_title="Gestor Obras | Enterprise",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CSS CUSTOMIZADO (VISUAL PROFISSIONAL) ---
st.markdown("""
    <style>
        .main { background-color: #f8f9fa; }
        h1, h2, h3 { font-family: 'Segoe UI', sans-serif; color: #2c3e50; }
        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }
        section[data-testid="stSidebar"] { background-color: #262730; }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. BACKEND (CONEXÃO) ---
@st.cache_resource
def conectar_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        json_creds = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json_creds, scope)
        client = gspread.authorize(creds)
        return client.open("GestorObras_DB")
    except Exception as e:
        st.error(f"⚠️ Erro de Conexão: {e}")
        return None

def carregar_dados():
    sheet = conectar_google_sheets()
    if sheet is None:
        return None, pd.DataFrame(), pd.DataFrame()

    try:
        # Aba Obras
        try:
            ws_obras = sheet.worksheet("Obras")
        except:
            ws_obras = sheet.add_worksheet(title="Obras", rows="100", cols="20")
            ws_obras.append_row(["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"])
        
        df_obras = pd.DataFrame(ws_obras.get_all_records())
        if not df_obras.empty:
            df_obras['Valor Total'] = pd.to_numeric(df_obras['Valor Total'], errors='coerce').fillna(0)

        # Aba Financeiro
        try:
            ws_fin = sheet.worksheet("Financeiro")
        except:
            ws_fin = sheet.add_worksheet(title="Financeiro", rows="500", cols="20")
            ws_fin.append_row(["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"])
        
        df_financeiro = pd.DataFrame(ws_fin.get_all_records())
        if not df_financeiro.empty:
            df_financeiro['Valor'] = pd.to_numeric(df_financeiro['Valor'], errors='coerce').fillna(0)
            df_financeiro['Data'] = pd.to_datetime(df_financeiro['Data'], errors='coerce').dt.date

        return sheet, df_obras, df_financeiro

    except Exception as e:
        st.error(f"Erro ao ler dados: {e}")
        return sheet, pd.DataFrame(), pd.DataFrame()

def salvar_dado(sheet, aba, linha):
    ws = sheet.worksheet(aba)
    ws.append_row(list(linha.values()))

# --- 4. INTERFACE ---
sheet, df_obras, df_financeiro = carregar_dados()

with st.sidebar:
    st.markdown("## 🏗️ Gestor **PRO**")
    st.markdown("---")
    menu = st.radio("MENU", ["📊 Dashboard", "📁 Obras", "💸 Financeiro", "⚙️ Config"])
    st.markdown("---")
    if sheet: st.success("Online ✅")

# --- LÓGICA ---
if menu == "📊 Dashboard":
    st.markdown("### 📊 Visão Estratégica")
    if not df_obras.empty:
        total_contratos = df_obras["Valor Total"].sum()
        
        if not df_financeiro.empty and 'Tipo' in df_financeiro.columns:
            total_gasto = df_financeiro[df_financeiro['Tipo'].str.contains('Saída', case=False, na=False)]['Valor'].sum()
        else:
            total_gasto = 0
            
        c1, c2, c3 = st.columns(3)
        c1.metric("Faturamento", f"R$ {total_contratos:,.2f}")
        c2.metric("Despesas", f"R$ {total_gasto:,.2f}")
        c3.metric("Saldo", f"R$ {total_contratos - total_gasto:,.2f}")
        
        st.markdown("---")
        
        # Gráficos
        col_g1, col_g2 = st.columns([2,1])
        with col_g1:
            st.subheader("Contratos por Cliente")
            st.plotly_chart(px.bar(df_obras, x='Cliente', y='Valor Total', color='Status'), use_container_width=True)
        with col_g2:
            st.subheader("Status")
            # Correção do gráfico de rosca
            st.plotly_chart(px.pie(df_obras, names='Status', hole=0.5), use_container_width=True)
    else:
        st.info("Cadastre sua primeira obra no menu lateral.")

elif menu == "📁 Obras":
    tab1, tab2 = st.tabs(["📝 Novo", "🔍 Lista"])
    with tab1:
        with st.form("form_obra"):
            c1, c2 = st.columns(2)
            cliente = c1.text_input("Cliente")
            endereco = c1.text_input("Endereço")
            data_ini = c1.date_input("Início", datetime.now())
            valor = c2.number_input("Valor R$", step=1000.0)
            status = c2.selectbox("Status", ["Planejamento", "Em Andamento", "Concluída"])
            prazo = c2.text_input("Prazo")
            
            if st.form_submit_button("Salvar Obra", type="primary"):
                salvar_dado(sheet, "Obras", {
                    "ID": len(df_obras)+1, "Cliente": cliente, "Endereço": endereco,
                    "Status": status, "Valor Total": valor, "Data Início": str(data_ini), "Prazo": prazo
                })
                st.toast("Salvo!")
                st.markdown('<meta http-equiv="refresh" content="1">', unsafe_allow_html=True)
    
    with tab2:
        if not df_obras.empty:
            # AQUI ESTAVA O ERRO - Corrigido
            st.dataframe(
                df_obras, use_container_width=True, hide_index=True,
                column_config={
                    "Valor Total": st.column_config.NumberColumn("Valor Total", format="R$ %.2f"),
                    "Status": st.column_config.SelectboxColumn("Status", options=["Em Andamento", "Concluída"], disabled=True)
                }
            )

elif menu == "💸 Financeiro":
    st.markdown("### 💸 Caixa")
    c1, c2 = st.columns([1,2])
    with c1:
        with st.form("fin_form"):
            tipo = st.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
            obra = st.selectbox("Obra", ["Geral"] + (df_obras['Cliente'].tolist() if not df_obras.empty else []))
            desc = st.text_input("Descrição")
            val = st.number_input("Valor R$", step=50.0)
            data = st.date_input("Data", datetime.now())
            
            if st.form_submit_button("Lançar"):
                salvar_dado(sheet, "Financeiro", {
                    "Data": str(data), "Tipo": tipo, "Categoria": "Geral", 
                    "Descrição": desc, "Valor": val, "Obra Vinculada": obra
                })
                st.toast("Lançado!")
                st.markdown('<meta http-equiv="refresh" content="1">', unsafe_allow_html=True)
    
    with c2:
        if not df_financeiro.empty:
            st.dataframe(df_financeiro, use_container_width=True, hide_index=True)

elif menu == "⚙️ Config":
    st.info("Sistema v3.3 - Stable Enterprise")
    if sheet: st.write(f"[Acessar Planilha Google]({sheet.url})")
