import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, datetime
from streamlit_option_menu import option_menu
import time

from database import carregar_dados, salvar_financeiro, salvar_obra
from relatorios import fmt_moeda, gerar_relatorio_investimentos_pdf, download_pdf_one_click

# =================================================
# CONFIG
# =================================================
st.set_page_config(page_title="GESTOR PRO | Business Intelligence", layout="wide")

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 28px; color: #1B4332; }
div.stButton > button {
    width: 100%;
    height: 3em;
    border-radius: 8px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# =================================================
# FEEDBACK
# =================================================
def toast(msg, icon="✅"):
    st.toast(msg, icon=icon)

# =================================================
# FUNÇÃO CENTRAL DE CÁLCULO (CHAVE DO SISTEMA)
# =================================================
def calcular_resultado_obra(df_fin, obra, vgv):
    df = df_fin[df_fin["Obra Vinculada"] == obra].copy()

    if df.empty:
        return {
            "custos": 0,
            "receitas": 0,
            "lucro": vgv,
            "roi": 0,
            "df_saidas": pd.DataFrame(),
            "df_receitas": pd.DataFrame()
        }

    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)

    df_saidas = df[df["Tipo"].str.contains("Saída", case=False, na=False)]
    df_receitas = df[df["Tipo"].str.contains("Entrada", case=False, na=False)]

    custos = df_saidas["Valor"].sum()
    receitas = df_receitas["Valor"].sum()

    lucro = vgv - custos + receitas
    roi = (lucro / custos * 100) if custos > 0 else 0

    return {
        "custos": custos,
        "receitas": receitas,
        "lucro": lucro,
        "roi": roi,
        "df_saidas": df_saidas,
        "df_receitas": df_receitas
    }

# =================================================
# LOGIN
# =================================================
if "auth" not in st.session_state:
    st.session_state["auth"] = False

if not st.session_state["auth"]:
    _, c, _ = st.columns([1,1,1])
    with c:
        st.title("🔐 Gestor Pro")
        pwd = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if pwd == st.secrets["password"]:
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
# MENU
# =================================================
with st.sidebar:
    sel = option_menu(
        "MENU",
        ["Investimentos", "Caixa", "Projetos"],
        icons=["pie-chart", "currency-dollar", "bricks"],
        default_index=0
    )

# =================================================
# INVESTIMENTOS (DASHBOARD CONSISTENTE)
# =================================================
if sel == "Investimentos":

    if df_obras.empty:
        st.info("Cadastre uma obra primeiro.")
        st.stop()

    st.title("📊 Dashboard Financeiro da Obra")

    obra_sel = st.selectbox("Selecione a obra", lista_obras)
    obra = df_obras[df_obras["Cliente"] == obra_sel].iloc[0]
    vgv = float(obra["Valor Total"])

    res = calcular_resultado_obra(df_fin, obra_sel, vgv)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VGV", fmt_moeda(vgv))
    c2.metric("Custos", fmt_moeda(res["custos"]))
    c3.metric("Lucro", fmt_moeda(res["lucro"]))
    c4.metric("ROI", f"{res['roi']:.1f}%")

    perc = res["custos"] / vgv if vgv > 0 else 0
    st.progress(min(perc, 1.0))
    st.caption(f"{perc*100:.1f}% do orçamento consumido")

    st.divider()

    if not res["df_saidas"].empty:
        pie = res["df_saidas"].groupby("Categoria")["Valor"].sum().reset_index()
        fig = px.pie(pie, values="Valor", names="Categoria", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

# =================================================
# CAIXA (ISOLADO)
# =================================================
if sel == "Caixa":

    if not lista_obras:
        st.info("Cadastre uma obra primeiro.")
        st.stop()

    st.title("💸 Fluxo de Caixa")
    obra_sel = st.selectbox("Selecione a obra", lista_obras)

    if "novo_lanc" not in st.session_state:
        st.session_state["novo_lanc"] = False

    if st.button("➕ Efetuar Lançamento"):
        st.session_state["novo_lanc"] = True

    if st.session_state["novo_lanc"]:
        with st.form("form_caixa", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            f_data = c1.date_input("Data", date.today())
            f_tipo = c2.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
            f_cat = c3.selectbox("Categoria", ["Material","Mão de Obra","Serviços","Impostos","Outros"])

            c4, c5 = st.columns(2)
            f_valor = c4.number_input("Valor", min_value=0.0)
            f_desc = c5.text_input("Descrição")

            if st.form_submit_button("Salvar"):
                salvar_financeiro([
                    f_data.strftime("%Y-%m-%d"),
                    f_tipo,
                    f_cat,
                    f_desc,
                    f_valor,
                    obra_sel
                ])
                st.session_state["novo_lanc"] = False
                st.rerun()

    st.divider()

    df_vis = df_fin[df_fin["Obra Vinculada"] == obra_sel].copy()

    if df_vis.empty:
        st.info("Nenhuma movimentação.")
    else:
        df_vis["Data"] = pd.to_datetime(df_vis["Data"]).dt.strftime("%d/%m/%Y")
        df_vis["Valor"] = df_vis["Valor"].apply(fmt_moeda)

        st.dataframe(
            df_vis[["Data","Tipo","Categoria","Descrição","Valor","Obra Vinculada"]],
            use_container_width=True,
            hide_index=True
        )

# =================================================
# PROJETOS
# =================================================
if sel == "Projetos":

    st.title("🏗️ Portfólio de Obras")

    with st.expander("➕ Cadastrar Nova Obra"):
        with st.form("form_obra", clear_on_submit=True):
            nome = st.text_input("Nome da Obra")
            vgv = st.number_input("VGV", min_value=0.0)
            if st.form_submit_button("Salvar"):
                salvar_obra([
                    len(df_obras)+1,
                    nome,
                    "",
                    "Casa",
                    vgv,
                    date.today().strftime("%Y-%m-%d"),
                    "Planejamento"
                ])
                st.rerun()

    st.divider()

    if df_obras.empty:
        st.info("Nenhuma obra cadastrada.")
    else:
        st.dataframe(df_obras, use_container_width=True, hide_index=True)
