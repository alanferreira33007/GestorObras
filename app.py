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

# --- 1. CONFIGURAÇÃO E AUTENTICAÇÃO ---
st.set_page_config(page_title="Gestor Obras | Secure", layout="wide")

def check_password():
    """Retorna True se a senha estiver correta."""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        st.title("🏗️ Acesso Restrito - Gestor PRO")
        pwd = st.text_input("Digite a senha de administrador:", type="password")
        if st.button("Entrar"):
            if pwd == st.secrets["password"]:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("⚠️ Senha incorreta. Acesso negado.")
        return False
    return True

# --- SÓ EXECUTA O RESTO SE ESTIVER AUTENTICADO ---
if check_password():
    
    # --- 2. CSS E ESTILO ---
    st.markdown("""
        <style>
            .main { background-color: #f4f6f9; }
            section[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e0e0e0; }
            div[data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px; border-radius: 8px; }
            #MainMenu, footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

    # --- 3. BACKEND (GOOGLE SHEETS) ---
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
        except: return sheet, pd.DataFrame(), pd.DataFrame()

    def gerar_pdf_obra(obra_nome, df_obra_info, df_fin_obra):
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        p.setFont("Helvetica-Bold", 16)
        p.drawString(100, 750, f"RELATÓRIO DE OBRA: {obra_nome}")
        p.setFont("Helvetica", 12)
        p.drawString(100, 730, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        total_gasto = df_fin_obra[df_fin_obra['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
        p.drawString(100, 700, f"Valor do Contrato: R$ {df_obra_info['Valor Total'].values[0]:,.2f}")
        p.drawString(100, 680, f"Total Gasto: R$ {total_gasto:,.2f}")
        p.line(100, 660, 500, 660)
        p.drawString(100, 640, "Lançamentos Recentes:")
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
        if st.button("Sair (Logout)"):
            st.session_state["authenticated"] = False
            st.rerun()
        st.markdown("---")
        menu = st.radio("Navegação", ["📊 Dashboard", "📁 Obras", "💸 Financeiro", "📄 Relatórios"])

    # --- PÁGINAS ---
    if menu == "📊 Dashboard":
        st.subheader("📊 Inteligência de Negócio")
        if not df_obras.empty:
            obra_filtro = st.selectbox("Selecione a Obra", ["Todas"] + df_obras['Cliente'].tolist())
            df_fin_view = df_fin.copy()
            if obra_filtro != "Todas":
                df_fin_view = df_fin[df_fin['Obra Vinculada'] == obra_filtro]
            
            ent = df_fin_view[df_fin_view['Tipo'].str.contains('Entrada', na=False)]['Valor'].sum()
            sai = df_fin_view[df_fin_view['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Recebido", f"R$ {ent:,.2f}")
            c2.metric("Gasto", f"R$ {sai:,.2f}")
            c3.metric("Saldo", f"R$ {ent-sai:,.2f}")
            
            st.markdown("---")
            if not df_fin_view.empty:
                df_evol = df_fin_view[df_fin_view['Tipo'].str.contains('Saída', na=False)].sort_values('Data')
                st.plotly_chart(px.line(df_evol, x='Data', y='Valor', title="Fluxo de Saída"), use_container_width=True)
        else: st.info("Sem dados.")

    elif menu == "📁 Obras":
        st.subheader("📁 Cadastro de Obras")
        with st.form("obra_f"):
            c1, c2 = st.columns(2)
            cli = c1.text_input("Cliente")
            val = c2.number_input("Valor Contrato", step=100.0)
            if st.form_submit_button("Salvar"):
                sheet.worksheet("Obras").append_row([len(df_obras)+1, cli, "", "Em Andamento", val, str(date.today()), ""])
                st.rerun()
        st.dataframe(df_obras, use_container_width=True, hide_index=True)

    elif menu == "💸 Financeiro":
        st.subheader("💸 Fluxo de Caixa")
        with st.form("fin_f"):
            t = st.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
            o = st.selectbox("Obra", df_obras['Cliente'].tolist() if not df_obras.empty else ["Geral"])
            d = st.text_input("Descrição")
            v = st.number_input("Valor", step=10.0)
            if st.form_submit_button("Lançar"):
                sheet.worksheet("Financeiro").append_row([str(date.today()), t, "Geral", d, v, o])
                st.rerun()
        st.dataframe(df_fin, use_container_width=True, hide_index=True)

    elif menu == "📄 Relatórios":
        st.subheader("📄 Gerador de PDF")
        if not df_obras.empty:
            o_sel = st.selectbox("Escolha a Obra", df_obras['Cliente'].tolist())
            if st.button("Gerar PDF Profissional"):
                pdf = gerar_pdf_obra(o_sel, df_obras[df_obras['Cliente']==o_sel], df_fin[df_fin['Obra Vinculada']==o_sel])
                st.download_button("📥 Baixar Relatório", data=pdf, file_name=f"Relatorio_{o_sel}.pdf", mime="application/pdf")
