import streamlit as st
import pandas as pd
from core.sheets import get_db
from core.data import clear_cache
from core.formatters import fmt_moeda
from core.constants import CATEGORIAS_PADRAO, BUDGET_WARN, BUDGET_FAIL


def render(df_obras: pd.DataFrame, df_fin: pd.DataFrame, lista_obras: list[str]):
    st.markdown("### 🎯 Orçamento — Planejado x Realizado")

    if not lista_obras:
        st.info("Cadastre uma obra primeiro.")
        return

    obra_sel = st.selectbox("Obra", lista_obras)

    db = get_db()
    ws = db.worksheet("Orcamento")

    # Carrega orçamento
    vals = ws.get_all_values()
    if len(vals) >= 2:
        headers = vals[0]
        rows = vals[1:]
        df_orc = pd.DataFrame(rows, columns=headers)
    else:
        df_orc = pd.DataFrame(columns=["Obra", "Categoria", "Planejado"])

    df_orc = df_orc[df_orc["Obra"].astype(str).str.strip() == str(obra_sel).strip()].copy()
    if not df_orc.empty:
        df_orc["Planejado"] = pd.to_numeric(df_orc["Planejado"], errors="coerce").fillna(0)

    # Realizado (somente Saídas)
    df_saida = df_fin[
        (df_fin["Obra Vinculada"].astype(str).str.strip() == str(obra_sel).strip()) &
        (df_fin["Tipo"].astype(str).str.contains("Saída", na=False))
    ].copy()
    if not df_saida.empty:
        df_saida["Categoria"] = df_saida["Categoria"].fillna("Geral").astype(str).str.strip()
        df_real = df_saida.groupby("Categoria", as_index=False)["Valor"].sum().rename(columns={"Valor": "Realizado"})
    else:
        df_real = pd.DataFrame(columns=["Categoria", "Realizado"])

    # Junta
    df_base = pd.DataFrame({"Categoria": CATEGORIAS_PADRAO})
    df_join = df_base.merge(df_real, on="Categoria", how="left").merge(df_orc[["Categoria","Planejado"]] if not df_orc.empty else pd.DataFrame(columns=["Categoria","Planejado"]), on="Categoria", how="left")
    df_join["Realizado"] = df_join["Realizado"].fillna(0)
    df_join["Planejado"] = df_join["Planejado"].fillna(0)
    df_join["% Execução"] = df_join.apply(lambda r: (r["Realizado"]/r["Planejado"]*100) if r["Planejado"]>0 else 0, axis=1)

    # Alertas
    alertas = []
    for _, r in df_join.iterrows():
        if r["Planejado"] > 0:
            ratio = r["Realizado"]/r["Planejado"]
            if ratio >= BUDGET_FAIL:
                alertas.append(f"🚨 {r['Categoria']}: estourou o orçamento ({ratio*100:.0f}%)")
            elif ratio >= BUDGET_WARN:
                alertas.append(f"⚠️ {r['Categoria']}: acima de {int(BUDGET_WARN*100)}% ({ratio*100:.0f}%)")

    if alertas:
        st.error(" / ".join(alertas))

    # Cadastro/edição do orçamento
    st.markdown("#### Definir orçamento por categoria")
    with st.form("f_orc"):
        cat = st.selectbox("Categoria", CATEGORIAS_PADRAO)
        val = st.number_input("Planejado (R$)", min_value=0.0, step=100.0, format="%.2f")
        if st.form_submit_button("Salvar/Atualizar"):
            # Upsert simples
            vals2 = ws.get_all_values()
            headers2 = vals2[0] if vals2 else ["Obra","Categoria","Planejado"]
            if not vals2:
                ws.update("A1", [headers2])

            # procura linha existente
            found_row = None
            for i in range(2, len(vals2)+1):
                if ws.cell(i, 1).value == str(obra_sel) and ws.cell(i, 2).value == str(cat):
                    found_row = i
                    break

            if found_row:
                ws.update_cell(found_row, 3, float(val))
            else:
                ws.append_row([str(obra_sel), str(cat), float(val)], value_input_option="USER_ENTERED")

            clear_cache()
            st.success("Orçamento salvo!")
            st.rerun()

    st.markdown("#### Planejado x Realizado")
    df_show = df_join.copy()
    df_show["Planejado"] = df_show["Planejado"].apply(fmt_moeda)
    df_show["Realizado"] = df_show["Realizado"].apply(fmt_moeda)
    df_show["% Execução"] = df_show["% Execução"].round(1).astype(str) + "%"
    st.dataframe(df_show[["Categoria","Planejado","Realizado","% Execução"]], use_container_width=True, hide_index=True)
