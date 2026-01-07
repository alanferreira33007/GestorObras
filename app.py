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
st.set_page_config(page_title="GESTOR PRO | Registro Manual", layout="wide")

# --- 2. CSS CORPORATIVO REFINADO ---
st.markdown("""
    <style>
        .stApp { background-color: #F8F9FA; color: #1A1C1E; font-family: 'Inter', sans-serif; }
        [data-testid="stMetric"] { background-color: #FFFFFF; border: 1px solid #E9ECEF; border-radius: 12px; padding: 20px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
        div.stButton > button { background-color: #2D6A4F !important; color: white !important; border-radius: 6px !important; font-weight: 600 !important; width: 100%; height: 45px; }
        .alert-card { background-color: #FFF5F5; border: 1px solid #FEB2B2; padding: 15px; border-radius: 10px; margin-bottom: 10px; color: #C53030; }
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
    # --- 4. BACKEND ---
    def obter_conector():
        creds_json = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        return gspread.authorize(creds)

    @st.cache_data(ttl=60)
    def carregar_dados_v18():
        try:
            client = obter_conector()
            db = client.open("GestorObras_DB")
            df_o = pd.DataFrame(db.worksheet("Obras").get_all_records())
            df_f = pd.DataFrame(db.worksheet("Financeiro").get_all_records())
            
            df_o['Valor Total'] = pd.to_numeric(df_o['Valor Total'], errors='coerce').fillna(0)
            df_f['Valor'] = pd.to_numeric(df_f['Valor'], errors='coerce').fillna(0)
            
            # Tratamento de Datas para processamento e exibição
            df_f['Data_DT'] = pd.to_datetime(df_f['Data'], errors='coerce')
            df_f['Data_BR'] = df_f['Data_DT'].dt.strftime('%d/%m/%Y')
            
            return df_o, df_f
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return pd.DataFrame(), pd.DataFrame()

    df_obras, df_fin = carregar_dados_v18()

    # --- 5. LÓGICA DE MONITORAMENTO DE PREÇOS ---
    def analisar_inflacao(df):
        df_gastos = df[df['Tipo'].str.contains('Saída', na=False)].copy()
        if df_gastos.empty: return pd.DataFrame()
        
        df_gastos['Insumo'] = df_gastos['Descrição'].apply(lambda x: x.split(':')[0].strip() if ':' in x else x.strip())
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
        st.markdown("<h3 style='text-align:center; color:#2D6A4F;'>GESTOR PRO</h3>", unsafe_allow_html=True)
        sel = option_menu(None, ["Investimentos", "Caixa", "Insumos", "Projetos"], 
            icons=['graph-up-arrow', 'wallet2', 'cart-check', 'building'], default_index=0,
            styles={"nav-link-selected": {"background-color": "#E9F5EE", "color": "#2D6A4F"}})
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- 7. TELAS ---
    if sel == "Investimentos":
        st.markdown("### 📊 Performance e ROI")
        if not df_obras.empty:
            escolha = st.selectbox("Selecione a Casa", df_obras['Cliente'].tolist())
            dados_obra = df_obras[df_obras['Cliente'] == escolha].iloc[0]
            vgv = dados_obra['Valor Total']
            
            fin_obra = df_fin[df_fin['Obra Vinculada'] == escolha]
            custos = fin_obra[fin_obra['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
            lucro = vgv - custos
            roi = (lucro / custos * 100) if custos > 0 else 0
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("VGV (Venda)", f"R$ {vgv:,.2f}")
            c2.metric("Custo Total", f"R$ {custos:,.2f}", delta=f"{(custos/vgv*100 if vgv>0 else 0):.1f}% do VGV", delta_color="inverse")
            c3.metric("Lucro Estimado", f"R$ {lucro:,.2f}")
            c4.metric("ROI Atual", f"{roi:.1f}%")
            
            st.markdown("---")
            df_ev = fin_obra[fin_obra['Tipo'].str.contains('Saída')].sort_values('Data_DT')
            fig = px.line(df_ev, x='Data_DT', y='Valor', markers=True, title="Histórico de Desembolso", color_discrete_sequence=['#E63946'])
            fig.update_layout(xaxis_tickformat='%d/%m/%Y', xaxis_title="Data da Compra")
            st.plotly_chart(fig, use_container_width=True)

    elif sel == "Caixa":
        st.markdown("### 💸 Lançamento Financeiro")
        with st.form("form_caixa", clear_on_submit=True):
            c1, c2 = st.columns(2)
            data_manual = c1.date_input("Data da Compra/Recebimento", value=date.today(), format="DD/MM/YYYY")
            tp = c2.selectbox("Tipo de Movimentação", ["Saída (Despesa)", "Entrada"])
            
            c3, c4 = st.columns(2)
            ob = c3.selectbox("Vincular à Casa", df_obras['Cliente'].tolist() if not df_obras.empty else ["Geral"])
            vl = c4.number_input("Valor da Nota/Recibo (R$)", min_value=0.0, step=50.0)
            
            ds = st.text_input("Descrição (Produto: Detalhes para monitorar preço)")
            
            if st.form_submit_button("EFETIVAR LANÇAMENTO"):
                obter_conector().open("GestorObras_DB").worksheet("Financeiro").append_row([
                    data_manual.strftime('%Y-%m-%d'), tp, "Geral", ds, vl, ob
                ])
                st.cache_data.clear()
                st.success(f"Lançamento de {data_manual.strftime('%d/%m/%Y')} registrado com sucesso!")
                st.rerun()
        
        st.markdown("#### Extrato Recente")
        df_exibir = df_fin[['Data_BR', 'Tipo', 'Descrição', 'Valor', 'Obra Vinculada']].sort_values('Data_BR', ascending=False)
        st.dataframe(df_exibir, use_container_width=True, hide_index=True)

    elif sel == "Insumos":
        st.title("🛒 Monitor de Inflação")
        df_alertas = analisar_inflacao(df_fin)
        if not df_alertas.empty:
            for _, row in df_alertas.iterrows():
                st.markdown(f"""<div class='alert-card'><strong>{row['Insumo']}</strong> subiu {row['Aumento']:.1f}% (De R$ {row['Preço Anterior']:,.2f} para R$ {row['Preço Atual']:,.2f})</div>""", unsafe_allow_html=True)
        else:
            st.success("Nenhuma variação brusca de preço detectada.")

    elif sel == "Projetos":
        st.title("📁 Gestão de Obras")
        with st.form("form_obra"):
            c1, c2, c3 = st.columns([2,1,1])
            nome = c1.text_input("Nome da Obra")
            vgv = c2.number_input("VGV Venda", step=1000.0)
            dt_inicio = c3.date_input("Data de Início", value=date.today(), format="DD/MM/YYYY")
            if st.form_submit_button("CADASTRAR"):
                obter_conector().open("GestorObras_DB").worksheet("Obras").append_row([
                    len(df_obras)+1, nome, "", "Construção", vgv, dt_inicio.strftime('%Y-%m-%d'), ""
                ])
                st.cache_data.clear()
                st.rerun()
        st.dataframe(df_obras, use_container_width=True)
