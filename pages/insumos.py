
import streamlit as st
import pandas as pd
from core.formatters import fmt_moeda

def render(df_fin: pd.DataFrame):
    st.markdown("### 🛒 Monitor de Preços (Inflação)")

    if df_fin.empty:
        st.info("Sem dados para monitoramento.")
        return

    df_g = df_fin[df_fin["Tipo"].astype(str).str.contains("Saída", case=False, na=False)].copy()
    if df_g.empty:
        st.info("Sem despesas registradas.")
        return

    df_g["Insumo"] = df_g["Descrição"].astype(str).apply(lambda x: x.split(":")[0].strip() if ":" in x else x.strip())
    df_g = df_g.dropna(subset=["Data_DT"]).sort_values("Data_DT")

    alertas = False
    for item in df_g["Insumo"].dropna().unique():
        historico = df_g[df_g["Insumo"] == item].sort_values("Data_DT")
        if len(historico) >= 2:
            atual = historico.iloc[-1]
            ant = historico.iloc[-2]
            if float(ant["Valor"]) > 0 and float(atual["Valor"]) > float(ant["Valor"]):
                var = ((float(atual["Valor"]) / float(ant["Valor"])) - 1) * 100
                if var >= 2:
                    alertas = True
                    st.markdown(f"""
                    <div class='alert-card'>
                        <strong>{item}</strong> <span style='color:#E63946; float:right;'>+{var:.1f}%</span><br>
                        <small>Anterior: {fmt_moeda(ant['Valor'])} ({ant['Data_BR']})</small><br>
                        <strong>Atual: {fmt_moeda(atual['Valor'])} ({atual['Data_BR']})</strong>
                    </div>
                    """, unsafe_allow_html=True)

    if not alertas:
        st.success("Nenhum aumento relevante detectado nos insumos (>= 2%).")
