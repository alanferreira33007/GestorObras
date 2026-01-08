# app.py
import streamlit as st
from auth import autenticar
from db import carregar_dados
from finance import calcular_indicadores, custo_por_categoria
from utils import fmt_moeda
from pdf_reports import gerar_relatorio_investimentos_pdf

st.set_page_config(page_title="GESTOR PRO | Master", layout="wide")

autenticar()

df_obras, df_fin = carregar_dados()

lista_obras = df_obras["Cliente"].dropna().unique().tolist()
obra_sel = st.selectbox("Selecione a obra", lista_obras)

obra = df_obras[df_obras["Cliente"] == obra_sel].iloc[0]
vgv = obra["Valor Total"]

df_v = df_fin[df_fin["Obra Vinculada"] == obra_sel]
df_saidas = df_v[df_v["Tipo"].str.contains("Saída", na=False)]
custos = df_saidas["Valor"].sum()

lucro, roi, perc_vgv = calcular_indicadores(vgv, custos)

c1, c2, c3, c4 = st.columns(4)
c1.metric("VGV", fmt_moeda(vgv))
c2.metric("Custos", fmt_moeda(custos))
c3.metric("Lucro", fmt_moeda(lucro))
c4.metric("ROI", f"{roi:.1f}%")

df_cat = custo_por_categoria(df_saidas)
st.dataframe(df_cat.assign(Valor=df_cat["Valor"].apply(fmt_moeda)))
