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
st.set_page_config(page_title="Gestor Obras | PRO", layout="wide")

def check_password():
    """Verifica a senha e permite o uso da tecla Enter através do st.form."""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        # Centraliza o formulário de login na tela
        _, col_central, _ = st.columns([1, 1, 1])
        
        with col_central:
            st.markdown("<br><br>", unsafe_allow_html=True)
            st.title("🏗️ Gestor PRO")
            st.subheader("Acesso Restrito")
            
            with st.form("login_form"):
                pwd = st.text_input("Senha de Administrador", type="password")
                login_submit = st.form_submit_button("Entrar no Sistema")
                
                if login_submit:
                    if pwd == st.secrets["password"]:
                        st.session_state["authenticated"] = True
                        st.rerun()
                    else:
                        st.error("⚠️ Senha incorreta.")
        return False
    return True

# --- SÓ EXECUTA O SISTEMA SE ESTIVER AUTENTICADO ---
if check_password():
    
    # --- 2. ESTILO CSS ---
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
            st.error(f"Erro de Conexão com a Base de Dados: {e}")
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
        
        # Resumo Financeiro
        sai = df_fin_obra[df_fin_obra['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
        p.drawString(100, 700, f"Valor do Contrato: R$ {df_obra_info['Valor Total'].values[0]:,.2f}")
        p.drawString(100, 680, f"Total Gasto até o momento: R$ {sai:,.2f}")
        p.line(100, 660, 500, 660)
        
        y = 630
        p.drawString(100, 645, "Lançamentos Recentes:")
        for _, row in df_fin_obra.tail(15).iterrows():
            p.drawString(100, y, f"{row['Data']} - {row['Descrição']}: R$ {row['Valor']:,.2f}")
            y -= 20
            if y < 50: break
        p.showPage()
        p.save()
        buffer.seek(0)
        return buffer

    # --- 4. INTERFACE PRINCIPAL ---
    sheet, df_obras, df_fin = carregar_dados()

    with st.sidebar:
        st.markdown("## 🏗️ Menu Principal")
        if st.button("Sair (Logout)"):
            st.session_state["authenticated"] = False
            st.rerun()
        st.markdown("---")
        menu = st.radio("Selecione a Área", ["📊 Dashboard", "📁 Gestão de Obras", "💸 Financeiro", "📄 Relatórios"])

    # --- LÓGICA DAS PÁGINAS ---

    if menu == "📊 Dashboard":
        st.title("📊 Painel Estratégico")
        if not df_obras.empty:
            obra_sel = st.selectbox("Filtrar por Obra específica", ["Todas"] + df_obras['Cliente'].tolist())
            df_v = df_fin.copy()
            if obra_sel != "Todas":
                df_v = df_fin[df_fin['Obra Vinculada'] == obra_sel]
            
            ent = df_v[df_v['Tipo'].str.contains('Entrada', na=False)]['Valor'].sum()
            sai = df_v[df_v['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Recebido", f"R$ {ent:,.2f}")
            c2.metric("Total Gasto", f"R$ {sai:,.2f}")
            c3.metric("Saldo de Caixa", f"R$ {ent-sai:,.2f}")
            
            st.markdown("---")
            if not df_v.empty:
                st.subheader("📈 Evolução de Custos")
                df_ev = df_v[df_v['Tipo'].str.contains('Saída', na=False)].sort_values('Data')
                st.plotly_chart(px.line(df_ev, x='Data', y='Valor', markers=True), use_container_width=True)
        else: st.info("Cadastre uma obra para ver as estatísticas.")

    elif menu == "📁 Gestão de Obras":
        st.title("📁 Cadastro de Projetos")
        with st.form("form_obra_new"):
            c1, c2 = st.columns(2)
            cli = c1.text_input("Nome do Cliente")
            val = c2.number_input("Valor do Contrato", step=100.0)
            if st.form_submit_button("💾 Salvar Obra"):
                sheet.worksheet("Obras").append_row([len(df_obras)+1, cli, "", "Em Andamento", val, str(date.today()), ""])
                st.rerun()
        st.dataframe(df_obras, use_container_width=True, hide_index=True)

    elif menu == "💸 Financeiro":
        st.title("💸 Fluxo de Caixa")
        with st.form("form_fin_new"):
            t = st.selectbox("Tipo de Lançamento", ["Saída (Despesa)", "Entrada"])
            o = st.selectbox("Vincular à Obra", df_obras['Cliente'].tolist() if not df_obras.empty else ["Geral"])
            d = st.text_input("Descrição do Gasto/Receita")
            v = st.number_input("Valor (R$)", step=10.0)
            if st.form_submit_button("💾 Confirmar Lançamento"):
                sheet.worksheet("Financeiro").append_row([str(date.today()), t, "Geral", d, v, o])
                st.rerun()
        st.dataframe(df_fin, use_container_width=True, hide_index=True)

    elif menu == "📄 Relatórios":
        st.title("📄 Gerador de Documentos")
        if not df_obras.empty:
            o_rep = st.selectbox("Selecione a Obra para gerar PDF", df_obras['Cliente'].tolist())
            if st.button("Gerar Relatório de Medição"):
                pdf_out = gerar_pdf_obra(o_rep, df_obras[df_obras['Cliente']==o_rep], df_fin[df_fin['Obra Vinculada']==o_rep])
                st.download_button("📥 Baixar PDF Profissional", data=pdf_out, file_name=f"Relatorio_{o_rep}.pdf")
        else: st.warning("Não há obras registradas para gerar relatórios.")
