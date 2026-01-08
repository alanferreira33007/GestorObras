# ============================
# IMPORTS
# ============================
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

# ============================
# PDF HELPERS
# ============================
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
        w, _ = A4
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.grey)
        self.line(24, 28, w - 24, 28)
        self.drawString(24, 14, self.footer_left)
        self.drawRightString(w - 24, 14, f"Página {self.getPageNumber()} de {total}")

def fmt_moeda(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

# ============================
# CONFIG UI
# ============================
st.set_page_config("GESTOR PRO | Master v26", layout="wide")

# ============================
# SCHEMA
# ============================
OBRAS_COLS = ["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"]
FIN_COLS   = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]
CATEGORIAS_PADRAO = ["Geral", "Material", "Mão de Obra", "Serviços", "Impostos", "Outros"]

def ensure_cols(df, cols):
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]

# ============================
# DB
# ============================
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
    return df_o, df_f

# ============================
# AUTH
# ============================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    with st.form("login"):
        st.markdown("## 🔐 GESTOR PRO")
        pwd = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if pwd == st.secrets["password"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    st.stop()

# ============================
# LOAD APP
# ============================
df_obras, df_fin = carregar_dados()
lista_obras = df_obras["Cliente"].dropna().unique().tolist()

# ============================
# SIDEBAR
# ============================
with st.sidebar:
    sel = option_menu("GESTOR PRO", ["Investimentos", "Caixa", "Insumos", "Projetos"])
    if st.button("Sair"):
        st.session_state.authenticated = False
        st.rerun()

# ============================
# TELAS (mínimo funcional)
# ============================
st.markdown(f"## {sel}")
st.success("Aplicação carregada com sucesso ✅")
