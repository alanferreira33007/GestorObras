import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, datetime
from streamlit_option_menu import option_menu

# Nossas "peças" separadas
from database import carregar_dados, salvar_financeiro, salvar_obra
from relatorios import fmt_moeda

st.set_page_config(page_title="GESTOR PRO | Master", layout="wide")

# CSS para melhorar o visual
st.markdown("""
<style>
    .stMetric { background-color: #FFFFFF; border: 1px solid #EEE; padding: 15px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    div.stButton > button { background-color: #2D6A4F !important; color: white !important; }
</style>
""", unsafe_allow_html=True)

# --- LOGIN ---
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if not st.session_state["authenticated"]:
    with st.form("login"):
        st.title("🔐 Acesso Gestor Pro")
        pwd = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if pwd == st.secrets["password"]:
                st.session_state["authenticated"] = True
                st.rerun()
            else: st.error("Senha incorreta.")
    st.stop()

# --- CARREGAR DADOS ---
df_obras, df_fin = carregar_dados()
lista_obras = df_obras["Cliente"].unique().tolist()

with st.sidebar:
    sel = option_menu("GESTOR PRO", ["Investimentos", "Caixa", "Projetos"], 
                     icons=["graph-up", "wallet2", "building"], default_index=0)
    if st.button("Sair"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- TELA 1: DASHBOARD (INVESTIMENTOS) ---
if sel == "Investimentos":
    st.header("📊 Performance e ROI por Obra")
    
    if not lista_obras:
        st.info("Cadastre uma obra na aba 'Projetos' para ver os dados.")
    else:
        obra_sel = st.selectbox("Selecione a obra", lista_obras)
        
        # Dados da Obra Selecionada
        obra_row = df_obras[df_obras["Cliente"] == obra_sel].iloc[0]
        vgv = float(obra_row["Valor Total"])
        
        # Filtros de Data
        df_v = df_fin[df_fin["Obra Vinculada"] == obra_sel].copy()
        
        with st.expander("📅 Filtros de Período"):
            df_v_valid = df_v.dropna(subset=["Data_DT"])
            anos = sorted(df_v_valid["Data_DT"].dt.year.unique())
            anos_sel = st.multiselect("Anos", anos, default=anos)
            df_periodo = df_v[df_v["Data_DT"].dt.year.isin(anos_sel)]

        # Cálculos
        df_saidas = df_periodo[df_periodo["Tipo"].str.contains("Saída", case=False, na=False)]
        custos = float(df_saidas["Valor"].sum())
        lucro = vgv - custos
        roi = (lucro / custos * 100) if custos > 0 else 0
        
        # Exibição das Métricas (Os Cards)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("VGV Venda", fmt_moeda(vgv))
        c2.metric("Custo Total", fmt_moeda(custos))
        c3.metric("Lucro Estimado", fmt_moeda(lucro))
        c4.metric("ROI", f"{roi:.1f}%")
        
        # Gráfico 1: Custo por Categoria
        st.subheader("🧾 Custos por Categoria")
        if not df_saidas.empty:
            df_cat = df_saidas.groupby("Categoria")["Valor"].sum().reset_index()
            fig_cat = px.bar(df_cat, x="Categoria", y="Valor", color_discrete_sequence=['#2D6A4F'])
            st.plotly_chart(fig_cat, use_container_width=True)
        else:
            st.write("Sem gastos registrados para esta obra.")

# --- TELA 2: CAIXA (LANÇAMENTOS) ---
elif sel == "Caixa":
    st.header("💸 Gestão de Caixa")
    
    # Formulário de Cadastro
    with st.expander("➕ Novo Lançamento", expanded=False):
        with st.form("f_caixa", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            f_data = col1.date_input("Data", value=date.today())
            f_tipo = col2.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
            f_cat  = col3.selectbox("Categoria", ["Material", "Mão de Obra", "Serviços", "Impostos", "Outros"])
            
            col4, col5 = st.columns(2)
            f_obra = col4.selectbox("Obra", lista_obras if lista_obras else ["Geral"])
            f_valor = col5.number_input("Valor R$", min_value=0.0, step=0.01)
            
            f_desc = st.text_input("Descrição")
            
            if st.form_submit_button("REGISTRAR"):
                salvar_financeiro([f_data.strftime("%Y-%m-%d"), f_tipo, f_cat, f_desc, f_valor, f_obra])
                st.success("Salvo!")
                st.rerun()

    st.subheader("Histórico de Movimentações")
    st.dataframe(df_fin.sort_values("Data_DT", ascending=False), use_container_width=True, hide_index=True)

# --- TELA 3: PROJETOS (OBRAS) ---
elif sel == "Projetos":
    st.header("🏗️ Gestão de Obras")
    
    with st.expander("➕ Cadastrar Nova Obra"):
        with st.form("f_obra", clear_on_submit=True):
            f_nome = st.text_input("Nome do Cliente / Obra")
            f_end = st.text_input("Endereço")
            f_vgv = st.number_input("Valor do Contrato (VGV)", min_value=0.0)
            f_status = st.selectbox("Status", ["Planejamento", "Construção", "Finalizada"])
            
            if st.form_submit_button("CADASTRAR"):
                novo_id = len(df_obras) + 1
                salvar_obra([novo_id, f_nome, f_end, f_status, f_vgv, date.today().strftime("%Y-%m-%d"), "A definir"])
                st.success("Obra cadastrada!")
                st.rerun()

    st.subheader("Lista de Obras")
    st.dataframe(df_obras, use_container_width=True, hide_index=True)
