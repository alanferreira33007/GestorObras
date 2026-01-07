import streamlit as st
import pandas as pd
from datetime import date, datetime
from core.sheets import get_db
from core.data import clear_cache
from core.formatters import fmt_moeda
from core.constants import CATEGORIAS_PADRAO
from core.drive import upload_to_drive


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
        df2 = df2[df2["Data_DT"].dt.year == int(ano_sel)]
    if mes_sel != "Todos":
        df2 = df2[df2["Data_DT"].dt.month == int(mes_sel)]
    return df2


def render(df_obras: pd.DataFrame, df_fin: pd.DataFrame, lista_obras: list[str]):
    st.markdown("### 💸 Caixa — Lançamentos")

    # -------- FORM LANÇAMENTO --------
    with st.form("f_caixa", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        dt_input = c1.date_input("Data", value=date.today(), format="DD/MM/YYYY")
        tp_input = c2.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])

        cat_opcoes = ["Selecione..."] + CATEGORIAS_PADRAO
        cat_input = c3.selectbox("Categoria", cat_opcoes, index=0)

        c4, c5 = st.columns(2)
        ob_input = c4.selectbox("Obra Vinculada", lista_obras if lista_obras else ["Geral"])
        vl_input = c5.number_input("Valor R$", format="%.2f", step=0.01, min_value=0.0)

        ds_input = st.text_input("Descrição")

        up = st.file_uploader("Anexar nota (PDF/Imagem) — opcional", type=["pdf", "png", "jpg", "jpeg"])

        if st.form_submit_button("REGISTRAR"):
            if cat_input == "Selecione...":
                st.error("Selecione uma categoria antes de registrar.")
                st.stop()
            if not ds_input.strip():
                st.error("Preencha a descrição.")
                st.stop()
            if vl_input <= 0:
                st.error("Valor deve ser maior que zero.")
                st.stop()

            anexo_url = ""
            if up is not None:
                folder_id = st.secrets.get("drive_folder_id", None)
                anexo_url = upload_to_drive(
                    file_bytes=up.read(),
                    filename=f"{dt_input.strftime('%Y%m%d')}_{ob_input}_{up.name}",
                    mime=up.type,
                    folder_id=folder_id,
                )

            db = get_db()
            ws = db.worksheet("Financeiro")

            # ID simples: timestamp
            new_id = str(int(datetime.now().timestamp() * 1000))

            ws.append_row(
                [
                    new_id,
                    dt_input.strftime("%Y-%m-%d"),
                    tp_input,
                    cat_input,
                    ds_input,
                    float(vl_input),
                    ob_input,
                    anexo_url,
                ],
                value_input_option="USER_ENTERED",
            )

            clear_cache()
            st.success("Lançamento registrado!")
            st.rerun()

    if df_fin.empty:
        return

    # -------- FILTRO --------
    df_temp = df_fin.dropna(subset=["Data_DT"]).copy()
    anos = sorted(df_temp["Data_DT"].dt.year.dropna().astype(int).unique().tolist())
    op_anos = ["Todos"] + [str(a) for a in anos]

    with st.expander("📅 Filtros (Ano/Mês)", expanded=False):
        f1, f2 = st.columns(2)
        ano_sel = f1.selectbox("Ano", op_anos, index=0)
        mes_label = f2.selectbox("Mês", [m[1] for m in MESES], index=0)
        mes_sel = "Todos"
        for num, lab in MESES:
            if lab == mes_label:
                mes_sel = num
                break

    df_view = _filtrar_periodo(df_fin, ano_sel, mes_sel)

    # -------- HISTÓRICO --------
    st.markdown("#### Histórico")
    cols = [c for c in ["Data_BR", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada", "Anexo"] if c in df_view.columns]
    df_display = df_view[cols].copy()
    df_display = df_display.assign(_dt=df_view["Data_DT"]).sort_values("_dt", ascending=False).drop(columns="_dt")
    if "Valor" in df_display.columns:
        df_display["Valor"] = df_display["Valor"].apply(fmt_moeda)
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    # -------- EDITAR / EXCLUIR --------
    st.markdown("#### 🛠️ Editar / Excluir lançamento")
    with st.expander("Abrir editor", expanded=False):
        if df_view.empty:
            st.info("Sem lançamentos no filtro selecionado.")
            return

        # Monta opções com _row (linha real da planilha)
        df_edit = df_view.copy()
        df_edit["_label"] = df_edit.apply(
            lambda r: f"{r.get('Data_BR','')} | {r.get('Tipo','')} | {r.get('Categoria','')} | {r.get('Descrição','')[:40]} | {fmt_moeda(r.get('Valor',0))}",
            axis=1
        )

        escolha = st.selectbox("Escolha o lançamento", df_edit["_label"].tolist())
        row = df_edit[df_edit["_label"] == escolha].iloc[0]
        row_idx = int(row["_row"])  # linha da planilha

        c1, c2, c3 = st.columns(3)
        nova_data = c1.date_input("Data", value=row["Data_DT"].date() if pd.notna(row["Data_DT"]) else date.today(), format="DD/MM/YYYY")
        novo_tipo = c2.selectbox("Tipo", ["Saída (Despesa)", "Entrada"], index=0 if "Saída" in str(row["Tipo"]) else 1)
        nova_cat = c3.selectbox("Categoria", CATEGORIAS_PADRAO, index=CATEGORIAS_PADRAO.index(row["Categoria"]) if row["Categoria"] in CATEGORIAS_PADRAO else 0)

        c4, c5 = st.columns(2)
        nova_obra = c4.selectbox("Obra", lista_obras if lista_obras else ["Geral"], index=(lista_obras.index(row["Obra Vinculada"]) if row["Obra Vinculada"] in lista_obras else 0) if lista_obras else 0)
        novo_valor = c5.number_input("Valor", value=float(row["Valor"]), step=0.01, format="%.2f")

        nova_desc = st.text_input("Descrição", value=str(row["Descrição"]))

        col_a, col_b = st.columns(2)
        if col_a.button("💾 Salvar alteração"):
            db = get_db()
            ws = db.worksheet("Financeiro")

            # localiza colunas pelo header
            headers = ws.row_values(1)
            def col(h): return headers.index(h) + 1

            ws.update_cell(row_idx, col("Data"), nova_data.strftime("%Y-%m-%d"))
            ws.update_cell(row_idx, col("Tipo"), novo_tipo)
            ws.update_cell(row_idx, col("Categoria"), nova_cat)
            ws.update_cell(row_idx, col("Descrição"), nova_desc)
            ws.update_cell(row_idx, col("Valor"), float(novo_valor))
            ws.update_cell(row_idx, col("Obra Vinculada"), nova_obra)

            clear_cache()
            st.success("Alterado!")
            st.rerun()

        if col_b.button("🗑️ Excluir lançamento"):
            db = get_db()
            ws = db.worksheet("Financeiro")
            ws.delete_rows(row_idx)
            clear_cache()
            st.success("Excluído!")
            st.rerun()
