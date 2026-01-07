import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import datetime, date
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestor Obras | Intelligence", layout="wide")

# --- 2. CSS CUSTOMIZADO ---
st.markdown("""
    <style>
        .main { background-color: #f4f6f9; }
        section[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e0e0e0; }
        div[data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. FUNÇÕES TÉCNICAS (BACKEND) ---
@st.cache_resource
def conectar_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        json_creds = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json_creds, scope)
        client = gspread.authorize(creds)
        return client.open("GestorObras_DB")
    except Exception as e:
        st.error(f"Erro de Conexão: {e}")
        return None

def carregar_dados():
    sheet = conectar_google_sheets()
    if not sheet: return None, pd.DataFrame(), pd.DataFrame()
    
    try:
        df_obras = pd.DataFrame(sheet.worksheet("Obras").get_all_records())
        df_fin = pd.DataFrame(sheet.worksheet("Financeiro").get_all_records())
        
        if not df_obras.empty:
            df_obras['Valor Total'] = pd.to_numeric(df_obras['Valor Total'], errors='coerce').fillna(0)
        if not df_fin.empty:
            df_fin['Valor'] = pd.to_numeric(df_fin['Valor'], errors='coerce').fillna(0)
            df_fin['Data'] = pd.to_datetime(df_fin['Data']).dt.date
            
        return sheet, df_obras, df_fin
    except:
        return sheet, pd.DataFrame(), pd.DataFrame()

def gerar_pdf_obra(obra_nome, df_obra_info, df_fin_obra):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 750, f"RELATÓRIO DE OBRA: {obra_nome}")
    p.setFont("Helvetica", 12)
    p.drawString(100, 730, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    # Resumo Financeiro
    total_gasto = df_fin_obra[df_fin_obra['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
    p.drawString(100, 700, f"Valor Total do Contrato: R$ {df_obra_info['Valor Total'].values[0]:,.2f}")
    p.drawString(100, 680, f"Total Gasto até o momento: R$ {total_gasto:,.2f}")
    
    p.line(100, 660, 500, 660)
    p.drawString(100, 640, "Últimos Lançamentos:")
    
    y = 620
    for idx, row in df_fin_obra.tail(10).iterrows():
        p.drawString(100, y, f"{row['Data']} - {row['Descrição']}: R$ {row['Valor']:,.2f}")
        y -= 20
        if y < 50: break
        
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# --- 4. INTERFACE ---
sheet, df_obras, df_fin = carregar_dados()

with st.sidebar:
    st.title("🏗️ Gestor PRO")
    menu = st.radio("Menu", ["📊 Dashboard", "📁 Obras", "💸 Financeiro", "📄 Relatórios"])

if menu == "📊 Dashboard":
    st.subheader("📊 Inteligência de Negócio")
    
    if not df_obras.empty:
        # FILTROS
        col_f1, col_f2 = st.columns(2)
        obra_filtro = col_f1.selectbox("Filtrar por Obra", ["Todas"] + df_obras['Cliente'].tolist())
        
        # Lógica de Filtro
        df_fin_view = df_fin.copy()
        if obra_filtro != "Todas":
            df_fin_view = df_fin[df_fin['Obra Vinculada'] == obra_filtro]
            
        # KPIs
        total_ent = df_fin_view[df_fin_view['Tipo'].str.contains('Entrada', na=False)]['Valor'].sum()
        total_sai = df_fin_view[df_fin_view['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Recebido", f"R$ {total_ent:,.2f}")
        c2.metric("Gasto", f"R$ {total_sai:,.2f}")
        c3.metric("Saldo Atual", f"R$ {total_ent - total_sai:,.2f}")

        # GRÁFICO DE EVOLUÇÃO
        st.markdown("---")
        st.subheader("📈 Evolução de Gastos")
        if not df_fin_view.empty:
            df_evolucao = df_fin_view[df_fin_view['Tipo'].str.contains('Saída', na=False)].sort_values('Data')
            fig_evol = px.line(df_evolucao, x='Data', y='Valor', title="Saídas de Caixa no Tempo", markers=True)
            st.plotly_chart(fig_evol, use_container_width=True)
    else:
        st.info("Sem dados para exibir.")

elif menu == "📁 Obras":
    st.subheader("📁 Gestão de Obras")
    # (Mantém a lógica de cadastro anterior...)
    with st.form("nova_obra"):
        c1, c2 = st.columns(2)
        cliente = c1.text_input("Cliente")
        valor = c2.number_input("Valor", step=100.0)
        if st.form_submit_button("Salvar"):
            sheet.worksheet("Obras").append_row([len(df_obras)+1, cliente, "", "Em Andamento", valor, str(date.today()), ""])
            st.rerun()
    st.dataframe(df_obras, use_container_width=True, hide_index=True)

elif menu == "💸 Financeiro":
    st.subheader("💸 Fluxo de Caixa")
    # (Mantém a lógica de lançamentos anterior...)
    with st.form("fin"):
        tipo = st.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
        obra = st.selectbox("Obra", df_obras['Cliente'].tolist() if not df_obras.empty else ["Geral"])
        desc = st.text_input("Descrição")
        val = st.number_input("Valor", step=10.0)
        if st.form_submit_button("Lançar"):
            sheet.worksheet("Financeiro").append_row([str(date.today()), tipo, "Geral", desc, val, obra])
            st.rerun()
    st.dataframe(df_fin, use_container_width=True, hide_index=True)

elif menu == "📄 Relatórios":
    st.subheader("📄 Gerador de Documentos")
    if not df_obras.empty:
        obra_sel = st.selectbox("Selecione a Obra para o PDF", df_obras['Cliente'].tolist())
        if st.button("Gerar Relatório Profissional"):
            df_info = df_obras[df_obras['Cliente'] == obra_sel]
            df_f_obra = df_fin[df_fin['Obra Vinculada'] == obra_sel]
            
            pdf = gerar_pdf_obra(obra_sel, df_info, df_f_obra)
            st.download_button(
                label="📥 Descarregar PDF",
                data=pdf,
                file_name=f"Relatorio_{obra_sel}.pdf",
                mime="application/pdf"
            )
    else:
        st.warning("Cadastre uma obra primeiro.")
