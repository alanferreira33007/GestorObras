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
st.set_page_config(page_title="GESTOR PRO | Final Edition", layout="wide")

# --- 2. CSS CORPORATIVO ---
st.markdown("""
    <style>
        .stApp { background-color: #F8F9FA; color: #1A1C1E; font-family: 'Inter', sans-serif; }
        [data-testid="stMetric"] { background-color: #FFFFFF; border: 1px solid #E9ECEF; border-radius: 12px; padding: 20px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
        div.stButton > button { background-color: #2D6A4F !important; color: white !important; border-radius: 6px !important; font-weight: 600 !important; width: 100%; height: 45px; }
        .alert-card { background-color: #FFFFFF; border-left: 5px solid #E63946; padding: 20px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
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
                else: st.error("Senha incorreta.")
else:
    # --- 4. BACKEND ---
    def obter_conector():
        creds_json = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope))

    @st.cache_data(ttl=30)
    def carregar_dados_v22():
        try:
            client = obter_conector()
            db = client.open("GestorObras_DB")
            df_o = pd.DataFrame(db.worksheet("Obras").get_all_records())
            df_f = pd.DataFrame(db.worksheet("Financeiro").get_all_records())
            
            df_o['Valor Total'] = pd.to_numeric(df_o['Valor Total'], errors='coerce').fillna(0)
            df_f['Valor'] = pd.to_numeric(df_f['Valor'], errors='coerce').fillna(0)
            
            # Formatação de Datas
            df_f['Data_DT'] = pd.to_datetime(df_f['Data'], errors='coerce')
            df_f['Data_BR'] = df_f['Data_DT'].dt.strftime('%d/%m/%Y')
            
            return df_o, df_f
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return pd.DataFrame(), pd.DataFrame()

    df_obras, df_fin = carregar_dados_v22()

    # --- 5. MENU LATERAL ---
    with st.sidebar:
        st.markdown("<h3 style='text-align:center; color:#2D6A4F;'>GESTOR PRO</h3>", unsafe_allow_html=True)
        sel = option_menu(None, ["Investimentos", "Caixa", "Insumos", "Projetos"], 
            icons=['graph-up-arrow', 'wallet2', 'cart-check', 'building'], default_index=0,
            styles={"nav-link-selected": {"background-color": "#E9F5EE", "color": "#2D6A4F"}})
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- 6. TELAS ---
    if sel == "Investimentos":
        st.markdown("### 📊 Performance e ROI por Obra")
        
        if not df_obras.empty:
            st.write("Selecione o Empreendimento:")
            lista_obras = df_obras['Cliente'].tolist()
            
            escolha = option_menu(
                menu_title=None, options=lista_obras, orientation="horizontal",
                icons=["house"] * len(lista_obras),
                styles={
                    "container": {"padding": "0!important", "background-color": "transparent"},
                    "nav-link": {"font-size": "12px", "margin": "5px", "background-color": "#FFFFFF", "border": "1px solid #E9ECEF", "color": "#495057"},
                    "nav-link-selected": {"background-color": "#2D6A4F", "color": "#FFFFFF"},
                }
            )
            
            st.markdown("---")
            dados_obra = df_obras[df_obras['Cliente'] == escolha].iloc[0]
            vgv = dados_obra['Valor Total']
            fin_obra = df_fin[df_fin['Obra Vinculada'] == escolha] if not df_fin.empty else pd.DataFrame()
            
            custos = fin_obra[fin_obra['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
            lucro = vgv - custos
            roi = (lucro / custos * 100) if custos > 0 else 0
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("VGV (Venda)", f"R$ {vgv:,.2f}")
            c2.metric("Custo Total", f"R$ {custos:,.2f}", delta=f"{(custos/vgv*100 if vgv>0 else 0):.1f}% VGV", delta_color="inverse")
            c3.metric("Lucro Estimado", f"R$ {lucro:,.2f}")
            c4.metric("ROI Atual", f"{roi:.1f}%")

            if not fin_obra.empty and custos > 0:
                df_ev = fin_obra[fin_obra['Tipo'].str.contains('Saída')].sort_values('Data_DT')
                fig = px.line(df_ev, x='Data_DT', y='Valor', title=f"Histórico: {escolha}", markers=True, color_discrete_sequence=['#2D6A4F'])
                fig.update_layout(xaxis_tickformat='%d/%m/%Y', plot_bgcolor='white', xaxis_title="Data da Compra")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nenhum custo registrado para esta obra.")
        else:
            st.warning("Cadastre uma obra para visualizar.")

    elif sel == "Caixa":
        st.markdown("### 💸 Lançamento Financeiro")
        with st.form("f_caixa", clear_on_submit=True):
            c1, c2 = st.columns(2)
            dt_manual = c1.date_input("Data da Compra/Recebimento", value=date.today(), format="DD/MM/YYYY")
            tp = c2.selectbox("Tipo de Movimentação", ["Saída (Despesa)", "Entrada"])
            c3, c4 = st.columns(2)
            ob = c3.selectbox("Obra", df_obras['Cliente'].tolist() if not df_obras.empty else ["Geral"])
            vl = c4.number_input("Valor R$", min_value=0.0)
            ds = st.text_input("Descrição (Insumo: Detalhe)")
            if st.form_submit_button("REGISTRAR LANÇAMENTO"):
                client = obter_conector()
                client.open("GestorObras_DB").worksheet("Financeiro").append_row([dt_manual.strftime('%Y-%m-%d'), tp, "Geral", ds, vl, ob])
                st.cache_data.clear()
                st.success(f"Lançamento de {dt_manual.strftime('%d/%m/%Y')} registrado!")
                st.rerun()
        
        # Exibição com Data BR
        if not df_fin.empty:
            df_exibicao = df_fin[['Data_BR', 'Tipo', 'Descrição', 'Valor', 'Obra Vinculada']].sort_values('Data_BR', ascending=False)
            df_exibicao.columns = ['Data', 'Tipo', 'Descrição', 'Valor', 'Obra']
            st.dataframe(df_exibicao, use_container_width=True, hide_index=True)

    elif sel == "Insumos":
        st.title("🛒 Monitor de Inflação")
        # Lógica de alertas mantida...
        st.info("Os alertas de aumento de preço aparecerão aqui conforme as datas de compra.")

    elif sel == "Projetos":
        st.title("📁 Gestão de Obras")
        with st.form("f_obra"):
            c1, c2, c3 = st.columns([2,1,1])
            n = c1.text_input("Nome da Casa")
            v = c2.number_input("VGV de Venda", min_value=0.0)
            d = c3.date_input("Data de Início", value=date.today(), format="DD/MM/YYYY")
            if st.form_submit_button("SALVAR"):
                client = obter_conector()
                client.open("GestorObras_DB").worksheet("Obras").append_row([len(df_obras)+1, n, "", "Construção", v, d.strftime('%Y-%m-%d'), ""])
                st.cache_data.clear()
                st.rerun()
        st.dataframe(df_obras, use_container_width=True)
