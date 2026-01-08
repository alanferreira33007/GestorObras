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
import re

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas

# ======================================================
# 0) PDF HELPERS
# ======================================================
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, footer_left: str = "Gestor Pro", **kwargs):
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


def fmt_moeda(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"


def _to_float(x):
    if x is None or x == "":
        return 0.0
    try:
        s = str(x).replace("R$", "").replace(".", "").replace(",", ".")
        return float(s)
    except:
        return 0.0


def _df_to_table(df, max_rows=None):
    styles = getSampleStyleSheet()
    if df is None or df.empty:
        return Paragraph("<i>Sem dados.</i>", styles["BodyText"])

    df2 = df.copy()
    if max_rows and len(df2) > max_rows:
        df2 = df2.head(max_rows)

    data = [list(df2.columns)] + df2.astype(str).values.tolist()
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2D6A4F")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.white]),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ]))
    return t


def gerar_relatorio_investimentos_pdf(
    obra, periodo, vgv, custos, lucro, roi, perc_vgv, df_categorias, df_lancamentos
):
    buffer = io.BytesIO()
    footer = f"Gestor Pro • {obra} • {periodo}"

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=24, rightMargin=24,
        topMargin=24, bottomMargin=40
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("GESTOR PRO — Relatório de Investimentos", styles["Title"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>Obra:</b> {obra}", styles["BodyText"]))
    story.append(Paragraph(f"<b>Período:</b> {periodo}", styles["BodyText"]))
    story.append(Paragraph(f"<b>Gerado em:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["BodyText"]))
    story.append(Spacer(1, 14))

    resumo = pd.DataFrame([
        ["VGV", fmt_moeda(vgv)],
        ["Custos", fmt_moeda(custos)],
        ["Lucro", fmt_moeda(lucro)],
        ["ROI", f"{roi:.1f}%"],
        ["% do VGV", f"{perc_vgv:.2f}%"],
    ], columns=["Indicador", "Valor"])

    story.append(Paragraph("Resumo", styles["Heading2"]))
    story.append(_df_to_table(resumo))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Custos por Categoria", styles["Heading2"]))
    story.append(_df_to_table(df_categorias))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Lançamentos", styles["Heading2"]))
    story.append(_df_to_table(df_lancamentos))

    doc.build(
        story,
        canvasmaker=lambda *a, **k: NumberedCanvas(*a, footer_left=footer, **k)
    )

    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def _download_pdf_one_click(pdf, nome):
    b64 = base64.b64encode(pdf).decode()
    html = f"""
    <a id="dl" href="data:application/pdf;base64,{b64}" download="{nome}"></a>
    <script>document.getElementById("dl").click();</script>
    """
    st.components.v1.html(html, height=0)

# ======================================================
# 1) CONFIG UI
# ======================================================
st.set_page_config("GESTOR PRO | Master v26", layout="wide")

# ======================================================
# 2) SCHEMA
# ======================================================
OBRAS_COLS = ["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"]
FIN_COLS = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]
CATEGORIAS_PADRAO = ["Geral", "Material", "Mão de Obra", "Serviços", "Impostos", "Outros"]


def ensure_cols(df, cols):
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]

# ======================================================
# 3) DB
# ======================================================
@st.cache_resource
def obter_db():
    creds = json.loads(st.secrets["gcp_service_account"]["json_content"])
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds, scope))
    return client.open("GestorObras_DB")


@st.cache_data(ttl=10)
def carregar_dados():
    db = obter_db()

    df_o = ensure_cols(pd.DataFrame(db.worksheet("Obras").get_all_records()), OBRAS_COLS)
    df_o["Valor Total"] = pd.to_numeric(df_o["Valor Total"], errors="coerce").fillna(0)

    df_f = ensure_cols(pd.DataFrame(db.worksheet("Financeiro").get_all_records()), FIN_COLS)
    df_f["Valor"] = pd.to_numeric(df_f["Valor"], errors="coerce").fillna(0)
    df_f["Data_DT"] = pd.to_datetime(df_f["Data"], errors="coerce")
    df_f["Data_BR"] = df_f["Data_DT"].dt.strftime("%d/%m/%Y").fillna("")

    for c in ["Tipo", "Categoria", "Descrição", "Obra Vinculada"]:
        df_f[c] = df_f[c].fillna("").astype(str).str.strip()

    df_f["_obra_norm"] = df_f["Obra Vinculada"]
    return df_o, df_f

# ======================================================
# 4) AUTH
# ======================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    pwd = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if pwd == st.secrets["password"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Senha incorreta")
    st.stop()

# ======================================================
# 5) LOAD
# ======================================================
df_obras, df_fin = carregar_dados()
lista_obras = df_obras["Cliente"].dropna().astype(str).str.strip().unique().tolist()

# ======================================================
# 6) SIDEBAR
# ======================================================
with st.sidebar:
    sel = option_menu("GESTOR PRO", ["Investimentos", "Caixa", "Insumos", "Projetos"])
    if st.button("Sair"):
        st.session_state.authenticated = False
        st.rerun()

# ======================================================
# 7) INVESTIMENTOS
# ======================================================
if sel == "Investimentos":
    obra_sel = st.selectbox("Obra", lista_obras)

    obra = df_obras[df_obras["Cliente"] == obra_sel].iloc[0]
    vgv = float(obra["Valor Total"])

    df_v = df_fin[df_fin["_obra_norm"] == obra_sel]
    df_saidas = df_v[df_v["Tipo"].str.lower().str.startswith("saída")]

    custos = df_saidas["Valor"].sum()
    lucro = vgv - custos
    roi = (lucro / custos * 100) if custos > 0 else 0
    perc_vgv = (custos / vgv * 100) if vgv > 0 else 0

    st.metric("VGV", fmt_moeda(vgv))
    st.metric("Custos", fmt_moeda(custos))
    st.metric("Lucro", fmt_moeda(lucro))
    st.metric("ROI", f"{roi:.1f}%")

    df_cat = df_saidas.groupby("Categoria", as_index=False)["Valor"].sum()
    fig = px.bar(df_cat, x="Categoria", y="Valor")
    st.plotly_chart(fig, use_container_width=True)

    if st.button("⬇️ Baixar PDF"):
        periodo = "Período selecionado"
        pdf = gerar_relatorio_investimentos_pdf(
            obra_sel, periodo, vgv, custos, lucro, roi, perc_vgv,
            df_cat.assign(Valor=df_cat["Valor"].apply(fmt_moeda)),
            df_saidas[["Data_BR", "Categoria", "Descrição", "Valor"]]
        )
        nome = re.sub(r"[^A-Za-z0-9_-]", "_", obra_sel)
        _download_pdf_one_click(pdf, f"relatorio_{nome}.pdf")
