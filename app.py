import streamlit as st
import pandas as pd
from database import carregar_dados, obter_db
from relatorios import gerar_relatorio_investimentos_pdf, fmt_moeda, download_pdf_one_click
from streamlit_option_menu import option_menu
from datetime import date, datetime

st.set_page_config(page_title="GESTOR PRO | Master", layout="wide")

# CSS para ficar bonito
st.markdown("<style>.stMetric { background-color: white; border: 1px solid #EEE; padding: 15px; border-radius: 10px; }</style>", unsafe_allow_html=True)

# 1. Autenticação
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    with st.form("login"):
        st.subheader("Acesso ao Sistema")
        pwd = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if pwd == st.secrets["password"]:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    st.stop()

# 2. Carregar Dados
df_obras, df_fin = carregar_dados()

# 3. Sidebar Menu
with st.sidebar:
    sel = option_menu("GESTOR PRO", ["Investimentos", "Caixa", "Projetos"], 
                     icons=["graph-up", "wallet2", "building"])
    if st.button("Sair"):
        st.session_state["authenticated"] = False
        st.rerun()

# 4. Telas
if sel == "Investimentos":
    st.title("📊 Performance e ROI")
    
    lista_obras = df_obras["Cliente"].unique().tolist()
    if not lista_obras:
        st.warning("Nenhuma obra cadastrada.")
    else:
        obra_sel = st.selectbox("Selecione a Obra", lista_obras)
        
        # Filtra dados da obra
        obra_row = df_obras[df_obras["Cliente"] == obra_sel].iloc[0]
        vgv = float(obra_row["Valor Total"])
        
        df_v = df_fin[df_fin["Obra Vinculada"] == obra_sel].copy()
        df_saidas = df_v[df_v["Tipo"].str.contains("Saída", case=False, na=False)]
        
        custos = float(df_saidas["Valor"].sum())
        lucro = vgv - custos
        roi = (lucro / custos * 100) if custos > 0 else 0
        
        # Métricas
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("VGV", fmt_moeda(vgv))
        c2.metric("Custos", fmt_moeda(custos))
        c3.metric("Lucro", fmt_moeda(lucro))
        c4.metric("ROI", f"{roi:.1f}%")
        
        if st.button("Gerar PDF"):
            pdf = gerar_relatorio_investimentos_pdf(obra_sel, "Geral", vgv, custos, lucro, roi, 0, None, df_saidas)
            download_pdf_one_click(pdf, f"Relatorio_{obra_sel}.pdf")

elif sel == "Caixa":
    st.title("💸 Lançamentos")
    # Exibe a tabela financeira
    st.dataframe(df_fin[["Data_BR", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]], use_container_width=True)

elif sel == "Projetos":
    st.title("🏗️ Gestão de Obras")
    st.dataframe(df_obras, use_container_width=True)
