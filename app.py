import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from streamlit_option_menu import option_menu

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="GESTOR PRO | Investment Analysis", layout="wide")

# --- 2. CSS CORPORATIVO REFINADO ---
st.markdown("""
    <style>
        .stApp { background-color: #F8F9FA; color: #1A1C1E; font-family: 'Inter', sans-serif; }
        [data-testid="stMetric"] { background-color: #FFFFFF; border: 1px solid #E9ECEF; border-radius: 12px; padding: 20px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
        div.stButton > button { background-color: #2D6A4F !important; color: white !important; border-radius: 6px !important; font-weight: 600 !important; width: 100%; height: 45px; }
        header, footer, #MainMenu {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. AUTENTICAÇÃO ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        with st.form("login"):
            st.markdown("<h2 style='text-align:center; color:#2D6A4F;'>GESTOR PRO</h2>", unsafe_allow_html=True)
            pwd = st.text_input("Senha", type="password")
            if st.form_submit_button("Acessar Painel"):
                if pwd == st.secrets["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
else:
    # --- 4. BACKEND (CORRIGIDO) ---
    def obter_conector():
        creds_json = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        return gspread.authorize(creds)

    @st.cache_data(ttl=60)
    def carregar_dados_v15():
        try:
            client = obter_conector()
            db = client.open("GestorObras_DB")
            df_o = pd.DataFrame(db.worksheet("Obras").get_all_records())
            df_f = pd.DataFrame(db.worksheet("Financeiro").get_all_records())
            df_o['Valor Total'] = pd.to_numeric(df_o['Valor Total'], errors='coerce').fillna(0)
            df_f['Valor'] = pd.to_numeric(df_f['Valor'], errors='coerce').fillna(0)
            df_f['Data'] = pd.to_datetime(df_f['Data'], errors='coerce').dt.date
            return df_o, df_f
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return pd.DataFrame(), pd.DataFrame()

    df_obras, df_fin = carregar_dados_v15()

    # --- 5. MENU ---
    with st.sidebar:
        st.markdown("<h3 style='text-align:center; color:#2D6A4F;'>GESTOR PRO</h3>", unsafe_allow_html=True)
        sel = option_menu(None, ["Investimentos", "Projetos", "Caixa", "Relatórios"], 
            icons=['graph-up-arrow', 'building', 'wallet2', 'file-text'], default_index=0,
            styles={"nav-link-selected": {"background-color": "#E9F5EE", "color": "#2D6A4F"}})
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- 6. TELAS ---
    if sel == "Investimentos":
        st.markdown("### 📊 Performance e ROI por Obra")
        if not df_obras.empty:
            escolha = st.selectbox("Selecione a Casa para Analisar", df_obras['Cliente'].tolist())
            
            # Filtros e Cálculos
            dados_obra = df_obras[df_obras['Cliente'] == escolha].iloc[0]
            vgv = dados_obra['Valor Total'] # Valor Estimado de Venda
            
            fin_obra = df_fin[df_fin['Obra Vinculada'] == escolha]
            custos = fin_obra[fin_obra['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
            entradas = fin_obra[fin_obra['Tipo'].str.contains('Entrada', na=False)]['Valor'].sum()
            
            lucro_estimado = vgv - custos
            roi = (lucro_estimado / custos * 100) if custos > 0 else 0
            
            # Cards de ROI
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("VGV (Venda)", f"R$ {vgv:,.2f}")
            c2.metric("Custo Total", f"R$ {custos:,.2f}", delta=f"{(custos/vgv*100 if vgv>0 else 0):.1f}% do VGV", delta_color="inverse")
            c3.metric("Lucro Estimado", f"R$ {lucro_estimado:,.2f}")
            c4.metric("ROI Atual", f"{roi:.1f}%")

            st.markdown("---")
            col_a, col_b = st.columns([2, 1])
            with col_a:
                st.markdown("**Evolução de Gastos**")
                fig = px.line(fin_obra[fin_obra['Tipo'].str.contains('Saída')], x='Data', y='Valor', markers=True, color_discrete_sequence=['#E63946'])
                st.plotly_chart(fig, use_container_width=True)
            with col_b:
                st.markdown("**Margem de Lucro (%)**")
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number", value = (lucro_estimado/vgv*100 if vgv>0 else 0),
                    gauge = {'axis': {'range': [None, 100]}, 'bar': {'color': "#2D6A4F"}}))
                fig_gauge.update_layout(height=250, margin=dict(l=20, r=20, t=30, b=20))
                st.plotly_chart(fig_gauge, use_container_width=True)

    elif sel == "Projetos":
        st.markdown("### 📁 Cadastro de Obras para Venda")
        with st.form("form_obra_fix", clear_on_submit=True):
            col1, col2 = st.columns(2)
            nome_casa = col1.text_input("Identificação da Casa/Lote (Ex: Casa 01 - Sul)")
            vgv_venda = col2.number_input("Valor Estimado de Venda (VGV)", min_value=0.0, step=1000.0)
            if st.form_submit_button("CADASTRAR EMPREENDIMENTO"):
                if nome_casa:
                    client = obter_conector()
                    client.open("GestorObras_DB").worksheet("Obras").append_row([
                        len(df_obras)+1, nome_casa, "", "Construção", vgv_venda, str(date.today()), ""
                    ])
                    st.cache_data.clear()
                    st.success("Obra cadastrada!")
                    st.rerun()

    elif sel == "Caixa":
        st.markdown("### 💸 Lançamento Financeiro")
        with st.form("form_fin_fix", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            tp = c1.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
            ob = c2.selectbox("Obra", df_obras['Cliente'].tolist() if not df_obras.empty else ["Geral"])
            vl = c3.number_input("Valor R$", min_value=0.0)
            ds = st.text_input("Descrição (Ex: Mão de Obra, Material, Terreno)")
            if st.form_submit_button("CONFIRMAR LANÇAMENTO"):
                client = obter_conector()
                client.open("GestorObras_DB").worksheet("Financeiro").append_row([str(date.today()), tp, "Geral", ds, vl, ob])
                st.cache_data.clear()
                st.success("Lançamento efetuado!")
                st.rerun()
        st.dataframe(df_fin.sort_values('Data', ascending=False), use_container_width=True, hide_index=True)
