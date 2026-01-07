import streamlit as st

from core.data import carregar_dados
from core.formatters import fmt_moeda

st.title("🛒 Insumos (alertas de aumento)")

_, df_fin = carregar_dados()

if df_fin.empty:
    st.info("Sem dados no Financeiro.")
    st.stop()

df_g = df_fin[df_fin["Tipo"].astype(str).str.contains("Saída", na=False)].copy()
if df_g.empty:
    st.info("Sem saídas registradas.")
    st.stop()

# define “insumo” como texto antes de ":" (se houver)
df_g["Insumo"] = df_g["Descrição"].astype(str).apply(lambda x: x.split(":")[0].strip() if ":" in x else x.strip())

alertas = False
for item in df_g["Insumo"].dropna().unique():
    historico = df_g[df_g["Insumo"] == item].sort_values("Data_DT")
    if len(historico) >= 2:
        atual = historico.iloc[-1]
        ant = historico.iloc[-2]
        if float(atual["Valor"]) > float(ant["Valor"]):
            alertas = True
            var = ((float(atual["Valor"]) / float(ant["Valor"])) - 1) * 100
            st.warning(
                f"**{item}** subiu **+{var:.1f}%** | "
                f"Anterior: {fmt_moeda(ant['Valor'])} ({ant['Data_BR']}) → "
                f"Atual: {fmt_moeda(atual['Valor'])} ({atual['Data_BR']})"
            )

if not alertas:
    st.success("Nenhum aumento detectado nos insumos.")
