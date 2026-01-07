import streamlit as st
import pandas as pd
import plotly.express as px

from core.data import carregar_dados
from core.formatters import fmt_moeda
from core.reports import gerar_pdf_relatorio

st.title("📊 Investimentos")

df_obras, df_fin = carregar_dados()

if df_obras.empty:
    st.info("Cadastre uma obra em Projetos para iniciar.")
    st.stop()

obra = st.selectbox("Selecione a obra", df_obras["Cliente"].dropna().unique().tolist())

# filtros ano/mês
with st.expander("📅 Filtros (Ano/Mês)"):
    anos = sorted(df_fin["Data_DT"].dropna().dt.year.unique().tolist()) if "Data_DT" in df_fin else []
    ano_sel = st.selectbox("Ano", ["Todos"] + [str(a) for a in anos], index=0)
    meses = list(range(1, 13))
    mes_sel = st.selectbox("Mês", ["Todos"] + [f"{m:02d}" for m in meses], index=0)

# dados da obra
obra_row = df_obras[df_obras["Cliente"] == obra].iloc[0]
vgv = float(obra_row.get("Valor Total", 0) or 0)

df_v = df_fin[df_fin["Obra Vinculada"] == obra].copy()

# aplica filtro
if not df_v.empty and "Data_DT" in df_v.columns:
    if ano_sel != "Todos":
        df_v = df_v[df_v["Data_DT"].dt.year == int(ano_sel)]
    if mes_sel != "Todos":
        df_v = df_v[df_v["Data_DT"].dt.month == int(mes_sel)]

periodo_txt = f"Ano: {ano_sel} | Mês: {mes_sel}"

# só saídas
df_saida = df_v[df_v["Tipo"].astype(str).str.contains("Saída", na=False)].copy()

custos = float(df_saida["Valor"].sum()) if not df_saida.empty else 0.0
lucro = vgv - custos
roi = (lucro / custos * 100) if custos > 0 else 0.0

c1, c2, c3, c4 = st.columns(4)
c1.metric("VGV Venda", fmt_moeda(vgv))
c2.metric("Custo (no período)", fmt_moeda(custos))
c3.metric("Lucro Estimado", fmt_moeda(lucro))
c4.metric("ROI (no período)", f"{roi:.1f}%")

# custo por categoria
st.subheader("🧾 Custo por categoria (no período)")
if df_saida.empty:
    st.info("Sem saídas no período selecionado.")
else:
    grp = df_saida.groupby("Categoria", dropna=False)["Valor"].sum().reset_index()
    fig_cat = px.bar(grp, x="Categoria", y="Valor")
    fig_cat.update_layout(yaxis_title="Total (R$)", xaxis_title="Categoria")
    st.plotly_chart(fig_cat, use_container_width=True)

# evolução acumulada
st.subheader("📈 Evolução do custo (acumulado)")
if not df_saida.empty and "Data_DT" in df_saida.columns:
    df_line = df_saida.sort_values("Data_DT").copy()
    df_line["Acumulado"] = df_line["Valor"].cumsum()
    fig_line = px.line(df_line, x="Data_DT", y="Acumulado", markers=True)
    # linha meta (VGV)
    fig_line.add_hline(y=vgv, line_width=3, line_color="black", annotation_text="VGV (meta)")
    fig_line.update_layout(yaxis_title="Custo acumulado (R$)", xaxis_title="Data")
    st.plotly_chart(fig_line, use_container_width=True)

# PDF (um botão)
st.subheader("📄 Relatório em PDF")

resumo = {"vgv": vgv, "custo": custos, "lucro": lucro, "roi": roi}

pdf_bytes = gerar_pdf_relatorio(
    obra=obra,
    periodo_txt=periodo_txt,
    resumo=resumo,
    lancamentos_df=df_saida[["Data_DT","Data_BR","Categoria","Descrição","Valor"]].copy() if not df_saida.empty else pd.DataFrame()
)

st.download_button(
    "📥 Baixar PDF",
    data=pdf_bytes,
    file_name=f"relatorio_{obra.replace(' ', '_')}.pdf",
    mime="application/pdf"
)
