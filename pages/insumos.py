import streamlit as st
import pandas as pd
from core.formatters import fmt_moeda
from core.normalize import extrair_insumo


def render(df_obras: pd.DataFrame, df_fin: pd.DataFrame, lista_obras: list[str]):
    st.markdown("### 🛒 Insumos — Monitor de preços")

    if df_fin.empty:
        st.info("Sem dados.")
        return

    df_g = df_fin[df_fin["Tipo"].astype(str).str.contains("Saída", na=False)].copy()
    df_g = df_g.dropna(subset=["Data_DT"])
    if df_g.empty:
        st.info("Sem saídas para monitorar.")
        return

    with st.expander("⚙️ Configurações de alerta", expanded=False):
        limiar_pct = st.slider("Alertar se subir mais que (%)", 1, 30, 5)
        apenas_top = st.checkbox("Mostrar só Top 10 maiores altas", value=True)

    df_g["Insumo"] = df_g["Descrição"].astype(str).apply(extrair_insumo)
    df_g = df_g.sort_values("Data_DT")

    alertas = []
    for item in df_g["Insumo"].unique():
        hist = df_g[df_g["Insumo"] == item].sort_values("Data_DT")
        if len(hist) >= 2:
            atual = hist.iloc[-1]
            ant = hist.iloc[-2]
            if ant["Valor"] > 0 and atual["Valor"] > ant["Valor"]:
                var = ((atual["Valor"] / ant["Valor"]) - 1) * 100
                if var >= limiar_pct:
                    alertas.append((item, var, ant, atual))

    alertas.sort(key=lambda x: x[1], reverse=True)
    if apenas_top:
        alertas = alertas[:10]

    if not alertas:
        st.success("Nenhum aumento relevante detectado.")
        return

    for item, var, ant, atual in alertas:
        st.markdown(
            f"""
            <div style="background:#fff;border-left:5px solid #E63946;padding:16px;border-radius:8px;margin-bottom:10px">
              <strong>{item}</strong>
              <span style="color:#E63946;float:right">+{var:.1f}%</span><br>
              <small>Anterior: {fmt_moeda(ant['Valor'])} ({ant['Data_BR']})</small><br>
              <strong>Atual: {fmt_moeda(atual['Valor'])} ({atual['Data_BR']})</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
