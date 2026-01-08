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
            df_o = pd.DataFrame(columns=["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"])

        ws_f = db.worksheet("Financeiro")
        df_f = pd.DataFrame(ws_f.get_all_records())
        if df_f.empty:
            df_f = pd.DataFrame(columns=["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"])

        df_f["Valor"] = pd.to_numeric(df_f["Valor"], errors="coerce").fillna(0)
        df_f["Data_DT"] = pd.to_datetime(df_f["Data"], errors="coerce")
        df_f["Data_BR"] = df_f["Data_DT"].dt.strftime("%d/%m/%Y")
        df_f.loc[df_f["Data_DT"].isna(), "Data_BR"] = ""

        # 🔹 MELHORIA 1 APLICADA AQUI 🔹
        # Normaliza strings (evita "nan", remove espaços)
        for col in ["Tipo", "Categoria", "Descrição", "Obra Vinculada"]:
            if col in df_f.columns:
                df_f[col] = (
                    df_f[col]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )

        return df_o, df_f

    except Exception as e:
        st.error(f"Erro de Conexão: {e}")
        return pd.DataFrame(), pd.DataFrame()
