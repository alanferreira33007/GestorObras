import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import date, datetime, timedelta
from streamlit_option_menu import option_menu
import io
import hmac
import logging
from typing import Union, Optional, List, Dict, Any, Tuple
from gspread.utils import rowcol_to_a1

# ==============================================================================
# CONFIGURAÇÃO DE LOGGING
# ==============================================================================
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTES CENTRALIZADAS
# ==============================================================================
COR_PRIMARIA = "#2D6A4F"
COR_PRIMARIA_ESCURA = "#1B4332"
COR_SUCESSO = "#40916C"
COR_FUNDO = "#F8F9FA"
COR_FUNDO_ESCURO = "#1A1C1E"
COR_CINZA_CLARO = "#e9ecef"
COR_CINZA_MEDIO = "#adb5bd"

APP_VERSION = "v3.0.0"

STATUS_OBRA = ["Projeto", "Fundação", "Alvenaria", "Acabamento", "Concluída", "Vendida"]

OBRAS_COLS = [
    "ID", "Cliente", "Endereço", "Status", "Valor Total",
    "Data Início", "Prazo", "Area Construida", "Area Terreno",
    "Quartos", "Custo Previsto"
]

FIN_COLS = ["ID", "Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada", "Fornecedor", "Forma Pagamento"]

AUDIT_COLS = ["Timestamp", "Usuário", "Ação", "Detalhes"]

CATS = [
    "Material",
    "Mão de Obra",
    "Serviços",
    "Administrativo",
    "Impostos",
    "Emolumentos Cartorários",
    "Outros"
]

PAGAMENTOS = [
    "PIX",
    "Cartão de Crédito",
    "Cartão de Débito",
    "Dinheiro",
    "Transferência",
    "Boleto",
    "Cheque",
    "Outro"
]

DEFAULTS_FIN = {
    "data": date.today(),
    "tipo": "Saída (Despesa)",
    "cat": "",
    "obra": "",
    "pag": "",
    "valor": 0.0,
    "desc": "",
    "forn": ""
}

DEFAULTS_OBRA = {
    "nome": "",
    "end": "",
    "area_c": 0.0,
    "area_t": 0.0,
    "quartos": 0,
    "status": "Projeto",
    "custo": 0.0,
    "vgv": 0.0,
    "prazo": "",
    "data": date.today()
}

# ==============================================================================
# 1. CONFIGURAÇÃO VISUAL (UI) - Com suporte a Dark Mode
# ==============================================================================
st.set_page_config(
    page_title="GESTOR PRO | Incorporadora",
    layout="wide",
    page_icon="🏗️",
    initial_sidebar_state="collapsed"
)

st.markdown(f"""
<style>
    /* ---- GERAL ---- */
    div.stButton > button {{
        background-color: {COR_PRIMARIA};
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1rem;
        font-weight: 600;
        min-height: 44px;
    }}
    div.stButton > button:hover {{
        background-color: {COR_PRIMARIA_ESCURA};
    }}
    [data-testid="stMetric"] {{
        background: {COR_FUNDO};
        border: 1px solid {COR_CINZA_CLARO};
        border-radius: 8px;
        padding: 10px 14px;
    }}
    [data-testid="stDownloadButton"] > button {{
        background-color: {COR_PRIMARIA} !important;
        color: white !important;
        border-radius: 8px;
        min-height: 44px;
        font-weight: 600;
    }}
    [data-testid="stFormSubmitButton"] > button {{
        min-height: 48px;
    }}
    /* Previne zoom no iOS */
    input, select, textarea {{
        font-size: 16px !important;
    }}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. FUNÇÕES HELPERS
# ==============================================================================

def check_password(input_pwd: str, stored_pwd: str) -> bool:
    """Compara senhas de forma segura contra timing attacks."""
    return hmac.compare_digest(input_pwd, stored_pwd)


def get_users_config() -> dict:
    """Carrega config de usuários. Compatível com senha legada."""
    if "users" in st.secrets:
        return dict(st.secrets["users"])
    return {
        "admin": {
            "password": st.secrets["password"],
            "role": "admin",
            "name": "Administrador",
        }
    }


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Autentica usuário. Retorna dados ou None."""
    users = get_users_config()

    if username == "":
        for uid, udata in users.items():
            pwd = udata["password"] if isinstance(udata, dict) else str(udata)
            if check_password(password, pwd):
                return {
                    "username": uid,
                    "role": udata.get("role", "admin") if isinstance(udata, dict) else "admin",
                    "name": udata.get("name", uid) if isinstance(udata, dict) else uid,
                }
        return None

    if username not in users:
        return None

    udata = users[username]
    stored_pwd = udata["password"] if isinstance(udata, dict) else str(udata)

    if check_password(password, stored_pwd):
        return {
            "username": username,
            "role": udata.get("role", "admin") if isinstance(udata, dict) else "admin",
            "name": udata.get("name", username) if isinstance(udata, dict) else username,
        }
    return None


def require_role(min_role: str) -> bool:
    """Verifica permissão mínima. Hierarquia: admin > editor > viewer."""
    hierarchy = {"viewer": 0, "editor": 1, "admin": 2}
    user_role = st.session_state.get("user_role", "admin")
    return hierarchy.get(user_role, 0) >= hierarchy.get(min_role, 0)


def get_current_user() -> str:
    return st.session_state.get("user_name", "Administrador")


def verify_admin_password(pwd: str) -> bool:
    """Verifica senha de confirmação."""
    users = get_users_config()
    for uid, udata in users.items():
        stored = udata["password"] if isinstance(udata, dict) else str(udata)
        if check_password(pwd, stored):
            return True
    return False


def reset_form_state(prefix: str, defaults: Dict[str, Any]) -> None:
    """Reseta o estado do formulário para valores padrão."""
    for key, value in defaults.items():
        st.session_state[f"{prefix}_{key}"] = value


def fmt_moeda(valor: Union[float, int, str, None], simbolo: str = "R$") -> str:
    """Formata valor numérico para moeda brasileira (R$)."""
    if pd.isna(valor) or valor == "" or valor is None:
        return f"{simbolo} 0,00"
    try:
        val = float(valor)
        negativo = val < 0
        val = abs(val)
        parte_inteira = int(val)
        parte_decimal = int(round((val - parte_inteira) * 100))
        str_inteira = f"{parte_inteira:,}".replace(",", ".")
        return f"{simbolo} {'-' if negativo else ''}{str_inteira},{parte_decimal:02d}"
    except (ValueError, TypeError, AttributeError):
        return f"{simbolo} {valor}"


def safe_float(x: Union[int, float, str, None]) -> float:
    """Converte valor para float de forma segura."""
    if isinstance(x, (int, float)):
        return float(x)
    if x is None:
        return 0.0
    s = str(x).strip().replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError, AttributeError):
        return 0.0


def normalize_string(value: Union[str, None]) -> str:
    """Normaliza string removendo espaços extras."""
    if value is None:
        return ""
    return str(value).strip()


def ensure_financeiro_id(ws_fin) -> None:
    """Garante que a aba Financeiro tenha a coluna ID."""
    headers = ws_fin.row_values(1)
    if "ID" in headers:
        return
    n_rows = len(ws_fin.get_all_values())
    ws_fin.insert_cols([["ID"]], 1)
    if n_rows > 1:
        ids = [[i] for i in range(1, n_rows)]
        ws_fin.update(f"A2:A{n_rows}", ids)


def ensure_financeiro_schema(ws_fin, required_cols: List[str]) -> None:
    """Migração segura: garante ID e colunas novas sem quebrar base antiga."""
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
            ws_fin.update(f"{start}:{end}", [[""]]*(n_rows-1))


def ensure_audit_sheet(db) -> None:
    """Cria aba de Auditoria se não existir."""
    try:
        db.worksheet("Auditoria")
    except gspread.exceptions.WorksheetNotFound:
        ws = db.add_worksheet(title="Auditoria", rows=1000, cols=len(AUDIT_COLS))
        ws.update("A1:D1", [AUDIT_COLS])


def init_session_state_defaults(prefix: str, defaults: Dict[str, Any]) -> None:
    """Inicializa valores padrão no session_state se não existirem."""
    for key, value in defaults.items():
        state_key = f"{prefix}_{key}"
        if state_key not in st.session_state:
            st.session_state[state_key] = value


def clear_data_cache() -> None:
    """Limpa cache de dados do session_state e do Streamlit."""
    for key in ["data_obras", "data_fin"]:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state["last_sync"] = datetime.now()
    st.cache_data.clear()


def generate_unique_id(existing_ids: pd.Series) -> int:
    """Gera um ID único baseado em timestamp para evitar colisões."""
    timestamp_id = int(datetime.now().timestamp() * 1000) % 1_000_000_000
    if not existing_ids.empty:
        existing_set = set(existing_ids.dropna().astype(int).tolist())
        while timestamp_id in existing_set:
            timestamp_id += 1
    return timestamp_id


def validate_lancamento(
    obra: str, categoria: str, tipo: str, descricao: str,
    valor: float, fornecedor: str = "", forma_pagamento: str = ""
) -> Tuple[bool, List[str]]:
    """Valida dados de um lançamento financeiro."""
    erros = []
    if not normalize_string(obra):
        erros.append("Selecione a Obra Vinculada.")
    if not normalize_string(categoria):
        erros.append("Selecione a Categoria.")
    if not normalize_string(tipo):
        erros.append("Selecione o Tipo.")
    if not normalize_string(descricao):
        erros.append("A Descrição é obrigatória.")
    if valor <= 0:
        erros.append("O Valor deve ser maior que zero.")
    if normalize_string(categoria) == "Material" and not normalize_string(fornecedor):
        erros.append("Para categoria 'Material', o campo Fornecedor é obrigatório.")
    if not normalize_string(forma_pagamento):
        erros.append("Selecione a Forma de Pagamento.")
    return (len(erros) == 0, erros)


def validate_obra(
    nome: str, endereco: str, prazo: str,
    vgv: float, custo: float, area_const: float, area_terr: float
) -> Tuple[bool, List[str]]:
    """Valida dados de uma obra."""
    erros = []
    nome_norm = normalize_string(nome)
    if not nome_norm:
        erros.append("O 'Nome do Empreendimento' é obrigatório.")
    elif len(nome_norm) < 3:
        erros.append("O 'Nome do Empreendimento' deve ter pelo menos 3 caracteres.")
    if not normalize_string(endereco):
        erros.append("O 'Endereço' é obrigatório.")
    if not normalize_string(prazo):
        erros.append("O 'Prazo' é obrigatório.")
    if vgv <= 0:
        erros.append("O 'Valor de Venda (VGV)' deve ser maior que zero.")
    if custo <= 0:
        erros.append("O 'Orçamento Previsto' deve ser maior que zero.")
    if area_const <= 0 and area_terr <= 0:
        erros.append("Preencha ao menos a Área Construída ou do Terreno.")
    return (len(erros) == 0, erros)


def build_row_values(row, headers: list) -> list:
    """Constrói lista de valores para atualizar uma linha no Google Sheets."""
    values = []
    for h in headers:
        v = row.get(h, "")
        if h == "ID":
            values.append(int(row["ID"]))
        elif h == "Data":
            if isinstance(v, (date, datetime)):
                values.append(v.strftime("%Y-%m-%d"))
            else:
                values.append(str(v)[:10])
        elif h == "Valor":
            values.append(float(safe_float(v)))
        else:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                values.append("")
            else:
                values.append(str(v).strip())
    return values


def log_action(action: str, details: str = "") -> None:
    """Registra ação no log de auditoria (Google Sheets)."""
    try:
        conn = get_conn()
        try:
            ws = conn.worksheet("Auditoria")
        except Exception:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user = get_current_user()
        if len(details) > 500:
            details = details[:497] + "..."
        ws.append_row([timestamp, user, action, details])
    except Exception as e:
        logger.warning(f"Falha ao registrar auditoria: {e}")


# ==============================================================================
# 3. MOTOR PDF (ENTERPRISE V5)
# ==============================================================================
def gerar_pdf_empresarial(
    escopo: str, periodo: str, vgv: float, custos: float,
    lucro: float, roi: float,
    df_cat: Optional[pd.DataFrame], df_lanc: Optional[pd.DataFrame]
) -> bytes:
    """Gera relatório PDF empresarial."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm

    class EnterpriseCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []

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

        def _draw_footer(self, page_count):
            width, height = A4
            self.setStrokeColor(colors.lightgrey)
            self.setLineWidth(0.5)
            self.line(30, 50, width-30, 50)
            self.setFillColor(colors.grey)
            self.setFont("Helvetica", 8)
            self.drawString(30, 35, "GESTOR PRO - Sistema Integrado de Gestão de Obras")
            self.drawString(30, 25, "Relatório contábil individualizado.")
            data_hora = datetime.now().strftime("%d/%m/%Y às %H:%M")
            self.drawRightString(width-30, 35, f"Emitido em: {data_hora}")
            self.drawRightString(width-30, 25, f"Página {self.getPageNumber()} de {page_count}")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=60
    )
    story = []

    styles = getSampleStyleSheet()
    style_header_title = ParagraphStyle('HeadTitle', parent=styles['Normal'], fontSize=14, leading=16, textColor=colors.white, fontName='Helvetica-Bold')
    style_header_sub = ParagraphStyle('HeadSub', parent=styles['Normal'], fontSize=9, leading=11, textColor=colors.whitesmoke)
    style_h2 = ParagraphStyle('SecTitle', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor(COR_PRIMARIA_ESCURA), spaceBefore=15, spaceAfter=8, fontName='Helvetica-Bold')

    if "Visão Geral" in str(escopo):
        titulo_principal = "RELATÓRIO DE PORTFÓLIO (CONSOLIDADO)"
    else:
        titulo_principal = f"RELATÓRIO INDIVIDUAL: {str(escopo).upper()}"

    header_content = [[Paragraph(titulo_principal, style_header_title), Paragraph(f"PERÍODO:<br/>{periodo}", style_header_sub)]]
    t_header = Table(header_content, colWidths=[12*cm, 5*cm])
    t_header.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(COR_PRIMARIA)),
        ('PADDING', (0,0), (-1,-1), 15),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 15))

    story.append(Paragraph("RESUMO FINANCEIRO", style_h2))
    perc_gasto = (custos/vgv*100) if vgv > 0 else 0
    resumo_data = [
        ["ORÇAMENTO (VGV)", "GASTO TOTAL", "SALDO / LUCRO", "ROI", "CONSUMO"],
        [fmt_moeda(vgv), fmt_moeda(custos), fmt_moeda(lucro), f"{roi:.1f}%", f"{perc_gasto:.1f}%"]
    ]
    t_resumo = Table(resumo_data, colWidths=[3.7*cm]*5)
    t_resumo.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 7),
        ('TEXTCOLOR', (0,0), (-1,0), colors.grey),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTSIZE', (0,1), (-1,1), 10),
        ('TEXTCOLOR', (0,1), (-1,1), colors.black),
        ('BACKGROUND', (0,0), (-1,1), colors.HexColor(COR_FUNDO)),
        ('BOX', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_resumo)
    story.append(Spacer(1, 15))

    if df_cat is not None and not df_cat.empty:
        story.append(Paragraph("DISTRIBUIÇÃO POR CATEGORIA", style_h2))
        df_c = df_cat.copy()
        df_c["Valor"] = df_c["Valor"].apply(fmt_moeda)
        if custos > 0:
            df_c["%"] = (df_cat["Valor"] / custos * 100).apply(lambda x: f"{x:.1f}%")
        else:
            df_c["%"] = "0,0%"
        cat_data = [["CATEGORIA", "VALOR", "%"]] + df_c[["Categoria", "Valor", "%"]].values.tolist()
        t_cat = Table(cat_data, colWidths=[10*cm, 4*cm, 3*cm], hAlign='LEFT')
        t_cat.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 8),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor(COR_SUCESSO)),
            ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.whitesmoke]),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(t_cat)
        story.append(Spacer(1, 15))

    story.append(Paragraph("EXTRATO DE LANÇAMENTOS", style_h2))

    if df_lanc is not None and not df_lanc.empty:
        df_l = df_lanc.copy()
        for c in ["Data", "Categoria", "Descrição", "Valor"]:
            if c not in df_l.columns:
                df_l[c] = ""
        df_l["Valor"] = df_l["Valor"].apply(fmt_moeda)
        cols_sel = ["Data", "Categoria", "Descrição", "Valor"]
        data_lanc = [cols_sel] + df_l[cols_sel].values.tolist()
        data_lanc.append(["", "", "SUBTOTAL (Página):", fmt_moeda(custos)])

        t_lanc = Table(data_lanc, colWidths=[2.5*cm, 3.5*cm, 8*cm, 3*cm])
        estilo_tabela = [
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 8),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor(COR_PRIMARIA)),
            ('FONTSIZE', (0,1), (-1,-1), 8),
            ('ALIGN', (-1,0), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-2), 0.25, colors.lightgrey),
            ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.whitesmoke]),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]
        estilo_total_linha = [
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor(COR_CINZA_CLARO)),
            ('TEXTCOLOR', (2,-1), (2,-1), colors.black),
            ('TEXTCOLOR', (-1,-1), (-1,-1), colors.black),
            ('ALIGN', (2,-1), (2,-1), 'RIGHT'),
            ('LINEABOVE', (0,-1), (-1,-1), 1, colors.black),
        ]
        t_lanc.setStyle(TableStyle(estilo_tabela + estilo_total_linha))
        story.append(t_lanc)
    else:
        story.append(Paragraph("Nenhum lançamento no período.", styles['Normal']))

    story.append(Spacer(1, 25))

    msg_total = "TOTAL ACUMULADO GASTO (ATÉ EMISSÃO)"
    total_lbl = Paragraph(
        f"<b>{msg_total}</b>",
        ParagraphStyle('TLabel', parent=styles['Normal'], textColor=colors.black, fontSize=10, alignment=TA_RIGHT)
    )
    total_val = Paragraph(
        f"<b>{fmt_moeda(custos)}</b>",
        ParagraphStyle('TVal', parent=styles['Normal'], textColor=colors.white, fontSize=14, alignment=TA_RIGHT)
    )

    data_total = [[total_lbl, total_val]]
    t_total = Table(data_total, colWidths=[12*cm, 5*cm])
    t_total.setStyle(TableStyle([
        ('BACKGROUND', (1,0), (1,0), colors.HexColor(COR_FUNDO_ESCURO)),
        ('BACKGROUND', (0,0), (0,0), colors.white),
        ('LINEBELOW', (0,0), (1,0), 2, colors.HexColor(COR_FUNDO_ESCURO)),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
    ]))
    story.append(KeepTogether([t_total]))

    story.append(Spacer(1, 40))

    sig_data = [
        ["_______________________________________", "_______________________________________"],
        ["GESTOR RESPONSÁVEL", "DIRETORIA FINANCEIRA"],
        [f"Data: {date.today().strftime('%d/%m/%Y')}", "Data: ____/____/________"]
    ]
    t_sig = Table(sig_data, colWidths=[8.5*cm, 8.5*cm])
    t_sig.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.grey),
    ]))
    story.append(t_sig)

    doc.build(story, canvasmaker=EnterpriseCanvas)
    return buffer.getvalue()


# ==============================================================================
# 4. DADOS E CONEXÃO (Migrado para google-auth)
# ==============================================================================
@st.cache_resource
def get_conn():
    """Obtém conexão com Google Sheets usando google-auth (moderna)."""
    creds_dict = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
    scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    db = gspread.authorize(credentials).open("GestorObras_DB")

    if "schema_verified" not in st.session_state:
        try:
            ws_fin = db.worksheet("Financeiro")
            ensure_financeiro_schema(ws_fin, FIN_COLS)
            ensure_audit_sheet(db)
            st.session_state["schema_verified"] = True
        except gspread.exceptions.GSpreadException as e:
            logger.warning(f"Falha ao garantir schema na conexão: {e}")
        except Exception as e:
            logger.warning(f"Erro inesperado ao garantir schema: {e}")

    return db


@st.cache_data(ttl=120)
def fetch_data_from_google() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Busca dados do Google Sheets com cache e limpeza de strings."""
    try:
        db = get_conn()

        ws_o = db.worksheet("Obras")
        raw_o = ws_o.get_all_records()
        df_o = pd.DataFrame(raw_o)

        if df_o.empty:
            df_o = pd.DataFrame(columns=OBRAS_COLS)
        else:
            for c in OBRAS_COLS:
                if c not in df_o.columns:
                    df_o[c] = None

        ws_f = db.worksheet("Financeiro")

        if not st.session_state.get("schema_verified"):
            try:
                ensure_financeiro_schema(ws_f, FIN_COLS)
                st.session_state["schema_verified"] = True
            except gspread.exceptions.GSpreadException as e:
                logger.warning(f"Falha ao garantir schema: {e}")

        raw_f = ws_f.get_all_records()
        df_f = pd.DataFrame(raw_f)

        if df_f.empty:
            df_f = pd.DataFrame(columns=FIN_COLS)
        else:
            for c in FIN_COLS:
                if c not in df_f.columns:
                    df_f[c] = None

        df_o["Valor Total"] = df_o["Valor Total"].apply(safe_float)
        if "Custo Previsto" in df_o.columns:
            df_o["Custo Previsto"] = df_o["Custo Previsto"].apply(safe_float)

        if "ID" in df_f.columns:
            df_f["ID"] = pd.to_numeric(df_f["ID"], errors="coerce").fillna(0).astype(int)

        df_f["Valor"] = df_f["Valor"].apply(safe_float)
        df_f["Data_DT"] = pd.to_datetime(df_f["Data"], errors="coerce")

        str_cols_fin = ["Obra Vinculada", "Categoria", "Fornecedor", "Forma Pagamento"]
        for col in str_cols_fin:
            if col in df_f.columns:
                df_f[col] = df_f[col].astype(str).str.strip()

        if "Cliente" in df_o.columns:
            df_o["Cliente"] = df_o["Cliente"].astype(str).str.strip()

        return df_o, df_f

    except gspread.exceptions.GSpreadException as e:
        st.error(f"Erro de conexão com Google Sheets: {e}")
        logger.error(f"GSpread error: {e}")
        return pd.DataFrame(), pd.DataFrame()
    except Exception as e:
        st.error(f"Erro DB: {e}")
        logger.error(f"Database error: {e}")
        return pd.DataFrame(), pd.DataFrame()


# ==============================================================================
# 5. APP PRINCIPAL - Autenticação multi-usuário
# ==============================================================================
if "auth" not in st.session_state:
    st.session_state.auth = False


def logout() -> None:
    """Logout e limpeza de sessão."""
    keys_to_clear = ["auth", "user_id", "user_name", "user_role", "schema_verified"]
    for k in keys_to_clear:
        if k in st.session_state:
            del st.session_state[k]
    st.session_state.auth = False
    clear_data_cache()


if not st.session_state.auth:
    st.markdown(f"""
        <div style='text-align:center; padding: 2rem 0 1rem 0;'>
            <h1 style='color:{COR_PRIMARIA}; font-size: 2rem; margin-bottom: 0.2rem;'>GESTOR PRO</h1>
            <p style='color: gray; font-size: 0.9rem;'>Incorporação & Obras</p>
        </div>
    """, unsafe_allow_html=True)

    # Container centralizado que funciona bem no mobile
    login_left, login_center, login_right = st.columns([1, 2, 1])
    with login_center:
        if st.session_state.get("login_error"):
            st.error(st.session_state["login_error"])

        has_multi_users = "users" in st.secrets
        if has_multi_users:
            login_user = st.text_input("Usuário", key="login_username", placeholder="seu.usuario")
        else:
            login_user = ""

        login_pwd = st.text_input("Senha", type="password", key="login_password")

        st.write("")
        if st.button("ENTRAR", use_container_width=True):
            user = authenticate_user(login_user, login_pwd)
            if user:
                st.session_state.auth = True
                st.session_state.user_id = user["username"]
                st.session_state.user_name = user["name"]
                st.session_state.user_role = user["role"]
                if "login_error" in st.session_state:
                    del st.session_state["login_error"]
                try:
                    df_o, df_f = fetch_data_from_google()
                    st.session_state["data_obras"] = df_o
                    st.session_state["data_fin"] = df_f
                except Exception as e:
                    logger.error(f"Erro ao sincronizar login: {e}")
                st.rerun()
            else:
                st.session_state.login_error = "Credenciais incorretas"
                st.rerun()

        st.markdown(f"""
            <p style='text-align:center; color:{COR_CINZA_MEDIO}; font-size: 0.75rem; margin-top: 2rem;'>
                {APP_VERSION} © 2026 Gestor Pro
            </p>
        """, unsafe_allow_html=True)
    st.stop()


# ==============================================================================
# 6. BARRA LATERAL
# ==============================================================================
with st.sidebar:
    st.markdown(f"""
        <div style='text-align: left; margin-bottom: 20px;'>
            <h1 style='color: {COR_PRIMARIA}; font-size: 24px; margin-bottom: 0px;'>GESTOR PRO</h1>
            <p style='color: gray; font-size: 12px; margin-top: 0px;'>Incorporação & Obras</p>
        </div>
    """, unsafe_allow_html=True)

    menu_options = ["Dashboard", "Financeiro", "Obras"]
    menu_icons = ["pie-chart-fill", "wallet-fill", "building-fill"]

    if require_role("admin"):
        menu_options.append("Auditoria")
        menu_icons.append("shield-check")

    sel = option_menu(
        menu_title=None,
        options=menu_options,
        icons=menu_icons,
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": COR_PRIMARIA, "font-size": "16px"},
            "nav-link": {"font-size": "14px", "text-align": "left", "margin": "5px", "--hover-color": "#eee"},
            "nav-link-selected": {"background-color": COR_PRIMARIA, "color": "white"},
        }
    )

    st.write("")
    st.markdown("---")

    col_p1, col_p2 = st.columns([1, 4])
    with col_p1:
        st.markdown("<h2 style='text-align: center; margin: 0;'>👤</h2>", unsafe_allow_html=True)
    with col_p2:
        st.caption("Logado como:")
        user_name = get_current_user()
        user_role = st.session_state.get("user_role", "admin")
        role_labels = {"admin": "Administrador", "editor": "Editor", "viewer": "Visualizador"}
        st.markdown(f"**{user_name}**")
        st.caption(role_labels.get(user_role, user_role))

    # Indicador de conexão e sincronização
    try:
        get_conn()
        last_sync = st.session_state.get("last_sync")
        if last_sync:
            delta = datetime.now() - last_sync
            if delta.seconds < 60:
                sync_txt = "agora"
            elif delta.seconds < 3600:
                sync_txt = f"há {delta.seconds // 60} min"
            else:
                sync_txt = last_sync.strftime("%H:%M")
            st.caption(f"🟢 Sincronizado {sync_txt}")
        else:
            st.caption("🟢 Conectado")
    except Exception:
        st.caption("🔴 Sem conexão")

    st.write("")
    st.button("Sair do Sistema", on_click=logout, use_container_width=True)

    st.markdown(f"""
        <div style='margin-top: 30px; text-align: center;'>
            <p style='color: {COR_CINZA_MEDIO}; font-size: 10px;'>{APP_VERSION} © 2026 Gestor Pro</p>
        </div>
    """, unsafe_allow_html=True)


# ==============================================================================
# 7. GESTÃO DE DADOS (CACHE)
# ==============================================================================
if "data_obras" not in st.session_state or "data_fin" not in st.session_state:
    with st.spinner("Sincronizando base de dados..."):
        try:
            df_obras, df_fin = fetch_data_from_google()
            st.session_state["data_obras"] = df_obras
            st.session_state["data_fin"] = df_fin
            st.session_state["last_sync"] = datetime.now()
        except Exception as e:
            logger.error(f"Falha na conexão: {e}")
            st.error(f"Falha na conexão: {e}")
            st.stop()
else:
    df_obras = st.session_state["data_obras"]
    df_fin = st.session_state["data_fin"]

lista_obras = sorted(df_obras["Cliente"].unique().tolist()) if not df_obras.empty else []


# ==============================================================================
# 8. CONTEÚDO DAS PÁGINAS
# ==============================================================================

# --- DASHBOARD ---
if sel == "Dashboard":
    import plotly.express as px
    import plotly.graph_objects as go

    st.title("Visão Geral")

    c_sel, c_btn = st.columns([3, 1])
    with c_sel:
        if lista_obras:
            opcoes = ["Visão Geral (Todas as Obras)"] + lista_obras
            escopo = st.selectbox("Escopo", opcoes, label_visibility="collapsed")
        else:
            st.warning("Cadastre uma obra.")
            st.stop()
    with c_btn:
        if st.button("🔄 Atualizar", use_container_width=True):
            clear_data_cache()
            st.rerun()

    # -------------------------
    # Alertas de Prazo (NOVO)
    # -------------------------
    if not df_obras.empty and "Prazo" in df_obras.columns:
        hoje = date.today()
        for _, ob_row in df_obras.iterrows():
            status_ob = str(ob_row.get("Status", "")).strip().lower()
            if status_ob in ["concluída", "vendida"]:
                continue
            prazo_str = str(ob_row.get("Prazo", "")).strip()
            nome_ob = str(ob_row["Cliente"]).strip()
            # Tenta parsear prazo como data (formatos comuns)
            prazo_date = None
            for fmt in ["%m/%Y", "%b/%Y", "%Y-%m-%d", "%d/%m/%Y"]:
                try:
                    prazo_date = datetime.strptime(prazo_str, fmt).date()
                    break
                except (ValueError, TypeError):
                    continue
            if prazo_date:
                dias_restantes = (prazo_date - hoje).days
                if dias_restantes < 0:
                    st.error(f"🚨 **{nome_ob}** — Prazo vencido há {abs(dias_restantes)} dias! (Prazo: {prazo_str})")
                elif dias_restantes <= 30:
                    st.warning(f"⏰ **{nome_ob}** — Prazo em {dias_restantes} dias (Prazo: {prazo_str})")
                elif dias_restantes <= 60:
                    st.info(f"📅 **{nome_ob}** — Prazo em {dias_restantes} dias (Prazo: {prazo_str})")

    # -------------------------
    # Filtro de Período (NOVO)
    # -------------------------
    # Base: só saídas/despesas
    df_saida_all = df_fin[df_fin["Tipo"].astype(str).str.contains("Saída|Despesa", case=False, na=False)].copy()

    with st.expander("📅 Filtrar por período", expanded=False):
        datas_dash = df_saida_all["Data_DT"].dropna()
        if not datas_dash.empty:
            dash_dt_min = datas_dash.min().date()
            dash_dt_max = datas_dash.max().date()
        else:
            dash_dt_min = date.today() - timedelta(days=365)
            dash_dt_max = date.today()
        dash_periodo = st.date_input(
            "Período", value=(dash_dt_min, dash_dt_max),
            min_value=dash_dt_min, max_value=dash_dt_max, key="dash_periodo"
        )
        if isinstance(dash_periodo, tuple) and len(dash_periodo) == 2:
            dp_inicio, dp_fim = dash_periodo
            mask_p = df_saida_all["Data_DT"].notna()
            df_saida_all = df_saida_all[mask_p & (df_saida_all["Data_DT"].dt.date >= dp_inicio) & (df_saida_all["Data_DT"].dt.date <= dp_fim)]

    # -------------------------
    # Escopo
    # -------------------------
    if escopo == "Visão Geral (Todas as Obras)":
        vgv_total = float(df_obras["Valor Total"].sum()) if not df_obras.empty else 0.0
        df_show = df_saida_all.copy()

        if not df_obras.empty and "Status" in df_obras.columns:
            sold_mask = df_obras["Status"].astype(str).str.strip().str.lower() == "vendida"
        else:
            sold_mask = pd.Series([False] * len(df_obras))

        sold_names = df_obras.loc[sold_mask, "Cliente"].astype(str).str.strip().tolist() if not df_obras.empty else []
        vgv_sold = float(df_obras.loc[sold_mask, "Valor Total"].sum()) if not df_obras.empty else 0.0

        if sold_names:
            df_sold = df_saida_all[df_saida_all["Obra Vinculada"].astype(str).isin(sold_names)].copy()
        else:
            df_sold = pd.DataFrame(columns=df_saida_all.columns)

        custos_total = float(df_show["Valor"].sum()) if not df_show.empty else 0.0
        custos_sold = float(df_sold["Valor"].sum()) if not df_sold.empty else 0.0

        lucro_sold = float(vgv_sold - custos_sold)
        roi_sold = (lucro_sold / custos_sold * 100) if custos_sold > 0 else 0.0

        perc_total = (custos_total / vgv_total * 100) if vgv_total > 0 else 0.0

        k1, k2 = st.columns(2)
        k1.metric("VGV Total", fmt_moeda(vgv_total))
        k2.metric("Custos Totais", fmt_moeda(custos_total), delta=f"{perc_total:.1f}%", delta_color="inverse")

        k3, k4 = st.columns(2)
        if sold_names:
            k3.metric("Lucro (Vendidas)", fmt_moeda(lucro_sold))
            k4.metric("ROI (Vendidas)", f"{roi_sold:.1f}%")
        else:
            k3.metric("Lucro (Vendidas)", "—")
            k4.metric("ROI (Vendidas)", "—")

        vgv = vgv_total
        custos = custos_total
        lucro = vgv - custos
        roi = (lucro / custos * 100) if custos > 0 else 0.0

    else:
        row = df_obras[df_obras["Cliente"] == escopo].iloc[0]
        status_obra = str(row.get("Status", "")).strip()
        vgv = float(row["Valor Total"]) if "Valor Total" in row else 0.0

        df_show = df_saida_all[df_saida_all["Obra Vinculada"].astype(str) == str(escopo)].copy()

        custos = float(df_show["Valor"].sum()) if not df_show.empty else 0.0
        lucro = float(vgv - custos)
        roi = (lucro / custos * 100) if custos > 0 else 0.0
        perc = (custos / vgv * 100) if vgv > 0 else 0.0

        is_vendida = status_obra.lower() == "vendida"

        k1, k2 = st.columns(2)
        k1.metric("VGV", fmt_moeda(vgv))
        k2.metric("Custos", fmt_moeda(custos), delta=f"{perc:.1f}%", delta_color="inverse")

        k3, k4 = st.columns(2)
        if is_vendida:
            k3.metric("Lucro", fmt_moeda(lucro))
            k4.metric("ROI", f"{roi:.1f}%")
        else:
            k3.metric("Status", status_obra if status_obra else "—")
            k4.metric("Lucro / ROI", "—")

    # -------------------------
    # Atividade Recente (NOVO)
    # -------------------------
    if not df_fin.empty:
        st.markdown("---")
        st.subheader("🕐 Atividade Recente")
        df_recentes = df_fin.sort_values("Data_DT", ascending=False).head(5)
        for _, rec in df_recentes.iterrows():
            tipo_icon = "🔴" if "Saída" in str(rec.get("Tipo", "")) or "Despesa" in str(rec.get("Tipo", "")) else "🟢"
            rec_data = str(rec.get("Data", ""))[:10]
            rec_desc = str(rec.get("Descrição", ""))[:40]
            rec_obra = str(rec.get("Obra Vinculada", ""))
            rec_valor = fmt_moeda(rec.get("Valor", 0))
            st.caption(f"{tipo_icon} **{rec_data}** — {rec_desc} | {rec_obra} | **{rec_valor}**")

    # -------------------------
    # Gráficos
    # -------------------------
    st.markdown("---")
    st.subheader("📈 Evolução de Custos")
    if not df_show.empty:
        df_ev = df_show.sort_values("Data_DT")
        df_ev["Acumulado"] = df_ev["Valor"].cumsum()
        fig = px.area(df_ev, x="Data_DT", y="Acumulado", color_discrete_sequence=[COR_PRIMARIA])
        fig.update_layout(
            plot_bgcolor="white",
            margin=dict(t=5, l=5, r=5, b=5),
            height=250,
            xaxis_title="",
            yaxis_title="",
            xaxis=dict(tickfont=dict(size=10)),
            yaxis=dict(tickfont=dict(size=10)),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem despesas registradas para o escopo selecionado.")

    st.subheader("🍩 Categorias")
    if not df_show.empty:
        df_cat = df_show.groupby("Categoria", as_index=False)["Valor"].sum()

        fig2 = px.pie(df_cat, values="Valor", names="Categoria", hole=0.6, color_discrete_sequence=px.colors.qualitative.Bold)
        fig2.update_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5, font=dict(size=10)),
            margin=dict(t=5, l=5, r=5, b=5),
            height=250,
        )
        fig2.update_traces(textinfo="percent", textfont_size=10)
        st.plotly_chart(fig2, use_container_width=True)

        df_cat_display = df_cat.sort_values("Valor", ascending=False).copy()
        st.dataframe(
            df_cat_display,
            use_container_width=True,
            hide_index=True,
            height=min(len(df_cat_display) * 35 + 40, 250),
            column_config={"Valor": st.column_config.NumberColumn(format="R$ %.2f")}
        )
    else:
        st.info("Sem dados")

    # -------------------------
    # Top 5 Fornecedores (NOVO)
    # -------------------------
    if not df_show.empty and "Fornecedor" in df_show.columns:
        df_forn = df_show[df_show["Fornecedor"].astype(str).str.strip() != ""].copy()
        if not df_forn.empty:
            st.markdown("---")
            st.subheader("🏢 Top 5 Fornecedores")
            df_top_forn = df_forn.groupby("Fornecedor", as_index=False)["Valor"].sum()
            df_top_forn = df_top_forn.sort_values("Valor", ascending=False).head(5)

            fig_forn = px.bar(
                df_top_forn, x="Valor", y="Fornecedor", orientation="h",
                color_discrete_sequence=[COR_PRIMARIA],
            )
            fig_forn.update_layout(
                plot_bgcolor="white", margin=dict(t=5, l=5, r=5, b=5),
                height=200, xaxis_title="", yaxis_title="",
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_forn, use_container_width=True)

    # -------------------------
    # Comparativo Mensal
    # -------------------------
    if not df_show.empty and pd.notna(df_show["Data_DT"]).any():
        st.markdown("---")
        st.subheader("📊 Comparativo Mensal")

        df_mensal = df_show.copy()
        df_mensal["Mês"] = df_mensal["Data_DT"].dt.to_period("M").astype(str)
        mensal_agg = df_mensal.groupby("Mês", as_index=False)["Valor"].sum().sort_values("Mês")

        if len(mensal_agg) > 1:
            mensal_agg["Variação %"] = mensal_agg["Valor"].pct_change() * 100
        else:
            mensal_agg["Variação %"] = 0.0

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=mensal_agg["Mês"], y=mensal_agg["Valor"],
            marker_color=COR_PRIMARIA, name="Custo Mensal",
        ))
        fig_bar.update_layout(
            plot_bgcolor="white", margin=dict(t=5, l=5, r=5, b=5),
            height=230, xaxis_title="", yaxis_title="",
            xaxis=dict(tickfont=dict(size=10)),
            yaxis=dict(tickfont=dict(size=10)),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        df_mensal_display = mensal_agg.copy()
        df_mensal_display["Valor"] = df_mensal_display["Valor"].apply(fmt_moeda)
        df_mensal_display["Variação %"] = df_mensal_display["Variação %"].apply(
            lambda x: f"{x:+.1f}%" if pd.notna(x) else "—"
        )
        st.dataframe(
            df_mensal_display[["Mês", "Valor", "Variação %"]],
            use_container_width=True, hide_index=True,
            height=min(len(df_mensal_display) * 35 + 40, 200),
        )

    # -------------------------
    # Orçado vs Realizado (NOVO)
    # -------------------------
    if escopo == "Visão Geral (Todas as Obras)" and not df_obras.empty:
        st.markdown("---")
        st.subheader("📊 Orçado vs Realizado")

        orc_rows = []
        for _, ob_r in df_obras.iterrows():
            nome_ob = str(ob_r["Cliente"]).strip()
            custo_prev_ob = float(ob_r.get("Custo Previsto", 0))
            gasto_real = float(df_saida_all[df_saida_all["Obra Vinculada"].astype(str) == nome_ob]["Valor"].sum())
            orc_rows.append({"Obra": nome_ob, "Orçado": custo_prev_ob, "Realizado": gasto_real})

        df_orc = pd.DataFrame(orc_rows)
        if not df_orc.empty and df_orc["Orçado"].sum() > 0:
            fig_orc = go.Figure()
            fig_orc.add_trace(go.Bar(name="Orçado", x=df_orc["Obra"], y=df_orc["Orçado"], marker_color=COR_CINZA_MEDIO))
            fig_orc.add_trace(go.Bar(name="Realizado", x=df_orc["Obra"], y=df_orc["Realizado"], marker_color=COR_PRIMARIA))
            fig_orc.update_layout(
                barmode="group", plot_bgcolor="white",
                margin=dict(t=5, l=5, r=5, b=5), height=260,
                xaxis_title="", yaxis_title="",
                legend=dict(orientation="h", yanchor="top", y=1.1, xanchor="center", x=0.5),
            )
            st.plotly_chart(fig_orc, use_container_width=True)

    # -------------------------
    # Resumo por Obra com Saúde Financeira (MELHORADO)
    # -------------------------
    if escopo == "Visão Geral (Todas as Obras)" and not df_obras.empty:
        st.markdown("---")
        st.subheader("📋 Resumo por Obra")

        resumo_rows = []
        for _, obra_row in df_obras.iterrows():
            nome = str(obra_row["Cliente"]).strip()
            vgv_obra = float(obra_row["Valor Total"])
            custo_prev = float(obra_row.get("Custo Previsto", 0))
            status_r = str(obra_row.get("Status", "")).strip()

            gasto = float(
                df_saida_all[df_saida_all["Obra Vinculada"].astype(str) == nome]["Valor"].sum()
            )
            saldo = vgv_obra - gasto
            perc_exec = (gasto / custo_prev * 100) if custo_prev > 0 else 0

            # Saúde financeira
            if custo_prev > 0:
                if perc_exec > 100:
                    saude = "🔴 Estourado"
                elif perc_exec > 80:
                    saude = "🟡 Atenção"
                else:
                    saude = "🟢 Saudável"
            else:
                saude = "⚪ Sem orçamento"

            resumo_rows.append({
                "Obra": nome, "Fase": status_r, "Saúde": saude,
                "VGV": vgv_obra, "Orçamento": custo_prev,
                "Gasto Real": gasto, "Saldo": saldo,
                "Execução %": perc_exec,
            })

        df_resumo = pd.DataFrame(resumo_rows)
        st.dataframe(
            df_resumo, use_container_width=True, hide_index=True,
            column_config={
                "VGV": st.column_config.NumberColumn(format="R$ %.0f"),
                "Orçamento": st.column_config.NumberColumn(format="R$ %.0f"),
                "Gasto Real": st.column_config.NumberColumn(format="R$ %.0f"),
                "Saldo": st.column_config.NumberColumn(format="R$ %.0f"),
                "Execução %": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%"),
            },
        )

    # -------------------------
    # PDF + CSV
    # -------------------------
    st.markdown("---")

    if not df_show.empty:
        dmin = df_show["Data_DT"].min().strftime("%d/%m/%Y") if pd.notna(df_show["Data_DT"].min()) else ""
        dmax = df_show["Data_DT"].max().strftime("%d/%m/%Y") if pd.notna(df_show["Data_DT"].max()) else ""
        per_str = f"De {dmin} até {dmax}" if dmin and dmax else "Período indisponível"

        df_cat_pdf = df_show.groupby("Categoria", as_index=False)["Valor"].sum() if not df_show.empty else pd.DataFrame()

        cols_pdf = ["Data", "Categoria", "Descrição", "Valor"]
        df_pdf = df_show.copy()
        for c in cols_pdf:
            if c not in df_pdf.columns:
                df_pdf[c] = ""
        df_pdf = df_pdf[cols_pdf].sort_values("Data", ascending=False)

        pdf_data = gerar_pdf_empresarial(
            escopo, per_str, vgv, custos, lucro, roi,
            df_cat_pdf, df_pdf
        )

        st.download_button(
            label="⬇️ BAIXAR RELATÓRIO PDF",
            data=pdf_data,
            file_name=f"Relatorio_{escopo}_{date.today()}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
        csv_buffer = io.StringIO()
        df_show.to_csv(csv_buffer, index=False, sep=";", decimal=",")
        st.download_button(
            label="📊 EXPORTAR CSV",
            data=csv_buffer.getvalue(),
            file_name=f"Dados_{escopo}_{date.today()}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info("Sem lançamentos no escopo para gerar relatório.")


# --- FINANCEIRO ---
elif sel == "Financeiro":
    st.title("Financeiro")

    if st.session_state.get("sucesso_fin"):
        st.success("✅ Lançamento realizado com sucesso!", icon="✅")
        reset_form_state("k_fin", DEFAULTS_FIN)
        st.session_state["sucesso_fin"] = False

    init_session_state_defaults("k_fin", DEFAULTS_FIN)

    # --- NOVO LANÇAMENTO ---
    if require_role("editor"):
        with st.expander("Novo Lançamento", expanded=True):
            with st.form("ffin", clear_on_submit=False):

                c_r1a, c_r1b = st.columns(2)
                with c_r1a:
                    dt = st.date_input("Data", value=st.session_state.k_fin_data, key="k_fin_data")
                with c_r1b:
                    vl = st.number_input("Valor R$ *", min_value=0.0, format="%.2f", step=100.0, value=st.session_state.k_fin_valor, key="k_fin_valor_input")

                ob = st.selectbox("Obra Vinculada *", [""] + lista_obras, key="k_fin_obra")

                c_r2a, c_r2b = st.columns(2)
                with c_r2a:
                    tp = st.selectbox("Tipo", ["Saída (Despesa)", "Entrada"], key="k_fin_tipo")
                with c_r2b:
                    ct = st.selectbox("Categoria *", [""] + CATS, key="k_fin_cat")

                c_r3a, c_r3b = st.columns(2)
                with c_r3a:
                    pg = st.selectbox("Forma de Pagamento *", [""] + PAGAMENTOS, key="k_fin_pag")
                with c_r3b:
                    fn = st.text_input("Fornecedor", value=st.session_state.k_fin_forn, key="k_fin_forn", placeholder="Obrigatório se Material")

                dc = st.text_input("Descrição *", value=st.session_state.k_fin_desc, key="k_fin_desc", placeholder="Detalhes do gasto")

                # Parcelas (NOVO)
                c_parc1, c_parc2 = st.columns(2)
                with c_parc1:
                    num_parcelas = st.number_input("Parcelas", min_value=1, max_value=48, value=1, step=1, key="k_fin_parcelas")
                with c_parc2:
                    if num_parcelas > 1 and vl > 0:
                        st.caption(f"💳 {num_parcelas}x de **{fmt_moeda(vl / num_parcelas)}**")

                if ct == "Material" and not fn:
                    st.caption("⚠️ Fornecedor é obrigatório para categoria 'Material'")

                st.write("")
                submitted_fin = st.form_submit_button("Salvar Lançamento", use_container_width=True)

                if submitted_fin:
                    st.session_state.k_fin_valor = vl

                    is_valid, erros = validate_lancamento(
                        obra=ob, categoria=ct, tipo=tp,
                        descricao=dc, valor=vl,
                        fornecedor=fn, forma_pagamento=pg
                    )

                    if erros:
                        st.error("⚠️ Atenção:")
                        for e in erros:
                            st.caption(f"- {e}")
                    else:
                        try:
                            conn = get_conn()
                            ws_fin = conn.worksheet("Financeiro")

                            if not st.session_state.get("schema_verified"):
                                ensure_financeiro_schema(ws_fin, FIN_COLS)
                                st.session_state["schema_verified"] = True

                            if not df_fin.empty and "ID" in df_fin.columns:
                                ids_exist = pd.to_numeric(df_fin["ID"], errors="coerce").fillna(0)
                            else:
                                ids_exist = pd.Series()

                            # Parcelas: divide valor e gera linhas com datas incrementais
                            n_parc = int(num_parcelas) if num_parcelas > 1 else 1
                            valor_parcela = round(float(vl) / n_parc, 2)

                            for p in range(n_parc):
                                new_id = generate_unique_id(ids_exist)
                                ids_exist = pd.concat([ids_exist, pd.Series([new_id])], ignore_index=True)

                                # Data da parcela: mês a mês
                                dt_parcela = dt
                                if p > 0:
                                    month = dt.month + p
                                    year = dt.year + (month - 1) // 12
                                    month = ((month - 1) % 12) + 1
                                    try:
                                        dt_parcela = dt.replace(year=year, month=month)
                                    except ValueError:
                                        dt_parcela = dt.replace(year=year, month=month, day=28)

                                desc_parc = f"{dc.strip()} ({p+1}/{n_parc})" if n_parc > 1 else dc.strip()

                                ws_fin.append_row([
                                    new_id, dt_parcela.strftime("%Y-%m-%d"), tp,
                                    ct.strip(), desc_parc, valor_parcela,
                                    ob.strip(), fn.strip(), pg.strip()
                                ])

                            log_action("CRIAR_LANCAMENTO", f"{n_parc}x | {ob} | {ct} | {fmt_moeda(vl)} | {dc[:50]}")
                            clear_data_cache()
                            st.session_state["sucesso_fin"] = True
                            st.rerun()
                        except gspread.exceptions.GSpreadException as e:
                            logger.error(f"Erro GSpread ao salvar: {e}")
                            st.error(f"Erro ao salvar: {e}")
                        except Exception as e:
                            logger.error(f"Erro ao salvar lançamento: {e}")
                            st.error(f"Erro: {e}")

    # --- DUPLICAR LANÇAMENTO (NOVO) ---
    if require_role("editor") and not df_fin.empty:
        with st.expander("📋 Duplicar Lançamento Existente", expanded=False):
            opcoes_dup = df_fin.apply(
                lambda r: f"#{r['ID']} - {r.get('Data', '')[:10]} - {str(r.get('Descrição', ''))[:30]} - {fmt_moeda(r.get('Valor', 0))}",
                axis=1
            ).tolist()
            sel_dup = st.selectbox("Selecione o lançamento", opcoes_dup, key="sel_duplicar")
            if st.button("Duplicar para o formulário acima", use_container_width=True, key="btn_duplicar"):
                idx_dup = opcoes_dup.index(sel_dup)
                row_dup = df_fin.iloc[idx_dup]
                st.session_state.k_fin_data = date.today()
                st.session_state.k_fin_valor = float(safe_float(row_dup.get("Valor", 0)))
                st.session_state.k_fin_desc = str(row_dup.get("Descrição", ""))
                st.session_state.k_fin_forn = str(row_dup.get("Fornecedor", ""))
                st.toast("📋 Dados copiados! Edite e salve no formulário acima.", icon="📋")
                st.rerun()

    st.markdown("---")
    st.markdown("### 🔍 Consultar Lançamentos")

    if not df_fin.empty:
        df_view = df_fin.copy()

        # --- FILTROS (expandido com data, texto e tipo) ---
        with st.expander("Filtros de Busca", expanded=True):
            c_f1, c_f2 = st.columns(2)
            with c_f1:
                filtro_obra = st.selectbox("Obra", ["Todas as Obras"] + lista_obras)
            with c_f2:
                filtro_cat = st.selectbox("Categoria", ["Todas as Categorias"] + CATS)

            c_f3, c_f4 = st.columns(2)
            with c_f3:
                filtro_tipo = st.selectbox("Tipo", ["Todos", "Saída (Despesa)", "Entrada"])
            with c_f4:
                busca_texto = st.text_input(
                    "Buscar", placeholder="Descrição ou Fornecedor...", key="busca_texto"
                )

            # Período
            datas_validas = df_view["Data_DT"].dropna()
            if not datas_validas.empty:
                dt_min_f = datas_validas.min().date()
                dt_max_f = datas_validas.max().date()
            else:
                dt_min_f = date.today()
                dt_max_f = date.today()
            filtro_datas = st.date_input(
                "Período", value=(dt_min_f, dt_max_f),
                min_value=dt_min_f, max_value=dt_max_f, key="filtro_periodo"
            )

        # Aplicar filtros
        if filtro_obra != "Todas as Obras":
            df_view = df_view[df_view["Obra Vinculada"].astype(str).str.strip() == str(filtro_obra).strip()]

        if filtro_cat != "Todas as Categorias":
            df_view = df_view[df_view["Categoria"].astype(str).str.strip() == str(filtro_cat).strip()]

        if filtro_tipo != "Todos":
            df_view = df_view[df_view["Tipo"].astype(str).str.strip() == filtro_tipo]

        # Filtro por data (NOVO)
        if isinstance(filtro_datas, tuple) and len(filtro_datas) == 2:
            dt_inicio, dt_fim = filtro_datas
            mask_data = df_view["Data_DT"].notna()
            df_view = df_view[
                mask_data
                & (df_view["Data_DT"].dt.date >= dt_inicio)
                & (df_view["Data_DT"].dt.date <= dt_fim)
            ]

        # Busca por texto (NOVO)
        if busca_texto:
            busca_lower = busca_texto.lower()
            mask_desc = df_view["Descrição"].astype(str).str.lower().str.contains(busca_lower, na=False)
            mask_forn = df_view["Fornecedor"].astype(str).str.lower().str.contains(busca_lower, na=False)
            df_view = df_view[mask_desc | mask_forn]

        total_filtrado = df_view["Valor"].sum()
        count_filtrado = len(df_view)

        st.caption(f"Exibindo **{count_filtrado}** lançamentos | Total Filtrado: **{fmt_moeda(total_filtrado)}**")

        cols_order = ["ID", "Data", "Tipo", "Forma Pagamento", "Obra Vinculada", "Categoria", "Fornecedor", "Descrição", "Valor"]
        for c in cols_order:
            if c not in df_view.columns:
                df_view[c] = ""

        df_to_edit = df_view[cols_order].copy()

        df_to_edit["ID"] = pd.to_numeric(df_to_edit["ID"], errors="coerce").fillna(0).astype(int)
        df_to_edit["Data"] = pd.to_datetime(df_to_edit["Data"], errors="coerce").dt.date
        df_to_edit["Valor"] = pd.to_numeric(df_to_edit["Valor"], errors="coerce").fillna(0.0)

        can_delete = require_role("admin")
        can_edit = require_role("editor")

        if can_delete:
            df_to_edit.insert(1, "Excluir", False)

        if can_delete:
            st.info("🧾 **Como excluir:** marque **🗑️ Excluir?** na linha desejada e depois clique em **💾 SALVAR** (com senha).")

        disabled_cols = ["ID"] if can_edit else list(cols_order)

        edited_df = st.data_editor(
            df_to_edit,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            disabled=disabled_cols,
            height=320,
            column_config={
                "ID": st.column_config.NumberColumn("#", width="small"),
                **({"Excluir": st.column_config.CheckboxColumn("🗑️", help="Marque para excluir", width="small")} if can_delete else {}),
                "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY", required=True),
                "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Saída (Despesa)", "Entrada"], required=True),
                "Forma Pagamento": st.column_config.SelectboxColumn("Pgto", options=[""] + PAGAMENTOS, required=False),
                "Obra Vinculada": st.column_config.SelectboxColumn("Obra", options=[""] + lista_obras, required=True),
                "Categoria": st.column_config.SelectboxColumn("Categ.", options=[""] + CATS, required=True),
                "Fornecedor": st.column_config.TextColumn("Forn."),
                "Descrição": st.column_config.TextColumn("Descrição", required=True),
                "Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f", min_value=0),
            }
        )

        # RESUMO VISUAL
        try:
            total_atual = float(pd.to_numeric(edited_df["Valor"], errors="coerce").fillna(0.0).sum())
            if can_delete and "Excluir" in edited_df.columns:
                marcados = int(edited_df["Excluir"].astype(bool).sum())
                valor_marcado = float(pd.to_numeric(edited_df.loc[edited_df["Excluir"] == True, "Valor"], errors="coerce").fillna(0.0).sum()) if marcados > 0 else 0.0
            else:
                marcados = 0
                valor_marcado = 0.0
            total_pos_excluir = total_atual - valor_marcado
        except (ValueError, TypeError, KeyError):
            total_atual, marcados, valor_marcado, total_pos_excluir = 0.0, 0, 0.0, 0.0

        with st.container(border=True):
            st.caption("📌 Resumo da tabela")
            m1, m2 = st.columns(2)
            m1.metric("Total (Filtro)", fmt_moeda(total_atual))
            m2.metric("Após exclusões", fmt_moeda(total_pos_excluir))
            if marcados > 0:
                m3, m4 = st.columns(2)
                m3.metric("Marcados", f"{marcados}")
                m4.metric("Valor a excluir", fmt_moeda(valor_marcado))

        if marcados > 0:
            st.warning(f"🗑️ Você marcou **{marcados}** lançamento(s) para exclusão. Ao salvar, eles serão removidos.", icon="⚠️")
            st.markdown("##### 🗑️ Marcados para exclusão (prévia)")

            cols_preview = ["ID", "Data", "Obra Vinculada", "Categoria", "Fornecedor", "Descrição", "Valor"]
            df_del_preview = edited_df.loc[edited_df["Excluir"] == True, cols_preview].copy()

            st.dataframe(
                df_del_preview.style.apply(lambda row: ["background-color: #ffe3e3"] * len(row), axis=1),
                use_container_width=True, hide_index=True, height=200,
                column_config={"Valor": st.column_config.NumberColumn(format="R$ %.2f")}
            )

        def _norm_df(df: pd.DataFrame) -> pd.DataFrame:
            """Normaliza DataFrame para comparação."""
            d = df.copy()
            d["Data"] = d["Data"].astype(str)
            d["Valor"] = pd.to_numeric(d["Valor"], errors="coerce").fillna(0.0).astype(float)
            for c in ["Tipo", "Forma Pagamento", "Obra Vinculada", "Categoria", "Fornecedor", "Descrição"]:
                if c not in d.columns:
                    d[c] = ""
                d[c] = d[c].astype(str).fillna("").str.strip()
            if "Excluir" in d.columns:
                d["Excluir"] = d["Excluir"].astype(bool)
            d["ID"] = pd.to_numeric(d["ID"], errors="coerce").fillna(0).astype(int)
            return d

        base_cmp = _norm_df(df_to_edit)
        edit_cmp = _norm_df(edited_df)
        has_changes = not edit_cmp.equals(base_cmp)

        st.write("")
        if has_changes and can_edit:
            with st.container(border=True):
                st.warning("⚠️ Alterações pendentes. Confirme com senha para salvar.")
                pwd_confirm = st.text_input("Senha de confirmação", type="password", placeholder="Digite sua senha", label_visibility="collapsed")
                if st.button("💾 SALVAR ALTERAÇÕES", type="primary", use_container_width=True):
                    if not verify_admin_password(pwd_confirm):
                        st.toast("Senha incorreta!", icon="⛔")
                    else:
                        erros = []
                        for _, r in edited_df.iterrows():
                            if can_delete and bool(r.get("Excluir")):
                                continue

                            row_id = int(r['ID'])
                            obra = normalize_string(r.get("Obra Vinculada", ""))
                            cat = normalize_string(r.get("Categoria", ""))
                            desc = normalize_string(r.get("Descrição", ""))
                            tp2 = normalize_string(r.get("Tipo", ""))
                            val = float(pd.to_numeric(r.get("Valor", 0), errors="coerce") or 0)
                            forn = normalize_string(r.get("Fornecedor", ""))

                            is_valid, row_erros = validate_lancamento(
                                obra=obra, categoria=cat, tipo=tp2,
                                descricao=desc, valor=val, fornecedor=forn
                            )

                            for err in row_erros:
                                erros.append(f"ID {row_id}: {err}")

                        if erros:
                            st.error("⚠️ Corrija antes de salvar:")
                            for e in erros:
                                st.caption(f"- {e}")
                        else:
                            try:
                                conn = get_conn()
                                ws_fin = conn.worksheet("Financeiro")

                                if not st.session_state.get("schema_verified"):
                                    ensure_financeiro_schema(ws_fin, FIN_COLS)
                                    st.session_state["schema_verified"] = True

                                headers_fin = ws_fin.row_values(1)
                                col_id = headers_fin.index("ID") + 1

                                # Exclusões
                                rows_del = []
                                if can_delete and "Excluir" in edited_df.columns:
                                    df_del = edited_df[edited_df["Excluir"] == True].copy()
                                    for _, rr in df_del.iterrows():
                                        idv = int(rr["ID"])
                                        cell = ws_fin.find(str(idv), in_column=col_id)
                                        if cell:
                                            rows_del.append(cell.row)
                                        log_action("EXCLUIR_LANCAMENTO", f"ID={idv} | {rr.get('Obra Vinculada', '')} | {fmt_moeda(rr.get('Valor', 0))}")

                                for rr in sorted(rows_del, reverse=True):
                                    ws_fin.delete_rows(rr)

                                # Atualizações
                                upd_count = 0
                                if can_delete and "Excluir" in edited_df.columns:
                                    df_upd = edited_df[edited_df["Excluir"] == False].copy()
                                else:
                                    df_upd = edited_df.copy()

                                for _, rr in df_upd.iterrows():
                                    idv = int(rr["ID"])
                                    cell = ws_fin.find(str(idv), in_column=col_id)
                                    if not cell:
                                        continue

                                    update_values = build_row_values(rr, headers_fin)

                                    start = rowcol_to_a1(cell.row, 1)
                                    end = rowcol_to_a1(cell.row, len(headers_fin))
                                    ws_fin.update(f"{start}:{end}", [update_values])

                                    upd_count += 1

                                log_action("SALVAR_FINANCEIRO", f"{upd_count} atualizações, {len(rows_del)} exclusões")
                                clear_data_cache()

                                st.toast(f"✅ Salvo! {upd_count} atualizações • {len(rows_del)} exclusões", icon="✅")
                                st.rerun()

                            except gspread.exceptions.GSpreadException as e:
                                logger.error(f"Erro GSpread ao salvar Financeiro: {e}")
                                st.error(f"Erro ao salvar Financeiro: {e}")
                            except Exception as e:
                                logger.error(f"Erro ao salvar Financeiro: {e}")
                                st.error(f"Erro ao salvar Financeiro: {e}")
        elif not can_edit:
            st.caption("🔒 Modo visualização. Sem permissão para editar.")
        else:
            st.caption("💡 Edite a tabela acima. Marque 🗑️ para excluir. O botão SALVAR aparece automaticamente.")

        st.write("")
        st.markdown("---")

        # --- EXPORTS (PDF + CSV) ---
        if not df_view.empty:
            dmin = df_view["Data_DT"].min().strftime("%d/%m/%Y")
            dmax = df_view["Data_DT"].max().strftime("%d/%m/%Y")
            per_str = f"De {dmin} até {dmax}"

            escopo_pdf = filtro_obra if filtro_obra != "Todas as Obras" else "Visão Geral (Filtro)"

            cols_pdf = ["Data", "Categoria", "Descrição", "Valor"]
            if can_delete and "Excluir" in edited_df.columns:
                df_pdf = edited_df[edited_df["Excluir"] == False].copy()
            else:
                df_pdf = edited_df.copy()
            for c in cols_pdf:
                if c not in df_pdf.columns:
                    df_pdf[c] = ""
            df_pdf = df_pdf[cols_pdf].sort_values("Data", ascending=False)

            pdf_data = gerar_pdf_empresarial(
                escopo_pdf, per_str,
                0.0,
                float(df_pdf["Valor"].apply(safe_float).sum()) if "Valor" in df_pdf.columns else 0.0,
                0.0, 0.0,
                pd.DataFrame(), df_pdf
            )

            st.download_button(
                label="⬇️ BAIXAR RELATÓRIO PDF",
                data=pdf_data,
                file_name=f"Extrato_{date.today()}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            csv_buf = io.StringIO()
            df_view.to_csv(csv_buf, index=False, sep=";", decimal=",")
            st.download_button(
                label="📊 EXPORTAR CSV",
                data=csv_buf.getvalue(),
                file_name=f"Financeiro_{date.today()}.csv",
                mime="text/csv",
                use_container_width=True
            )

    else:
        st.info("Nenhum lançamento registrado.")


# --- OBRAS ---
elif sel == "Obras":
    st.title("📂 Gestão de Incorporação e Obras")
    st.markdown("---")

    if st.session_state.get("sucesso_obra"):
        st.success("✅ Dados atualizados com sucesso!", icon="🏡")
        reset_form_state("k_ob", DEFAULTS_OBRA)
        st.session_state["sucesso_obra"] = False

    init_session_state_defaults("k_ob", DEFAULTS_OBRA)

    if require_role("editor"):
        with st.expander("➕ Novo Cadastro (Clique para expandir)", expanded=False):
            with st.form("f_obra_completa", clear_on_submit=False):
                st.markdown("#### 1. Identificação")
                nome_obra = st.text_input(
                    "Nome do Empreendimento *",
                    placeholder="Ex: Res. Vila Verde - Casa 04",
                    value=st.session_state.k_ob_nome,
                    key="k_ob_nome"
                )
                if nome_obra and len(nome_obra.strip()) < 3:
                    st.caption("⚠️ Nome muito curto (mínimo 3 caracteres)")
                endereco = st.text_input(
                    "Endereço *",
                    placeholder="Rua, Bairro...",
                    value=st.session_state.k_ob_end,
                    key="k_ob_end"
                )
                foto_url = st.text_input(
                    "Link da Foto (opcional)",
                    placeholder="https://drive.google.com/... ou URL da imagem",
                    key="k_ob_foto"
                )

                st.markdown("#### 2. Características Físicas")
                c_a1, c_a2 = st.columns(2)
                with c_a1:
                    area_const = st.number_input(
                        "Área Construída (m²)", min_value=0.0, format="%.2f",
                        value=st.session_state.k_ob_area_c, key="k_ob_area_c"
                    )
                with c_a2:
                    area_terr = st.number_input(
                        "Área Terreno (m²)", min_value=0.0, format="%.2f",
                        value=st.session_state.k_ob_area_t, key="k_ob_area_t"
                    )
                c_a3, c_a4 = st.columns(2)
                with c_a3:
                    quartos = st.number_input(
                        "Qtd. Quartos", min_value=0, step=1,
                        value=st.session_state.k_ob_quartos, key="k_ob_quartos"
                    )
                with c_a4:
                    status = st.selectbox("Fase Atual", STATUS_OBRA, key="k_ob_status")

                st.markdown("#### 3. Financeiro e Prazos")
                c_b1, c_b2 = st.columns(2)
                with c_b1:
                    custo_previsto = st.number_input(
                        "Orçamento (Custo) *", min_value=0.0, format="%.2f", step=1000.0,
                        value=st.session_state.k_ob_custo, key="k_ob_custo_input"
                    )
                with c_b2:
                    valor_venda = st.number_input(
                        "VGV (Venda) *", min_value=0.0, format="%.2f", step=1000.0,
                        value=st.session_state.k_ob_vgv, key="k_ob_vgv_input"
                    )
                c_b3, c_b4 = st.columns(2)
                with c_b3:
                    data_inicio = st.date_input("Início da Obra", value=st.session_state.k_ob_data, key="k_ob_data")
                with c_b4:
                    prazo_entrega = st.text_input(
                        "Prazo / Entrega *", placeholder="Ex: dez/2025",
                        value=st.session_state.k_ob_prazo, key="k_ob_prazo"
                    )

                if valor_venda > 0 and custo_previsto > 0:
                    margem_proj = ((valor_venda - custo_previsto) / custo_previsto) * 100
                    lucro_proj = valor_venda - custo_previsto

                    if margem_proj < 10:
                        st.warning(f"⚠️ **Atenção:** Margem baixa ({margem_proj:.1f}%). Lucro projetado: {fmt_moeda(lucro_proj)}")
                    elif margem_proj < 20:
                        st.info(f"💰 **Projeção:** Lucro de **{fmt_moeda(lucro_proj)}** (Margem: **{margem_proj:.1f}%**)")
                    else:
                        st.success(f"✅ **Boa margem!** Lucro de **{fmt_moeda(lucro_proj)}** (Margem: **{margem_proj:.1f}%**)")
                elif valor_venda > 0 or custo_previsto > 0:
                    st.caption("ℹ️ Preencha VGV e Custo para ver a projeção de margem")

                st.markdown("---")
                st.caption("(*) Campos Obrigatórios")
                submitted = st.form_submit_button("✅ SALVAR PROJETO", use_container_width=True)

                if submitted:
                    st.session_state.k_ob_custo = custo_previsto
                    st.session_state.k_ob_vgv = valor_venda

                    is_valid, erros = validate_obra(
                        nome=nome_obra, endereco=endereco, prazo=prazo_entrega,
                        vgv=valor_venda, custo=custo_previsto,
                        area_const=area_const, area_terr=area_terr
                    )

                    if erros:
                        st.error("⚠️ Não foi possível salvar. Verifique os campos:")
                        for e in erros:
                            st.markdown(f"- {e}")
                    else:
                        try:
                            conn = get_conn()
                            ws = conn.worksheet("Obras")
                            ids_existentes = pd.to_numeric(df_obras["ID"], errors="coerce").fillna(0)
                            novo_id = generate_unique_id(ids_existentes)
                            ws.append_row([
                                novo_id, nome_obra.strip(), endereco.strip(), status, float(valor_venda),
                                data_inicio.strftime("%Y-%m-%d"), prazo_entrega.strip(),
                                float(area_const), float(area_terr), int(quartos), float(custo_previsto)
                            ])

                            log_action("CRIAR_OBRA", f"ID={novo_id} | {nome_obra.strip()} | VGV={fmt_moeda(valor_venda)}")
                            clear_data_cache()
                            st.session_state["sucesso_obra"] = True
                            st.rerun()
                        except gspread.exceptions.GSpreadException as e:
                            logger.error(f"Erro GSpread ao salvar obra: {e}")
                            st.error(f"Erro no Google Sheets: {e}")
                        except Exception as e:
                            logger.error(f"Erro ao salvar obra: {e}")
                            st.error(f"Erro no Google Sheets: {e}")

    st.markdown("### 📋 Carteira de Obras")
    if not df_obras.empty:
        cols_order = ["ID", "Cliente", "Status", "Prazo", "Valor Total", "Custo Previsto", "Area Construida", "Area Terreno", "Quartos"]
        valid_cols = [c for c in cols_order if c in df_obras.columns]
        df_to_edit = df_obras[valid_cols].copy().reset_index(drop=True)
        num_cols = ["Valor Total", "Custo Previsto", "Area Construida", "Area Terreno", "Quartos", "ID"]
        for c in df_to_edit.columns:
            if c in num_cols:
                df_to_edit[c] = pd.to_numeric(df_to_edit[c], errors='coerce').fillna(0)
            else:
                df_to_edit[c] = df_to_edit[c].fillna("")

        can_edit_obras = require_role("editor")
        disabled_cols_obras = ["ID"] if can_edit_obras else list(valid_cols)

        edited_df = st.data_editor(
            df_to_edit,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            disabled=disabled_cols_obras,
            height=280,
            column_config={
                "ID": st.column_config.NumberColumn("#", width="small"),
                "Cliente": st.column_config.TextColumn("Empreendimento", required=True),
                "Status": st.column_config.SelectboxColumn("Fase", options=STATUS_OBRA, required=True),
                "Prazo": st.column_config.TextColumn("Entrega"),
                "Valor Total": st.column_config.NumberColumn("VGV", format="R$ %.0f", min_value=0),
                "Custo Previsto": st.column_config.NumberColumn("Custo", format="R$ %.0f", min_value=0),
                "Area Construida": st.column_config.NumberColumn("Área m²", format="%.0f"),
                "Area Terreno": st.column_config.NumberColumn("Terr. m²", format="%.0f"),
                "Quartos": st.column_config.NumberColumn("Qts", min_value=0, step=1, width="small"),
            }
        )

        st.write("")
        has_changes = not edited_df.equals(df_to_edit)
        if has_changes and can_edit_obras:
            with st.container(border=True):
                st.warning("⚠️ Alterações pendentes. Confirme com senha para salvar.")
                pwd_confirm = st.text_input("Senha de confirmação", type="password", placeholder="Digite sua senha", label_visibility="collapsed", key="pwd_obras")
                if st.button("💾 SALVAR ALTERAÇÕES", type="primary", use_container_width=True, key="btn_salvar_obras"):
                    if not verify_admin_password(pwd_confirm):
                        st.toast("Senha incorreta!", icon="⛔")
                    else:
                        try:
                            conn = get_conn()
                            ws = conn.worksheet("Obras")
                            ws_fin = conn.worksheet("Financeiro")

                            with st.spinner("Salvando alterações..."):
                                for index, row in edited_df.iterrows():
                                    id_obra = row["ID"]
                                    found_cell = ws.find(str(id_obra), in_column=1)

                                    if found_cell:
                                        original_row = df_obras[df_obras["ID"] == id_obra].iloc[0]
                                        old_name = str(original_row["Cliente"]).strip()
                                        new_name = str(row["Cliente"]).strip()

                                        if old_name != new_name and old_name != "":
                                            headers_fin = ws_fin.row_values(1)
                                            try:
                                                col_idx_fin = headers_fin.index("Obra Vinculada") + 1
                                            except ValueError:
                                                col_idx_fin = 6

                                            cells_to_update = ws_fin.findall(old_name, in_column=col_idx_fin)
                                            for cell in cells_to_update:
                                                cell.value = new_name
                                            if cells_to_update:
                                                ws_fin.update_cells(cells_to_update)
                                                st.toast(f"♻️ Atualizados {len(cells_to_update)} lançamentos para '{new_name}'")
                                                log_action("RENOMEAR_OBRA", f"'{old_name}' -> '{new_name}' | {len(cells_to_update)} lançamentos")

                                        update_values = []
                                        for col in OBRAS_COLS:
                                            if col in row:
                                                val = row[col]
                                            else:
                                                val = original_row[col]

                                            if isinstance(val, (pd.Timestamp, date, datetime)):
                                                val = val.strftime("%Y-%m-%d")
                                            elif pd.isna(val):
                                                val = ""
                                            update_values.append(val)

                                        ws.update(f"A{found_cell.row}:K{found_cell.row}", [update_values])

                                log_action("SALVAR_OBRAS", f"{len(edited_df)} obras atualizadas")
                                clear_data_cache()
                                st.session_state["sucesso_obra"] = True
                                st.rerun()
                        except gspread.exceptions.GSpreadException as e:
                            logger.error(f"Erro GSpread ao salvar obras: {e}")
                            st.error(f"Erro ao salvar: {e}")
                        except Exception as e:
                            logger.error(f"Erro ao salvar obras: {e}")
                            st.error(f"Erro ao salvar: {e}")
        elif not can_edit_obras:
            st.caption("🔒 Modo visualização. Sem permissão para editar.")
        else:
            st.caption("💡 Edite diretamente na tabela acima. O botão de salvar aparecerá automaticamente.")
    else:
        st.info("Nenhuma obra cadastrada.")

    # -------------------------
    # Cronograma Visual (NOVO)
    # -------------------------
    if not df_obras.empty:
        st.markdown("---")
        st.subheader("📊 Cronograma de Fases")

        for _, ob_row in df_obras.iterrows():
            nome_ob = str(ob_row["Cliente"]).strip()
            status_ob = str(ob_row.get("Status", "Projeto")).strip()
            prazo_ob = str(ob_row.get("Prazo", "")).strip()

            # Calcula progresso baseado na posição do status
            if status_ob in STATUS_OBRA:
                idx_status = STATUS_OBRA.index(status_ob)
                progresso = int((idx_status / (len(STATUS_OBRA) - 1)) * 100)
            else:
                progresso = 0

            # Cor baseada no progresso
            if status_ob.lower() in ["concluída", "vendida"]:
                status_label = f"✅ {status_ob}"
            elif progresso >= 50:
                status_label = f"🔨 {status_ob}"
            else:
                status_label = f"📐 {status_ob}"

            st.caption(f"**{nome_ob}** — {status_label} | Prazo: {prazo_ob if prazo_ob else '—'}")
            st.progress(progresso / 100, text=f"{progresso}%")


# --- AUDITORIA (NOVO) ---
elif sel == "Auditoria":
    st.title("🛡️ Log de Auditoria")
    st.caption("Registro de todas as ações realizadas no sistema.")

    try:
        conn = get_conn()
        ws_audit = conn.worksheet("Auditoria")
        records = ws_audit.get_all_records()

        if not records:
            st.info("Nenhum registro de auditoria encontrado.")
        else:
            df_audit = pd.DataFrame(records).tail(200).iloc[::-1].reset_index(drop=True)

            c1, c2 = st.columns(2)
            with c1:
                filtro_acao = st.selectbox(
                    "Filtrar por ação",
                    ["Todas"] + sorted(df_audit["Ação"].unique().tolist()),
                )
            with c2:
                filtro_usuario = st.selectbox(
                    "Filtrar por usuário",
                    ["Todos"] + sorted(df_audit["Usuário"].unique().tolist()),
                )

            df_display = df_audit.copy()
            if filtro_acao != "Todas":
                df_display = df_display[df_display["Ação"] == filtro_acao]
            if filtro_usuario != "Todos":
                df_display = df_display[df_display["Usuário"] == filtro_usuario]

            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Timestamp": st.column_config.TextColumn("Data/Hora", width=160),
                    "Usuário": st.column_config.TextColumn("Usuário", width=180),
                    "Ação": st.column_config.TextColumn("Ação", width=180),
                    "Detalhes": st.column_config.TextColumn("Detalhes", width="large"),
                },
            )
            st.caption(f"Exibindo {len(df_display)} de {len(df_audit)} registros")

    except Exception as e:
        st.error(f"Erro ao carregar auditoria: {e}")
