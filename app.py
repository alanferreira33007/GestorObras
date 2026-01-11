import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from datetime import date, datetime, timedelta
from streamlit_option_menu import option_menu
import io
import random
import re

# ==============================================================================
# 1. CONFIGURAÇÃO VISUAL (UI)
# ==============================================================================
st.set_page_config(
    page_title="GESTOR PRO | Incorporadora",
    layout="wide",
    page_icon="🏗️",
    initial_sidebar_state="expanded"
)

# CSS OTIMIZADO
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 700; color: #1a1a1a; }
    
    div.stButton > button {
        background-color: #2D6A4F;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.75rem 1rem;
        font-weight: 600;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: all 0.2s;
    }
    div.stButton > button:hover {
        background-color: #1B4332;
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    button:disabled {
        background-color: #e9ecef !important;
        color: #adb5bd !important;
        cursor: not-allowed;
    }
    
    [data-testid="stSidebar"] { 
        background-color: #f8f9fa; 
        border-right: 1px solid #e9ecef; 
    }
    
    [data-testid="stSidebarUserContent"] {
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. FUNÇÕES HELPERS
# ==============================================================================
def fmt_moeda(valor):
    if pd.isna(valor) or valor == "":
        return "R$ 0,00"
    try:
        val = float(valor)
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return f"R$ {valor}"

def safe_float(x) -> float:
    if isinstance(x, (int, float)):
        return float(x)
    if x is None:
        return 0.0
    s = str(x).strip().replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0

def ensure_columns(ws, required_cols):
    """
    Garante que a worksheet tenha todas as colunas necessárias no cabeçalho.
    Se faltarem, adiciona colunas ao final (não reordena colunas existentes).
    """
    headers = ws.row_values(1)
    if not headers:
        ws.update("A1", [required_cols])
        return

    missing = [c for c in required_cols if c not in headers]
    if missing:
        try:
            ws.add_cols(len(missing))
        except Exception:
            pass
        new_headers = headers + missing
        ws.update("A1", [new_headers])

def ensure_financeiro_id(ws_fin):
    """
    Garante que a aba Financeiro tenha a coluna ID (primeira coluna).
    Se não tiver, cria e preenche IDs sequenciais para as linhas existentes.
    """
    headers = ws_fin.row_values(1)
    if "ID" in headers:
        return

    n_rows = len(ws_fin.get_all_values())
    ws_fin.insert_cols([["ID"]], 1)

    if n_rows > 1:
        ids = [[i] for i in range(1, n_rows)]
        ws_fin.update(f"A2:A{n_rows}", ids)

def ensure_checklist_sheet(db):
    """
    Garante que exista a aba Checklist e que contenha as colunas necessárias.
    Também garante IDs sequenciais caso a coluna ID esteja vazia.
    """
    CHECK_COLS = ["ID", "Obra", "Item", "Status", "Criado Em", "Concluído Em", "Observação"]

    try:
        ws = db.worksheet("Checklist")
    except Exception:
        ws = db.add_worksheet(title="Checklist", rows="2000", cols="12")
        ws.update("A1", [CHECK_COLS])
        return ws

    # Garante colunas
    ensure_columns(ws, CHECK_COLS)

    # Garante cabeçalho (se a planilha existe mas a primeira linha está vazia)
    headers = ws.row_values(1)
    if not headers:
        ws.update("A1", [CHECK_COLS])
        headers = CHECK_COLS

    # Garante IDs (se coluna ID existe mas está vazia nas linhas)
    try:
        col_id = headers.index("ID") + 1
        col_vals = ws.col_values(col_id)  # inclui cabeçalho
        if len(col_vals) <= 1:
            return ws
        data_vals = col_vals[1:]
        # se quase tudo vazio -> preencher
        if sum([1 for v in data_vals if str(v).strip() != ""]) == 0:
            n_rows = len(ws.get_all_values())
            if n_rows > 1:
                ids = [[i] for i in range(1, n_rows)]
                start_col_letter = "A"
                # se ID não é coluna A, ainda assim atualiza pelo range de coluna específica
                # (mais simples: usa rowcol_to_a1)
                from gspread.utils import rowcol_to_a1
                a1_start = rowcol_to_a1(2, col_id)
                a1_end = rowcol_to_a1(n_rows, col_id)
                ws.update(f"{a1_start}:{a1_end}", ids)
    except Exception:
        pass

    return ws

# ==============================================================================
# 3. MOTOR PDF (ENTERPRISE V5)
# ==============================================================================
def gerar_pdf_empresarial(escopo, periodo, vgv, custos, lucro, roi, df_cat, df_lanc):
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
            self.drawString(30, 35, "GESTOR PRO • Sistema Integrado de Gestão de Obras")
            self.drawString(30, 25, "Relatório contábil individualizado.")

            data_hora = datetime.now().strftime("%d/%m/%Y às %H:%M")
            self.drawRightString(width-30, 35, f"Emitido em: {data_hora}")
            self.drawRightString(width-30, 25, f"Página {self.getPageNumber()} de {page_count}")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=60
    )
    story = []

    styles = getSampleStyleSheet()
    style_header_title = ParagraphStyle('HeadTitle', parent=styles['Normal'], fontSize=14, leading=16, textColor=colors.white, fontName='Helvetica-Bold')
    style_header_sub = ParagraphStyle('HeadSub', parent=styles['Normal'], fontSize=9, leading=11, textColor=colors.whitesmoke)
    style_h2 = ParagraphStyle('SecTitle', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor("#1B4332"), spaceBefore=15, spaceAfter=8, fontName='Helvetica-Bold')

    if "Visão Geral" in str(escopo):
        titulo_principal = "RELATÓRIO DE PORTFÓLIO (CONSOLIDADO)"
    else:
        titulo_principal = f"RELATÓRIO INDIVIDUAL: {str(escopo).upper()}"

    header_content = [[Paragraph(titulo_principal, style_header_title), Paragraph(f"PERÍODO:<br/>{periodo}", style_header_sub)]]
    t_header = Table(header_content, colWidths=[12*cm, 5*cm])
    t_header.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#2D6A4F")),
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
        ('BACKGROUND', (0,0), (-1,1), colors.HexColor("#F8F9FA")),
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
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#40916C")),
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
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2D6A4F")),
            ('FONTSIZE', (0,1), (-1,-1), 8),
            ('ALIGN', (-1,0), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-2), 0.25, colors.lightgrey),
            ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.whitesmoke]),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]
        estilo_total_linha = [
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#e9ecef")),
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
    total_lbl = Paragraph(f"<b>{msg_total}</b>", ParagraphStyle('TLabel', parent=styles['Normal'], textColor=colors.black, fontSize=10, alignment=TA_RIGHT))
    total_val = Paragraph(f"<b>{fmt_moeda(custos)}</b>", ParagraphStyle('TVal', parent=styles['Normal'], textColor=colors.white, fontSize=14, alignment=TA_RIGHT))

    data_total = [[total_lbl, total_val]]
    t_total = Table(data_total, colWidths=[12*cm, 5*cm])
    t_total.setStyle(TableStyle([
        ('BACKGROUND', (1,0), (1,0), colors.HexColor("#1A1C1E")),
        ('BACKGROUND', (0,0), (0,0), colors.white),
        ('LINEBELOW', (0,0), (1,0), 2, colors.HexColor("#1A1C1E")),
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
# 4. DADOS E CONEXÃO
# ==============================================================================
OBRAS_COLS = [
    "ID", "Cliente", "Endereço", "Status", "Valor Total",
    "Data Início", "Prazo", "Area Construida", "Area Terreno",
    "Quartos", "Custo Previsto"
]

FIN_COLS = ["ID", "Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada", "Fornecedor"]

CATS = [
    "Material",
    "Mão de Obra",
    "Serviços",
    "Administrativo",
    "Impostos",
    "Emolumentos Cartorários",
    "Outros"
]

CHECK_COLS = ["ID", "Obra", "Item", "Status", "Criado Em", "Concluído Em", "Observação"]
CHECK_STATUS = ["Pendente", "Em andamento", "Concluído"]

CHECKLIST_PADRAO = [
    "Documentos: Matrícula atualizada do imóvel",
    "Documentos: Escritura/Contrato de compra e venda",
    "Cartório: ITBI pago",
    "Cartório: Registro da compra (RGI)",
    "Obra: Alvará / licença (se aplicável)",
    "Obra: Início da obra registrado (data)",
    "Obra: Habite-se (se aplicável)",
    "Venda: Contrato assinado",
    "Venda: Registro/averbação (se aplicável)",
]

@st.cache_resource
def get_conn():
    creds = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
    db = gspread.authorize(
        ServiceAccountCredentials.from_json_keyfile_dict(
            creds,
            ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        )
    ).open("GestorObras_DB")

    # Migrações seguras
    try:
        ws_fin = db.worksheet("Financeiro")
        ensure_financeiro_id(ws_fin)
    except Exception:
        pass

    try:
        ensure_checklist_sheet(db)
    except Exception:
        pass

    return db

@st.cache_data(ttl=120)
def fetch_data_from_google():
    """Busca dados do Google Sheets com cache e limpeza."""
    try:
        db = get_conn()

        # Obras
        ws_o = db.worksheet("Obras")
        raw_o = ws_o.get_all_records()
        df_o = pd.DataFrame(raw_o)

        if df_o.empty:
            df_o = pd.DataFrame(columns=OBRAS_COLS)
        else:
            for c in OBRAS_COLS:
                if c not in df_o.columns:
                    df_o[c] = None

        # Financeiro
        ws_f = db.worksheet("Financeiro")
        try:
            ensure_financeiro_id(ws_f)
        except Exception:
            pass

        raw_f = ws_f.get_all_records()
        df_f = pd.DataFrame(raw_f)

        if df_f.empty:
            df_f = pd.DataFrame(columns=FIN_COLS)
        else:
            for c in FIN_COLS:
                if c not in df_f.columns:
                    df_f[c] = None

        # Checklist
        ws_c = ensure_checklist_sheet(db)
        raw_c = ws_c.get_all_records()
        df_c = pd.DataFrame(raw_c)
        if df_c.empty:
            df_c = pd.DataFrame(columns=CHECK_COLS)
        else:
            for c in CHECK_COLS:
                if c not in df_c.columns:
                    df_c[c] = None

        # Conversões / limpeza
        df_o["Valor Total"] = df_o["Valor Total"].apply(safe_float)
        if "Custo Previsto" in df_o.columns:
            df_o["Custo Previsto"] = df_o["Custo Previsto"].apply(safe_float)

        if "Cliente" in df_o.columns:
            df_o["Cliente"] = df_o["Cliente"].astype(str).str.strip()

        if "ID" in df_f.columns:
            df_f["ID"] = pd.to_numeric(df_f["ID"], errors="coerce").fillna(0).astype(int)
        df_f["Valor"] = df_f["Valor"].apply(safe_float)
        df_f["Data_DT"] = pd.to_datetime(df_f["Data"], errors="coerce")

        for col in ["Obra Vinculada", "Categoria", "Fornecedor", "Descrição", "Tipo"]:
            if col in df_f.columns:
                df_f[col] = df_f[col].astype(str).str.strip()

        if "ID" in df_c.columns:
            df_c["ID"] = pd.to_numeric(df_c["ID"], errors="coerce").fillna(0).astype(int)
        if "Obra" in df_c.columns:
            df_c["Obra"] = df_c["Obra"].astype(str).str.strip()
        if "Item" in df_c.columns:
            df_c["Item"] = df_c["Item"].astype(str).str.strip()
        if "Status" in df_c.columns:
            df_c["Status"] = df_c["Status"].astype(str).str.strip()

        df_c["Criado Em_DT"] = pd.to_datetime(df_c.get("Criado Em", None), errors="coerce")
        df_c["Concluído Em_DT"] = pd.to_datetime(df_c.get("Concluído Em", None), errors="coerce")

        return df_o, df_f, df_c

    except Exception as e:
        st.error(f"Erro DB: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# ==============================================================================
# 5. APP PRINCIPAL
# ==============================================================================
if "auth" not in st.session_state:
    st.session_state.auth = False

def password_entered():
    """Valida senha e carrega dados imediatamente para evitar delay"""
    if st.session_state["password_input"] == st.secrets["password"]:
        st.session_state.auth = True
        if "login_error" in st.session_state:
            del st.session_state["login_error"]

        try:
            df_o, df_f, df_c = fetch_data_from_google()
            st.session_state["data_obras"] = df_o
            st.session_state["data_fin"] = df_f
            st.session_state["data_chk"] = df_c
        except Exception as e:
            st.error(f"Erro ao sincronizar login: {e}")
    else:
        st.session_state.auth = False
        st.session_state.login_error = "Senha incorreta"

def logout():
    """Logout e limpeza"""
    st.session_state.auth = False
    if "password_input" in st.session_state:
        st.session_state["password_input"] = ""
    for k in ["data_obras", "data_fin", "data_chk"]:
        if k in st.session_state:
            del st.session_state[k]

# --- TELA DE LOGIN ---
if not st.session_state.auth:
    _, c2, _ = st.columns([1, 1, 1])
    with c2:
        st.markdown("<br><h2 style='text-align:center; color:#2D6A4F'>GESTOR PRO</h2>", unsafe_allow_html=True)
        if st.session_state.get("login_error"):
            st.error(st.session_state["login_error"])
        st.text_input("Senha", type="password", key="password_input", on_change=password_entered)
        st.button("ENTRAR", use_container_width=True, on_click=password_entered)
    st.stop()

# ==============================================================================
# 6. BARRA LATERAL
# ==============================================================================
with st.sidebar:
    st.markdown("""
        <div style='text-align: left; margin-bottom: 20px;'>
            <h1 style='color: #2D6A4F; font-size': 24px; margin-bottom: 0px;'>GESTOR PRO</h1>
            <p style='color: gray; font-size: 12px; margin-top: 0px;'>Incorporação & Obras</p>
        </div>
    """, unsafe_allow_html=True)

    sel = option_menu(
        menu_title=None,
        options=["Dashboard", "Financeiro", "Obras"],
        icons=["pie-chart-fill", "wallet-fill", "building-fill"],
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "#2D6A4F", "font-size": "16px"},
            "nav-link": {"font-size": "14px", "text-align": "left", "margin": "5px", "--hover-color": "#eee"},
            "nav-link-selected": {"background-color": "#2D6A4F", "color": "white"},
        }
    )

    st.write("")
    st.markdown("---")

    col_p1, col_p2 = st.columns([1, 4])
    with col_p1:
        st.markdown("<h2 style='text-align: center; margin: 0;'>👤</h2>", unsafe_allow_html=True)
    with col_p2:
        st.caption("Logado como:")
        st.markdown("**Administrador**")

    st.write("")
    st.button("🚪 Sair do Sistema", on_click=logout, use_container_width=True)

    st.markdown("""
        <div style='margin-top: 30px; text-align: center;'>
            <p style='color: #adb5bd; font-size: 10px;'>v1.4.0 • © 2026 Gestor Pro</p>
        </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# 7. GESTÃO DE DADOS (CACHE)
# ==============================================================================
if ("data_obras" not in st.session_state) or ("data_fin" not in st.session_state) or ("data_chk" not in st.session_state):
    with st.spinner("Sincronizando base de dados..."):
        try:
            df_obras, df_fin, df_chk = fetch_data_from_google()
            st.session_state["data_obras"] = df_obras
            st.session_state["data_fin"] = df_fin
            st.session_state["data_chk"] = df_chk
        except Exception as e:
            st.error(f"Falha na conexão: {e}")
            st.stop()
else:
    df_obras = st.session_state["data_obras"]
    df_fin = st.session_state["data_fin"]
    df_chk = st.session_state["data_chk"]

lista_obras = sorted(df_obras["Cliente"].unique().tolist()) if not df_obras.empty else []

# ==============================================================================
# 8. CONTEÚDO DAS PÁGINAS
# ==============================================================================

# --- DASHBOARD ---
if sel == "Dashboard":
    import plotly.express as px

    c_tit, c_sel, c_btn = st.columns([1.5, 2, 1])
    with c_tit:
        st.title("Visão Geral")
    with c_sel:
        if lista_obras:
            opcoes = ["Visão Geral (Todas as Obras)"] + lista_obras
            escopo = st.selectbox("Escopo", opcoes, label_visibility="collapsed")
        else:
            st.warning("Cadastre uma obra.")
            st.stop()
    with c_btn:
        if st.button("🔄 Atualizar Dados", use_container_width=True):
            st.cache_data.clear()
            for k in ["data_obras", "data_fin", "data_chk"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

    if escopo == "Visão Geral (Todas as Obras)":
        vgv = df_obras["Valor Total"].sum()
        df_show = df_fin[df_fin["Tipo"].astype(str).str.contains("Saída|Despesa", case=False, na=False)].copy()
        label_btn_pdf = "⬇️ BAIXAR PDF (PORTFÓLIO CONSOLIDADO)"
    else:
        row = df_obras[df_obras["Cliente"] == escopo].iloc[0]
        vgv = row["Valor Total"]
        df_show = df_fin[
            (df_fin["Obra Vinculada"] == escopo) &
            (df_fin["Tipo"].astype(str).str.contains("Saída|Despesa", case=False, na=False))
        ].copy()
        label_btn_pdf = f"⬇️ BAIXAR RELATÓRIO PDF: {escopo.upper()}"

    custos = df_show["Valor"].sum()
    lucro = vgv - custos
    roi = (lucro / custos * 100) if custos > 0 else 0
    perc = (custos / vgv) if vgv > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("VGV Total", fmt_moeda(vgv))
    k2.metric("Custos", fmt_moeda(custos), delta=f"{perc * 100:.1f}%", delta_color="inverse")
    k3.metric("Lucro", fmt_moeda(lucro))
    k4.metric("ROI", f"{roi:.1f}%")

    g1, g2 = st.columns([2, 1])
    with g1:
        st.subheader("Evolução de Custos")
        if not df_show.empty:
            df_ev = df_show.sort_values("Data_DT")
            df_ev["Acumulado"] = df_ev["Valor"].cumsum()
            fig = px.area(df_ev, x="Data_DT", y="Acumulado", color_discrete_sequence=["#2D6A4F"])
            fig.update_layout(plot_bgcolor="white", margin=dict(t=10, l=10, r=10, b=10), height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados")
    with g2:
        st.subheader("Categorias")
        if not df_show.empty:
            df_cat = df_show.groupby("Categoria", as_index=False)["Valor"].sum()
            fig2 = px.pie(df_cat, values="Valor", names="Categoria", hole=0.6, color_discrete_sequence=px.colors.qualitative.Bold)
            fig2.update_layout(showlegend=False, margin=dict(t=0, l=0, r=0, b=0), height=200)
            st.plotly_chart(fig2, use_container_width=True)
            st.dataframe(
                df_cat.sort_values("Valor", ascending=False).head(3),
                use_container_width=True,
                hide_index=True,
                column_config={"Valor": st.column_config.NumberColumn(format="R$ %.2f")}
            )
        else:
            st.info("Sem dados")

    st.markdown("### Lançamentos")
    if not df_show.empty:
        cols_view = ["Data", "Categoria", "Descrição", "Valor"]
        if "Fornecedor" in df_show.columns:
            cols_view.insert(3, "Fornecedor")

        df_tab = df_show[cols_view].sort_values("Data", ascending=False)
        st.dataframe(
            df_tab,
            use_container_width=True,
            hide_index=True,
            height=250,
            column_config={"Valor": st.column_config.NumberColumn(format="R$ %.2f")}
        )

        st.write("")
        st.markdown("---")

        dmin = df_show["Data_DT"].min().strftime("%d/%m/%Y")
        dmax = df_show["Data_DT"].max().strftime("%d/%m/%Y")
        per_str = f"De {dmin} até {dmax}"

        pdf_data = gerar_pdf_empresarial(
            escopo, per_str, vgv, custos, lucro, roi,
            df_cat if 'df_cat' in locals() else pd.DataFrame(),
            df_tab
        )

        st.download_button(
            label=label_btn_pdf,
            data=pdf_data,
            file_name=f"Relatorio_{escopo}_{date.today()}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

# --- FINANCEIRO ---
elif sel == "Financeiro":
    st.title("Financeiro")

    if st.session_state.get("sucesso_fin"):
        st.success("✅ Lançamento realizado com sucesso!", icon="✅")
        st.session_state["k_fin_data"] = date.today()
        st.session_state["k_fin_tipo"] = "Saída (Despesa)"
        st.session_state["k_fin_cat"] = ""
        st.session_state["k_fin_obra"] = ""
        st.session_state["k_fin_valor"] = 0.0
        st.session_state["k_fin_desc"] = ""
        st.session_state["k_fin_forn"] = ""
        st.session_state["sucesso_fin"] = False

    if "k_fin_data" not in st.session_state:
        st.session_state.k_fin_data = date.today()
    if "k_fin_tipo" not in st.session_state:
        st.session_state.k_fin_tipo = "Saída (Despesa)"
    if "k_fin_cat" not in st.session_state:
        st.session_state.k_fin_cat = ""
    if "k_fin_obra" not in st.session_state:
        st.session_state.k_fin_obra = ""
    if "k_fin_valor" not in st.session_state:
        st.session_state.k_fin_valor = 0.0
    if "k_fin_desc" not in st.session_state:
        st.session_state.k_fin_desc = ""
    if "k_fin_forn" not in st.session_state:
        st.session_state.k_fin_forn = ""

    with st.expander("Novo Lançamento", expanded=True):
        with st.form("ffin", clear_on_submit=False):

            c_row1_1, c_row1_2, c_row1_3 = st.columns([1, 1, 1])
            with c_row1_1:
                dt = st.date_input("Data", value=st.session_state.k_fin_data, key="k_fin_data")
            with c_row1_2:
                tp = st.selectbox("Tipo", ["Saída (Despesa)", "Entrada"], key="k_fin_tipo")
            with c_row1_3:
                vl = st.number_input("Valor R$ *", min_value=0.0, format="%.2f", step=100.0, value=st.session_state.k_fin_valor, key="k_fin_valor_input")

            c_row2_1, c_row2_2 = st.columns([1, 1])
            with c_row2_1:
                opcoes_obras = [""] + lista_obras
                ob = st.selectbox("Obra *", opcoes_obras, key="k_fin_obra")
            with c_row2_2:
                opcoes_cats = [""] + CATS
                ct = st.selectbox("Categoria *", opcoes_cats, key="k_fin_cat")

            c_row3_1, c_row3_2 = st.columns([1, 1])
            with c_row3_1:
                fn = st.text_input("Fornecedor", value=st.session_state.k_fin_forn, key="k_fin_forn", placeholder="Obrigatório se Categoria = Material")
            with c_row3_2:
                dc = st.text_input("Descrição *", value=st.session_state.k_fin_desc, key="k_fin_desc", placeholder="Detalhes do gasto")

            st.write("")
            submitted_fin = st.form_submit_button("Salvar Lançamento", use_container_width=True)

            if submitted_fin:
                st.session_state.k_fin_valor = vl
                erros = []
                if not ob or ob == "":
                    erros.append("Selecione a Obra Vinculada.")
                if not ct or ct == "":
                    erros.append("Selecione a Categoria.")
                if vl <= 0:
                    erros.append("O Valor deve ser maior que zero.")
                if not dc.strip():
                    erros.append("A Descrição é obrigatória.")

                if ct == "Material" and not fn.strip():
                    erros.append("Para a categoria 'Material', o campo Fornecedor é obrigatório.")

                if erros:
                    st.error("⚠️ Atenção:")
                    for e in erros:
                        st.caption(f"- {e}")
                else:
                    try:
                        conn = get_conn()
                        ws_fin = conn.worksheet("Financeiro")
                        ensure_financeiro_id(ws_fin)

                        if not df_fin.empty and "ID" in df_fin.columns:
                            ids_exist = pd.to_numeric(df_fin["ID"], errors="coerce").fillna(0)
                            new_id = int(ids_exist.max()) + 1
                        else:
                            new_id = 1

                        ws_fin.append_row([
                            new_id,
                            dt.strftime("%Y-%m-%d"),
                            tp,
                            ct.strip(),
                            dc.strip(),
                            float(vl),
                            ob.strip(),
                            fn.strip()
                        ])

                        if "data_fin" in st.session_state:
                            del st.session_state["data_fin"]
                        st.cache_data.clear()

                        st.session_state["sucesso_fin"] = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")

    st.markdown("---")
    st.markdown("### 🔍 Consultar Lançamentos")

    if not df_fin.empty:
        df_view = df_fin.copy()

        with st.expander("Filtros de Busca", expanded=True):
            c_filter1, c_filter2 = st.columns(2)

            with c_filter1:
                opcoes_filtro_obra = ["Todas as Obras"] + lista_obras
                filtro_obra = st.selectbox("Filtrar por Obra", options=opcoes_filtro_obra)

            with c_filter2:
                opcoes_filtro_cat = ["Todas as Categorias"] + CATS
                filtro_cat = st.selectbox("Filtrar por Categoria", options=opcoes_filtro_cat)

        if filtro_obra != "Todas as Obras":
            df_view = df_view[df_view["Obra Vinculada"].astype(str) == str(filtro_obra)]

        if filtro_cat != "Todas as Categorias":
            df_view = df_view[df_view["Categoria"].astype(str) == str(filtro_cat)]

        total_filtrado = df_view["Valor"].sum()
        count_filtrado = len(df_view)

        st.caption(f"Exibindo **{count_filtrado}** lançamentos | Total Filtrado: **{fmt_moeda(total_filtrado)}**")

        # Tabela editável (com exclusão)
        cols_order = ["ID", "Data", "Tipo", "Obra Vinculada", "Categoria", "Fornecedor", "Descrição", "Valor"]
        for c in cols_order:
            if c not in df_view.columns:
                df_view[c] = ""

        df_to_edit = df_view[cols_order].copy()
        df_to_edit["ID"] = pd.to_numeric(df_to_edit["ID"], errors="coerce").fillna(0).astype(int)
        df_to_edit["Data"] = pd.to_datetime(df_to_edit["Data"], errors="coerce").dt.date
        df_to_edit["Valor"] = pd.to_numeric(df_to_edit["Valor"], errors="coerce").fillna(0.0)

        df_to_edit.insert(1, "Excluir", False)

        st.info("🧾 **Como excluir:** marque **🗑️ Excluir?** na linha desejada e depois clique em **💾 SALVAR** (com senha).")

        edited_df = st.data_editor(
            df_to_edit,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            disabled=["ID"],
            height=360,
            column_config={
                "ID": st.column_config.NumberColumn("#", width=55),
                "Excluir": st.column_config.CheckboxColumn("🗑️ Excluir?", help="Marque para excluir e clique em SALVAR", width=90),
                "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY", required=True, width=110),
                "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Saída (Despesa)", "Entrada"], required=True, width=140),
                "Obra Vinculada": st.column_config.SelectboxColumn("Obra", options=[""] + lista_obras, required=True, width=220),
                "Categoria": st.column_config.SelectboxColumn("Categoria", options=[""] + CATS, required=True, width=190),
                "Fornecedor": st.column_config.TextColumn("Fornecedor", width=160),
                "Descrição": st.column_config.TextColumn("Descrição", width="large", required=True),
                "Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f", min_value=0, width=120),
            }
        )

        def _norm_fin(df):
            d = df.copy()
            d["Data"] = d["Data"].astype(str)
            d["Valor"] = pd.to_numeric(d["Valor"], errors="coerce").fillna(0.0).astype(float)
            for c in ["Tipo", "Obra Vinculada", "Categoria", "Fornecedor", "Descrição"]:
                d[c] = d[c].astype(str).fillna("").str.strip()
            d["Excluir"] = d["Excluir"].astype(bool)
            d["ID"] = pd.to_numeric(d["ID"], errors="coerce").fillna(0).astype(int)
            return d

        has_changes = not _norm_fin(edited_df).equals(_norm_fin(df_to_edit))

        st.write("")
        if has_changes:
            with st.container(border=True):
                c_alert, c_pwd, c_btn = st.columns([2, 1.5, 1])
                with c_alert:
                    st.warning("⚠️ Alterações pendentes (edição/exclusão). Confirme para salvar.", icon="⚠️")
                with c_pwd:
                    pwd_confirm = st.text_input("Senha", type="password", placeholder="Senha ADM", label_visibility="collapsed")
                with c_btn:
                    if st.button("💾 SALVAR", type="primary", use_container_width=True):
                        if pwd_confirm != st.secrets["password"]:
                            st.toast("Senha incorreta!", icon="⛔")
                        else:
                            # validações simples
                            erros = []
                            for _, r in edited_df.iterrows():
                                if bool(r.get("Excluir")):
                                    continue
                                obra = str(r.get("Obra Vinculada", "")).strip()
                                cat = str(r.get("Categoria", "")).strip()
                                desc = str(r.get("Descrição", "")).strip()
                                tp2 = str(r.get("Tipo", "")).strip()
                                val = float(pd.to_numeric(r.get("Valor", 0), errors="coerce") or 0)

                                if not obra:
                                    erros.append(f"ID {int(r['ID'])}: selecione a Obra.")
                                if not cat:
                                    erros.append(f"ID {int(r['ID'])}: selecione a Categoria.")
                                if not tp2:
                                    erros.append(f"ID {int(r['ID'])}: selecione o Tipo.")
                                if not desc:
                                    erros.append(f"ID {int(r['ID'])}: Descrição é obrigatória.")
                                if val <= 0:
                                    erros.append(f"ID {int(r['ID'])}: Valor deve ser > 0.")
                                forn = str(r.get("Fornecedor", "")).strip()
                                if cat == "Material" and not forn:
                                    erros.append(f"ID {int(r['ID'])}: Fornecedor é obrigatório para 'Material'.")

                            if erros:
                                st.error("⚠️ Corrija antes de salvar:")
                                for e in erros:
                                    st.caption(f"- {e}")
                            else:
                                try:
                                    conn = get_conn()
                                    ws_fin = conn.worksheet("Financeiro")
                                    ensure_financeiro_id(ws_fin)
                                    headers_fin = ws_fin.row_values(1)
                                    col_id = headers_fin.index("ID") + 1

                                    # Excluir (de baixo para cima)
                                    rows_del = []
                                    df_del = edited_df[edited_df["Excluir"] == True].copy()
                                    for _, rr in df_del.iterrows():
                                        idv = int(rr["ID"])
                                        cell = ws_fin.find(str(idv), in_column=col_id)
                                        if cell:
                                            rows_del.append(cell.row)

                                    for rr in sorted(rows_del, reverse=True):
                                        ws_fin.delete_rows(rr)

                                    # Atualizar
                                    from gspread.utils import rowcol_to_a1
                                    upd_count = 0
                                    df_upd = edited_df[edited_df["Excluir"] == False].copy()

                                    for _, rr in df_upd.iterrows():
                                        idv = int(rr["ID"])
                                        cell = ws_fin.find(str(idv), in_column=col_id)
                                        if not cell:
                                            continue

                                        def _val(h):
                                            if h == "ID":
                                                return idv
                                            if h == "Data":
                                                v = rr.get("Data", "")
                                                if isinstance(v, (date, datetime)):
                                                    return v.strftime("%Y-%m-%d")
                                                return str(v)[:10]
                                            if h == "Valor":
                                                return float(safe_float(rr.get("Valor", 0)))
                                            v = rr.get(h, "")
                                            if v is None or (isinstance(v, float) and pd.isna(v)):
                                                return ""
                                            return str(v).strip()

                                        update_values = [_val(h) for h in headers_fin]

                                        start = rowcol_to_a1(cell.row, 1)
                                        end = rowcol_to_a1(cell.row, len(headers_fin))
                                        ws_fin.update(f"{start}:{end}", [update_values])
                                        upd_count += 1

                                    for k in ["data_fin"]:
                                        if k in st.session_state:
                                            del st.session_state[k]
                                    st.cache_data.clear()

                                    st.toast(f"✅ Salvo! {upd_count} atualizações • {len(rows_del)} exclusões", icon="✅")
                                    st.rerun()

                                except Exception as e:
                                    st.error(f"Erro ao salvar Financeiro: {e}")
        else:
            st.caption("💡 Edite a tabela acima. Marque 🗑️ para excluir. O botão SALVAR aparece automaticamente.")

        st.write("")
        st.markdown("---")

        if not df_view.empty:
            dmin = df_view["Data_DT"].min().strftime("%d/%m/%Y")
            dmax = df_view["Data_DT"].max().strftime("%d/%m/%Y")
            per_str = f"De {dmin} até {dmax}"
            escopo_pdf = filtro_obra if filtro_obra != "Todas as Obras" else "Visão Geral (Filtro)"

            cols_pdf = ["Data", "Categoria", "Descrição", "Valor"]
            df_pdf = edited_df[edited_df["Excluir"] == False].copy()
            for c in cols_pdf:
                if c not in df_pdf.columns:
                    df_pdf[c] = ""
            df_pdf = df_pdf[cols_pdf].sort_values("Data", ascending=False)

            pdf_data = gerar_pdf_empresarial(
                escopo_pdf, per_str,
                0.0,
                float(df_pdf["Valor"].apply(safe_float).sum()) if "Valor" in df_pdf.columns else 0.0,
                0.0,
                0.0,
                pd.DataFrame(),
                df_pdf
            )

            st.download_button(
                label="⬇️ BAIXAR RELATÓRIO DA CONSULTA (PDF)",
                data=pdf_data,
                file_name=f"Extrato_{date.today()}.pdf",
                mime="application/pdf",
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
        st.session_state["k_ob_nome"] = ""
        st.session_state["k_ob_end"] = ""
        st.session_state["k_ob_area_c"] = 0.0
        st.session_state["k_ob_area_t"] = 0.0
        st.session_state["k_ob_quartos"] = 0
        st.session_state["k_ob_status"] = "Projeto"
        st.session_state["k_ob_custo"] = 0.0
        st.session_state["k_ob_vgv"] = 0.0
        st.session_state["k_ob_prazo"] = ""
        st.session_state["sucesso_obra"] = False

    # Session defaults
    if "k_ob_nome" not in st.session_state: st.session_state.k_ob_nome = ""
    if "k_ob_end" not in st.session_state: st.session_state.k_ob_end = ""
    if "k_ob_area_c" not in st.session_state: st.session_state.k_ob_area_c = 0.0
    if "k_ob_area_t" not in st.session_state: st.session_state.k_ob_area_t = 0.0
    if "k_ob_quartos" not in st.session_state: st.session_state.k_ob_quartos = 0
    if "k_ob_status" not in st.session_state: st.session_state.k_ob_status = "Projeto"
    if "k_ob_custo" not in st.session_state: st.session_state.k_ob_custo = 0.0
    if "k_ob_vgv" not in st.session_state: st.session_state.k_ob_vgv = 0.0
    if "k_ob_prazo" not in st.session_state: st.session_state.k_ob_prazo = ""
    if "k_ob_data" not in st.session_state: st.session_state.k_ob_data = date.today()

    with st.expander("➕ Novo Cadastro (Clique para expandir)", expanded=False):
        with st.form("f_obra_completa", clear_on_submit=False):
            st.markdown("#### 1. Identificação")
            c1, c2 = st.columns([3, 2])
            with c1:
                nome_obra = st.text_input("Nome do Empreendimento *", placeholder="Ex: Res. Vila Verde - Casa 04",
                                          value=st.session_state.k_ob_nome, key="k_ob_nome")
            with c2:
                endereco = st.text_input("Endereço *", placeholder="Rua, Bairro...",
                                         value=st.session_state.k_ob_end, key="k_ob_end")

            st.markdown("#### 2. Características Físicas (Produto)")
            c4, c5, c6, c7 = st.columns(4)
            with c4:
                area_const = st.number_input("Área Construída (m²)", min_value=0.0, format="%.2f",
                                             value=st.session_state.k_ob_area_c, key="k_ob_area_c")
            with c5:
                area_terr = st.number_input("Área Terreno (m²)", min_value=0.0, format="%.2f",
                                            value=st.session_state.k_ob_area_t, key="k_ob_area_t")
            with c6:
                quartos = st.number_input("Qtd. Quartos", min_value=0, step=1,
                                          value=st.session_state.k_ob_quartos, key="k_ob_quartos")
            with c7:
                status = st.selectbox("Fase Atual",
                                      ["Projeto", "Fundação", "Alvenaria", "Acabamento", "Concluída", "Vendida"],
                                      key="k_ob_status")

            st.markdown("#### 3. Viabilidade Financeira e Prazos")
            c8, c9, c10, c11 = st.columns(4)
            with c8:
                custo_previsto = st.number_input("Orçamento (Custo) *", min_value=0.0, format="%.2f", step=1000.0,
                                                 value=st.session_state.k_ob_custo, key="k_ob_custo_input")
            with c9:
                valor_venda = st.number_input("VGV (Venda) *", min_value=0.0, format="%.2f", step=1000.0,
                                              value=st.session_state.k_ob_vgv, key="k_ob_vgv_input")
            with c10:
                data_inicio = st.date_input("Início da Obra", value=st.session_state.k_ob_data, key="k_ob_data")
            with c11:
                prazo_entrega = st.text_input("Prazo / Entrega *", placeholder="Ex: dez/2025",
                                              value=st.session_state.k_ob_prazo, key="k_ob_prazo")

            if valor_venda > 0 and custo_previsto > 0:
                margem_proj = ((valor_venda - custo_previsto) / custo_previsto) * 100
                lucro_proj = valor_venda - custo_previsto
                st.info(f"💰 **Projeção:** Lucro de **{fmt_moeda(lucro_proj)}** (Margem: **{margem_proj:.1f}%**)")

            st.markdown("---")
            st.caption("(*) Campos Obrigatórios")
            submitted = st.form_submit_button("✅ SALVAR PROJETO", use_container_width=True)

            if submitted:
                st.session_state.k_ob_custo = custo_previsto
                st.session_state.k_ob_vgv = valor_venda
                st.session_state.k_ob_area_c = area_const
                st.session_state.k_ob_area_t = area_terr

                erros = []
                if not nome_obra.strip(): erros.append("O 'Nome do Empreendimento' é obrigatório.")
                if not endereco.strip(): erros.append("O 'Endereço' é obrigatório.")
                if not prazo_entrega.strip(): erros.append("O 'Prazo' é obrigatório.")
                if valor_venda <= 0: erros.append("O 'Valor de Venda (VGV)' deve ser maior que zero.")
                if custo_previsto <= 0: erros.append("O 'Orçamento Previsto' deve ser maior que zero.")
                if area_const <= 0 and area_terr <= 0: erros.append("Preencha ao menos a Área Construída ou do Terreno.")

                if erros:
                    st.error("⚠️ Não foi possível salvar. Verifique os campos:")
                    for e in erros: st.markdown(f"- {e}")
                else:
                    try:
                        conn = get_conn()
                        ws = conn.worksheet("Obras")
                        ids_existentes = pd.to_numeric(df_obras["ID"], errors="coerce").fillna(0)
                        novo_id = int(ids_existentes.max()) + 1 if not ids_existentes.empty else 1
                        ws.append_row([
                            novo_id, nome_obra.strip(), endereco.strip(), status, float(valor_venda),
                            data_inicio.strftime("%Y-%m-%d"), prazo_entrega.strip(),
                            float(area_const), float(area_terr), int(quartos), float(custo_previsto)
                        ])

                        for k in ["data_obras", "data_chk"]:
                            if k in st.session_state: del st.session_state[k]
                        st.cache_data.clear()

                        st.session_state["sucesso_obra"] = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro no Google Sheets: {e}")

    # ----------------------------
    # CARTEIRA DE OBRAS (Editor)
    # ----------------------------
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

        edited_df = st.data_editor(
            df_to_edit,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            disabled=["ID"],
            column_config={
                "ID": st.column_config.NumberColumn("#", width=40),
                "Cliente": st.column_config.TextColumn("Empreendimento", width="large", required=True),
                "Status": st.column_config.SelectboxColumn("Fase", options=["Projeto", "Fundação", "Alvenaria", "Acabamento", "Concluída", "Vendida"], required=True, width="medium"),
                "Prazo": st.column_config.TextColumn("Entrega", width="small"),
                "Valor Total": st.column_config.NumberColumn("VGV", format="R$ %.0f", min_value=0),
                "Custo Previsto": st.column_config.NumberColumn("Custo", format="R$ %.0f", min_value=0),
                "Area Construida": st.column_config.NumberColumn("Área", format="%.0f m²"),
                "Area Terreno": st.column_config.NumberColumn("Terr.", format="%.0f m²"),
                "Quartos": st.column_config.NumberColumn("Qts", min_value=0, step=1, width="small"),
            }
        )

        st.write("")
        has_changes = not edited_df.equals(df_to_edit)
        if has_changes:
            with st.container(border=True):
                c_alert, c_pwd, c_btn = st.columns([2, 1.5, 1])
                with c_alert:
                    st.warning("⚠️ Alterações pendentes. Confirme para salvar.", icon="⚠️")
                with c_pwd:
                    pwd_confirm = st.text_input("Senha", type="password", placeholder="Senha ADM", label_visibility="collapsed", key="pwd_obras_save")
                with c_btn:
                    if st.button("💾 SALVAR", type="primary", use_container_width=True):
                        if pwd_confirm == st.secrets["password"]:
                            try:
                                conn = get_conn()
                                ws = conn.worksheet("Obras")
                                ws_fin = conn.worksheet("Financeiro")
                                ws_chk = ensure_checklist_sheet(conn)

                                with st.spinner("Salvando alterações e sincronizando Financeiro + Checklist..."):
                                    for _, row in edited_df.iterrows():
                                        id_obra = row["ID"]
                                        found_cell = ws.find(str(id_obra), in_column=1)
                                        if not found_cell:
                                            continue

                                        original_row = df_obras[df_obras["ID"] == id_obra].iloc[0]
                                        old_name = str(original_row["Cliente"]).strip()
                                        new_name = str(row["Cliente"]).strip()

                                        # Cascata: Financeiro
                                        if old_name != new_name and old_name != "":
                                            headers_fin = ws_fin.row_values(1)
                                            try:
                                                col_idx_fin = headers_fin.index("Obra Vinculada") + 1
                                            except ValueError:
                                                col_idx_fin = 7
                                            cells_to_update = ws_fin.findall(old_name, in_column=col_idx_fin)
                                            for cell in cells_to_update:
                                                cell.value = new_name
                                            if cells_to_update:
                                                ws_fin.update_cells(cells_to_update)
                                                st.toast(f"♻️ Financeiro: {len(cells_to_update)} lançamentos atualizados para '{new_name}'")

                                        # Cascata: Checklist
                                        if old_name != new_name and old_name != "":
                                            headers_chk = ws_chk.row_values(1)
                                            try:
                                                col_idx_chk = headers_chk.index("Obra") + 1
                                                cells_chk = ws_chk.findall(old_name, in_column=col_idx_chk)
                                                for cell in cells_chk:
                                                    cell.value = new_name
                                                if cells_chk:
                                                    ws_chk.update_cells(cells_chk)
                                                    st.toast(f"✅ Checklist: {len(cells_chk)} itens vinculados atualizados para '{new_name}'")
                                            except Exception:
                                                pass

                                        # Atualiza Obras
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

                                    for k in ["data_obras", "data_fin", "data_chk"]:
                                        if k in st.session_state: del st.session_state[k]
                                    st.cache_data.clear()

                                    st.session_state["sucesso_obra"] = True
                                    st.rerun()

                            except Exception as e:
                                st.error(f"Erro ao salvar: {e}")
                        else:
                            st.toast("Senha incorreta!", icon="⛔")
        else:
            st.caption("💡 Edite diretamente na tabela acima. O botão de salvar aparecerá automaticamente.")
    else:
        st.info("Nenhuma obra cadastrada.")

    # ==============================================================================
    # ✅ CHECKLIST POR OBRA (NOVO)
    # ==============================================================================
    st.markdown("---")
    st.subheader("✅ Checklist por Obra")

    if not lista_obras:
        st.info("Cadastre uma obra para usar o checklist.")
    else:
        colA, colB = st.columns([2, 1])
        with colA:
            obra_chk = st.selectbox("Selecione a Obra", options=lista_obras, key="chk_obra_sel")
        with colB:
            if st.button("🔄 Atualizar Checklist", use_container_width=True):
                st.cache_data.clear()
                if "data_chk" in st.session_state:
                    del st.session_state["data_chk"]
                st.rerun()

        df_chk_all = df_chk.copy() if df_chk is not None else pd.DataFrame(columns=CHECK_COLS)
        for c in CHECK_COLS:
            if c not in df_chk_all.columns:
                df_chk_all[c] = ""

        df_chk_obra = df_chk_all[df_chk_all["Obra"].astype(str).str.strip() == str(obra_chk).strip()].copy()
        if "ID" in df_chk_obra.columns:
            df_chk_obra["ID"] = pd.to_numeric(df_chk_obra["ID"], errors="coerce").fillna(0).astype(int)

        total_itens = len(df_chk_obra)
        concluidos = int((df_chk_obra["Status"].astype(str).str.strip() == "Concluído").sum()) if total_itens > 0 else 0
        progresso = (concluidos / total_itens) if total_itens > 0 else 0.0

        m1, m2, m3 = st.columns(3)
        m1.metric("Itens", total_itens)
        m2.metric("Concluídos", concluidos)
        m3.metric("Progresso", f"{progresso*100:.0f}%")
        st.progress(progresso)

        with st.expander("➕ Adicionar Item ao Checklist", expanded=True):
            with st.form("form_add_chk", clear_on_submit=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    novo_item = st.text_input("Item *", placeholder="Ex.: Cartório: ITBI pago")
                with c2:
                    novo_status = st.selectbox("Status", CHECK_STATUS, index=0)
                obs = st.text_input("Observação", placeholder="Opcional")
                add_submit = st.form_submit_button("Adicionar", use_container_width=True)

                if add_submit:
                    erros = []
                    if not str(novo_item).strip():
                        erros.append("O campo Item é obrigatório.")

                    if erros:
                        st.error("⚠️ Verifique:")
                        for e in erros:
                            st.caption(f"- {e}")
                    else:
                        try:
                            conn = get_conn()
                            ws_chk = ensure_checklist_sheet(conn)
                            headers = ws_chk.row_values(1)
                            col_id = headers.index("ID") + 1

                            # novo ID
                            if df_chk_all is not None and not df_chk_all.empty and "ID" in df_chk_all.columns:
                                mx = int(pd.to_numeric(df_chk_all["ID"], errors="coerce").fillna(0).max())
                                new_id = mx + 1
                            else:
                                new_id = 1

                            criado_em = date.today().strftime("%Y-%m-%d")
                            concluido_em = date.today().strftime("%Y-%m-%d") if novo_status == "Concluído" else ""

                            row_dict = {
                                "ID": new_id,
                                "Obra": str(obra_chk).strip(),
                                "Item": str(novo_item).strip(),
                                "Status": str(novo_status).strip(),
                                "Criado Em": criado_em,
                                "Concluído Em": concluido_em,
                                "Observação": str(obs).strip(),
                            }
                            row_to_append = [row_dict.get(h, "") for h in headers]
                           

                            ws_chk.append_row(row_to_append)

                            if "data_chk" in st.session_state:
                                del st.session_state["data_chk"]
                            st.cache_data.clear()

                            st.toast("✅ Item adicionado!", icon="✅")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao adicionar checklist: {e}")

            st.write("")
            if st.button("✨ Adicionar Checklist Padrão (somente itens que faltam)", use_container_width=True):
                try:
                    existentes = set(df_chk_obra["Item"].astype(str).str.strip().tolist()) if not df_chk_obra.empty else set()
                    novos = [x for x in CHECKLIST_PADRAO if x.strip() not in existentes]
                    if not novos:
                        st.info("Checklist padrão já está completo para esta obra.")
                    else:
                        conn = get_conn()
                        ws_chk = ensure_checklist_sheet(conn)
                        headers = ws_chk.row_values(1)

                        if df_chk_all is not None and not df_chk_all.empty and "ID" in df_chk_all.columns:
                            mx = int(pd.to_numeric(df_chk_all["ID"], errors="coerce").fillna(0).max())
                        else:
                            mx = 0

                        criado_em = date.today().strftime("%Y-%m-%d")
                        rows = []
                        for i, item in enumerate(novos, start=1):
                            rid = mx + i
                            row_dict = {
                                "ID": rid,
                                "Obra": str(obra_chk).strip(),
                                "Item": item.strip(),
                                "Status": "Pendente",
                                "Criado Em": criado_em,
                                "Concluído Em": "",
                                "Observação": "",
                            }
                            rows.append([row_dict.get(h, "") for h in headers])

                        ws_chk.append_rows(rows)

                        if "data_chk" in st.session_state:
                            del st.session_state["data_chk"]
                        st.cache_data.clear()

                        st.toast(f"✅ {len(novos)} itens padrão adicionados!", icon="✅")
                        st.rerun()
                except Exception as e:
                    st.error(f"Erro ao inserir checklist padrão: {e}")

        st.markdown("### 🗂️ Itens do Checklist (Editar / Concluir / Excluir)")

        # prepara tabela editável
        if df_chk_obra.empty:
            st.info("Nenhum item ainda. Adicione acima.")
        else:
            df_edit = df_chk_obra.copy()

            # garantir colunas
            for c in CHECK_COLS:
                if c not in df_edit.columns:
                    df_edit[c] = ""

            # tipos
            df_edit["ID"] = pd.to_numeric(df_edit["ID"], errors="coerce").fillna(0).astype(int)
            df_edit["Criado Em"] = pd.to_datetime(df_edit["Criado Em"], errors="coerce").dt.date
            df_edit["Concluído Em"] = pd.to_datetime(df_edit["Concluído Em"], errors="coerce").dt.date

            df_edit.insert(1, "Excluir", False)

            st.info("🧾 Para excluir: marque **🗑️ Excluir?** e clique **💾 SALVAR** (com senha).")

            chk_editor = st.data_editor(
                df_edit[["ID", "Excluir", "Item", "Status", "Observação", "Criado Em", "Concluído Em"]].copy(),
                use_container_width=True,
                hide_index=True,
                num_rows="fixed",
                height=360,
                disabled=["ID", "Criado Em", "Concluído Em"],
                column_config={
                    "ID": st.column_config.NumberColumn("#", width=60),
                    "Excluir": st.column_config.CheckboxColumn("🗑️ Excluir?", width=95),
                    "Item": st.column_config.TextColumn("Item", width="large", required=True),
                    "Status": st.column_config.SelectboxColumn("Status", options=CHECK_STATUS, required=True, width=140),
                    "Observação": st.column_config.TextColumn("Observação", width="large"),
                    "Criado Em": st.column_config.DateColumn("Criado Em", format="DD/MM/YYYY", width=120),
                    "Concluído Em": st.column_config.DateColumn("Concluído Em", format="DD/MM/YYYY", width=130),
                }
            )

            def _norm_chk(df):
                d = df.copy()
                d["ID"] = pd.to_numeric(d["ID"], errors="coerce").fillna(0).astype(int)
                d["Excluir"] = d["Excluir"].astype(bool)
                d["Item"] = d["Item"].astype(str).fillna("").str.strip()
                d["Status"] = d["Status"].astype(str).fillna("").str.strip()
                d["Observação"] = d["Observação"].astype(str).fillna("").str.strip()
                # datas não mudam (disabled), mas normaliza para comparar
                if "Criado Em" in d.columns:
                    d["Criado Em"] = d["Criado Em"].astype(str)
                if "Concluído Em" in d.columns:
                    d["Concluído Em"] = d["Concluído Em"].astype(str)
                return d

            base_cmp = _norm_chk(df_edit[["ID", "Excluir", "Item", "Status", "Observação", "Criado Em", "Concluído Em"]].copy())
            edit_cmp = _norm_chk(chk_editor.copy())

            has_chk_changes = not edit_cmp.equals(base_cmp)

            if has_chk_changes:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1.5, 1])
                    with c1:
                        st.warning("⚠️ Alterações pendentes no checklist. Confirme para salvar.", icon="⚠️")
                    with c2:
                        pwd_chk = st.text_input("Senha", type="password", placeholder="Senha ADM", label_visibility="collapsed", key="pwd_chk_save")
                    with c3:
                        if st.button("💾 SALVAR CHECKLIST", type="primary", use_container_width=True):
                            if pwd_chk != st.secrets["password"]:
                                st.toast("Senha incorreta!", icon="⛔")
                            else:
                                # validações
                                erros = []
                                for _, r in chk_editor.iterrows():
                                    if bool(r.get("Excluir")):
                                        continue
                                    if not str(r.get("Item", "")).strip():
                                        erros.append(f"ID {int(r['ID'])}: Item obrigatório.")
                                    if str(r.get("Status", "")).strip() not in CHECK_STATUS:
                                        erros.append(f"ID {int(r['ID'])}: Status inválido.")
                                if erros:
                                    st.error("⚠️ Corrija antes de salvar:")
                                    for e in erros:
                                        st.caption(f"- {e}")
                                else:
                                    try:
                                        conn = get_conn()
                                        ws_chk = ensure_checklist_sheet(conn)
                                        headers = ws_chk.row_values(1)
                                        col_id = headers.index("ID") + 1

                                        # Excluir (de baixo pra cima)
                                        rows_del = []
                                        df_del = chk_editor[chk_editor["Excluir"] == True].copy()
                                        for _, rr in df_del.iterrows():
                                            idv = int(rr["ID"])
                                            cell = ws_chk.find(str(idv), in_column=col_id)
                                            if cell:
                                                rows_del.append(cell.row)
                                        for rr in sorted(rows_del, reverse=True):
                                            ws_chk.delete_rows(rr)

                                        # Atualizar
                                        from gspread.utils import rowcol_to_a1
                                        upd_count = 0

                                        for _, rr in chk_editor[chk_editor["Excluir"] == False].iterrows():
                                            idv = int(rr["ID"])
                                            cell = ws_chk.find(str(idv), in_column=col_id)
                                            if not cell:
                                                continue

                                            # pega estado original (pra auto data de conclusão)
                                            orig = df_chk_obra[df_chk_obra["ID"] == idv]
                                            old_status = str(orig["Status"].iloc[0]).strip() if not orig.empty else ""
                                            old_done = str(orig.get("Concluído Em", "").iloc[0]).strip() if (not orig.empty and "Concluído Em" in orig.columns) else ""

                                            new_status = str(rr.get("Status", "")).strip()

                                            # decide concluído em
                                            if new_status == "Concluído":
                                                if not old_done or old_done in ["NaT", "None", "nan"]:
                                                    done_date = date.today().strftime("%Y-%m-%d")
                                                else:
                                                    # mantém data existente
                                                    try:
                                                        done_date = pd.to_datetime(old_done, errors="coerce").strftime("%Y-%m-%d")
                                                    except Exception:
                                                        done_date = date.today().strftime("%Y-%m-%d")
                                            else:
                                                done_date = ""

                                            # criado em (mantém)
                                            created_val = ""
                                            try:
                                                created_val = pd.to_datetime(orig["Criado Em"].iloc[0], errors="coerce").strftime("%Y-%m-%d") if (not orig.empty) else date.today().strftime("%Y-%m-%d")
                                            except Exception:
                                                created_val = date.today().strftime("%Y-%m-%d")

                                            row_dict = {
                                                "ID": idv,
                                                "Obra": str(obra_chk).strip(),
                                                "Item": str(rr.get("Item", "")).strip(),
                                                "Status": new_status,
                                                "Criado Em": created_val,
                                                "Concluído Em": done_date,
                                                "Observação": str(rr.get("Observação", "")).strip(),
                                            }

                                            update_values = [row_dict.get(h, "") for h in headers]

                                            start = rowcol_to_a1(cell.row, 1)
                                            end = rowcol_to_a1(cell.row, len(headers))
                                            ws_chk.update(f"{start}:{end}", [update_values])
                                            upd_count += 1

                                        if "data_chk" in st.session_state:
                                            del st.session_state["data_chk"]
                                        st.cache_data.clear()

                                        st.toast(f"✅ Checklist salvo! {upd_count} atualizações • {len(rows_del)} exclusões", icon="✅")
                                        st.rerun()

                                    except Exception as e:
                                        st.error(f"Erro ao salvar checklist: {e}")
            else:
                st.caption("💡 Edite os itens acima. Marque 🗑️ para excluir. O botão de salvar aparece automaticamente.")
