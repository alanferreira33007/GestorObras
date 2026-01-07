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
st.set_page_config(page_title="GESTOR PRO | Monitor Completo", layout="wide")

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
    def carregar_dados_v24():
        try:
            client = obter_conector()
            db = client.open("GestorObras_DB")
            df_o = pd.DataFrame(db.worksheet("Obras").get_all_records())
            df_f = pd.DataFrame(db.worksheet("Financeiro").get_all_records())
            df_o['Valor Total'] = pd.to_numeric(df_o['Valor Total'], errors='coerce').fillna(0)
            df_f['Valor'] = pd.to_numeric(df_f['Valor'], errors='coerce').fillna(0)
            df_f['Data_DT'] = pd.to_datetime(df_f['Data'], errors='coerce')
            df_f['Data_BR'] = df_f['Data_DT'].dt.strftime('%d/%m/%Y')
            return df_o, df_f
        except: return pd.DataFrame(), pd.DataFrame()

    df_obras, df_fin = carregar_dados_v24()

    # --- 5. FUNÇÃO DE FORMATAÇÃO R$ ---
    def fmt_moeda(valor):
        return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    # --- 6. MENU LATERAL ---
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
            lista_obras = df_obras['Cliente'].tolist()
            escolha = option_menu(menu_title=None, options=lista_obras, orientation="horizontal", icons=["house"] * len(lista_obras))
            
            dados_obra = df_obras[df_obras['Cliente'] == escolha].iloc[0]
            vgv = dados_obra['Valor Total']
            fin_obra = df_fin[df_fin['Obra Vinculada'] == escolha] if not df_fin.empty else pd.DataFrame()
            custos = fin_obra[fin_obra['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
            lucro = vgv - custos
            roi = (lucro / custos * 100) if custos > 0 else 0
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("VGV", fmt_moeda(vgv))
            c2.metric("Custo Acumulado", fmt_moeda(custos))
            c3.metric("Lucro Estimado", fmt_moeda(lucro))
            c4.metric("ROI", f"{roi:.1f}%")
            
            if not fin_obra.empty and custos > 0:
                df_ev = fin_obra[fin_obra['Tipo'].str.contains('Saída')].sort_values('Data_DT')
                st.plotly_chart(px.line(df_ev, x='Data_DT', y='Valor', title="Evolução de Gastos"), use_container_width=True)

    elif sel == "Caixa":
        st.markdown("### 💸 Lançamento Financeiro")
        with st.form("f_caixa", clear_on_submit=True):
            c1, c2 = st.columns(2); dt = c1.date_input("Data", value=date.today()); tp = c2.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
            c3, c4 = st.columns(2); ob = c3.selectbox("Obra", df_obras['Cliente'].tolist()); vl = c4.number_input("Valor", step=0.01)
            ds = st.text_input("Descrição (Insumo: Detalhe)")
            if st.form_submit_button("LANÇAR"):
                obter_conector().open("GestorObras_DB").worksheet("Financeiro").append_row([dt.strftime('%Y-%m-%d'), tp, "Geral", ds, vl, ob])
                st.cache_data.clear(); st.rerun()
        
        if not df_fin.empty:
            df_c = df_fin[['Data_BR', 'Tipo', 'Descrição', 'Valor', 'Obra Vinculada']].sort_values('Data_DT', ascending=False)
            df_c['Valor'] = df_c['Valor'].apply(fmt_moeda)
            st.dataframe(df_c, use_container_width=True, hide_index=True)

    elif sel == "Insumos":
        st.markdown("### 🛒 Monitor de Preços")
        df_gastos = df_fin[df_fin['Tipo'].str.contains('Saída', na=False)].copy()
        if not df_gastos.empty:
            df_gastos['Insumo'] = df_gastos['Descrição'].apply(lambda x: x.split(':')[0].strip() if ':' in x else x.strip())
            alertas_found = False
            for insumo in df_gastos['Insumo'].unique():
                compras = df_gastos[df_gastos['Insumo'] == insumo].sort_values('Data_DT')
                if len(compras) >= 2:
                    u = compras.iloc[-1]; p = compras.iloc[-2]
                    if u['Valor'] > p['Valor']:
                        alertas_found = True
                        var = ((u['Valor']/p['Valor'])-1)*100
                        st.markdown(f"""
                        <div class='alert-card'>
                            <h4 style='margin:0;'>{insumo} <span style='color:#E63946; float:right;'>+{var:.1f}%</span></h4>
                            <p style='margin:10px 0 0 0; font-size:14px; color:#666;'>
                                Anterior: {fmt_moeda(p['Valor'])} ({p['Data_DT'].strftime('%d/%m/%Y')})<br>
                                <strong>Atual: {fmt_moeda(u['Valor'])} ({u['Data_DT'].strftime('%d/%m/%Y')})</strong>
                            </p>
                        </div>""", unsafe_allow_html=True)
            if not alertas_found: st.success("Nenhum aumento detectado nos insumos monitorados.")
        else: st.info("Lance despesas no Caixa para monitorar preços.")

    elif sel == "Projetos":
        st.title("📁 Gestão de Obras")
        with st.form("f_obra"):
            n = st.text_input("Nome"); v = st.number_input("VGV", step=1000.0)
            if st.form_submit_button("SALVAR"):
                obter_conector().open("GestorObras_DB").worksheet("Obras").append_row([len(df_obras)+1, n, "", "Construção", v, date.today().strftime('%Y-%m-%d'), ""])
                st.cache_data.clear(); st.rerun()
        df_o_ex = df_obras[['Cliente', 'Status', 'Valor Total']].copy()
        df_o_ex['Valor Total'] = df_o_ex['Valor Total'].apply(fmt_moeda)
        st.dataframe(df_o_ex, use_container_width=True, hide_index=True)
