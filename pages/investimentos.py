import streamlit as st
import plotly.express as px
import pandas as pd
from core.formatters import fmt_moeda


MESES = [
    ("Todos", "Todos"),
    (1, "01 - Jan"),
    (2, "02 - Fev"),
    (3, "03 - Mar"),
    (4, "04 - Abr"),
    (5, "05 - Mai"),
    (6, "06 - Jun"),
    (7, "07 - Jul"),
    (8, "08 - Ago"),
    (9, "09 - Set"),
    (10, "10 - Out"),
    (11, "11 - Nov"),
    (12, "12 - Dez"),
]


def _filtrar_periodo(df: pd.DataFrame, ano_sel: str, mes_sel):
    df2 = df.copy()
    df2 = df2.dropna(subset=["Data_DT"])

    if ano_sel != "Todos":
        ano_int = int(ano_sel)
        df2 = df2[df2["Data_DT"].dt.year == ano_int]

    if mes_sel != "Todos":
        mes_int = int(mes_sel)
        df2 = df2[df2["Data_DT"].dt.month == mes_int]

    return df2


def render(df_obras: pd.DataFrame, df_fin: pd.DataFrame, lista_obras: list[str]):
    st.markdown("### 📊 Performance e ROI por Obra")

    if not lista_obras:
        st.info("Cadastre uma obra para iniciar a análise.")
        return

    obra_sel = st.selectbox("Selecione a obra", lista_obras)

    # Proteção: obra não encontrada (nome divergente)
    df_match = df_obras[df_obras["Cliente"].astype(str).str.strip() == str(obra_sel).strip()]
    if df_match.empty:
        st.warning("Obra não encontrada. Verifique se o nome está igual ao cadastrado na aba Obras.")
        return

    obra_row = df_match.iloc[0]
    vgv = float(obra_row.get("Valor Total", 0) or 0)

    # Dados financeiros da obra
    df_v = df_fin[df_fin["Obra Vinculada"].astype(str).str.strip() == str(obra_sel).strip()].copy()

    # -----------------------------
    # FILTRO DE PERÍODO (Ano/Mês)
    # -----------------------------
    df_temp = df_v.dropna(subset=["Data_DT"]).copy()
    anos = sorted(df_temp["Data_DT"].dt.year.dropna().astype(int).unique().tolist())
    op_anos = ["Todos"] + [str(a) for a in anos] if anos else ["Todos"]

    with st.expander("📅 Filtros (Ano/Mês)", expanded=False):
        f1, f2 = st.columns(2)
        ano_sel = f1.selectbox("Ano", op_anos, index=0)
        mes_label = f2.selectbox("Mês", [m[1] for m in MESES], index=0)

        mes_sel = "Todos"
        for num, lab in MESES:
            if lab == mes_label:
                mes_sel = num
                break

    df_v = _filtrar_periodo(df_v, ano_sel, mes_sel)

    # -----------------------------
    # MÉTRICAS
    # -----------------------------
    df_saida = df_v[df_v["Tipo"].astype(str).str.contains("Saída", case=False, na=False)].copy()

    custos = df_saida["Valor"].sum()
    lucro = vgv - custos
    roi = (lucro / custos * 100) if custos > 0 else 0.0
    perc_vgv = (custos / vgv * 100) if vgv > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VGV Venda", fmt_moeda(vgv))
    c2.metric("Custo (no período)", fmt_moeda(custos))
    c3.metric("Lucro Estimado", fmt_moeda(lucro))
    c4.metric("ROI (no período)", f"{roi:.1f}%")

    st.caption(f"📌 Percentual do VGV já gasto no período: **{perc_vgv:.2f}%**")

    # -----------------------------
    # CUSTO POR CATEGORIA (BARRAS)
    # -----------------------------
    st.markdown("#### 🧾 Custo por categoria (no período)")

    if not df_saida.empty:
        df_cat = df_saida.copy()
        df_cat["Categoria"] = df_cat["Categoria"].fillna("Sem categoria").astype(str).str.strip()
        df_cat = (
            df_cat.groupby("Categoria", as_index=False)["Valor"]
            .sum()
            .sort_values("Valor", ascending=False)
        )

        fig_cat = px.bar(df_cat, x="Categoria", y="Valor")
        fig_cat.update_layout(
            plot_bgcolor="white",
            xaxis_title="Categoria",
            yaxis_title="Total (R$)",
        )
        st.plotly_chart(fig_cat, use_container_width=True)

        df_cat_show = df_cat.copy()
        df_cat_show["Valor"] = df_cat_show["Valor"].apply(fmt_moeda)
        st.dataframe(df_cat_show, use_container_width=True, hide_index=True)
    else:
        st.info("Sem despesas (Saída) no período selecionado.")

    # -----------------------------
    # GRÁFICO: CUSTO ACUMULADO + LINHA VGV
    # (com ZOOM automático no eixo Y)
    # -----------------------------
    st.markdown("#### 📈 Evolução do custo (acumulado)")

    df_plot = df_saida.dropna(subset=["Data_DT"]).sort_values("Data_DT").copy()

    if not df_plot.empty:
        df_plot["Custo Acumulado"] = df_plot["Valor"].cumsum()

        fig = px.line(df_plot, x="Data_DT", y="Custo Acumulado", markers=True)

        # Linha horizontal do VGV (meta de venda)
        try:
            fig.add_hline(y=vgv, annotation_text="VGV (meta)", annotation_position="top left")
        except Exception:
            pass

        # Zoom automático para o custo ficar legível mesmo com VGV alto
        y_max = max(df_plot["Custo Acumulado"].max() * 1.15, 1)

        fig.update_layout(
            plot_bgcolor="white",
            xaxis_title="Data",
            yaxis_title="Custo acumulado (R$)",
            yaxis=dict(range=[0, y_max]),
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem despesas (Saída) no período para gerar a evolução do custo.")
