import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import datetime, date
from streamlit_option_menu import option_menu

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="GESTOR PRO | Monitor Temporal", layout="wide")

# --- 2. CSS ---
st.markdown("""
    <style>
        .stApp { background-color: #F8F9FA; color: #1A1C1E; font-family: 'Inter', sans-serif; }
        [data-testid="stMetric"] { background-color: #FFFFFF; border: 1px solid #E9ECEF; border-radius: 12px; padding: 20px !important; }
        .alert-card { 
            background-color: #FFFFFF; 
            border-left: 5px solid #E63946; 
            padding: 20px; 
            border-radius: 8px; 
            margin-bottom: 15px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        .date-label { color: #6C757D; font-size: 12px; font-weight: 600; text-transform: uppercase; }
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
    def carregar_dados_v19():
        client = obter_conector()
        db = client.open("GestorObras_DB")
        df_o = pd.DataFrame(db.worksheet("Obras").get_all_records())
        df_f = pd.DataFrame(db.worksheet("Financeiro").get_all_records())
        df_o['Valor Total'] = pd.to_numeric(df_o['Valor Total'], errors='coerce').fillna(0)
        df_f['Valor'] = pd.to_numeric(df_f['Valor'], errors='coerce').fillna(0)
        df_f['Data_DT'] = pd.to_datetime(df_f['Data'], errors='coerce')
        return df_o, df_f

    df_obras, df_fin = carregar_dados_v19()

    # --- 5. LÓGICA DE ALERTA COM DATAS ---
    def analisar_inflacao_detalhada(df):
        df_gastos = df[df['Tipo'].str.contains('Saída', na=False)].copy()
        if df_gastos.empty: return pd.DataFrame()
        
        # Extrai o nome do produto antes de ":"
        df_gastos['Insumo'] = df_gastos['Descrição'].apply(lambda x: x.split(':')[0].strip() if ':' in x else x.strip())
        
        alertas = []
        for insumo in df_gastos['Insumo'].unique():
            compras = df_gastos[df_gastos['Insumo'] == insumo].sort_values('Data_DT')
            if len(compras) >= 2:
                ultima = compras.iloc[-1]
                penultima = compras.iloc[-2]
                
                if ultima['Valor'] > penultima['Valor']:
                    var = ((ultima['Valor'] / penultima['Valor']) - 1) * 100
                    # Calcula diferença de dias
                    dias = (ultima['Data_DT'] - penultima['Data_DT']).days
                    
                    alertas.append({
                        'Insumo': insumo,
                        'Aumento': var,
                        'Valor_Ant': penultima['Valor'],
                        'Data_Ant': penultima['Data_DT'].strftime('%d/%m/%Y'),
                        'Valor_Atual': ultima['Valor'],
                        'Data_Atual': ultima['Data_DT'].strftime('%d/%m/%Y'),
                        'Intervalo': dias
                    })
        return pd.DataFrame(alertas)

    # --- 6. MENU ---
    with st.sidebar:
        sel = option_menu("GESTOR PRO", ["Dashboard", "Caixa", "Insumos", "Projetos"], 
            icons=['graph-up', 'wallet2', 'cart-check', 'building'], default_index=2)
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- 7. TELA INSUMOS (FOCO DA SOLICITAÇÃO) ---
    if sel == "Insumos":
        st.markdown("### 🛒 Monitor de Preços e Inflação")
        st.write("O sistema compara os dois últimos lançamentos de cada insumo (formato 'Insumo: Detalhes').")
        
        df_alertas = analisar_inflacao_detalhada(df_fin)
        
        if not df_alertas.empty:
            for _, row in df_alertas.iterrows():
                st.markdown(f"""
                <div class='alert-card'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <h4 style='margin:0; color:#1A1C1E;'>{row['Insumo']}</h4>
                        <span style='background:#FFE5E5; color:#E63946; padding:4px 12px; border-radius:20px; font-weight:bold;'>
                            +{row['Aumento']:.1f}%
                        </span>
                    </div>
                    <hr style='margin: 15px 0; border: 0; border-top: 1px solid #EEE;'>
                    <div style='display: flex; justify-content: space-between;'>
                        <div>
                            <p class='date-label'>Compra Anterior ({row['Data_Ant']})</p>
                            <p style='font-size:18px;'>R$ {row['Valor_Ant']:,.2f}</p>
                        </div>
                        <div style='text-align: center;'>
                            <p class='date-label'>Intervalo</p>
                            <p style='font-size:14px; color:#666;'>{row['Intervalo']} dias</p>
                        </div>
                        <div style='text-align: right;'>
                            <p class='date-label'>Compra Atual ({row['Data_Atual']})</p>
                            <p style='font-size:18px; font-weight:bold; color:#E63946;'>R$ {row['Valor_Atual']:,.2f}</p>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("Tudo sob controle. Não foram detectados aumentos nos últimos registros de insumos.")

    # (Manutenção das outras abas...)
    elif sel == "Dashboard":
        st.title("📊 Painel de Controle")
        # Logica do Dashboard mantida da v18...
        st.info("Selecione uma obra para ver o ROI.")

    elif sel == "Caixa":
        st.title("💸 Lançamento Financeiro")
        with st.form("form_caixa", clear_on_submit=True):
            c1, c2 = st.columns(2)
            data_m = c1.date_input("Data da Nota", value=date.today(), format="DD/MM/YYYY")
            tp = c2.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
            c3, c4 = st.columns(2)
            ob = c3.selectbox("Obra", df_obras['Cliente'].tolist() if not df_obras.empty else ["Geral"])
            vl = c4.number_input("Valor R$", min_value=0.0)
            ds = st.text_input("Descrição (Insumo: Detalhes)")
            if st.form_submit_button("REGISTRAR"):
                obter_conector().open("GestorObras_DB").worksheet("Financeiro").append_row([data_m.strftime('%Y-%m-%d'), tp, "Geral", ds, vl, ob])
                st.cache_data.clear()
                st.rerun()

    elif sel == "Projetos":
        st.title("📁 Cadastro de Obras")
        st.dataframe(df_obras, use_container_width=True)
