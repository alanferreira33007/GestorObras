import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import datetime, date
from streamlit_option_menu import option_menu

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="GESTOR PRO | Monitor de Preços", layout="wide")

# --- 2. CSS CORPORATIVO ---
st.markdown("""
    <style>
        .stApp { background-color: #F8F9FA; color: #1A1C1E; font-family: 'Inter', sans-serif; }
        [data-testid="stMetric"] { background-color: #FFFFFF; border: 1px solid #E9ECEF; border-radius: 12px; padding: 20px !important; }
        .alert-card { background-color: #FFF5F5; border: 1px solid #FEB2B2; padding: 15px; border-radius: 10px; margin-bottom: 10px; }
        div.stButton > button { background-color: #2D6A4F !important; color: white !important; font-weight: 600 !important; }
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
            pwd = st.text_input("Senha", type="password")
            if st.form_submit_button("Acessar"):
                if pwd == st.secrets["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
else:
    # --- 4. BACKEND ---
    def obter_conector():
        creds_json = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
        return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_json, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]))

    @st.cache_data(ttl=60)
    def carregar_dados_v17():
        client = obter_conector()
        db = client.open("GestorObras_DB")
        df_o = pd.DataFrame(db.worksheet("Obras").get_all_records())
        df_f = pd.DataFrame(db.worksheet("Financeiro").get_all_records())
        df_o['Valor Total'] = pd.to_numeric(df_o['Valor Total'], errors='coerce').fillna(0)
        df_f['Valor'] = pd.to_numeric(df_f['Valor'], errors='coerce').fillna(0)
        df_f['Data_DT'] = pd.to_datetime(df_f['Data'], errors='coerce')
        return df_o, df_f

    df_obras, df_fin = carregar_dados_v17()

    # --- 5. LÓGICA DE ALERTA DE PREÇOS ---
    def analisar_inflacao(df):
        # Filtra apenas saídas e tenta extrair o nome do produto antes do ":"
        df_gastos = df[df['Tipo'].str.contains('Saída')].copy()
        df_gastos['Insumo'] = df_gastos['Descrição'].apply(lambda x: x.split(':')[0].strip() if ':' in x else x.strip())
        
        # Agrupa por insumo e pega as duas últimas compras
        alertas = []
        for insumo in df_gastos['Insumo'].unique():
            compras = df_gastos[df_gastos['Insumo'] == insumo].sort_values('Data_DT')
            if len(compras) >= 2:
                ultima = compras.iloc[-1]
                penultima = compras.iloc[-2]
                if ultima['Valor'] > penultima['Valor']:
                    var = ((ultima['Valor'] / penultima['Valor']) - 1) * 100
                    alertas.append({'Insumo': insumo, 'Aumento': var, 'Preço Anterior': penultima['Valor'], 'Preço Atual': ultima['Valor']})
        return pd.DataFrame(alertas)

    # --- 6. MENU ---
    with st.sidebar:
        sel = option_menu("GESTOR PRO", ["Dashboard", "Caixa", "Insumos", "Projetos"], 
            icons=['graph-up', 'wallet2', 'cart-check', 'building'], default_index=0)
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- 7. TELAS ---
    if sel == "Dashboard":
        st.title("📊 Painel de Controle")
        c1, c2, c3 = st.columns(3)
        ent = df_fin[df_fin['Tipo'].str.contains('Entrada')]['Valor'].sum()
        sai = df_fin[df_fin['Tipo'].str.contains('Saída')]['Valor'].sum()
        c1.metric("Faturamento", f"R$ {ent:,.2f}")
        c2.metric("Custos", f"R$ {sai:,.2f}")
        c3.metric("Saldo", f"R$ {ent-sai:,.2f}")
        
        st.markdown("---")
        st.plotly_chart(px.area(df_fin[df_fin['Tipo'].str.contains('Saída')].sort_values('Data_DT'), x='Data_DT', y='Valor', title="Evolução de Gastos"), use_container_width=True)

    elif sel == "Insumos":
        st.title("🛒 Monitor de Preços e Inflação")
        df_alertas = analisar_inflacao(df_fin)
        
        if not df_alertas.empty:
            st.error("🚨 ALERTA: Aumento Detectado nos Insumos")
            for _, row in df_alertas.iterrows():
                st.markdown(f"""
                <div class='alert-card'>
                    <strong>{row['Insumo']}</strong> subiu <strong>{row['Aumento']:.1f}%</strong>!<br>
                    De R$ {row['Preço Anterior']:,.2f} para R$ {row['Preço Atual']:,.2f}
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("### Histórico Comparativo")
            st.table(df_alertas)
        else:
            st.success("✅ Nenhum aumento crítico detectado nas últimas compras.")

    elif sel == "Caixa":
        st.title("💸 Lançamento Financeiro")
        st.info("💡 DICA: Para monitorar preços, use o formato 'Produto: Detalhe'. Ex: 'Tijolo: Milheiro tipo A'")
        with st.form("form_caixa"):
            c1, c2, c3 = st.columns(3)
            tp = c1.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
            ob = c2.selectbox("Obra", df_obras['Cliente'].tolist())
            vl = c3.number_input("Valor R$", min_value=0.0)
            ds = st.text_input("Descrição (Produto: Detalhe)")
            if st.form_submit_button("LANÇAR"):
                obter_conector().open("GestorObras_DB").worksheet("Financeiro").append_row([datetime.now().strftime('%Y-%m-%d'), tp, "Geral", ds, vl, ob])
                st.cache_data.clear()
                st.rerun()

    elif sel == "Projetos":
        st.title("📁 Gestão de Obras")
        st.dataframe(df_obras, use_container_width=True)
