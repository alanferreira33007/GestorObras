import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
from streamlit_option_menu import option_menu
import time

from database import carregar_dados, salvar_financeiro, salvar_obra
from relatorios import fmt_moeda, gerar_relatorio_investimentos_pdf, download_pdf_one_click

# -------------------------------------------------
# CONFIGURAÇÃO DE PÁGINA
# -------------------------------------------------
st.set_page_config(page_title="GESTOR PRO | Business Intelligence", layout="wide")

# -------------------------------------------------
# ESTILO
# -------------------------------------------------
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

# -------------------------------------------------
# HELPERS DE FEEDBACK (PADRÃO DO APP)
# -------------------------------------------------
def feedback_sucesso_temporario(texto: str, segundos: int = 3):
    box = st.empty()
    box.success(texto)
    time.sleep(segundos)
    box.empty()

def feedback_toast(texto: str, icon: str = "✅"):
    st.toast(texto, icon=icon)

# -------------------------------------------------
# LOGIN
# -------------------------------------------------
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

# -------------------------------------------------
# DADOS
# -------------------------------------------------
df_obras, df_fin = carregar_dados()
lista_obras = df_obras["Cliente"].unique().tolist() if not df_obras.empty else []

# -------------------------------------------------
# SIDEBAR
# -------------------------------------------------
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
        feedback_toast("Logout realizado", icon="👋")
        st.rerun()

# -------------------------------------------------
# TRAVA INICIAL
# -------------------------------------------------
if df_obras.empty and sel != "Projetos":
    st.info("👋 Cadastre sua primeira obra na aba **Projetos** para iniciar o dashboard.")
    st.stop()

# =================================================
# TELA: INVESTIMENTOS
# =================================================
if sel == "Investimentos":
    st.title("📊 Inteligência Financeira da Obra")

    if "gerando_pdf" not in st.session_state:
        st.session_state["gerando_pdf"] = False

    obra_sel = st.selectbox("Selecione a obra para análise:", lista_obras)

    obra = df_obras[df_obras["Cliente"] == obra_sel].iloc[0]
    vgv = float(obra["Valor Total"])

    df_v = df_fin[df_fin["Obra Vinculada"] == obra_sel].copy()
    df_saidas = df_v[df_v["Tipo"].str.contains("Saída", case=False, na=False)]

    custos = pd.to_numeric(df_saidas["Valor"], errors="coerce").fillna(0).sum()
    lucro = vgv - custos
    roi = (lucro / custos * 100) if custos > 0 else 0
    perc_gasto = (custos / vgv) if vgv > 0 else 0

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("VGV", fmt_moeda(vgv))
    k2.metric("Custo", fmt_moeda(custos))
    k3.metric("Lucro", fmt_moeda(lucro))
    k4.metric("ROI", f"{roi:.1f}%")

    st.progress(min(perc_gasto, 1.0))
    st.caption(f"{perc_gasto*100:.1f}% do orçamento consumido")

    st.divider()

    # ----------------------------
    # BOTÃO PDF (PADRONIZADO)
    # ----------------------------
    pode_gerar_pdf = not df_saidas.empty
    col_btn, col_msg = st.columns([1, 2])

    with col_btn:
        if st.button(
            "📄 Gerar relatório executivo em PDF",
            disabled=not pode_gerar_pdf or st.session_state["gerando_pdf"]
        ):
            st.session_state["gerando_pdf"] = True
            with st.spinner("Gerando relatório executivo..."):
                pdf = gerar_relatorio_investimentos_pdf(
                    obra_sel, vgv, custos, lucro, roi, df_saidas
                )
                nome_pdf = f"Relatorio_{obra_sel}_{datetime.now():%Y-%m-%d}.pdf"
                download_pdf_one_click(pdf, nome_pdf)

            feedback_sucesso_temporario("📄 Relatório PDF gerado com sucesso!")
            st.session_state["gerando_pdf"] = False

    with col_msg:
        if not pode_gerar_pdf:
            st.warning("⚠️ O relatório será liberado após o lançamento de despesas.")
        else:
            st.caption("📌 O relatório reflete exclusivamente esta obra.")

    st.divider()

    # GRÁFICOS
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Distribuição de Custos")
        if not df_saidas.empty:
            pie = df_saidas.groupby("Categoria")["Valor"].sum().reset_index()
            fig = px.pie(pie, values="Valor", names="Categoria", hole=.4)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem despesas lançadas.")

    with c2:
        st.subheader("Evolução de Gastos")
        if not df_saidas.empty:
            df_saidas["Data_DT"] = pd.to_datetime(df_saidas["Data_DT"])
            df_saidas = df_saidas.sort_values("Data_DT")
            df_saidas["Acumulado"] = df_saidas["Valor"].cumsum()
            fig = px.line(df_saidas, x="Data_DT", y="Acumulado", markers=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem histórico de gastos.")

# =================================================
# TELA: CAIXA
# =================================================
elif sel == "Caixa":
    st.title("💸 Fluxo de Caixa")

    with st.expander("📝 Novo Lançamento", expanded=False):
        with st.form("f_caixa", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            f_data = c1.date_input("Data", value=date.today())
            f_tipo = c2.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
            f_cat = c3.selectbox(
                "Categoria",
                ["Material", "Mão de Obra", "Serviços", "Impostos", "Outros"]
            )

            c4, c5 = st.columns(2)
            f_obra = c4.selectbox("Obra", lista_obras if lista_obras else ["Geral"])
            f_valor = c5.number_input("Valor R$", min_value=0.0)
            f_desc = st.text_input("Descrição")

            if st.form_submit_button("SALVAR NO GOOGLE SHEETS"):
                salvar_financeiro([
                    f_data.strftime("%Y-%m-%d"),
                    f_tipo,
                    f_cat,
                    f_desc,
                    f_valor,
                    f_obra
                ])
                feedback_toast("Lançamento salvo com sucesso")
                st.rerun()

    st.subheader("Últimas Movimentações")
    if df_fin.empty:
        st.info("Nenhuma movimentação registrada.")
    else:
        st.dataframe(df_fin, use_container_width=True)

# =================================================
# TELA: PROJETOS
# =================================================
elif sel == "Projetos":
    st.title("🏗️ Portfólio de Obras")

    with st.expander("➕ Cadastrar Nova Obra"):
        with st.form("f_obra", clear_on_submit=True):
            f_nome = st.text_input("Nome do Cliente / Identificação da Obra")
            f_vgv = st.number_input("Valor Total do Contrato (VGV)", min_value=0.0)

            if st.form_submit_button("CRIAR PROJETO"):
                salvar_obra([
                    len(df_obras) + 1,
                    f_nome,
                    "",
                    "Construção",
                    f_vgv,
                    date.today().strftime("%Y-%m-%d"),
                    ""
                ])
                feedback_toast("Obra cadastrada com sucesso", icon="🏗️")
                st.rerun()

    if df_obras.empty:
        st.info("Nenhuma obra cadastrada.")
    else:
        st.dataframe(df_obras, use_container_width=True)
