import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import date, datetime
from streamlit_option_menu import option_menu

import io
import base64

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas


# ----------------------------
# 0) PDF helpers (Relatório Investimentos)
# ----------------------------
class NumberedCanvas(canvas.Canvas):
    """
    Rodapé em todas as páginas:
    - Esquerda: "Gestor Pro • <Obra> • <Período>"
    - Direita: "Página X de Y"
    """

    def __init__(self, *args, footer_left: str = "Gestor Pro", **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self.footer_left = footer_left

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        super().showPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(num_pages)
            super().showPage()
        super().save()

    def _draw_footer(self, page_count: int):
        width, height = A4
        page_num = self.getPageNumber()

        self.setStrokeColor(colors.lightgrey)
        self.setLineWidth(0.5)
        self.line(24, 28, width - 24, 28)

        self.setFillColor(colors.grey)
        self.setFont("Helvetica", 9)

        self.drawString(24, 14, self.footer_left[:120])
        self.drawRightString(width - 24, 14, f"Página {page_num} de {page_count}")


def fmt_moeda(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return f"R$ {valor}"


def _to_float(x) -> float:
    if x is None:
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s:
        return 0.0
    s = s.replace("R$", "").replace(" ", "")
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def _df_to_table(df: pd.DataFrame, max_rows=None):
    styles = getSampleStyleSheet()

    if df is None or df.empty:
        return Paragraph("<i>Sem dados.</i>", styles["BodyText"])

    df2 = df.copy()
    if max_rows is not None and len(df2) > max_rows:
        df2 = df2.head(max_rows)

    data = [list(df2.columns)] + df2.astype(str).values.tolist()

    t = Table(data, hAlign="LEFT", repeatRows=1)
    t.splitByRow = 1

    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2D6A4F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),

                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),

                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),

                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def gerar_relatorio_investimentos_pdf(
    obra: str,
    periodo: str,
    vgv: float,
    custos: float,
    lucro: float,
    roi: float,
    perc_vgv: float,
    df_categorias: pd.DataFrame,
    df_lancamentos: pd.DataFrame,
) -> bytes:
    buffer = io.BytesIO()
    footer_left = f"Gestor Pro • {obra} • {periodo}"

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=24,
        leftMargin=24,
        topMargin=24,
        bottomMargin=40,
        title="Relatório - Investimentos",
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("GESTOR PRO — Relatório de Investimentos", styles["Title"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>Obra:</b> {obra}", styles["BodyText"]))
    story.append(Paragraph(f"<b>Período:</b> {periodo}", styles["BodyText"]))
    story.append(Paragraph(f"<b>Gerado em:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["BodyText"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Resumo", styles["Heading2"]))
    resumo = pd.DataFrame(
        [
            ["VGV", fmt_moeda(vgv)],
            ["Custo (período)", fmt_moeda(custos)],
            ["Lucro estimado", fmt_moeda(lucro)],
            ["ROI (lucro/custo)", f"{roi:.1f}%"],
            ["% do VGV gasto", f"{perc_vgv:.2f}%"],
        ],
        columns=["Indicador", "Valor"],
    )
    story.append(_df_to_table(resumo))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Custo por categoria (período)", styles["Heading2"]))
    df_cat = df_categorias.copy() if df_categorias is not None else pd.DataFrame()
    if df_cat.empty:
        story.append(_df_to_table(pd.DataFrame(columns=["Categoria", "Valor"])))
    else:
        if "Categoria" not in df_cat.columns:
            df_cat["Categoria"] = "Sem categoria"
        if "Valor" not in df_cat.columns:
            df_cat["Valor"] = 0

        df_cat["Categoria"] = df_cat["Categoria"].fillna("Sem categoria").astype(str).str.strip()
        df_cat["Valor_num"] = df_cat["Valor"].apply(_to_float)

        df_cat_agg = (
            df_cat.groupby("Categoria", as_index=False)["Valor_num"]
            .sum()
            .sort_values("Valor_num", ascending=False)
        )
        df_cat_tbl = df_cat_agg.rename(columns={"Valor_num": "Valor"})
        df_cat_tbl["Valor"] = df_cat_tbl["Valor"].apply(fmt_moeda)
        story.append(_df_to_table(df_cat_tbl))

    story.append(Spacer(1, 14))

    story.append(Paragraph("Lançamentos (Saídas) no período", styles["Heading2"]))
    df_l = df_lancamentos.copy() if df_lancamentos is not None else pd.DataFrame()

    if not df_l.empty:
        if "Data_DT" in df_l.columns and df_l["Data_DT"].notna().any():
            df_l["_data_ord"] = pd.to_datetime(df_l["Data_DT"], errors="coerce")
        elif "Data" in df_l.columns and df_l["Data"].notna().any():
            df_l["_data_ord"] = pd.to_datetime(df_l["Data"], errors="coerce")
        elif "Data_BR" in df_l.columns and df_l["Data_BR"].notna().any():
            df_l["_data_ord"] = pd.to_datetime(df_l["Data_BR"], errors="coerce", dayfirst=True)
        else:
            df_l["_data_ord"] = pd.NaT

        df_l = df_l.sort_values("_data_ord", ascending=False, na_position="last")
        df_l["Data"] = df_l["_data_ord"].dt.strftime("%d/%m/%Y").fillna("")
    else:
        df_l["Data"] = ""

    cols = []
    if "Data" in df_l.columns: cols.append("Data")
    if "Categoria" in df_l.columns: cols.append("Categoria")
    if "Descrição" in df_l.columns: cols.append("Descrição")
    if "Valor" in df_l.columns: cols.append("Valor")

    df_l_show = df_l[cols].copy() if cols else df_l.copy()
    if not df_l_show.empty and "Valor" in df_l_show.columns:
        df_l_show["Valor"] = df_l_show["Valor"].apply(fmt_moeda)

    story.append(_df_to_table(df_l_show, max_rows=None))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Fechamento do período", styles["Heading2"]))
    total_lanc = (
        float(df_lancamentos["Valor"].apply(_to_float).sum())
        if (df_lancamentos is not None and not df_lancamentos.empty and "Valor" in df_lancamentos.columns)
        else float(custos)
    )
    qtd_lanc = int(len(df_lancamentos)) if (df_lancamentos is not None and not df_lancamentos.empty) else 0

    fechamento = pd.DataFrame(
        [
            ["Total de lançamentos (Saídas)", str(qtd_lanc)],
            ["Total gasto no período", fmt_moeda(total_lanc)],
        ],
        columns=["Item", "Valor"],
    )
    story.append(_df_to_table(fechamento))
    story.append(Spacer(1, 10))

    doc.build(
        story,
        canvasmaker=lambda *args, **kwargs: NumberedCanvas(*args, footer_left=footer_left, **kwargs),
    )

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def _download_pdf_one_click(pdf_bytes: bytes, filename: str):
    """Dispara download com 1 clique usando HTML/JS (sem segundo botão)."""
    b64 = base64.b64encode(pdf_bytes).decode()
    html = f"""
    <a id="dl" href="data:application/pdf;base64,{b64}" download="{filename}"></a>
    <script>
      const a = document.getElementById("dl");
      a.click();
    </script>
    """
    st.components.v1.html(html, height=0)


# ----------------------------
# 1) CONFIG UI
# ----------------------------
st.set_page_config(page_title="GESTOR PRO | Master v26", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F8F9FA; color: #1A1C1E; font-family: 'Inter', sans-serif; }
    [data-testid="stMetric"] { background-color: #FFFFFF; border: 1px solid #E9ECEF; border-radius: 12px; padding: 20px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
    div.stButton > button { background-color: #2D6A4F !important; color: white !important; border-radius: 6px !important; font-weight: 600 !important; width: 100%; height: 45px; }
    .alert-card { background-color: #FFFFFF; border-left: 5px solid #E63946; padding: 20px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
    header, footer, #MainMenu {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ----------------------------
# 2) CONSTANTES (SCHEMA)
# ----------------------------
OBRAS_COLS = ["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"]
FIN_COLS   = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]
CATEGORIAS_PADRAO = ["Geral", "Material", "Mão de Obra", "Serviços", "Impostos", "Outros"]


def ensure_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]

def normalize_dates(df: pd.DataFrame, col_data: str = "Data") -> pd.DataFrame:
    """
    Garante colunas:
    - Data_DT (datetime)
    - Data_BR (dd/mm/yyyy)
    """
    if col_data not in df.columns:
        df["Data_DT"] = pd.NaT
        df["Data_BR"] = ""
        return df

    df["Data_DT"] = pd.to_datetime(df[col_data], errors="coerce")
    df["Data_BR"] = df["Data_DT"].dt.strftime("%d/%m/%Y")
    df.loc[df["Data_DT"].isna(), "Data_BR"] = ""

    return df


# ----------------------------
# 3) DB (Google Sheets)
# ----------------------------
@st.cache_resource
def obter_db():
    creds_json = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope))
    return client.open("GestorObras_DB")


@st.cache_data(ttl=10)
def carregar_dados():
    try:
        db = obter_db()

        ws_o = db.worksheet("Obras")
        df_o = pd.DataFrame(ws_o.get_all_records())
        if df_o.empty:
            df_o = pd.DataFrame(columns=OBRAS_COLS)
        df_o = ensure_cols(df_o, OBRAS_COLS)
        df_o["ID"] = pd.to_numeric(df_o["ID"], errors="coerce")
        df_o["Valor Total"] = pd.to_numeric(df_o["Valor Total"], errors="coerce").fillna(0)

        ws_f = db.worksheet("Financeiro")
        df_f = pd.DataFrame(ws_f.get_all_records())
        if df_f.empty:
            df_f = pd.DataFrame(columns=FIN_COLS)
        df_f = ensure_cols(df_f, FIN_COLS)
        df_f["Valor"] = pd.to_numeric(df_f["Valor"], errors="coerce").fillna(0)
        df_f = normalize_dates(df_f, "Data")

        # Normaliza strings
        for col in ["Tipo", "Categoria", "Descrição", "Obra Vinculada"]:
            if col in df_f.columns:
                df_f[col] = df_f[col].astype(str)

        return df_o, df_f

    except Exception as e:
        st.error(f"Erro de Conexão: {e}")
        return pd.DataFrame(columns=OBRAS_COLS), pd.DataFrame(columns=FIN_COLS + ["Data_DT", "Data_BR"])


# ----------------------------
# 4) AUTH
# ----------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        with st.form("login"):
            st.markdown("<h2 style='text-align:center; color:#2D6A4F;'>GESTOR PRO</h2>", unsafe_allow_html=True)
            pwd = st.text_input("Senha de Acesso", type="password")
            if st.form_submit_button("Acessar Painel"):
                if pwd == st.secrets["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
    st.stop()

# ----------------------------
# 5) LOAD
# ----------------------------
df_obras, df_fin = carregar_dados()

lista_obras = (
    df_obras["Cliente"]
    .dropna()
    .astype(str)
    .str.strip()
    .replace("", pd.NA)
    .dropna()
    .unique()
    .tolist()
)

# ----------------------------
# 6) SIDEBAR
# ----------------------------
with st.sidebar:
    sel = option_menu(
        "GESTOR PRO",
        ["Investimentos", "Caixa", "Insumos", "Projetos"],
        icons=["graph-up-arrow", "wallet2", "cart-check", "building"],
        default_index=0,
    )
    if st.button("Sair"):
        st.session_state["authenticated"] = False
        st.rerun()

# ----------------------------
# 7) TELAS
# ----------------------------
if sel == "Investimentos":
    st.markdown("### 📊 Performance e ROI por Obra")

    if not lista_obras:
        st.info("Cadastre uma obra para iniciar a análise.")
        st.stop()

    obra_sel = st.selectbox("Selecione a obra", lista_obras)

    obra_row = df_obras[df_obras["Cliente"].astype(str).str.strip() == obra_sel].iloc[0]
    vgv = float(obra_row["Valor Total"] or 0)

    df_v = df_fin[df_fin["Obra Vinculada"].astype(str).str.strip() == obra_sel].copy()

    # ----------------------------
    # Filtros Ano/Mês (no Investimentos)
    # ----------------------------
    with st.expander("📅 Filtros (Ano/Mês)", expanded=False):
        df_v_valid = df_v.dropna(subset=["Data_DT"]).copy()
        if df_v_valid.empty:
            st.info("Ainda não há datas válidas para filtrar.")
            anos_sel, meses_sel = [], []
        else:
            df_v_valid["Ano"] = df_v_valid["Data_DT"].dt.year
            df_v_valid["Mes"] = df_v_valid["Data_DT"].dt.month

            anos = sorted(df_v_valid["Ano"].dropna().unique().tolist())
            meses = list(range(1, 13))

            anos_sel = st.multiselect("Ano", anos, default=anos)
            meses_sel = st.multiselect("Mês", meses, default=meses)

    df_periodo = df_v.copy()
    if "Data_DT" in df_periodo.columns:
        df_periodo = df_periodo.dropna(subset=["Data_DT"])
        if anos_sel:
            df_periodo = df_periodo[df_periodo["Data_DT"].dt.year.isin(anos_sel)]
        if meses_sel:
            df_periodo = df_periodo[df_periodo["Data_DT"].dt.month.isin(meses_sel)]

    # Saídas no período
    df_saidas = df_periodo[df_periodo["Tipo"].astype(str).str.contains("Saída", case=False, na=False)].copy()
    custos = float(df_saidas["Valor"].sum()) if not df_saidas.empty else 0.0

    lucro = vgv - custos
    roi = (lucro / custos * 100) if custos > 0 else 0.0
    perc_vgv = (custos / vgv * 100) if vgv > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VGV Venda", fmt_moeda(vgv))
    c2.metric("Custo (no período)", fmt_moeda(custos))
    c3.metric("Lucro Estimado", fmt_moeda(lucro))
    c4.metric("ROI (no período)", f"{roi:.1f}%")

    st.caption(f"📌 Percentual do VGV já gasto no período: **{perc_vgv:.2f}%**")

    # ----------------------------
    # Custo por categoria (no período) - gráfico + tabela
    # ----------------------------
    st.markdown("#### 🧾 Custo por categoria (no período)")

    if df_saidas.empty:
        st.info("Sem saídas no período selecionado.")
        df_cat_agg = pd.DataFrame(columns=["Categoria", "Valor"])
        df_lancamentos = pd.DataFrame(columns=["Data_BR", "Categoria", "Descrição", "Valor"])
    else:
        df_cat = df_saidas.copy()
        if "Categoria" not in df_cat.columns:
            df_cat["Categoria"] = "Sem categoria"
        df_cat["Categoria"] = df_cat["Categoria"].fillna("Sem categoria").astype(str).str.strip()
        df_cat_agg = (
            df_cat.groupby("Categoria", as_index=False)["Valor"]
            .sum()
            .sort_values("Valor", ascending=False)
        )

        fig_cat = px.bar(df_cat_agg, x="Categoria", y="Valor")
        fig_cat.update_layout(plot_bgcolor="white", xaxis_title="Categoria", yaxis_title="Total (R$)")
        st.plotly_chart(fig_cat, use_container_width=True)

        df_cat_tbl = df_cat_agg.copy()
        df_cat_tbl["Valor"] = df_cat_tbl["Valor"].apply(fmt_moeda)
        st.dataframe(df_cat_tbl, use_container_width=True, hide_index=True)

        # Lançamentos (para PDF e para visualização)
        df_lancamentos = df_saidas.copy()
        df_lancamentos = df_lancamentos.sort_values("Data_DT", ascending=False, na_position="last")
        df_lancamentos["Data_BR"] = df_lancamentos["Data_DT"].dt.strftime("%d/%m/%Y").fillna("")
        df_lancamentos = df_lancamentos[["Data_BR", "Categoria", "Descrição", "Valor"]].copy()

    # ----------------------------
    # Evolução do custo (acumulado) - no período
    # ----------------------------
    st.markdown("#### 📈 Evolução do custo (acumulado)")

    df_plot = df_saidas.dropna(subset=["Data_DT"]).sort_values("Data_DT").copy()
    if not df_plot.empty:
        df_plot["Custo Acumulado"] = df_plot["Valor"].cumsum()
        fig = px.line(df_plot, x="Data_DT", y="Custo Acumulado", markers=True)
        fig.update_layout(plot_bgcolor="white", xaxis_title="Data", yaxis_title="Custo acumulado (R$)")
        st.plotly_chart(fig, use_container_width=True)

    # ----------------------------
    # PDF (1 clique)
    # ----------------------------
    st.markdown("---")
    col_btn = st.columns([1, 2, 1])[1]
    with col_btn:
        if st.button("⬇️ Baixar PDF", key="baixar_pdf_invest"):
            # Período “bonito”
            if df_plot.empty:
                periodo_str = "Sem movimentação"
            else:
                dmin = df_plot["Data_DT"].min()
                dmax = df_plot["Data_DT"].max()
                periodo_str = f"{dmin.strftime('%d/%m/%Y')} a {dmax.strftime('%d/%m/%Y')}"

            # Categorias para PDF: precisa ter colunas Categoria/Valor
            df_cat_pdf = df_cat_agg.copy()
            if not df_cat_pdf.empty:
                df_cat_pdf = df_cat_pdf.rename(columns={"Valor": "Valor"})
            else:
                df_cat_pdf = pd.DataFrame(columns=["Categoria", "Valor"])

            # Lançamentos para PDF: Data_DT / Data_BR / Categoria / Descrição / Valor
            df_lanc_pdf = df_saidas.copy()
            if not df_lanc_pdf.empty:
                df_lanc_pdf["Data_BR"] = df_lanc_pdf["Data_DT"].dt.strftime("%d/%m/%Y").fillna("")
                df_lanc_pdf = df_lanc_pdf[["Data_DT", "Data_BR", "Categoria", "Descrição", "Valor"]].copy()
            else:
                df_lanc_pdf = pd.DataFrame(columns=["Data_DT", "Data_BR", "Categoria", "Descrição", "Valor"])

            pdf_bytes = gerar_relatorio_investimentos_pdf(
                obra=obra_sel,
                periodo=periodo_str,
                vgv=vgv,
                custos=custos,
                lucro=lucro,
                roi=roi,
                perc_vgv=perc_vgv,
                df_categorias=df_cat_pdf,
                df_lancamentos=df_lanc_pdf,
            )

            nome = f"relatorio_investimentos_{obra_sel.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            _download_pdf_one_click(pdf_bytes, nome)

elif sel == "Caixa":
    st.markdown("### 💸 Lançamento Financeiro")

    with st.form("f_caixa", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        dt_input = c1.date_input("Data", value=date.today(), format="DD/MM/YYYY")
        tp_input = c2.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
        cat_input = c3.selectbox("Categoria", CATEGORIAS_PADRAO)

        c4, c5 = st.columns(2)
        ob_input = c4.selectbox("Obra Vinculada", lista_obras if lista_obras else ["Geral"])
        vl_input = c5.number_input("Valor R$", format="%.2f", step=0.01, min_value=0.0)

        ds_input = st.text_input("Descrição")

        if st.form_submit_button("REGISTRAR LANÇAMENTO"):
            try:
                db = obter_db()
                db.worksheet("Financeiro").append_row(
                    [
                        dt_input.strftime("%Y-%m-%d"),
                        tp_input,
                        cat_input,
                        ds_input,
                        float(vl_input),
                        ob_input,
                    ],
                    value_input_option="USER_ENTERED",
                )
                st.cache_data.clear()
                st.success("Lançamento realizado!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

    if not df_fin.empty:
        st.markdown("#### Histórico de Lançamentos")
        df_display = df_fin[["Data_BR", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]].copy()
        df_display = df_display.assign(_dt=df_fin["Data_DT"]).sort_values("_dt", ascending=False).drop(columns="_dt")
        df_display["Valor"] = df_display["Valor"].apply(fmt_moeda)
        df_display.columns = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra"]
        st.dataframe(df_display, use_container_width=True, hide_index=True)

elif sel == "Insumos":
    st.markdown("### 🛒 Monitor de Preços (Inflação)")

    if df_fin.empty:
        st.info("Sem dados para monitoramento.")
        st.stop()

    df_g = df_fin[df_fin["Tipo"].astype(str).str.contains("Saída", case=False, na=False)].copy()
    if df_g.empty:
        st.info("Sem despesas registradas.")
        st.stop()

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

elif sel == "Projetos":
    st.markdown("### 📁 Gestão de Obras")

    with st.form("f_obra", clear_on_submit=True):
        c1, c2 = st.columns(2)
        n_obra = c1.text_input("Cliente / Nome da Obra")
        end_obra = c2.text_input("Endereço")

        c3, c4, c5 = st.columns(3)
        st_obra = c3.selectbox("Status", ["Planejamento", "Construção", "Finalizada"])
        v_obra = c4.number_input("Valor Total (VGV)", format="%.2f", step=1000.0, min_value=0.0)
        prazo = c5.text_input("Prazo", value="A definir")

        if st.form_submit_button("CADASTRAR OBRA"):
            try:
                db = obter_db()
                ws = db.worksheet("Obras")

                max_id = pd.to_numeric(df_obras["ID"], errors="coerce").max()
                novo_id = int(max_id) + 1 if pd.notna(max_id) else 1

                ws.append_row(
                    [
                        novo_id,
                        n_obra.strip(),
                        end_obra.strip(),
                        st_obra,
                        float(v_obra),
                        date.today().strftime("%Y-%m-%d"),
                        prazo.strip(),
                    ],
                    value_input_option="USER_ENTERED",
                )
                st.cache_data.clear()
                st.success("Obra cadastrada!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")

    if not df_obras.empty:
        df_o_ex = df_obras[["Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"]].copy()
        df_o_ex["Valor Total"] = df_o_ex["Valor Total"].apply(fmt_moeda)
        st.dataframe(df_o_ex, use_container_width=True, hide_index=True)
