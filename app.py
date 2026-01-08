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
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.pdfgen import canvas


# =========================================================
# 0) HELPERS GERAIS
# =========================================================
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
    s = s.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0


def calc_roi(lucro: float, custo: float) -> float:
    return (lucro / custo * 100) if custo > 0 else 0.0


def normalizar_datas(df: pd.DataFrame, col_data="Data"):
    df = df.copy()
    if col_data not in df.columns:
        df["Data_DT"] = pd.NaT
        df["Data_BR"] = ""
        return df

    df["Data_DT"] = pd.to_datetime(df[col_data], errors="coerce")
    df["Data_BR"] = df["Data_DT"].dt.strftime("%d/%m/%Y")
    df.loc[df["Data_DT"].isna(), "Data_BR"] = ""
    return df


# =========================================================
# 1) PDF
# =========================================================
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, footer_left="Gestor Pro", **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self.footer_left = footer_left

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        super().showPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total):
        width, _ = A4
        self.setStrokeColor(colors.lightgrey)
        self.line(24, 28, width - 24, 28)
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.grey)
        self.drawString(24, 14, self.footer_left[:120])
        self.drawRightString(width - 24, 14, f"Página {self.getPageNumber()} de {total}")


def _df_to_table(df, max_rows=None):
    styles = getSampleStyleSheet()
    if df.empty:
        return Paragraph("<i>Sem dados.</i>", styles["BodyText"])

    if max_rows and len(df) > max_rows:
        df = df.head(max_rows)

    data = [list(df.columns)] + df.astype(str).values.tolist()
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2D6A4F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ]))
    return table


def gerar_relatorio_investimentos_pdf(
    obra, periodo, vgv, custos, lucro, roi, perc_vgv, df_categorias, df_lancamentos
):
    buffer = io.BytesIO()
    footer = f"Gestor Pro • {obra} • {periodo}"

    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=24, leftMargin=24,
        topMargin=24, bottomMargin=40
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("GESTOR PRO — Relatório de Investimentos", styles["Title"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>Obra:</b> {obra}", styles["BodyText"]))
    story.append(Paragraph(f"<b>Período:</b> {periodo}", styles["BodyText"]))
    story.append(Paragraph(f"<b>Gerado em:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["BodyText"]))
    story.append(Spacer(1, 12))

    resumo = pd.DataFrame([
        ["VGV", fmt_moeda(vgv)],
        ["Custo", fmt_moeda(custos)],
        ["Lucro", fmt_moeda(lucro)],
        ["ROI", f"{roi:.1f}%"],
        ["% VGV Gasto", f"{perc_vgv:.2f}%"],
    ], columns=["Indicador", "Valor"])

    story.append(Paragraph("Resumo", styles["Heading2"]))
    story.append(_df_to_table(resumo))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Custo por Categoria", styles["Heading2"]))
    story.append(_df_to_table(df_categorias))
    story.append(PageBreak())

    story.append(Paragraph("Lançamentos", styles["Heading2"]))
    story.append(_df_to_table(df_lancamentos))

    doc.build(
        story,
        canvasmaker=lambda *args, **kw: NumberedCanvas(*args, footer_left=footer, **kw),
    )

    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def download_pdf_one_click(pdf, nome):
    b64 = base64.b64encode(pdf).decode()
    html = f"""
    <a id="dl" href="data:application/pdf;base64,{b64}" download="{nome}"></a>
    <script>document.getElementById("dl").click();</script>
    """
    st.components.v1.html(html, height=0)


# =========================================================
# 2) CONFIG UI
# =========================================================
st.set_page_config("GESTOR PRO | Master", layout="wide")


# =========================================================
# 3) CONSTANTES
# =========================================================
OBRAS_COLS = ["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"]
FIN_COLS = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]
CATEGORIAS_PADRAO = ["Geral", "Material", "Mão de Obra", "Serviços", "Impostos", "Outros"]


def ensure_cols(df, cols):
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]


# =========================================================
# 4) DB
# =========================================================
@st.cache_resource
def obter_db():
    creds = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds, scope)).open("GestorObras_DB")


@st.cache_data(ttl=10)
def carregar_obras():
    ws = obter_db().worksheet("Obras")
    df = pd.DataFrame(ws.get_all_records())
    if df.empty:
        df = pd.DataFrame(columns=OBRAS_COLS)
    df = ensure_cols(df, OBRAS_COLS)
    df["Valor Total"] = df["Valor Total"].apply(_to_float)
    return df


@st.cache_data(ttl=10)
def carregar_financeiro():
    ws = obter_db().worksheet("Financeiro")
    df = pd.DataFrame(ws.get_all_records())
    if df.empty:
        df = pd.DataFrame(columns=FIN_COLS)
    df = ensure_cols(df, FIN_COLS)
    df["Valor"] = df["Valor"].apply(_to_float)
    return normalizar_datas(df, "Data")


# =========================================================
# 5) AUTH
# =========================================================
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "login_attempts" not in st.session_state:
    st.session_state["login_attempts"] = 0

if not st.session_state["authenticated"]:
    with st.form("login"):
        st.title("GESTOR PRO")
        pwd = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if pwd == st.secrets["password"]:
                st.session_state["authenticated"] = True
                st.session_state["login_attempts"] = 0
                st.rerun()
            else:
                st.session_state["login_attempts"] += 1
                st.error("Senha incorreta.")
                if st.session_state["login_attempts"] >= 5:
                    st.stop()
    st.stop()


# =========================================================
# 6) LOAD
# =========================================================
df_obras = carregar_obras()
df_fin = carregar_financeiro()

lista_obras = (
    df_obras["Cliente"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist()
)


# =========================================================
# 7) SIDEBAR
# =========================================================
with st.sidebar:
    sel = option_menu("GESTOR PRO", ["Investimentos", "Caixa", "Insumos", "Projetos"])
    if st.button("Sair"):
        st.session_state["authenticated"] = False
        st.rerun()


# =========================================================
# 8) INVESTIMENTOS
# =========================================================
if sel == "Investimentos":
    st.header("📊 Investimentos")

    obra = st.selectbox("Obra", lista_obras)
    obra_row = df_obras[df_obras["Cliente"] == obra].iloc[0]
    vgv = obra_row["Valor Total"]

    df_v = df_fin[df_fin["Obra Vinculada"] == obra]
    df_saidas = df_v[df_v["Tipo"].str.contains("Saída", case=False, na=False)]

    custos = df_saidas["Valor"].sum()
    lucro = vgv - custos
    roi = calc_roi(lucro, custos)
    perc_vgv = (custos / vgv * 100) if vgv > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VGV", fmt_moeda(vgv))
    c2.metric("Custos", fmt_moeda(custos))
    c3.metric("Lucro", fmt_moeda(lucro))
    c4.metric("ROI", f"{roi:.1f}%")

    st.divider()

    df_cat = df_saidas.groupby("Categoria", as_index=False)["Valor"].sum()
    df_cat["Valor_fmt"] = df_cat["Valor"].apply(fmt_moeda)

    if st.button("⬇️ Baixar PDF"):
        with st.spinner("Gerando relatório..."):
            pdf = gerar_relatorio_investimentos_pdf(
                obra, "Período selecionado", vgv, custos, lucro, roi, perc_vgv,
                df_cat[["Categoria", "Valor_fmt"]],
                df_saidas[["Data_BR", "Categoria", "Descrição", "Valor"]]
            )
            download_pdf_one_click(pdf, f"relatorio_{obra}.pdf")
