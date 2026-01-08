import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from streamlit_option_menu import option_menu

# --- 1. CONFIGURAÇÃO DE INTERFACE ---
st.set_page_config(page_title="GESTOR PRO | Master v27.1", layout="wide")

st.markdown("""
    <style>
        .stApp { background-color: #F8F9FA; color: #1A1C1E; font-family: 'Inter', sans-serif; }
        [data-testid="stMetric"] { background-color: #FFFFFF; border: 1px solid #E9ECEF; border-radius: 12px; padding: 20px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
        div.stButton > button { background-color: #2D6A4F !important; color: white !important; border-radius: 6px !important; font-weight: 600 !important; width: 100%; height: 45px; }
        .alert-card { background-color: #FFFFFF; border-left: 5px solid #E63946; padding: 20px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        header, footer, #MainMenu {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 2. FUNÇÕES DE FORMATAÇÃO E CONEXÃO ---
def fmt_moeda(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except:
        return f"R$ {valor}"

def obter_conector():
    creds_json = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope))

# --- 3. SISTEMA DE LOGIN CENTRALIZADO ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        with st.form("login_form"):
            st.markdown("<h2 style='text-align:center; color:#2D6A4F;'>GESTOR PRO</h2>", unsafe_allow_html=True)
            pwd = st.text_input("Chave de Acesso", type="password")
            if st.form_submit_button("ENTRAR NO SISTEMA"):
                if pwd == st.secrets["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else: st.error("Acesso Negado.")
else:
    # --- 4. CARREGAMENTO DE DADOS ---
    @st.cache_data(ttl=10)
    def carregar_dados():
        try:
            client = obter_conector()
            db = client.open("GestorObras_DB")
            df_o = pd.DataFrame(db.worksheet("Obras").get_all_records())
            df_f = pd.DataFrame(db.worksheet("Financeiro").get_all_records())
            
            # Garantir tipos e datas antes de qualquer operação
            if not df_o.empty:
                df_o['Valor Total'] = pd.to_numeric(df_o['Valor Total'], errors='coerce').fillna(0)
            if not df_f.empty:
                df_f['Valor'] = pd.to_numeric(df_f['Valor'], errors='coerce').fillna(0)
                df_f['Data_DT'] = pd.to_datetime(df_f['Data'], errors='coerce')
                df_f['Data_BR'] = df_f['Data_DT'].dt.strftime('%d/%m/%Y')
            else:
                df_f = pd.DataFrame(columns=['Data', 'Tipo', 'Descrição', 'Valor', 'Obra Vinculada', 'Data_DT', 'Data_BR'])
            return df_o, df_f
        except: return pd.DataFrame(), pd.DataFrame()

    df_obras, df_fin = carregar_dados()

    # --- 5. NAVEGAÇÃO LATERAL ---
    with st.sidebar:
        sel = option_menu("MENU", ["Investimentos", "Caixa", "Insumos", "Projetos"], 
            icons=['graph-up-arrow', 'wallet2', 'cart-check', 'building'], default_index=0)
        st.markdown("---")
        if st.button("🚪 Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- 6. TELAS ---
    if sel == "Investimentos":
        st.markdown("### 📊 Performance e ROI por Obra")
        if not df_obras.empty:
            lista = df_obras['Cliente'].tolist()
            escolha = option_menu(None, options=lista, orientation="horizontal", icons=["house"]*len(lista),
                styles={"nav-link-selected": {"background-color": "#2D6A4F"}})
            
            obra_row = df_obras[df_obras['Cliente'] == escolha].iloc[0]
            vgv = obra_row['Valor Total']
            df_v = df_fin[df_fin['Obra Vinculada'] == escolha] if not df_fin.empty else pd.DataFrame()
            
            custos = df_v[df_v['Tipo'].str.contains('Saída', na=False)]['Valor'].sum()
            lucro = vgv - custos
            roi = (lucro / custos * 100) if custos > 0 else 0
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("VGV Venda", fmt_moeda(vgv))
            c2.metric("Custo Total", fmt_moeda(custos))
            c3.metric("Lucro Estimado", fmt_moeda(lucro))
            c4.metric("ROI Atual", f"{roi:.1f}%")
            
            if not df_v.empty and custos > 0:
                fig = px.line(df_v[df_v['Tipo'].str.contains('Saída')].sort_values('Data_DT'), x='Data_DT', y='Valor', markers=True, color_discrete_sequence=['#2D6A4F'])
                fig.update_layout(xaxis_tickformat='%d/%m/%Y', plot_bgcolor='white')
                st.plotly_chart(fig, use_container_width=True)
        else: st.info("Cadastre uma obra para iniciar.")

    elif sel == "Caixa":
        st.markdown("### 💸 Lançamento de Caixa")
        with st.form("f_caixa", clear_on_submit=True):
            c1, c2 = st.columns(2)
            dt_input = c1.date_input("Data da Compra", value=date.today(), format="DD/MM/YYYY")
            tp_input = c2.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
            c3, c4 = st.columns(2)
            ob_input = c3.selectbox("Obra", df_obras['Cliente'].tolist() if not df_obras.empty else ["Geral"])
            vl_input = c4.number_input("Valor R$", format="%.2f", step=0.01)
            ds_input = st.text_input("Descrição (Ex: Insumo: Detalhe)")
            
            if st.form_submit_button("REGISTRAR"):
                try:
                    obter_conector().open("GestorObras_DB").worksheet("Financeiro").append_row([
                        dt_input.strftime('%Y-%m-%d'), tp_input, "Geral", ds_input, vl_input, ob_input
                    ])
                    st.cache_data.clear(); st.success("Lançado!"); st.rerun()
                except Exception as e: st.error(f"Erro: {e}")

        if not df_fin.empty:
            df_display = df_fin[['Data_BR', 'Tipo', 'Descrição', 'Valor', 'Obra Vinculada']].copy()
            # Ordenação segura pela coluna Data_DT que garantimos no carregamento
            df_display = df_display.sort_values(by=df_fin.columns.get_loc('Data_DT'), ascending=False)
            df_display['Valor'] = df_display['Valor'].apply(fmt_moeda)
            st.dataframe(df_display, use_container_width=True, hide_index=True)

    elif sel == "Insumos":
        st.markdown("### 🛒 Monitor de Inflação")
        df_g = df_fin[df_fin['Tipo'].str.contains('Saída', na=False)].copy()
        if not df_g.empty:
            df_g['Insumo'] = df_g['Descrição'].apply(lambda x: x.split(':')[0].strip() if ':' in x else x.strip())
            alertas = False
            for item in df_g['Insumo'].unique():
                hist = df_g[df_g['Insumo'] == item].sort_values('Data_DT')
                if len(hist) >= 2:
                    u, p = hist.iloc[-1], hist.iloc[-2]
                    if u['Valor'] > p['Valor']:
                        alertas = True
                        var = ((u['Valor']/p['Valor'])-1)*100
                        st.markdown(f"""<div class='alert-card'>
                            <strong>{item}</strong> <span style='color:#E63946; float:right;'>+{var:.1f}%</span><br>
                            <small>Anterior: {fmt_moeda(p['Valor'])} ({p['Data_BR']})</small><br>
                            <strong>Atual: {fmt_moeda(u['Valor'])} ({u['Data_BR']})</strong>
                        </div>""", unsafe_allow_html=True)
            if not alertas: st.success("Nenhum aumento detectado.")
        else: st.info("Sem dados para análise.")

    elif sel == "Projetos":
        st.markdown("### 📁 Gestão de Obras")
        with st.form("f_obra"):
            n_obra = st.text_input("Nome da Casa")
            v_obra = st.number_input("VGV Venda Pretendido", format="%.2f")
            if st.form_submit_button("CADASTRAR OBRA"):
                try:
                    obter_conector().open("GestorObras_DB").worksheet("Obras").append_row([
                        len(df_obras)+1, n_obra, "", "Construção", v_obra, date.today().strftime('%Y-%m-%d'), ""
                    ])
                    st.cache_data.clear(); st.success("Obra salva!"); st.rerun()
                except Exception as e: st.error(f"Erro: {e}")
        
        if not df_obras.empty:
            df_o_ex = df_obras[['Cliente', 'Status', 'Valor Total']].copy()
            df_o_ex['Valor Total'] = df_o_ex['Valor Total'].apply(fmt_moeda)
            st.dataframe(df_o_ex, use_container_width=True, hide_index=True)
