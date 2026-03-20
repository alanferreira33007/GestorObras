"""
GESTOR PRO v4.0 — Sistema Integrado de Gestão de Obras
Design moderno com navegação nativa do Streamlit.
"""

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import date, datetime, timedelta
import io
import hmac
import logging
from typing import Union, Optional, List, Dict, Any, Tuple
from gspread.utils import rowcol_to_a1

# ==============================================================================
# CONFIG
# ==============================================================================
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

APP_VERSION = "v4.0.0"

COR = "#0F4C75"
COR2 = "#1B262C"
COR_OK = "#27AE60"
COR_WARN = "#F39C12"
COR_ERR = "#E74C3C"

STATUS_OBRA = ["Projeto", "Fundação", "Alvenaria", "Acabamento", "Concluída", "Vendida"]

OBRAS_COLS = [
    "ID", "Cliente", "Endereço", "Status", "Valor Total",
    "Data Início", "Prazo", "Area Construida", "Area Terreno",
    "Quartos", "Custo Previsto"
]

FIN_COLS = ["ID", "Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada", "Fornecedor", "Forma Pagamento"]
AUDIT_COLS = ["Timestamp", "Usuário", "Ação", "Detalhes"]

CATS = ["Material", "Mão de Obra", "Serviços", "Administrativo", "Impostos", "Emolumentos Cartorários", "Outros"]
PAGAMENTOS = ["PIX", "Cartão de Crédito", "Cartão de Débito", "Dinheiro", "Transferência", "Boleto", "Cheque", "Outro"]

DEFAULTS_FIN = {"data": date.today(), "tipo": "Saída (Despesa)", "cat": "", "obra": "", "pag": "", "valor": 0.0, "desc": "", "forn": ""}
DEFAULTS_OBRA = {"nome": "", "end": "", "area_c": 0.0, "area_t": 0.0, "quartos": 0, "status": "Projeto", "custo": 0.0, "vgv": 0.0, "prazo": "", "data": date.today()}

# ==============================================================================
# PAGE CONFIG + CSS
# ==============================================================================
st.set_page_config(
    page_title="Gestor Pro",
    layout="wide",
    page_icon="🏗️",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* Reset padding */
    .main .block-container { padding-top: 1rem; }

    /* Buttons */
    div.stButton > button {
        background: linear-gradient(135deg, #0F4C75, #1B262C);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        min-height: 44px;
        transition: opacity 0.2s;
    }
    div.stButton > button:hover { opacity: 0.85; }

    /* Download buttons */
    [data-testid="stDownloadButton"] > button {
        background: linear-gradient(135deg, #0F4C75, #1B262C) !important;
        color: white !important;
        border-radius: 10px;
        min-height: 44px;
        font-weight: 600;
    }

    /* Form submit */
    [data-testid="stFormSubmitButton"] > button {
        min-height: 48px;
        font-size: 1rem;
    }

    /* Tabs styling */
    [data-testid="stTabs"] button {
        font-weight: 600;
        font-size: 0.9rem;
    }
    [data-testid="stTabs"] button[aria-selected="true"] {
        border-bottom-color: #0F4C75 !important;
        color: #0F4C75 !important;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: white;
        border: 1px solid #E8ECF0;
        border-radius: 12px;
        padding: 12px 16px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }

    /* iOS zoom prevention */
    input, select, textarea { font-size: 16px !important; }

    /* Divider */
    hr { margin: 0.8rem 0 !important; border-color: #E8ECF0 !important; }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# HELPERS
# ==============================================================================
def check_password(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)

def get_users_config() -> dict:
    if "users" in st.secrets:
        return dict(st.secrets["users"])
    return {"admin": {"password": st.secrets["password"], "role": "admin", "name": "Administrador"}}

def authenticate_user(username: str, password: str) -> Optional[dict]:
    users = get_users_config()
    if username == "":
        for uid, udata in users.items():
            pwd = udata["password"] if isinstance(udata, dict) else str(udata)
            if check_password(password, pwd):
                return {"username": uid, "role": udata.get("role", "admin") if isinstance(udata, dict) else "admin", "name": udata.get("name", uid) if isinstance(udata, dict) else uid}
        return None
    if username not in users:
        return None
    udata = users[username]
    stored_pwd = udata["password"] if isinstance(udata, dict) else str(udata)
    if check_password(password, stored_pwd):
        return {"username": username, "role": udata.get("role", "admin") if isinstance(udata, dict) else "admin", "name": udata.get("name", username) if isinstance(udata, dict) else username}
    return None

def require_role(min_role: str) -> bool:
    hierarchy = {"viewer": 0, "editor": 1, "admin": 2}
    return hierarchy.get(st.session_state.get("user_role", "admin"), 0) >= hierarchy.get(min_role, 0)

def get_current_user() -> str:
    return st.session_state.get("user_name", "Administrador")

def verify_admin_password(pwd: str) -> bool:
    for uid, udata in get_users_config().items():
        stored = udata["password"] if isinstance(udata, dict) else str(udata)
        if check_password(pwd, stored):
            return True
    return False

def reset_form_state(prefix: str, defaults: Dict[str, Any]) -> None:
    for key, value in defaults.items():
        st.session_state[f"{prefix}_{key}"] = value

def fmt_moeda(valor, simbolo: str = "R$") -> str:
    if pd.isna(valor) or valor == "" or valor is None:
        return f"{simbolo} 0,00"
    try:
        val = float(valor)
        neg = val < 0
        val = abs(val)
        inteiro = int(val)
        decimal = int(round((val - inteiro) * 100))
        s = f"{inteiro:,}".replace(",", ".")
        return f"{simbolo} {'-' if neg else ''}{s},{decimal:02d}"
    except (ValueError, TypeError):
        return f"{simbolo} {valor}"

def safe_float(x) -> float:
    if isinstance(x, (int, float)):
        return float(x)
    if x is None:
        return 0.0
    s = str(x).strip().replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0

def normalize_string(value) -> str:
    if value is None:
        return ""
    return str(value).strip()

def init_session_state_defaults(prefix: str, defaults: Dict[str, Any]) -> None:
    for key, value in defaults.items():
        k = f"{prefix}_{key}"
        if k not in st.session_state:
            st.session_state[k] = value

def clear_data_cache() -> None:
    for key in ["data_obras", "data_fin"]:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state["last_sync"] = datetime.now()
    st.cache_data.clear()

def generate_unique_id(existing_ids: pd.Series) -> int:
    ts_id = int(datetime.now().timestamp() * 1000) % 1_000_000_000
    if not existing_ids.empty:
        s = set(existing_ids.dropna().astype(int).tolist())
        while ts_id in s:
            ts_id += 1
    return ts_id

def validate_lancamento(obra, categoria, tipo, descricao, valor, fornecedor="", forma_pagamento=""):
    erros = []
    if not normalize_string(obra): erros.append("Selecione a Obra Vinculada.")
    if not normalize_string(categoria): erros.append("Selecione a Categoria.")
    if not normalize_string(tipo): erros.append("Selecione o Tipo.")
    if not normalize_string(descricao): erros.append("A Descrição é obrigatória.")
    if valor <= 0: erros.append("O Valor deve ser maior que zero.")
    if normalize_string(categoria) == "Material" and not normalize_string(fornecedor):
        erros.append("Para 'Material', Fornecedor é obrigatório.")
    if not normalize_string(forma_pagamento): erros.append("Selecione a Forma de Pagamento.")
    return (len(erros) == 0, erros)

def validate_obra(nome, endereco, prazo, vgv, custo, area_const, area_terr):
    erros = []
    n = normalize_string(nome)
    if not n: erros.append("Nome do Empreendimento é obrigatório.")
    elif len(n) < 3: erros.append("Nome deve ter pelo menos 3 caracteres.")
    if not normalize_string(endereco): erros.append("Endereço é obrigatório.")
    if not normalize_string(prazo): erros.append("Prazo é obrigatório.")
    if vgv <= 0: erros.append("VGV deve ser maior que zero.")
    if custo <= 0: erros.append("Orçamento deve ser maior que zero.")
    if area_const <= 0 and area_terr <= 0: erros.append("Preencha ao menos uma área.")
    return (len(erros) == 0, erros)

def build_row_values(row, headers: list) -> list:
    values = []
    for h in headers:
        v = row.get(h, "")
        if h == "ID":
            values.append(int(row["ID"]))
        elif h == "Data":
            values.append(v.strftime("%Y-%m-%d") if isinstance(v, (date, datetime)) else str(v)[:10])
        elif h == "Valor":
            values.append(float(safe_float(v)))
        else:
            values.append("" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip())
    return values

def log_action(action: str, details: str = "") -> None:
    try:
        ws = get_conn().worksheet("Auditoria")
        ws.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), get_current_user(), action, details[:500]])
    except Exception as e:
        logger.warning(f"Falha auditoria: {e}")


# ==============================================================================
# SCHEMA MIGRATION
# ==============================================================================
def ensure_financeiro_id(ws_fin):
    headers = ws_fin.row_values(1)
    if "ID" in headers:
        return
    n_rows = len(ws_fin.get_all_values())
    ws_fin.insert_cols([["ID"]], 1)
    if n_rows > 1:
        ws_fin.update(f"A2:A{n_rows}", [[i] for i in range(1, n_rows)])

def ensure_financeiro_schema(ws_fin, required_cols):
    ensure_financeiro_id(ws_fin)
    headers = ws_fin.row_values(1)
    missing = [c for c in required_cols if c not in headers]
    if not missing:
        return
    n_rows = len(ws_fin.get_all_values())
    for col_name in missing:
        headers = ws_fin.row_values(1)
        new_col = len(headers) + 1
        ws_fin.update_cell(1, new_col, col_name)
        if n_rows > 1:
            start = rowcol_to_a1(2, new_col)
            end = rowcol_to_a1(n_rows, new_col)
            ws_fin.update(f"{start}:{end}", [[""]] * (n_rows - 1))

def ensure_audit_sheet(db):
    try:
        db.worksheet("Auditoria")
    except gspread.exceptions.WorksheetNotFound:
        ws = db.add_worksheet(title="Auditoria", rows=1000, cols=len(AUDIT_COLS))
        ws.update("A1:D1", [AUDIT_COLS])


# ==============================================================================
# PDF ENGINE
# ==============================================================================
def gerar_pdf_empresarial(escopo, periodo, vgv, custos, lucro, roi, df_cat, df_lanc):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm

    class PDFCanvas(canvas.Canvas):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self._pages = []
        def showPage(self):
            self._pages.append(dict(self.__dict__))
            super().showPage()
        def save(self):
            n = len(self._pages)
            for s in self._pages:
                self.__dict__.update(s)
                w, _ = A4
                self.setStrokeColor(colors.lightgrey); self.setLineWidth(0.5)
                self.line(30, 50, w-30, 50)
                self.setFillColor(colors.grey); self.setFont("Helvetica", 8)
                self.drawString(30, 35, "GESTOR PRO — Relatório contábil")
                self.drawRightString(w-30, 35, f"Emitido: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
                self.drawRightString(w-30, 25, f"Pág. {self.getPageNumber()}/{n}")
                super().showPage()
            super().save()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=60)
    story = []
    styles = getSampleStyleSheet()
    h_title = ParagraphStyle('HT', parent=styles['Normal'], fontSize=14, leading=16, textColor=colors.white, fontName='Helvetica-Bold')
    h_sub = ParagraphStyle('HS', parent=styles['Normal'], fontSize=9, leading=11, textColor=colors.whitesmoke)
    h2 = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor(COR2), spaceBefore=15, spaceAfter=8, fontName='Helvetica-Bold')

    titulo = "RELATÓRIO DE PORTFÓLIO (CONSOLIDADO)" if "Visão Geral" in str(escopo) else f"RELATÓRIO: {str(escopo).upper()}"
    hdr = Table([[Paragraph(titulo, h_title), Paragraph(f"PERÍODO:<br/>{periodo}", h_sub)]], colWidths=[12*cm, 5*cm])
    hdr.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor(COR)), ('PADDING', (0,0), (-1,-1), 15), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (1,0), (1,0), 'RIGHT'), ('ROUNDEDCORNERS', [4,4,4,4])]))
    story.append(hdr); story.append(Spacer(1, 15))

    story.append(Paragraph("RESUMO FINANCEIRO", h2))
    p = (custos/vgv*100) if vgv > 0 else 0
    rd = [["ORÇAMENTO (VGV)", "GASTO TOTAL", "SALDO / LUCRO", "ROI", "CONSUMO"], [fmt_moeda(vgv), fmt_moeda(custos), fmt_moeda(lucro), f"{roi:.1f}%", f"{p:.1f}%"]]
    tr = Table(rd, colWidths=[3.7*cm]*5)
    tr.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'Helvetica-Bold'), ('FONTSIZE',(0,0),(-1,0),7), ('TEXTCOLOR',(0,0),(-1,0),colors.grey), ('ALIGN',(0,0),(-1,-1),'CENTER'), ('FONTSIZE',(0,1),(-1,1),10), ('BACKGROUND',(0,0),(-1,1),colors.HexColor('#F8F9FA')), ('BOX',(0,0),(-1,-1),0.5,colors.lightgrey), ('PADDING',(0,0),(-1,-1),8)]))
    story.append(tr); story.append(Spacer(1, 15))

    if df_cat is not None and not df_cat.empty:
        story.append(Paragraph("DISTRIBUIÇÃO POR CATEGORIA", h2))
        dc = df_cat.copy()
        dc["Valor"] = dc["Valor"].apply(fmt_moeda)
        dc["%"] = (df_cat["Valor"] / custos * 100).apply(lambda x: f"{x:.1f}%") if custos > 0 else "0%"
        cd = [["CATEGORIA", "VALOR", "%"]] + dc[["Categoria", "Valor", "%"]].values.tolist()
        tc = Table(cd, colWidths=[10*cm, 4*cm, 3*cm], hAlign='LEFT')
        tc.setStyle(TableStyle([('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'), ('FONTSIZE',(0,0),(-1,0),8), ('TEXTCOLOR',(0,0),(-1,0),colors.white), ('BACKGROUND',(0,0),(-1,0),colors.HexColor(COR_OK)), ('ALIGN',(1,0),(-1,-1),'RIGHT'), ('GRID',(0,0),(-1,-1),0.25,colors.lightgrey), ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, colors.whitesmoke]), ('PADDING',(0,0),(-1,-1),6)]))
        story.append(tc); story.append(Spacer(1, 15))

    story.append(Paragraph("EXTRATO DE LANÇAMENTOS", h2))
    if df_lanc is not None and not df_lanc.empty:
        dl = df_lanc.copy()
        for c in ["Data", "Categoria", "Descrição", "Valor"]:
            if c not in dl.columns: dl[c] = ""
        dl["Valor"] = dl["Valor"].apply(fmt_moeda)
        dd = [["Data", "Categoria", "Descrição", "Valor"]] + dl[["Data", "Categoria", "Descrição", "Valor"]].values.tolist()
        dd.append(["", "", "SUBTOTAL:", fmt_moeda(custos)])
        tl = Table(dd, colWidths=[2.5*cm, 3.5*cm, 8*cm, 3*cm])
        tl.setStyle(TableStyle([('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'), ('FONTSIZE',(0,0),(-1,0),8), ('TEXTCOLOR',(0,0),(-1,0),colors.white), ('BACKGROUND',(0,0),(-1,0),colors.HexColor(COR)), ('FONTSIZE',(0,1),(-1,-1),8), ('ALIGN',(-1,0),(-1,-1),'RIGHT'), ('GRID',(0,0),(-1,-2),0.25,colors.lightgrey), ('ROWBACKGROUNDS',(0,1),(-1,-2),[colors.white, colors.whitesmoke]), ('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'), ('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#e9ecef')), ('LINEABOVE',(0,-1),(-1,-1),1,colors.black)]))
        story.append(tl)
    else:
        story.append(Paragraph("Nenhum lançamento no período.", styles['Normal']))

    story.append(Spacer(1, 40))
    sig = [["_______________________________________", "_______________________________________"], ["GESTOR RESPONSÁVEL", "DIRETORIA FINANCEIRA"], [f"Data: {date.today().strftime('%d/%m/%Y')}", "Data: ____/____/________"]]
    ts = Table(sig, colWidths=[8.5*cm, 8.5*cm])
    ts.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER'), ('FONTNAME',(0,1),(-1,-1),'Helvetica-Bold'), ('FONTSIZE',(0,1),(-1,-1),8), ('TEXTCOLOR',(0,1),(-1,-1),colors.grey)]))
    story.append(ts)

    doc.build(story, canvasmaker=PDFCanvas)
    return buf.getvalue()


# ==============================================================================
# DB CONNECTION
# ==============================================================================
@st.cache_resource
def get_conn():
    creds_dict = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
    scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    db = gspread.authorize(credentials).open("GestorObras_DB")
    if "schema_verified" not in st.session_state:
        try:
            ensure_financeiro_schema(db.worksheet("Financeiro"), FIN_COLS)
            ensure_audit_sheet(db)
            st.session_state["schema_verified"] = True
        except Exception as e:
            logger.warning(f"Schema: {e}")
    return db

@st.cache_data(ttl=120)
def fetch_data():
    try:
        db = get_conn()
        df_o = pd.DataFrame(db.worksheet("Obras").get_all_records())
        if df_o.empty:
            df_o = pd.DataFrame(columns=OBRAS_COLS)
        else:
            for c in OBRAS_COLS:
                if c not in df_o.columns: df_o[c] = None

        ws_f = db.worksheet("Financeiro")
        if not st.session_state.get("schema_verified"):
            try:
                ensure_financeiro_schema(ws_f, FIN_COLS)
                st.session_state["schema_verified"] = True
            except Exception:
                pass
        df_f = pd.DataFrame(ws_f.get_all_records())
        if df_f.empty:
            df_f = pd.DataFrame(columns=FIN_COLS)
        else:
            for c in FIN_COLS:
                if c not in df_f.columns: df_f[c] = None

        df_o["Valor Total"] = df_o["Valor Total"].apply(safe_float)
        if "Custo Previsto" in df_o.columns:
            df_o["Custo Previsto"] = df_o["Custo Previsto"].apply(safe_float)
        if "Cliente" in df_o.columns:
            df_o["Cliente"] = df_o["Cliente"].astype(str).str.strip()

        if "ID" in df_f.columns:
            df_f["ID"] = pd.to_numeric(df_f["ID"], errors="coerce").fillna(0).astype(int)
        df_f["Valor"] = df_f["Valor"].apply(safe_float)
        df_f["Data_DT"] = pd.to_datetime(df_f["Data"], errors="coerce")
        for col in ["Obra Vinculada", "Categoria", "Fornecedor", "Forma Pagamento"]:
            if col in df_f.columns:
                df_f[col] = df_f[col].astype(str).str.strip()

        return df_o, df_f
    except Exception as e:
        st.error(f"Erro DB: {e}")
        logger.error(f"DB error: {e}")
        return pd.DataFrame(), pd.DataFrame()


# ==============================================================================
# AUTH
# ==============================================================================
if "auth" not in st.session_state:
    st.session_state.auth = False

def logout():
    for k in ["auth", "user_id", "user_name", "user_role", "schema_verified"]:
        if k in st.session_state:
            del st.session_state[k]
    st.session_state.auth = False
    clear_data_cache()

if not st.session_state.auth:
    st.markdown("""
        <div style='text-align:center; padding: 4rem 0 1.5rem 0;'>
            <h1 style='font-size: 2.5rem; font-weight: 800; margin-bottom: 0.2rem;'>
                <span style='color: #0F4C75;'>GESTOR</span> <span style='color: #1B262C;'>PRO</span>
            </h1>
            <p style='color: #888; font-size: 0.95rem; letter-spacing: 2px;'>INCORPORAÇÃO & OBRAS</p>
        </div>
    """, unsafe_allow_html=True)

    _, lc, _ = st.columns([1, 2, 1])
    with lc:
        if st.session_state.get("login_error"):
            st.error(st.session_state["login_error"])
        has_multi = "users" in st.secrets
        login_user = st.text_input("Usuário", key="lu", placeholder="seu.usuario") if has_multi else ""
        login_pwd = st.text_input("Senha", type="password", key="lp")
        st.write("")
        if st.button("Entrar", use_container_width=True):
            user = authenticate_user(login_user, login_pwd)
            if user:
                st.session_state.auth = True
                st.session_state.user_id = user["username"]
                st.session_state.user_name = user["name"]
                st.session_state.user_role = user["role"]
                st.session_state.pop("login_error", None)
                try:
                    o, f = fetch_data()
                    st.session_state["data_obras"] = o
                    st.session_state["data_fin"] = f
                except Exception:
                    pass
                st.rerun()
            else:
                st.session_state.login_error = "Credenciais incorretas"
                st.rerun()
        st.caption(f"<p style='text-align:center; margin-top:2rem; color:#aaa;'>{APP_VERSION}</p>", unsafe_allow_html=True)
    st.stop()


# ==============================================================================
# SIDEBAR
# ==============================================================================
with st.sidebar:
    st.markdown(f"""
        <div style='margin-bottom: 16px;'>
            <h2 style='margin:0; font-weight:800;'><span style='color:{COR};'>GESTOR</span> PRO</h2>
            <p style='color:#888; font-size:11px; margin:0; letter-spacing:1px;'>INCORPORAÇÃO & OBRAS</p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    user_name = get_current_user()
    user_role = st.session_state.get("user_role", "admin")
    role_map = {"admin": "Administrador", "editor": "Editor", "viewer": "Visualizador"}
    st.markdown(f"👤 **{user_name}** — {role_map.get(user_role, user_role)}")

    last_sync = st.session_state.get("last_sync")
    if last_sync:
        d = (datetime.now() - last_sync).seconds
        txt = "agora" if d < 60 else f"há {d // 60} min"
        st.caption(f"🟢 Sincronizado {txt}")
    else:
        st.caption("🟢 Conectado")

    st.markdown("---")
    st.button("Sair", on_click=logout, use_container_width=True)
    st.caption(f"<p style='text-align:center; color:#aaa; font-size:10px; margin-top:20px;'>{APP_VERSION} © 2026</p>", unsafe_allow_html=True)


# ==============================================================================
# DATA
# ==============================================================================
if "data_obras" not in st.session_state or "data_fin" not in st.session_state:
    with st.spinner("Sincronizando..."):
        try:
            df_obras, df_fin = fetch_data()
            st.session_state["data_obras"] = df_obras
            st.session_state["data_fin"] = df_fin
            st.session_state["last_sync"] = datetime.now()
        except Exception as e:
            st.error(f"Falha: {e}")
            st.stop()
else:
    df_obras = st.session_state["data_obras"]
    df_fin = st.session_state["data_fin"]

lista_obras = sorted(df_obras["Cliente"].unique().tolist()) if not df_obras.empty else []


# ==============================================================================
# NAVIGATION — Tabs no topo
# ==============================================================================
menu_tabs = ["Dashboard", "Financeiro", "Obras"]
if require_role("admin"):
    menu_tabs.append("Auditoria")

sel = st.radio("Navegação", menu_tabs, horizontal=True, label_visibility="collapsed")
st.markdown("---")


# ==============================================================================
# DASHBOARD
# ==============================================================================
if sel == "Dashboard":
    import plotly.express as px
    import plotly.graph_objects as go

    c1, c2 = st.columns([3, 1])
    with c1:
        if lista_obras:
            opcoes = ["Todas as Obras"] + lista_obras
            escopo = st.selectbox("Escopo", opcoes, label_visibility="collapsed")
        else:
            st.warning("Cadastre uma obra primeiro.")
            st.stop()
    with c2:
        if st.button("🔄 Atualizar", use_container_width=True):
            clear_data_cache()
            st.rerun()

    # Alertas de prazo
    if not df_obras.empty and "Prazo" in df_obras.columns:
        hoje = date.today()
        for _, ob in df_obras.iterrows():
            s = str(ob.get("Status", "")).strip().lower()
            if s in ["concluída", "vendida"]:
                continue
            prazo_str = str(ob.get("Prazo", "")).strip()
            nome_ob = str(ob["Cliente"]).strip()
            prazo_dt = None
            for fmt in ["%m/%Y", "%b/%Y", "%Y-%m-%d", "%d/%m/%Y"]:
                try:
                    prazo_dt = datetime.strptime(prazo_str, fmt).date()
                    break
                except (ValueError, TypeError):
                    continue
            if prazo_dt:
                dias = (prazo_dt - hoje).days
                if dias < 0:
                    st.error(f"🚨 **{nome_ob}** — Prazo vencido há {abs(dias)} dias!")
                elif dias <= 30:
                    st.warning(f"⏰ **{nome_ob}** — Vence em {dias} dias")

    df_saida = df_fin[df_fin["Tipo"].astype(str).str.contains("Saída|Despesa", case=False, na=False)].copy()

    # Filtro período
    with st.expander("📅 Filtrar período"):
        dts = df_saida["Data_DT"].dropna()
        dmin = dts.min().date() if not dts.empty else date.today() - timedelta(days=365)
        dmax = dts.max().date() if not dts.empty else date.today()
        dp = st.date_input("Período", value=(dmin, dmax), min_value=dmin, max_value=dmax, key="dp")
        if isinstance(dp, tuple) and len(dp) == 2:
            m = df_saida["Data_DT"].notna()
            df_saida = df_saida[m & (df_saida["Data_DT"].dt.date >= dp[0]) & (df_saida["Data_DT"].dt.date <= dp[1])]

    # Escopo
    if escopo == "Todas as Obras":
        vgv_total = float(df_obras["Valor Total"].sum()) if not df_obras.empty else 0.0
        df_show = df_saida.copy()
        sold_mask = df_obras["Status"].astype(str).str.strip().str.lower() == "vendida" if not df_obras.empty and "Status" in df_obras.columns else pd.Series([False] * len(df_obras))
        sold_names = df_obras.loc[sold_mask, "Cliente"].astype(str).str.strip().tolist() if not df_obras.empty else []
        vgv_sold = float(df_obras.loc[sold_mask, "Valor Total"].sum()) if not df_obras.empty else 0.0
        df_sold = df_saida[df_saida["Obra Vinculada"].astype(str).isin(sold_names)].copy() if sold_names else pd.DataFrame(columns=df_saida.columns)
        custos_total = float(df_show["Valor"].sum()) if not df_show.empty else 0.0
        custos_sold = float(df_sold["Valor"].sum()) if not df_sold.empty else 0.0
        lucro_sold = float(vgv_sold - custos_sold)
        roi_sold = (lucro_sold / custos_sold * 100) if custos_sold > 0 else 0.0
        perc_total = (custos_total / vgv_total * 100) if vgv_total > 0 else 0.0

        k1, k2 = st.columns(2)
        k1.metric("VGV Total", fmt_moeda(vgv_total))
        k2.metric("Custos", fmt_moeda(custos_total), delta=f"{perc_total:.1f}%", delta_color="inverse")
        k3, k4 = st.columns(2)
        k3.metric("Lucro (Vendidas)", fmt_moeda(lucro_sold) if sold_names else "—")
        k4.metric("ROI (Vendidas)", f"{roi_sold:.1f}%" if sold_names else "—")
        vgv, custos, lucro = vgv_total, custos_total, vgv_total - custos_total
        roi = (lucro / custos * 100) if custos > 0 else 0.0
    else:
        row = df_obras[df_obras["Cliente"] == escopo].iloc[0]
        status_obra = str(row.get("Status", "")).strip()
        vgv = float(row["Valor Total"]) if "Valor Total" in row else 0.0
        df_show = df_saida[df_saida["Obra Vinculada"].astype(str) == str(escopo)].copy()
        custos = float(df_show["Valor"].sum()) if not df_show.empty else 0.0
        lucro = float(vgv - custos)
        roi = (lucro / custos * 100) if custos > 0 else 0.0
        perc = (custos / vgv * 100) if vgv > 0 else 0.0

        k1, k2 = st.columns(2)
        k1.metric("VGV", fmt_moeda(vgv))
        k2.metric("Custos", fmt_moeda(custos), delta=f"{perc:.1f}%", delta_color="inverse")
        k3, k4 = st.columns(2)
        if status_obra.lower() == "vendida":
            k3.metric("Lucro", fmt_moeda(lucro))
            k4.metric("ROI", f"{roi:.1f}%")
        else:
            k3.metric("Fase", status_obra or "—")
            k4.metric("Saldo", fmt_moeda(lucro))

    # Tabs do Dashboard
    tab_charts, tab_fornec, tab_obras_resumo = st.tabs(["📈 Gráficos", "🏢 Fornecedores", "📋 Resumo Obras"])

    with tab_charts:
        if not df_show.empty:
            # Evolução
            df_ev = df_show.sort_values("Data_DT").copy()
            df_ev["Acumulado"] = df_ev["Valor"].cumsum()
            fig = px.area(df_ev, x="Data_DT", y="Acumulado", color_discrete_sequence=[COR])
            fig.update_layout(plot_bgcolor="white", margin=dict(t=5,l=5,r=5,b=5), height=250, xaxis_title="", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

            # Categorias
            df_cat = df_show.groupby("Categoria", as_index=False)["Valor"].sum()
            fig2 = px.pie(df_cat, values="Valor", names="Categoria", hole=0.6, color_discrete_sequence=px.colors.qualitative.Bold)
            fig2.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center", font=dict(size=10)), margin=dict(t=5,l=5,r=5,b=5), height=250)
            fig2.update_traces(textinfo="percent", textfont_size=10)
            st.plotly_chart(fig2, use_container_width=True)

            # Mensal
            if pd.notna(df_show["Data_DT"]).any():
                dm = df_show.copy()
                dm["Mês"] = dm["Data_DT"].dt.to_period("M").astype(str)
                ma = dm.groupby("Mês", as_index=False)["Valor"].sum().sort_values("Mês")
                fig3 = px.bar(ma, x="Mês", y="Valor", color_discrete_sequence=[COR])
                fig3.update_layout(plot_bgcolor="white", margin=dict(t=5,l=5,r=5,b=5), height=220, xaxis_title="", yaxis_title="")
                st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("Sem dados no período selecionado.")

    with tab_fornec:
        if not df_show.empty and "Fornecedor" in df_show.columns:
            df_f = df_show[df_show["Fornecedor"].astype(str).str.strip() != ""]
            if not df_f.empty:
                df_top = df_f.groupby("Fornecedor", as_index=False)["Valor"].sum().sort_values("Valor", ascending=False).head(10)
                fig_f = px.bar(df_top, x="Valor", y="Fornecedor", orientation="h", color_discrete_sequence=[COR])
                fig_f.update_layout(plot_bgcolor="white", margin=dict(t=5,l=5,r=5,b=5), height=300, xaxis_title="", yaxis_title="", yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_f, use_container_width=True)
            else:
                st.info("Nenhum fornecedor registrado.")
        else:
            st.info("Sem dados.")

    with tab_obras_resumo:
        if escopo == "Todas as Obras" and not df_obras.empty:
            # Orçado vs Realizado
            orc = []
            for _, r in df_obras.iterrows():
                n = str(r["Cliente"]).strip()
                cp = float(r.get("Custo Previsto", 0))
                gr = float(df_saida[df_saida["Obra Vinculada"].astype(str) == n]["Valor"].sum())
                perc_e = (gr / cp * 100) if cp > 0 else 0
                if cp > 0:
                    saude = "🔴 Estourado" if perc_e > 100 else ("🟡 Atenção" if perc_e > 80 else "🟢 OK")
                else:
                    saude = "⚪ Sem orç."
                orc.append({"Obra": n, "Fase": str(r.get("Status", "")), "Saúde": saude, "Orçado": cp, "Realizado": gr, "Saldo": cp - gr, "Exec %": perc_e})

            df_r = pd.DataFrame(orc)

            # Chart
            fig_o = go.Figure()
            fig_o.add_trace(go.Bar(name="Orçado", x=df_r["Obra"], y=df_r["Orçado"], marker_color="#BBE1FA"))
            fig_o.add_trace(go.Bar(name="Realizado", x=df_r["Obra"], y=df_r["Realizado"], marker_color=COR))
            fig_o.update_layout(barmode="group", plot_bgcolor="white", margin=dict(t=5,l=5,r=5,b=5), height=250, xaxis_title="", yaxis_title="", legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"))
            st.plotly_chart(fig_o, use_container_width=True)

            # Table
            st.dataframe(df_r, use_container_width=True, hide_index=True, column_config={
                "Orçado": st.column_config.NumberColumn(format="R$ %.0f"),
                "Realizado": st.column_config.NumberColumn(format="R$ %.0f"),
                "Saldo": st.column_config.NumberColumn(format="R$ %.0f"),
                "Exec %": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f%%"),
            })
        else:
            st.info("Selecione 'Todas as Obras' para ver o resumo.")

    # Atividade recente
    if not df_fin.empty:
        st.markdown("---")
        st.caption("**Atividade recente**")
        for _, rec in df_fin.sort_values("Data_DT", ascending=False).head(5).iterrows():
            icon = "🔴" if "Saída" in str(rec.get("Tipo", "")) or "Despesa" in str(rec.get("Tipo", "")) else "🟢"
            st.caption(f"{icon} {str(rec.get('Data',''))[:10]} — {str(rec.get('Descrição',''))[:35]} | **{fmt_moeda(rec.get('Valor',0))}**")

    # Downloads
    st.markdown("---")
    if not df_show.empty:
        dmin_s = df_show["Data_DT"].min()
        dmax_s = df_show["Data_DT"].max()
        per_str = f"De {dmin_s.strftime('%d/%m/%Y') if pd.notna(dmin_s) else ''} até {dmax_s.strftime('%d/%m/%Y') if pd.notna(dmax_s) else ''}"
        df_cat_pdf = df_show.groupby("Categoria", as_index=False)["Valor"].sum()
        cols_p = ["Data", "Categoria", "Descrição", "Valor"]
        df_pdf = df_show.copy()
        for c in cols_p:
            if c not in df_pdf.columns: df_pdf[c] = ""
        df_pdf = df_pdf[cols_p].sort_values("Data", ascending=False)
        pdf_data = gerar_pdf_empresarial(escopo, per_str, vgv, custos, lucro, roi, df_cat_pdf, df_pdf)

        c_dl1, c_dl2 = st.columns(2)
        with c_dl1:
            st.download_button("⬇️ PDF", data=pdf_data, file_name=f"Relatorio_{date.today()}.pdf", mime="application/pdf", use_container_width=True)
        with c_dl2:
            csv_buf = io.StringIO()
            df_show.to_csv(csv_buf, index=False, sep=";", decimal=",")
            st.download_button("📊 CSV", data=csv_buf.getvalue(), file_name=f"Dados_{date.today()}.csv", mime="text/csv", use_container_width=True)


# ==============================================================================
# FINANCEIRO
# ==============================================================================
elif sel == "Financeiro":
    if st.session_state.get("sucesso_fin"):
        st.success("✅ Lançamento salvo!")
        reset_form_state("k_fin", DEFAULTS_FIN)
        st.session_state["sucesso_fin"] = False

    init_session_state_defaults("k_fin", DEFAULTS_FIN)

    tab_novo, tab_consulta = st.tabs(["➕ Novo Lançamento", "🔍 Consultar"])

    with tab_novo:
        if not require_role("editor"):
            st.caption("🔒 Sem permissão para criar lançamentos.")
        else:
            with st.form("ffin", clear_on_submit=False):
                c1, c2 = st.columns(2)
                with c1:
                    dt = st.date_input("Data", value=st.session_state.k_fin_data, key="k_fin_data")
                with c2:
                    vl = st.number_input("Valor R$", min_value=0.0, format="%.2f", step=100.0, value=st.session_state.k_fin_valor, key="k_fin_valor_input")

                ob = st.selectbox("Obra Vinculada", [""] + lista_obras, key="k_fin_obra")

                c3, c4 = st.columns(2)
                with c3:
                    tp = st.selectbox("Tipo", ["Saída (Despesa)", "Entrada"], key="k_fin_tipo")
                with c4:
                    ct = st.selectbox("Categoria", [""] + CATS, key="k_fin_cat")

                c5, c6 = st.columns(2)
                with c5:
                    pg = st.selectbox("Forma de Pagamento", [""] + PAGAMENTOS, key="k_fin_pag")
                with c6:
                    fn = st.text_input("Fornecedor", value=st.session_state.k_fin_forn, key="k_fin_forn")

                dc = st.text_input("Descrição", value=st.session_state.k_fin_desc, key="k_fin_desc")

                c7, c8 = st.columns(2)
                with c7:
                    num_parcelas = st.number_input("Parcelas", min_value=1, max_value=48, value=1, step=1, key="k_fin_parcelas")
                with c8:
                    if num_parcelas > 1 and vl > 0:
                        st.caption(f"💳 {num_parcelas}x de **{fmt_moeda(vl / num_parcelas)}**")

                submitted = st.form_submit_button("Salvar", use_container_width=True)

                if submitted:
                    st.session_state.k_fin_valor = vl
                    ok, erros = validate_lancamento(ob, ct, tp, dc, vl, fn, pg)
                    if erros:
                        for e in erros:
                            st.error(e)
                    else:
                        try:
                            conn = get_conn()
                            ws_fin = conn.worksheet("Financeiro")
                            if not st.session_state.get("schema_verified"):
                                ensure_financeiro_schema(ws_fin, FIN_COLS)
                                st.session_state["schema_verified"] = True
                            ids_exist = pd.to_numeric(df_fin["ID"], errors="coerce").fillna(0) if not df_fin.empty and "ID" in df_fin.columns else pd.Series()
                            n_parc = int(num_parcelas) if num_parcelas > 1 else 1
                            vp = round(float(vl) / n_parc, 2)
                            for p in range(n_parc):
                                new_id = generate_unique_id(ids_exist)
                                ids_exist = pd.concat([ids_exist, pd.Series([new_id])], ignore_index=True)
                                dt_p = dt
                                if p > 0:
                                    mo = dt.month + p
                                    yr = dt.year + (mo - 1) // 12
                                    mo = ((mo - 1) % 12) + 1
                                    try:
                                        dt_p = dt.replace(year=yr, month=mo)
                                    except ValueError:
                                        dt_p = dt.replace(year=yr, month=mo, day=28)
                                desc_p = f"{dc.strip()} ({p+1}/{n_parc})" if n_parc > 1 else dc.strip()
                                ws_fin.append_row([new_id, dt_p.strftime("%Y-%m-%d"), tp, ct.strip(), desc_p, vp, ob.strip(), fn.strip(), pg.strip()])
                            log_action("CRIAR_LANCAMENTO", f"{n_parc}x | {ob} | {ct} | {fmt_moeda(vl)}")
                            clear_data_cache()
                            st.session_state["sucesso_fin"] = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")

            # Duplicar
            if not df_fin.empty:
                with st.expander("📋 Duplicar lançamento existente"):
                    opts = df_fin.apply(lambda r: f"#{r['ID']} — {str(r.get('Data',''))[:10]} — {str(r.get('Descrição',''))[:30]} — {fmt_moeda(r.get('Valor',0))}", axis=1).tolist()
                    sel_d = st.selectbox("Selecione", opts, key="sel_dup")
                    if st.button("Copiar dados", use_container_width=True, key="btn_dup"):
                        idx = opts.index(sel_d)
                        rd = df_fin.iloc[idx]
                        st.session_state.k_fin_data = date.today()
                        st.session_state.k_fin_valor = float(safe_float(rd.get("Valor", 0)))
                        st.session_state.k_fin_desc = str(rd.get("Descrição", ""))
                        st.session_state.k_fin_forn = str(rd.get("Fornecedor", ""))
                        st.toast("📋 Dados copiados!", icon="📋")
                        st.rerun()

    with tab_consulta:
        if not df_fin.empty:
            df_view = df_fin.copy()

            with st.expander("🔍 Filtros"):
                fc1, fc2 = st.columns(2)
                with fc1:
                    fo = st.selectbox("Obra", ["Todas"] + lista_obras, key="fo")
                with fc2:
                    fcat = st.selectbox("Categoria", ["Todas"] + CATS, key="fcat")
                fc3, fc4 = st.columns(2)
                with fc3:
                    ftp = st.selectbox("Tipo", ["Todos", "Saída (Despesa)", "Entrada"], key="ftp")
                with fc4:
                    ftxt = st.text_input("Buscar", placeholder="Descrição ou fornecedor...", key="ftxt")
                dv = df_view["Data_DT"].dropna()
                if not dv.empty:
                    fd = st.date_input("Período", value=(dv.min().date(), dv.max().date()), min_value=dv.min().date(), max_value=dv.max().date(), key="fd")
                else:
                    fd = None

            if fo != "Todas":
                df_view = df_view[df_view["Obra Vinculada"].astype(str).str.strip() == fo]
            if fcat != "Todas":
                df_view = df_view[df_view["Categoria"].astype(str).str.strip() == fcat]
            if ftp != "Todos":
                df_view = df_view[df_view["Tipo"].astype(str).str.strip() == ftp]
            if fd and isinstance(fd, tuple) and len(fd) == 2:
                m = df_view["Data_DT"].notna()
                df_view = df_view[m & (df_view["Data_DT"].dt.date >= fd[0]) & (df_view["Data_DT"].dt.date <= fd[1])]
            if ftxt:
                bl = ftxt.lower()
                df_view = df_view[df_view["Descrição"].astype(str).str.lower().str.contains(bl, na=False) | df_view["Fornecedor"].astype(str).str.lower().str.contains(bl, na=False)]

            total_f = df_view["Valor"].sum()
            st.caption(f"**{len(df_view)}** lançamentos | Total: **{fmt_moeda(total_f)}**")

            cols_order = ["ID", "Data", "Tipo", "Forma Pagamento", "Obra Vinculada", "Categoria", "Fornecedor", "Descrição", "Valor"]
            for c in cols_order:
                if c not in df_view.columns: df_view[c] = ""
            df_te = df_view[cols_order].copy()
            df_te["ID"] = pd.to_numeric(df_te["ID"], errors="coerce").fillna(0).astype(int)
            df_te["Data"] = pd.to_datetime(df_te["Data"], errors="coerce").dt.date
            df_te["Valor"] = pd.to_numeric(df_te["Valor"], errors="coerce").fillna(0.0)

            can_del = require_role("admin")
            can_edit = require_role("editor")
            if can_del:
                df_te.insert(1, "Excluir", False)

            edited = st.data_editor(df_te, use_container_width=True, hide_index=True, num_rows="fixed", height=320, disabled=["ID"] if can_edit else list(cols_order), column_config={
                "ID": st.column_config.NumberColumn("#", width="small"),
                **({"Excluir": st.column_config.CheckboxColumn("🗑️", width="small")} if can_del else {}),
                "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Saída (Despesa)", "Entrada"]),
                "Forma Pagamento": st.column_config.SelectboxColumn("Pgto", options=[""] + PAGAMENTOS),
                "Obra Vinculada": st.column_config.SelectboxColumn("Obra", options=[""] + lista_obras),
                "Categoria": st.column_config.SelectboxColumn("Categ.", options=[""] + CATS),
                "Fornecedor": st.column_config.TextColumn("Forn."),
                "Descrição": st.column_config.TextColumn("Descrição"),
                "Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f", min_value=0),
            })

            # Resumo
            try:
                total_ed = float(pd.to_numeric(edited["Valor"], errors="coerce").fillna(0).sum())
                marcados = int(edited["Excluir"].astype(bool).sum()) if can_del and "Excluir" in edited.columns else 0
            except Exception:
                total_ed, marcados = 0.0, 0

            if marcados > 0:
                st.warning(f"🗑️ {marcados} marcado(s) para exclusão")

            # Comparação
            def _norm(df):
                d = df.copy()
                d["Data"] = d["Data"].astype(str)
                d["Valor"] = pd.to_numeric(d["Valor"], errors="coerce").fillna(0.0).astype(float)
                for c in ["Tipo", "Forma Pagamento", "Obra Vinculada", "Categoria", "Fornecedor", "Descrição"]:
                    if c not in d.columns: d[c] = ""
                    d[c] = d[c].astype(str).fillna("").str.strip()
                if "Excluir" in d.columns: d["Excluir"] = d["Excluir"].astype(bool)
                d["ID"] = pd.to_numeric(d["ID"], errors="coerce").fillna(0).astype(int)
                return d

            has_ch = not _norm(edited).equals(_norm(df_te))

            if has_ch and can_edit:
                st.markdown("---")
                pwd_c = st.text_input("Senha para confirmar", type="password", key="pwd_fin")
                if st.button("💾 Salvar alterações", type="primary", use_container_width=True):
                    if not verify_admin_password(pwd_c):
                        st.toast("Senha incorreta!", icon="⛔")
                    else:
                        try:
                            conn = get_conn()
                            ws_fin = conn.worksheet("Financeiro")
                            if not st.session_state.get("schema_verified"):
                                ensure_financeiro_schema(ws_fin, FIN_COLS)
                                st.session_state["schema_verified"] = True
                            headers_fin = ws_fin.row_values(1)
                            col_id = headers_fin.index("ID") + 1
                            rows_del = []
                            if can_del and "Excluir" in edited.columns:
                                for _, rr in edited[edited["Excluir"] == True].iterrows():
                                    cell = ws_fin.find(str(int(rr["ID"])), in_column=col_id)
                                    if cell: rows_del.append(cell.row)
                                    log_action("EXCLUIR_LANCAMENTO", f"ID={int(rr['ID'])}")
                            for r in sorted(rows_del, reverse=True):
                                ws_fin.delete_rows(r)
                            upd = 0
                            df_upd = edited[edited["Excluir"] == False].copy() if can_del and "Excluir" in edited.columns else edited.copy()
                            for _, rr in df_upd.iterrows():
                                cell = ws_fin.find(str(int(rr["ID"])), in_column=col_id)
                                if not cell: continue
                                ws_fin.update(f"{rowcol_to_a1(cell.row, 1)}:{rowcol_to_a1(cell.row, len(headers_fin))}", [build_row_values(rr, headers_fin)])
                                upd += 1
                            log_action("SALVAR_FINANCEIRO", f"{upd} atualizações, {len(rows_del)} exclusões")
                            clear_data_cache()
                            st.toast(f"✅ {upd} atualizados, {len(rows_del)} excluídos", icon="✅")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")

            # Downloads
            if not df_view.empty:
                st.markdown("---")
                c_d1, c_d2 = st.columns(2)
                with c_d1:
                    dmin_v = df_view["Data_DT"].min()
                    dmax_v = df_view["Data_DT"].max()
                    per = f"De {dmin_v.strftime('%d/%m/%Y') if pd.notna(dmin_v) else ''} até {dmax_v.strftime('%d/%m/%Y') if pd.notna(dmax_v) else ''}"
                    cols_p = ["Data", "Categoria", "Descrição", "Valor"]
                    df_pdf = (edited[edited["Excluir"] == False].copy() if can_del and "Excluir" in edited.columns else edited.copy())
                    for c in cols_p:
                        if c not in df_pdf.columns: df_pdf[c] = ""
                    df_pdf = df_pdf[cols_p].sort_values("Data", ascending=False)
                    pdf = gerar_pdf_empresarial(fo if fo != "Todas" else "Visão Geral", per, 0, float(df_pdf["Valor"].apply(safe_float).sum()), 0, 0, pd.DataFrame(), df_pdf)
                    st.download_button("⬇️ PDF", data=pdf, file_name=f"Extrato_{date.today()}.pdf", mime="application/pdf", use_container_width=True)
                with c_d2:
                    buf = io.StringIO()
                    df_view.to_csv(buf, index=False, sep=";", decimal=",")
                    st.download_button("📊 CSV", data=buf.getvalue(), file_name=f"Financeiro_{date.today()}.csv", mime="text/csv", use_container_width=True)
        else:
            st.info("Nenhum lançamento registrado.")


# ==============================================================================
# OBRAS
# ==============================================================================
elif sel == "Obras":
    if st.session_state.get("sucesso_obra"):
        st.success("✅ Obra salva!")
        reset_form_state("k_ob", DEFAULTS_OBRA)
        st.session_state["sucesso_obra"] = False

    init_session_state_defaults("k_ob", DEFAULTS_OBRA)

    tab_cadastro, tab_carteira, tab_timeline = st.tabs(["➕ Nova Obra", "📋 Carteira", "📊 Cronograma"])

    with tab_cadastro:
        if not require_role("editor"):
            st.caption("🔒 Sem permissão.")
        else:
            with st.form("f_obra", clear_on_submit=False):
                st.markdown("**Identificação**")
                nome_obra = st.text_input("Nome do Empreendimento", value=st.session_state.k_ob_nome, key="k_ob_nome", placeholder="Ex: Res. Vila Verde")
                endereco = st.text_input("Endereço", value=st.session_state.k_ob_end, key="k_ob_end", placeholder="Rua, Bairro...")

                st.markdown("**Características**")
                ca1, ca2 = st.columns(2)
                with ca1:
                    area_const = st.number_input("Área Construída m²", min_value=0.0, format="%.2f", value=st.session_state.k_ob_area_c, key="k_ob_area_c")
                with ca2:
                    area_terr = st.number_input("Área Terreno m²", min_value=0.0, format="%.2f", value=st.session_state.k_ob_area_t, key="k_ob_area_t")
                ca3, ca4 = st.columns(2)
                with ca3:
                    quartos = st.number_input("Quartos", min_value=0, step=1, value=st.session_state.k_ob_quartos, key="k_ob_quartos")
                with ca4:
                    status = st.selectbox("Fase", STATUS_OBRA, key="k_ob_status")

                st.markdown("**Financeiro e Prazos**")
                cb1, cb2 = st.columns(2)
                with cb1:
                    custo_previsto = st.number_input("Orçamento (Custo)", min_value=0.0, format="%.2f", step=1000.0, value=st.session_state.k_ob_custo, key="k_ob_custo_input")
                with cb2:
                    valor_venda = st.number_input("VGV (Venda)", min_value=0.0, format="%.2f", step=1000.0, value=st.session_state.k_ob_vgv, key="k_ob_vgv_input")
                cb3, cb4 = st.columns(2)
                with cb3:
                    data_inicio = st.date_input("Início", value=st.session_state.k_ob_data, key="k_ob_data")
                with cb4:
                    prazo_entrega = st.text_input("Prazo / Entrega", value=st.session_state.k_ob_prazo, key="k_ob_prazo", placeholder="Ex: 12/2026")

                if valor_venda > 0 and custo_previsto > 0:
                    margem = ((valor_venda - custo_previsto) / custo_previsto) * 100
                    lp = valor_venda - custo_previsto
                    if margem < 10:
                        st.warning(f"Margem baixa: {margem:.1f}% | Lucro: {fmt_moeda(lp)}")
                    elif margem < 20:
                        st.info(f"Margem: {margem:.1f}% | Lucro: {fmt_moeda(lp)}")
                    else:
                        st.success(f"Boa margem: {margem:.1f}% | Lucro: {fmt_moeda(lp)}")

                submitted = st.form_submit_button("Salvar Obra", use_container_width=True)
                if submitted:
                    st.session_state.k_ob_custo = custo_previsto
                    st.session_state.k_ob_vgv = valor_venda
                    ok, erros = validate_obra(nome_obra, endereco, prazo_entrega, valor_venda, custo_previsto, area_const, area_terr)
                    if erros:
                        for e in erros: st.error(e)
                    else:
                        try:
                            conn = get_conn()
                            ws = conn.worksheet("Obras")
                            novo_id = generate_unique_id(pd.to_numeric(df_obras["ID"], errors="coerce").fillna(0))
                            ws.append_row([novo_id, nome_obra.strip(), endereco.strip(), status, float(valor_venda), data_inicio.strftime("%Y-%m-%d"), prazo_entrega.strip(), float(area_const), float(area_terr), int(quartos), float(custo_previsto)])
                            log_action("CRIAR_OBRA", f"ID={novo_id} | {nome_obra.strip()}")
                            clear_data_cache()
                            st.session_state["sucesso_obra"] = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")

    with tab_carteira:
        if not df_obras.empty:
            cols_o = ["ID", "Cliente", "Status", "Prazo", "Valor Total", "Custo Previsto", "Area Construida", "Area Terreno", "Quartos"]
            valid_c = [c for c in cols_o if c in df_obras.columns]
            df_te = df_obras[valid_c].copy().reset_index(drop=True)
            for c in df_te.columns:
                if c in ["Valor Total", "Custo Previsto", "Area Construida", "Area Terreno", "Quartos", "ID"]:
                    df_te[c] = pd.to_numeric(df_te[c], errors='coerce').fillna(0)
                else:
                    df_te[c] = df_te[c].fillna("")

            can_edit_o = require_role("editor")
            edited = st.data_editor(df_te, use_container_width=True, hide_index=True, num_rows="fixed", height=280, disabled=["ID"] if can_edit_o else list(valid_c), column_config={
                "ID": st.column_config.NumberColumn("#", width="small"),
                "Cliente": st.column_config.TextColumn("Empreendimento"),
                "Status": st.column_config.SelectboxColumn("Fase", options=STATUS_OBRA),
                "Prazo": st.column_config.TextColumn("Entrega"),
                "Valor Total": st.column_config.NumberColumn("VGV", format="R$ %.0f", min_value=0),
                "Custo Previsto": st.column_config.NumberColumn("Custo", format="R$ %.0f", min_value=0),
                "Area Construida": st.column_config.NumberColumn("Área m²", format="%.0f"),
                "Area Terreno": st.column_config.NumberColumn("Terr. m²", format="%.0f"),
                "Quartos": st.column_config.NumberColumn("Qts", min_value=0, step=1, width="small"),
            })

            has_ch = not edited.equals(df_te)
            if has_ch and can_edit_o:
                st.markdown("---")
                pwd_o = st.text_input("Senha", type="password", key="pwd_obras")
                if st.button("💾 Salvar", type="primary", use_container_width=True, key="btn_obras"):
                    if not verify_admin_password(pwd_o):
                        st.toast("Senha incorreta!", icon="⛔")
                    else:
                        try:
                            conn = get_conn()
                            ws = conn.worksheet("Obras")
                            ws_fin = conn.worksheet("Financeiro")
                            with st.spinner("Salvando..."):
                                for _, row in edited.iterrows():
                                    cell = ws.find(str(row["ID"]), in_column=1)
                                    if cell:
                                        orig = df_obras[df_obras["ID"] == row["ID"]].iloc[0]
                                        old_n = str(orig["Cliente"]).strip()
                                        new_n = str(row["Cliente"]).strip()
                                        if old_n != new_n and old_n:
                                            hf = ws_fin.row_values(1)
                                            try:
                                                ci = hf.index("Obra Vinculada") + 1
                                            except ValueError:
                                                ci = 6
                                            cells_u = ws_fin.findall(old_n, in_column=ci)
                                            for c in cells_u: c.value = new_n
                                            if cells_u:
                                                ws_fin.update_cells(cells_u)
                                                log_action("RENOMEAR_OBRA", f"'{old_n}' -> '{new_n}'")
                                        vals = []
                                        for col in OBRAS_COLS:
                                            v = row[col] if col in row else orig[col]
                                            if isinstance(v, (pd.Timestamp, date, datetime)):
                                                v = v.strftime("%Y-%m-%d")
                                            elif pd.isna(v):
                                                v = ""
                                            vals.append(v)
                                        ws.update(f"A{cell.row}:K{cell.row}", [vals])
                                log_action("SALVAR_OBRAS", f"{len(edited)} obras")
                                clear_data_cache()
                                st.session_state["sucesso_obra"] = True
                                st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")
        else:
            st.info("Nenhuma obra cadastrada.")

    with tab_timeline:
        if not df_obras.empty:
            for _, ob in df_obras.iterrows():
                nome = str(ob["Cliente"]).strip()
                stat = str(ob.get("Status", "Projeto")).strip()
                prazo = str(ob.get("Prazo", "")).strip()
                idx = STATUS_OBRA.index(stat) if stat in STATUS_OBRA else 0
                prog = int((idx / (len(STATUS_OBRA) - 1)) * 100)

                icon = "✅" if stat.lower() in ["concluída", "vendida"] else ("🔨" if prog >= 50 else "📐")
                st.markdown(f"**{nome}** — {icon} {stat} | Prazo: {prazo or '—'}")
                st.progress(prog / 100)
                st.caption(f"Etapas: {' → '.join(STATUS_OBRA[:idx+1])}")
                st.markdown("")
        else:
            st.info("Nenhuma obra cadastrada.")


# ==============================================================================
# AUDITORIA
# ==============================================================================
elif sel == "Auditoria":
    st.subheader("🛡️ Log de Auditoria")
    try:
        records = get_conn().worksheet("Auditoria").get_all_records()
        if not records:
            st.info("Nenhum registro.")
        else:
            df_a = pd.DataFrame(records).tail(200).iloc[::-1].reset_index(drop=True)
            c1, c2 = st.columns(2)
            with c1:
                fa = st.selectbox("Ação", ["Todas"] + sorted(df_a["Ação"].unique().tolist()))
            with c2:
                fu = st.selectbox("Usuário", ["Todos"] + sorted(df_a["Usuário"].unique().tolist()))
            df_d = df_a.copy()
            if fa != "Todas": df_d = df_d[df_d["Ação"] == fa]
            if fu != "Todos": df_d = df_d[df_d["Usuário"] == fu]
            st.dataframe(df_d, use_container_width=True, hide_index=True)
            st.caption(f"{len(df_d)} de {len(df_a)} registros")
    except Exception as e:
        st.error(f"Erro: {e}")
