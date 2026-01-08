import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
from streamlit_option_menu import option_menu

# Nossas peças separadas
from database import carregar_dados, salvar_financeiro, salvar_obra
from relatorios import fmt_moeda, gerar_relatorio_investimentos_pdf, download_pdf_one_click

# ----------------------------
# CONFIGURAÇÃO DE PÁGINA
# ----------------------------
st.set_page_config(page_title="GESTOR PRO | Business Intelligence", layout="wide")

# ----------------------------
# ESTILIZAÇÃO
# ----------------------------
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 28px; color: #1B4332; }
    .main-cards {
        background-color: #FFFFFF;
        border-radius: 15px;
        padding: 20px;
        border: 1px solid #E9ECEF;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }
    div.stButton > button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------
# LOGIN (SIMPLIFICADO)
# ----------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.title("🔐 Gestor Pro")
        pwd = st.text_input("Senha de Acesso", type="password")
        if st.button("ACESSAR PAINEL"):
            if pwd == st.secrets["password"]:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Senha Incorreta")
    st.stop()

# ----------------------------
# CARREGAMENTO DE DADOS
# ----------------------------
df_obras, df_fin = carregar_dados()
lista_obras = df_obras["Cliente"].unique().tolist() if not df_obras.empty else []

# ----------------------------
# SIDEBAR / MENU
# ----------------------------
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4222/4222031.png", width=80)

    sel = option_menu(
        "MENU PRINCIPAL",
        ["Investimentos", "Caixa", "Projetos"],
        icons=["pie-chart-fill", "currency-dollar", "bricks"],
        menu_icon="cast",
        default_index=0
    )

    st.divider()

    if st.button("Sair / Logout"):
        st.session_state["authenticated"] = False
        st.rerun()

# ----------------------------
# TRAVA DE SEGURANÇA (BUG CORRIGIDO)
# ----------------------------
if df_obras.empty and sel != "Projetos":
    st.info(
        "👋 Bem-vindo ao **GESTOR PRO**!\n\n"
        "Para começar, vá até a aba **Projetos** e cadastre sua primeira obra."
    )
    st.stop()

# ======================================================
# TELA 1: INVESTIMENTOS
# ======================================================
if sel == "Investimentos":
    st.title("📊 BI - Inteligência de Obra")

    if not lista_obras:
        st.info("Nenhuma obra encontrada. Cadastre em 'Projetos'.")
    else:
        c_obra, c_rel = st.columns([3, 1])
        obra_sel = c_obra.selectbox("Selecione a unidade de análise:", lista_obras)

        obra_row = df_obras[df_obras["Cliente"] == obra_sel].iloc[0]
        vgv = float(obra_row["Valor Total"])

        df_v = df_fin[df_fin["Obra Vinculada"] == obra_sel].copy()
        df_saidas = df_v[df_v["Tipo"].str.contains("Saída", case=False, na=False)]

        custos = pd.to_numeric(df_saidas["Valor"], errors="coerce").fillna(0).sum()
        lucro = vgv - custos
        roi = (lucro / custos * 100) if custos > 0 else 0
        perc_gasto = (custos / vgv) if vgv > 0 else 0

        if c_rel.button("⬇️ Gerar PDF"):
            pdf = gerar_relatorio_investimentos_pdf(
                obra_sel, vgv, custos, lucro, roi, df_saidas
            )
            download_pdf_one_click(pdf, f"Dashboard_{obra_sel}.pdf")

        st.divider()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Valor Contrato (VGV)", fmt_moeda(vgv))
        k2.metric(
            "Custo Acumulado",
            fmt_moeda(custos),
            delta=f"{perc_gasto*100:.1f}% do total",
            delta_color="inverse"
        )
        k3.metric("Lucro Estimado", fmt_moeda(lucro))
        k4.metric("ROI Atual", f"{roi:.1f}%")

        st.write(f"**Consumo do Orçamento (VGV):** {perc_gasto*100:.1f}%")
        st.progress(min(perc_gasto, 1.0))

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🔥 Distribuição por Categoria")
            if not df_saidas.empty:
                df_pie = df_saidas.groupby("Categoria")["Valor"].sum().reset_index()
                fig = px.pie(
                    df_pie,
                    values="Valor",
                    names="Categoria",
                    hole=.4,
                    color_discrete_sequence=px.colors.sequential.Greens_r
                )
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sem dados de saída.")

        with col2:
            st.subheader("📈 Evolução de Gastos")
            if not df_saidas.empty:
                df_saidas["Data_DT"] = pd.to_datetime(df_saidas["Data_DT"])
                df_evol = df_saidas.sort_values("Data_DT")
                df_evol["Acumulado"] = df_evol["Valor"].cumsum()

                fig = px.line(
                    df_evol,
                    x="Data_DT",
                    y="Acumulado",
                    markers=True,
                    line_shape="spline"
                )
                fig.update_traces(line_color="#2D6A4F")
                st.plotly_chart(fig, use_container_width=True)

# ======================================================
# TELA 2: CAIXA
# ======================================================
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
                st.toast("Lançamento realizado!", icon="✅")
                st.rerun()

    st.subheader("Últimas Movimentações")
    st.dataframe(
        df_fin.sort_values("Data_DT", ascending=False),
        use_container_width=True,
        hide_index=True
    )

# ======================================================
# TELA 3: PROJETOS
# ======================================================
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
                st.toast("Obra cadastrada!", icon="🏗️")
                st.rerun()

    st.subheader("Status das Obras")
    st.dataframe(df_obras, use_container_width=True, hide_index=True)
