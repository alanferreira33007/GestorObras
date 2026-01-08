import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from streamlit_option_menu import option_menu

from database import carregar_dados, salvar_financeiro, salvar_obra
from relatorios import fmt_moeda, gerar_relatorio_investimentos_pdf, download_pdf_one_click

st.set_page_config(page_title="GESTOR PRO | Master", layout="wide")

# LOGIN
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if not st.session_state["authenticated"]:
    with st.form("login"):
        st.title("🔐 Acesso")
        pwd = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if pwd == st.secrets["password"]:
                st.session_state["authenticated"] = True
                st.rerun()
            else: st.error("Senha incorreta.")
    st.stop()

# DADOS
df_obras, df_fin = carregar_dados()
lista_obras = df_obras["Cliente"].unique().tolist()

with st.sidebar:
    sel = option_menu("GESTOR PRO", ["Investimentos", "Caixa", "Projetos"], 
                     icons=["graph-up", "wallet2", "building"])
    if st.button("Sair"):
        st.session_state["authenticated"] = False
        st.rerun()

# TELA INVESTIMENTOS
if sel == "Investimentos":
    st.header("📊 Performance e ROI")
    if not lista_obras:
        st.info("Cadastre uma obra primeiro.")
    else:
        obra_sel = st.selectbox("Selecione a obra", lista_obras)
        obra_row = df_obras[df_obras["Cliente"] == obra_sel].iloc[0]
        vgv = float(obra_row["Valor Total"])
        
        df_v = df_fin[df_fin["Obra Vinculada"] == obra_sel].copy()
        df_saidas = df_v[df_v["Tipo"].str.contains("Saída", case=False, na=False)]
        
        custos = float(df_saidas["Valor"].sum())
        lucro = vgv - custos
        roi = (lucro / custos * 100) if custos > 0 else 0
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("VGV", fmt_moeda(vgv))
        c2.metric("Custo Total", fmt_moeda(custos))
        c3.metric("Lucro", fmt_moeda(lucro))
        c4.metric("ROI", f"{roi:.1f}%")

        # Gráfico
        if not df_saidas.empty:
            st.subheader("Custos por Categoria")
            df_cat = df_saidas.groupby("Categoria")["Valor"].sum().reset_index()
            fig = px.bar(df_cat, x="Categoria", y="Valor", color_discrete_sequence=['#2D6A4F'])
            st.plotly_chart(fig, use_container_width=True)

        # --- O BOTÃO QUE ESTAVA FALTANDO ---
        st.divider()
        col_pdf, _ = st.columns([1, 3])
        if col_pdf.button("⬇️ BAIXAR RELATÓRIO PDF"):
            with st.spinner("Gerando arquivo..."):
                pdf_arquivo = gerar_relatorio_investimentos_pdf(obra_sel, vgv, custos, lucro, roi, df_saidas)
                nome_arquivo = f"Relatorio_{obra_sel}_{date.today().strftime('%d_%m_%Y')}.pdf"
                download_pdf_one_click(pdf_arquivo, nome_arquivo)
                st.success("Download iniciado!")

# TELA CAIXA
elif sel == "Caixa":
    st.header("💸 Caixa")
    with st.expander("➕ Novo Lançamento"):
        with st.form("f_caixa", clear_on_submit=True):
            f_data = st.date_input("Data", value=date.today())
            f_tipo = st.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
            f_cat = st.selectbox("Categoria", ["Material", "Mão de Obra", "Serviços", "Impostos", "Outros"])
            f_obra = st.selectbox("Obra", lista_obras if lista_obras else ["Geral"])
            f_valor = st.number_input("Valor", min_value=0.0)
            f_desc = st.text_input("Descrição")
            if st.form_submit_button("REGISTRAR"):
                salvar_financeiro([f_data.strftime("%Y-%m-%d"), f_tipo, f_cat, f_desc, f_valor, f_obra])
                st.rerun()
    st.dataframe(df_fin.sort_values("Data_DT", ascending=False), use_container_width=True)

# TELA PROJETOS
elif sel == "Projetos":
    st.header("🏗️ Projetos")
    with st.expander("➕ Nova Obra"):
        with st.form("f_obra", clear_on_submit=True):
            f_nome = st.text_input("Nome/Cliente")
            f_vgv = st.number_input("VGV", min_value=0.0)
            if st.form_submit_button("CADASTRAR"):
                salvar_obra([len(df_obras)+1, f_nome, "", "Construção", f_vgv, date.today().strftime("%Y-%m-%d"), ""])
                st.rerun()
    st.dataframe(df_obras, use_container_width=True)
