import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import datetime, date
from streamlit_option_menu import option_menu

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="GESTOR PRO | Investimentos", layout="wide")

# --- CSS CORPORATIVO (MANTIDO) ---
st.markdown("""
    <style>
        .stApp { background-color: #F8F9FA; color: #1A1C1E; font-family: 'Inter', sans-serif; }
        [data-testid="stMetric"] { background-color: #FFFFFF; border: 1px solid #E9ECEF; border-radius: 12px; padding: 20px !important; }
        div.stButton > button { background-color: #2D6A4F !important; color: white !important; border-radius: 6px !important; font-weight: 600 !important; }
        header, footer, #MainMenu {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- AUTENTICAÇÃO ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        with st.form("login"):
            st.markdown("<h2 style='text-align:center;'>GESTOR PRO</h2>", unsafe_allow_html=True)
            pwd = st.text_input("Senha", type="password")
            if st.form_submit_button("Acessar"):
                if pwd == st.secrets["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
else:
    # --- DATA BACKEND ---
    @st.cache_data(ttl=60)
    def load_data():
        try:
            creds_dict = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
            client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]))
            sheet = client.open("GestorObras_DB")
            df_o = pd.DataFrame(sheet.worksheet("Obras").get_all_records())
            df_f = pd.DataFrame(sheet.worksheet("Financeiro").get_all_records())
            df_o['Valor Total'] = pd.to_numeric(df_o['Valor Total'], errors='coerce').fillna(0)
            df_f['Valor'] = pd.to_numeric(df_f['Valor'], errors='coerce').fillna(0)
            df_f['Data'] = pd.to_datetime(df_f['Data'], errors='coerce').dt.date
            return df_o, df_f, client
        except: return pd.DataFrame(), pd.DataFrame(), None

    df_obras, df_fin, connector = load_data()

    # --- NAVEGAÇÃO ---
    with st.sidebar:
        sel = option_menu(
            "GESTOR PRO", ["Dashboard", "Gestão de Obras", "Financeiro", "Relatórios"],
            icons=['house', 'building', 'wallet2', 'file-text'],
            menu_icon="cast", default_index=0,
            styles={"nav-link-selected": {"background-color": "#E9F5EE", "color": "#2D6A4F", "font-weight": "600"}}
        )
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- PÁGINAS ---
    if sel == "Dashboard":
        st.markdown("### 📊 Performance de Investimento")
        
        if not df_obras.empty:
            # Seleção de obra para análise de ROI
            obra_sel = st.selectbox("Selecione a Casa/Obra", df_obras['Cliente'].tolist())
            
            # Filtros Financeiros
            df_v = df_fin[df_fin['Obra Vinculada'] == obra_sel]
            obra_info = df_obras[df_obras['Cliente'] == obra_sel].iloc[0]
            
            # Cálculo de ROI e Lucro
            valor_venda = obra_info['Valor Total']
            custo_total = df_v[df_v['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
            lucro_previsto = valor_venda - custo_total
            roi = (lucro_previsto / custo_total * 100) if custo_total > 0 else 0
            
            # Cards Estratégicos
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço de Venda", f"R$ {valor_venda:,.2f}")
            c2.metric("Custo Acumulado", f"R$ {custo_total:,.2f}", delta=f"{ (custo_total/valor_venda*100 if valor_venda>0 else 0):.1f}% do VGV", delta_color="inverse")
            c3.metric("Lucro Estimado", f"R$ {lucro_previsto:,.2f}")
            c4.metric("ROI (%)", f"{roi:.2f}%")

            st.markdown("---")
            
            # Gráficos de Composição de Custos
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown("**Fluxo de Caixa da Obra**")
                df_ev = df_v.sort_values('Data')
                fig = px.area(df_ev, x='Data', y='Valor', color='Tipo', color_discrete_map={'Saída (Despesa)': '#E63946', 'Entrada': '#2D6A4F'})
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("**Composição de Gastos**")
                # Aqui agrupamos por descrição para simular categorias (Ex: Material, Mão de Obra)
                # Dica: Se você colocar "Material: Cimento" na descrição, o código abaixo agrupa.
                fig_pie = px.pie(df_v[df_v['Tipo'].str.contains('Saída')], names='Descrição', values='Valor', hole=0.4)
                fig_pie.update_layout(showlegend=False)
                st.plotly_chart(fig_pie, use_container_width=True)

    elif sel == "Gestão de Obras":
        st.markdown("### 📁 Registro de Novos Empreendimentos")
        tab1, tab2 = st.tabs(["Nova Obra para Venda", "Inventário de Obras"])
        with tab1:
            with st.form("new_o"):
                c1, c2 = st.columns(2)
                cli = c1.text_input("Identificação da Casa/Lote")
                val = c2.number_input("Valor Estimado de Venda (VGV)", min_value=0.0, step=10000.0)
                if st.form_submit_button("Cadastrar Empreendimento"):
                    connector.open("GestorObras_DB").worksheet("Obras").append_row([len(df_obras)+1, cli, "", "Construção", val, str(date.today()), ""])
                    st.cache_data.clear()
                    st.rerun()
        with tab2:
            st.dataframe(df_obras, use_container_width=True)

    elif sel == "Financeiro":
        st.markdown("### 💸 Lançamento de Custos e Receitas")
        with st.form("new_f"):
            c1, c2, c3 = st.columns(3)
            tipo = c1.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
            obra_v = c2.selectbox("Obra Vinculada", df_obras['Cliente'].tolist() if not df_obras.empty else ["Geral"])
            valor = c3.number_input("Valor R$", min_value=0.0, step=100.0)
            desc = st.text_input("Descrição (Ex: Fundação, Alvenaria, Acabamento, Terreno)")
            if st.form_submit_button("Confirmar Lançamento"):
                connector.open("GestorObras_DB").worksheet("Financeiro").append_row([str(date.today()), tipo, "Geral", desc, valor, obra_v])
                st.cache_data.clear()
                st.rerun()
        st.dataframe(df_fin.sort_values('Data', ascending=False), use_container_width=True)

    elif sel == "Relatórios":
        st.markdown("### 📄 Relatório de Viabilidade Econômica")
        st.write("Dados consolidados para análise de retorno de capital.")
