import streamlit as st
import plotly.express as px
import pandas as pd
from core.formatters import fmt_moeda

def render(df_obras: pd.DataFrame, df_fin: pd.DataFrame, lista_obras: list[str]):
    st.markdown("### 📊 Performance e ROI por Obra")

    if not lista_obras:
        st.info("Cadastre uma obra para iniciar a análise.")
        return

    obra_sel = st.selectbox("Selecione a obra", lista_obras)

    df_match = df_obras[df_obras["Cliente"].astype(str).str.strip() == str(obra_sel).strip()]
if df_match.empty:
    st.warning("Obra não encontrada. Verifique se o nome está igual ao cadastrado na aba Obras.")
    return

obra_row = df_match.iloc[0]
vgv = float(obra_row.get("Valor Total", 0) or 0)

    df_v = df_fin[df_fin["Obra Vinculada"].astype(str).str.strip() == obra_sel].copy()
    custos = df_v[df_v["Tipo"].astype(str).str.contains("Saída", case=False, na=False)]["Valor"].sum()
    lucro = vgv - custos
    roi = (lucro / custos * 100) if custos > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VGV Venda", fmt_moeda(vgv))
    c2.metric("Custo Total", fmt_moeda(custos))
    c3.metric("Lucro Estimado", fmt_moeda(lucro))
    c4.metric("ROI Atual", f"{roi:.1f}%")

    # Gráfico de custo acumulado
    df_plot = df_v[df_v["Tipo"].astype(str).str.contains("Saída", case=False, na=False)].copy()
    df_plot = df_plot.dropna(subset=["Data_DT"]).sort_values("Data_DT")
    if not df_plot.empty:
        df_plot["Custo Acumulado"] = df_plot["Valor"].cumsum()
        fig = px.line(df_plot, x="Data_DT", y="Custo Acumulado", markers=True)

# Linha horizontal do VGV (meta de venda)
try:
    fig.add_hline(y=vgv, annotation_text="VGV (meta)", annotation_position="top left")
except Exception:
    pass

fig.update_layout(
    plot_bgcolor="white",
    xaxis_title="Data",
    yaxis_title="Custo acumulado (R$)"
)
st.plotly_chart(fig, use_container_width=True)

