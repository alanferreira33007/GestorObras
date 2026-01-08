import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from streamlit_option_menu import option_menu
import time

from database import carregar_dados, salvar_financeiro, salvar_obra
from relatorios import fmt_moeda

# =================================================
# CONFIGURAÇÃO
# =================================================
st.set_page_config(
    page_title="GESTOR PRO | Business Intelligence",
    layout="wide"
)

# =================================================
# ESTILO GLOBAL (DASHBOARD)
# =================================================
st.markdown("""
<style>
.stApp {
    background-color: #F8F9FA;
}

h1, h2, h3 {
    color: #1B4332;
}

.card {
    background-color: #FFFFFF;
    border-radius: 14px;
    padding: 20px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.04);
    height: 100%;
}

.card-title {
    font-size: 14px;
    color: #6C757D;
    margin-bottom: 6px;
}

.card-value {
    font-size: 26px;
    font-weight: 700;
    color: #1B4332;
}

div.stButton > button {
    width: 100%;
    height: 45px;
    border-radius: 8px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# =================================================
# FUNÇÃO CENTRAL DE CÁLCULO
# =================================================
def calcular_resultado_obra(df_fin, obra, vgv):
    df = df_fin[df_fin["Obra Vinculada"] == obra].copy()
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)

    df_saidas = df[df["Tipo"].str.contains("Saída", case=False, na=False)]
    df_entradas = df[df["Tipo"].str.contains("Entrada", case=False, na=False)]

    custos = df_saidas["Valor"].sum()
    entradas = df_entradas["Valor"].sum()

    lucro = vgv - custos + entradas
    roi = (lucro / custos * 100) if custos > 0 else 0

    return custos, entradas, lucro, roi, df_saidas

# =================================================
# LOGIN
# =================================================
if "auth" not in st.session_state:
    st.session_state["auth"] = False

if not st.session_state["auth"]:
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        st.markdown("## 🔐 Gestor Pro")
        senha = st.text_input("Senha de acesso", type="password")
        if st.button("Entrar"):
            if senha == st.secrets["password"]:
                st.session_state["auth"] = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    st.stop()

# =================================================
# DADOS
# =================================================
df_obras, df_fin = carregar_dados()
lista_obras = df_obras["Cliente"].tolist() if not df_obras.empty else []

# =================================================
# SIDEBAR
# =================================================
with st.sidebar:
    st.markdown("### 📊 Gestor Pro")
    sel = option_menu(
        None,
        ["Investimentos", "Caixa", "Projetos"],
        icons=["bar-chart", "currency-dollar", "bricks"],
        default_index=0
    )

# =================================================
# INVESTIMENTOS (DASHBOARD)
# =================================================
if sel == "Investimentos":

    st.markdown("# 📊 Dashboard Financeiro")

    if df_obras.empty:
        st.info("Cadastre uma obra para iniciar.")
        st.stop()

    obra_sel = st.selectbox("Selecione a obra", lista_obras)
    obra = df_obras[df_obras["Cliente"] == obra_sel].iloc[0]
    vgv = float(obra["Valor Total"])

    custos, entradas, lucro, roi, df_saidas = calcular_resultado_obra(
        df_fin, obra_sel, vgv
    )

    # KPIs
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="card">
            <div class="card-title">VGV</div>
            <div class="card-value">{fmt_moeda(vgv)}</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="card">
            <div class="card-title">Custos</div>
            <div class="card-value">{fmt_moeda(custos)}</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="card">
            <div class="card-title">Lucro</div>
            <div class="card-value">{fmt_moeda(lucro)}</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="card">
            <div class="card-title">ROI</div>
            <div class="card-value">{roi:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Gráfico
    if not df_saidas.empty:
        st.markdown("### 📉 Distribuição de Custos")
        pie = df_saidas.groupby("Categoria")["Valor"].sum().reset_index()
        fig = px.pie(
            pie,
            values="Valor",
            names="Categoria",
            hole=0.5
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhuma despesa lançada.")

# =================================================
# CAIXA
# =================================================
if sel == "Caixa":

    st.markdown("# 💸 Fluxo de Caixa")

    if not lista_obras:
        st.info("Cadastre uma obra primeiro.")
        st.stop()

    obra_sel = st.selectbox("Obra", lista_obras)

    st.markdown("### ➕ Novo Lançamento")
    with st.form("form_caixa", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        data = c1.date_input("Data", date.today())
        tipo = c2.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
        cat = c3.selectbox("Categoria", ["Material", "Mão de Obra", "Serviços", "Impostos", "Outros"])

        c4, c5 = st.columns(2)
        valor = c4.number_input("Valor", min_value=0.0)
        desc = c5.text_input("Descrição")

        if st.form_submit_button("Salvar lançamento"):
            salvar_financeiro([
                data.strftime("%Y-%m-%d"),
                tipo,
                cat,
                desc,
                valor,
                obra_sel
            ])
            st.success("Lançamento salvo")
            st.rerun()

    st.divider()

    st.markdown("### 📋 Movimentações")
    df_vis = df_fin[df_fin["Obra Vinculada"] == obra_sel].copy()

    if df_vis.empty:
        st.info("Nenhuma movimentação.")
    else:
        df_vis["Data"] = pd.to_datetime(df_vis["Data"]).dt.strftime("%d/%m/%Y")
        df_vis["Valor"] = df_vis["Valor"].apply(fmt_moeda)

        st.dataframe(
            df_vis[["Data", "Tipo", "Categoria", "Descrição", "Valor"]],
            use_container_width=True,
            hide_index=True
        )

# =================================================
# PROJETOS
# =================================================
if sel == "Projetos":

    st.markdown("# 🏗️ Projetos / Obras")

    with st.expander("➕ Cadastrar Nova Obra"):
        with st.form("form_obra", clear_on_submit=True):
            nome = st.text_input("Nome da obra")
            vgv = st.number_input("VGV", min_value=0.0)
            if st.form_submit_button("Cadastrar"):
                salvar_obra([
                    len(df_obras) + 1,
                    nome,
                    "",
                    "Casa",
                    vgv,
                    date.today().strftime("%Y-%m-%d"),
                    "Planejamento"
                ])
                st.success("Obra cadastrada")
                st.rerun()

    st.divider()

    if df_obras.empty:
        st.info("Nenhuma obra cadastrada.")
    else:
        st.markdown("### 📋 Obras Cadastradas")
        st.dataframe(df_obras, use_container_width=True, hide_index=True)
