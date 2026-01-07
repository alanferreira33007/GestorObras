import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestor de Obras", layout="wide")

# --- CONEXÃO COM GOOGLE SHEETS ---
def conectar_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        json_creds = json.loads(st.secrets["gcp_service_account"]["json_content"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json_creds, scope)
        client = gspread.authorize(creds)
        sheet = client.open("GestorObras_DB")
        return sheet
    except Exception as e:
        st.error(f"⚠️ Erro na conexão: {e}")
        return None

# --- CARREGAR DADOS ---
def carregar_dados():
    sheet = conectar_google_sheets()
    if sheet is None:
        return None, pd.DataFrame(), pd.DataFrame()

    try:
        # Tenta abrir abas, se não existir cria
        try:
            ws_obras = sheet.worksheet("Obras")
        except:
            ws_obras = sheet.add_worksheet(title="Obras", rows="100", cols="20")
            ws_obras.append_row(["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"])

        try:
            ws_fin = sheet.worksheet("Financeiro")
        except:
            ws_fin = sheet.add_worksheet(title="Financeiro", rows="100", cols="20")
            ws_fin.append_row(["ID", "Obra ID", "Descrição", "Tipo", "Valor", "Data", "Comprovante"])

        obras = pd.DataFrame(ws_obras.get_all_records())
        financeiro = pd.DataFrame(ws_fin.get_all_records())
        return sheet, obras, financeiro
    except Exception as e:
        st.error(f"Erro ao ler dados: {e}")
        return sheet, pd.DataFrame(), pd.DataFrame()

# --- SALVAR DADOS ---
def salvar_obra(sheet, nova_obra):
    ws = sheet.worksheet("Obras")
    ws.append_row(list(nova_obra.values()))

def salvar_financeiro(sheet, nova_mov):
    ws = sheet.worksheet("Financeiro")
    ws.append_row(list(nova_mov.values()))

# --- LOGIN ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if not st.session_state.password_correct:
        st.markdown("### 🔒 Acesso Restrito")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if senha == "admin123":
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("Senha incorreta")
        return False
    return True

if not check_password():
    st.stop()

# --- APP PRINCIPAL ---
sheet, df_obras, df_financeiro = carregar_dados()

st.title("🏗️ Gestor de Obras (Google Sheets)")

# LINK MÁGICO PARA A PLANILHA
if sheet is not None:
    st.markdown(f"👉 **[CLIQUE AQUI PARA ABRIR SUA PLANILHA NO GOOGLE]({sheet.url})**")
    st.markdown("---")

# Menu Lateral
menu = st.sidebar.radio("Navegação", ["Dashboard", "Cadastrar Obra", "Financeiro", "Consultar Obras"])

if menu == "Dashboard":
    st.header("📊 Visão Geral")
    if not df_obras.empty:
        col1, col2 = st.columns(2)
        col1.metric("Total de Obras", len(df_obras))
        
        # Gráfico
        status_contagem = df_obras['Status'].value_counts()
        fig = px.pie(values=status_contagem.values, names=status_contagem.index, title="Obras por Status")
        st.plotly_chart(fig)
    else:
        st.info("Nenhuma obra cadastrada. Vá no menu 'Cadastrar Obra'.")

elif menu == "Cadastrar Obra":
    st.header("📝 Nova Obra")
    with st.form("form_obra"):
        cliente = st.text_input("Nome do Cliente")
        endereco = st.text_input("Endereço")
        valor = st.number_input("Valor do Contrato", min_value=0.0)
        status = st.selectbox("Status", ["Planejamento", "Em Andamento", "Concluída"])
        
        if st.form_submit_button("Salvar Obra"):
            nova_obra = {
                "ID": len(df_obras) + 1,
                "Cliente": cliente,
                "Endereço": endereco,
                "Status": status,
                "Valor Total": valor,
                "Data Início": str(datetime.now().date()),
                "Prazo": "A definir"
            }
            salvar_obra(sheet, nova_obra)
            st.success("✅ Obra salva no Google Sheets com sucesso!")
            st.balloons()
            st.rerun() # Atualiza a página

elif menu == "Consultar Obras":
    st.header("📂 Base de Dados")
    st.dataframe(df_obras)

elif menu == "Financeiro":
    st.header("💰 Financeiro")
    st.info("Cadastre obras primeiro para lançar gastos.")
      
  
