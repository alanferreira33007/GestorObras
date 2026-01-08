import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, datetime
from streamlit_option_menu import option_menu
import time

from database import carregar_dados, salvar_financeiro, salvar_obra
from relatorios import fmt_moeda, gerar_relatorio_investimentos_pdf, download_pdf_one_click

# =================================================
# CONFIGURAÇÃO DE PÁGINA
# =================================================
st.set_page_config(page_title="GESTOR PRO | Business Intelligence", layout="wide")

# =================================================
# ESTILO
# =================================================
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
def feedback_sucesso_temporario(texto, segundos=3):
    box = st.empty()
    box.success(texto)
    time.sleep(segundos)
    box.empty()

def feedback_toast(texto, icon="✅"):
    st.toast(texto, icon=icon)

# =================================================
# LOGIN
# =================================================
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    _, col, _ = st.columns([1,1,1])
    with col:
        st.title("🔐 Gestor Pro")
        pwd = st.text_input("Senha de Acesso", type="password")
        if st.button("ACESSAR PAINEL"):
            if pwd == st.secrets["password"]:
                st.session_state["authenticated"] = True
                feedback_toast("Login realizado com sucesso")
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
    st.image("https://cdn-icons-png.flaticon.com/512/4222/4222031.png", width=80)
    sel = option_menu(
        "MENU PRINCIPAL",
        ["Investimentos", "Caixa", "Projetos"],
        icons=["pie-chart-fill", "currency-dollar", "bricks"],
        default_index=0
    )
    st.divider()
    if st.button("Sair / Logout"):
        st.session_state["authenticated"] = False
        st.rerun()

# =================================================
# INVESTIMENTOS
# =================================================
if sel == "Investimentos":

    if df_obras.empty:
        st.info("Cadastre uma obra para iniciar.")
        st.stop()

    st.title("📊 Inteligência Financeira")

    obra_sel = st.selectbox("Selecione a obra:", lista_obras)
    obra = df_obras[df_obras["Cliente"] == obra_sel].iloc[0]

    vgv = float(obra["Valor Total"])
    df_v = df_fin[df_fin["Obra Vinculada"] == obra_sel].copy()
    df_saidas = df_v[df_v["Tipo"].str.contains("Saída", case=False, na=False)]

    custos = df_saidas["Valor"].sum()
    lucro = vgv - custos
    roi = (lucro / custos * 100) if custos > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VGV", fmt_moeda(vgv))
    c2.metric("Custos", fmt_moeda(custos))
    c3.metric("Lucro", fmt_moeda(lucro))
    c4.metric("ROI", f"{roi:.1f}%")

# =================================================
# CAIXA (TOTALMENTE ISOLADO)
# =================================================
if sel == "Caixa":

    st.title("💸 Fluxo de Caixa")

    if not lista_obras:
        st.info("Cadastre uma obra primeiro.")
        st.stop()

    obra_sel = st.selectbox("Selecione a obra", lista_obras)

    st.divider()

    if "abrir_form_caixa" not in st.session_state:
        st.session_state["abrir_form_caixa"] = False

    if st.button("➕ Efetuar Lançamento"):
        st.session_state["abrir_form_caixa"] = True

    if st.session_state["abrir_form_caixa"]:
        with st.form("f_caixa", clear_on_submit=True):

            c1, c2, c3 = st.columns(3)
            f_data = c1.date_input("Data", value=date.today())
            f_tipo = c2.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
            f_cat = c3.selectbox(
                "Categoria",
                ["Material", "Mão de Obra", "Serviços", "Impostos", "Outros"]
            )

            c4, c5 = st.columns(2)
            f_valor = c4.number_input("Valor R$", min_value=0.0)
            f_desc = c5.text_input("Descrição")

            if st.form_submit_button("SALVAR"):
                salvar_financeiro([
                    f_data.strftime("%Y-%m-%d"),
                    f_tipo,
                    f_cat,
                    f_desc,
                    f_valor,
                    obra_sel
                ])
                feedback_toast("Lançamento salvo 💸")
                st.session_state["abrir_form_caixa"] = False
                st.rerun()

    st.divider()

    st.subheader("📋 Últimas Movimentações")

    df_vis = df_fin[df_fin["Obra Vinculada"] == obra_sel].copy()

    if df_vis.empty:
        st.info("Nenhuma movimentação registrada.")
    else:
        df_vis["Data"] = pd.to_datetime(df_vis["Data"]).dt.strftime("%d/%m/%Y")
        df_vis["Valor"] = df_vis["Valor"].apply(fmt_moeda)

        st.dataframe(
            df_vis[["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]],
            use_container_width=True,
            hide_index=True
        )

# =================================================
# PROJETOS (TOTALMENTE ISOLADO)
# =================================================
if sel == "Projetos":

    st.title("🏗️ Portfólio de Obras")

    with st.expander("➕ Cadastrar Nova Obra", expanded=False):
        with st.form("f_obra_nova", clear_on_submit=True):

            c1, c2 = st.columns(2)
            f_nome = c1.text_input("Identificação da Obra *")
            f_tipo = c2.selectbox(
                "Tipo de Imóvel",
                ["Casa térrea", "Casa duplex", "Apartamento", "Outro"]
            )

            c3, c4 = st.columns(2)
            f_local = c3.text_input("Localização")
            f_status = c4.selectbox(
                "Status",
                ["Planejamento", "Em execução", "Finalizada", "Vendida"]
            )

            c5, c6 = st.columns(2)
            f_vgv = c5.number_input("VGV *", min_value=0.0, step=1000.0)
            f_custo_prev = c6.number_input("Custo Estimado", min_value=0.0)

            f_inicio = st.date_input("Data de Início", value=date.today())

            if st.form_submit_button("CRIAR OBRA"):
                if not f_nome or f_vgv <= 0:
                    st.error("Informe nome e VGV.")
                else:
                    salvar_obra([
                        len(df_obras) + 1,
                        f_nome,
                        f_local,
                        f_tipo,
                        f_vgv,
                        f_inicio.strftime("%Y-%m-%d"),
                        f_status,
                        f_custo_prev
                    ])
                    feedback_toast("Obra cadastrada 🏗️")
                    st.rerun()

    st.divider()

    if df_obras.empty:
        st.info("Nenhuma obra cadastrada.")
    else:
        st.subheader("📋 Obras Cadastradas")
        st.dataframe(df_obras, use_container_width=True, hide_index=True)
