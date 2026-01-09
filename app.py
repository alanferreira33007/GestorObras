import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import date, datetime, timedelta
from streamlit_option_menu import option_menu
import io
import random

# --- BIBLIOTECAS PDF (REPORTLAB) ---
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

# ==============================================================================
# 1. CONFIGURAÇÃO VISUAL (UI)
# ==============================================================================
st.set_page_config(
    page_title="GESTOR PRO | Incorporadora",
    layout="wide",
    page_icon="🏗️",
    initial_sidebar_state="expanded"
)

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
    
    [data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #e9ecef; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. FUNÇÕES HELPERS
# ==============================================================================
def fmt_moeda(valor):
    if pd.isna(valor) or valor == "": return "R$ 0,00"
    try:
        val = float(valor)
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return f"R$ {valor}"

def safe_float(x) -> float:
    if isinstance(x, (int, float)): return float(x)
    if x is None: return 0.0
    s = str(x).strip().replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try: return float(s)
    except: return 0.0

# ==============================================================================
# 3. MOTOR PDF (ENTERPRISE V5)
# ==============================================================================
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

def gerar_pdf_empresarial(escopo, periodo, vgv, custos, lucro, roi, df_cat, df_lanc):
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
    
    # --- 1. CABEÇALHO DINÂMICO ---
    if "Visão Geral" in escopo:
        titulo_principal = "RELATÓRIO DE PORTFÓLIO (CONSOLIDADO)"
    else:
        titulo_principal = f"RELATÓRIO INDIVIDUAL: {escopo.upper()}"
        
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
    
    # --- 2. RESUMO (KPIs) ---
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
    
    # --- 3. CATEGORIAS ---
    if not df_cat.empty:
        story.append(Paragraph("DISTRIBUIÇÃO POR CATEGORIA", style_h2))
        df_c = df_cat.copy()
        df_c["Valor"] = df_c["Valor"].apply(fmt_moeda)
        df_c["%"] = (df_cat["Valor"] / custos * 100).apply(lambda x: f"{x:.1f}%")
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
        
    # --- 4. EXTRATO FINANCEIRO ---
    story.append(Paragraph("EXTRATO DE LANÇAMENTOS", style_h2))
    
    if not df_lanc.empty:
        df_l = df_lanc.copy()
        df_l["Valor"] = df_l["Valor"].apply(fmt_moeda)
        cols_sel = ["Data", "Categoria", "Descrição", "Valor"]
        data_lanc = [cols_sel] + df_l[cols_sel].values.tolist()
        
        # LINHA DE TOTAL NA TABELA
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

    # --- 5. BLOCO DE TOTALIZAÇÃO FINAL (DESTAQUE) ---
    bloco_total = []
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
    bloco_total.append(t_total)
    story.append(KeepTogether(bloco_total))
    
    story.append(Spacer(1, 40))

    # --- 6. ASSINATURAS ---
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
# ATENÇÃO: Adicione as colunas novas manualmente no seu Google Sheets (Aba Obras)
OBRAS_COLS = [
    "ID", "Cliente", "Endereço", "Status", "Valor Total", 
    "Data Início", "Prazo", "Area Construida", "Area Terreno", 
    "Quartos", "Custo Previsto"
]
FIN_COLS   = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]
CATS       = ["Material", "Mão de Obra", "Serviços", "Administrativo", "Impostos", "Outros"]

@st.cache_resource
def get_conn():
    creds = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
    return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])).open("GestorObras_DB")

@st.cache_data(ttl=60)
def load_data():
    try:
        db = get_conn()
        ws_o = db.worksheet("Obras")
        raw_o = ws_o.get_all_records()
        df_o = pd.DataFrame(raw_o)
        
        if df_o.empty:
            df_o = pd.DataFrame(columns=OBRAS_COLS)
        else:
            # Garante que todas as colunas existem
            for c in OBRAS_COLS: 
                if c not in df_o.columns: df_o[c] = None
        
        ws_f = db.worksheet("Financeiro")
        raw_f = ws_f.get_all_records()
        df_f = pd.DataFrame(raw_f)

        if df_f.empty:
             df_f = pd.DataFrame(columns=FIN_COLS)
        else:
            for c in FIN_COLS:
                if c not in df_f.columns: df_f[c] = None
        
        # Tratamento de Tipos Numéricos
        df_o["Valor Total"] = df_o["Valor Total"].apply(safe_float)
        if "Custo Previsto" in df_o.columns:
            df_o["Custo Previsto"] = df_o["Custo Previsto"].apply(safe_float)
            
        df_f["Valor"] = df_f["Valor"].apply(safe_float)
        df_f["Data_DT"] = pd.to_datetime(df_f["Data"], errors="coerce")
        
        return df_o, df_f
    except Exception as e:
        st.error(f"Erro DB: {e}")
        return pd.DataFrame(), pd.DataFrame()

# ==============================================================================
# 5. APP PRINCIPAL
# ==============================================================================
if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    _, c2, _ = st.columns([1,1,1])
    with c2:
        st.markdown("<br><h2 style='text-align:center; color:#2D6A4F'>GESTOR PRO</h2>", unsafe_allow_html=True)
        pwd = st.text_input("Senha", type="password")
        if st.button("ENTRAR", use_container_width=True):
            if pwd == st.secrets["password"]: st.session_state.auth = True; st.rerun()
            else: st.error("Senha incorreta")
    st.stop()

df_obras, df_fin = load_data()
lista_obras = df_obras["Cliente"].unique().tolist() if not df_obras.empty else []

with st.sidebar:
    st.markdown("### 🏢 MENU")
    sel = option_menu(None, ["Dashboard", "Financeiro", "Obras"], icons=["graph-up", "wallet", "building"], default_index=0, styles={"nav-link-selected": {"background-color": "#2D6A4F"}})
    st.markdown("---")
    if st.button("Sair"): st.session_state.auth=False; st.rerun()

# --- DASHBOARD ---
if sel == "Dashboard":
    c_tit, c_sel, c_btn = st.columns([1.5, 2, 1])
    with c_tit: st.title("Visão Geral")
    with c_sel:
        if lista_obras:
            opcoes = ["Visão Geral (Todas as Obras)"] + lista_obras
            escopo = st.selectbox("Escopo", opcoes, label_visibility="collapsed")
        else: st.warning("Cadastre uma obra."); st.stop()
    with c_btn:
        if st.button("🔄 Atualizar Dados", use_container_width=True): st.cache_data.clear(); st.rerun()

    # Filtros
    if escopo == "Visão Geral (Todas as Obras)":
        vgv = df_obras["Valor Total"].sum()
        df_show = df_fin[df_fin["Tipo"].astype(str).str.contains("Saída|Despesa", case=False, na=False)].copy()
        label_btn_pdf = "⬇️ BAIXAR PDF (PORTFÓLIO CONSOLIDADO)"
    else:
        row = df_obras[df_obras["Cliente"] == escopo].iloc[0]
        vgv = row["Valor Total"]
        df_show = df_fin[(df_fin["Obra Vinculada"] == escopo) & (df_fin["Tipo"].astype(str).str.contains("Saída|Despesa", case=False, na=False))].copy()
        label_btn_pdf = f"⬇️ BAIXAR RELATÓRIO PDF: {escopo.upper()}"
    
    custos = df_show["Valor"].sum()
    lucro = vgv - custos
    roi = (lucro/custos*100) if custos > 0 else 0
    perc = (custos/vgv) if vgv > 0 else 0
    
    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("VGV Total", fmt_moeda(vgv))
    k2.metric("Custos", fmt_moeda(custos), delta=f"{perc*100:.1f}%", delta_color="inverse")
    k3.metric("Lucro", fmt_moeda(lucro))
    k4.metric("ROI", f"{roi:.1f}%")
    
    # Gráficos
    g1, g2 = st.columns([2,1])
    with g1:
        st.subheader("Evolução de Custos")
        if not df_show.empty:
            df_ev = df_show.sort_values("Data_DT")
            df_ev["Acumulado"] = df_ev["Valor"].cumsum()
            fig = px.area(df_ev, x="Data_DT", y="Acumulado", color_discrete_sequence=["#2D6A4F"])
            fig.update_layout(plot_bgcolor="white", margin=dict(t=10,l=10,r=10,b=10), height=300)
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("Sem dados")
    with g2:
        st.subheader("Categorias")
        if not df_show.empty:
            df_cat = df_show.groupby("Categoria", as_index=False)["Valor"].sum()
            fig2 = px.pie(df_cat, values="Valor", names="Categoria", hole=0.6, color_discrete_sequence=px.colors.sequential.Greens_r)
            fig2.update_layout(showlegend=False, margin=dict(t=0,l=0,r=0,b=0), height=200)
            st.plotly_chart(fig2, use_container_width=True)
            st.dataframe(df_cat.sort_values("Valor", ascending=False).head(3), use_container_width=True, hide_index=True, column_config={"Valor": st.column_config.NumberColumn(format="R$ %.2f")})
        else: st.info("Sem dados")

    # Tabela
    st.markdown("### Lançamentos")
    if not df_show.empty:
        df_tab = df_show[["Data", "Categoria", "Descrição", "Valor"]].sort_values("Data", ascending=False)
        st.dataframe(df_tab, use_container_width=True, hide_index=True, height=250, column_config={"Valor": st.column_config.NumberColumn(format="R$ %.2f")})
        
        st.write("")
        st.markdown("---")
        
        # PDF Call
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

# --- FINANCEIRO (COM VALIDAÇÃO TOTAL) ---
elif sel == "Financeiro":
    st.title("Financeiro")
    with st.expander("Novo Lançamento", expanded=True):
        with st.form("ffin", clear_on_submit=False):
            c1, c2 = st.columns(2)
            dt = c1.date_input("Data", date.today())
            tp = c1.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
            ct = c1.selectbox("Categoria", CATS)
            
            # --- ATUALIZAÇÃO: Obra inicia vazia e validação é exigida ---
            # Adicionei a opção vazia "" na lista
            opcoes_obras = [""] + lista_obras
            ob = c2.selectbox("Obra *", opcoes_obras)
            
            vl = c2.number_input("Valor R$ *", min_value=0.0)
            dc = c2.text_input("Descrição *")
            
            submitted_fin = st.form_submit_button("Salvar", use_container_width=True)

            if submitted_fin:
                erros = []
                # Validando a seleção da Obra (não pode ser vazia)
                if not ob or ob == "": erros.append("Selecione a Obra Vinculada.")
                if vl <= 0: erros.append("O Valor deve ser maior que zero.")
                if not dc.strip(): erros.append("A Descrição é obrigatória.")

                if erros:
                    st.error("⚠️ Atenção:")
                    for e in erros: st.caption(f"- {e}")
                else:
                    try:
                        conn = get_conn()
                        conn.worksheet("Financeiro").append_row([dt.strftime("%Y-%m-%d"),tp,ct,dc,vl,ob])
                        st.toast("Lançamento salvo com sucesso!")
                        st.cache_data.clear()
                        st.rerun() 
                    except Exception as e: st.error(f"Erro: {e}")

    if not df_fin.empty:
        fob = st.multiselect("Filtrar Obra", lista_obras)
        dview = df_fin[df_fin["Obra Vinculada"].isin(fob)] if fob else df_fin
        st.dataframe(dview.sort_values("Data_DT", ascending=False), use_container_width=True, hide_index=True)

# --- OBRAS (COM VALIDAÇÃO RÍGIDA) ---
elif sel == "Obras":
    st.title("📂 Gestão de Incorporação e Obras")
    st.markdown("---")

    # 1. FORMULÁRIO DE CADASTRO
    with st.expander("➕ Cadastrar Novo Empreendimento / Obra", expanded=True):
        with st.form("f_obra_completa", clear_on_submit=False):
            
            st.markdown("#### 1. Identificação")
            c1, c2 = st.columns([3, 2])
            nome_obra = c1.text_input("Nome do Empreendimento *", placeholder="Ex: Res. Vila Verde - Casa 04")
            endereco = c2.text_input("Endereço *", placeholder="Rua, Bairro...")

            st.markdown("#### 2. Características Físicas (Produto)")
            c4, c5, c6, c7 = st.columns(4)
            area_const = c4.number_input("Área Construída (m²)", min_value=0.0, format="%.2f")
            area_terr = c5.number_input("Área Terreno (m²)", min_value=0.0, format="%.2f")
            quartos = c6.number_input("Qtd. Quartos", min_value=0, step=1)
            status = c7.selectbox("Fase Atual", ["Projeto", "Fundação", "Alvenaria", "Acabamento", "Concluída", "Vendida"])

            st.markdown("#### 3. Viabilidade Financeira e Prazos")
            c8, c9, c10, c11 = st.columns(4)
            custo_previsto = c8.number_input("Orçamento (Custo) *", min_value=0.0, format="%.2f")
            valor_venda = c9.number_input("VGV (Venda) *", min_value=0.0, format="%.2f")
            data_inicio = c10.date_input("Início da Obra", value=date.today())
            prazo_entrega = c11.text_input("Prazo / Entrega *", placeholder="Ex: dez/2025")

            # Cálculo automático visual
            if valor_venda > 0 and custo_previsto > 0:
                margem_proj = ((valor_venda - custo_previsto) / custo_previsto) * 100
                lucro_proj = valor_venda - custo_previsto
                st.info(f"💰 **Projeção:** Lucro de **{fmt_moeda(lucro_proj)}** (Margem: **{margem_proj:.1f}%**)")

            st.markdown("---")
            st.caption("(*) Campos Obrigatórios")
            
            submitted = st.form_submit_button("✅ SALVAR PROJETO", use_container_width=True)

            if submitted:
                # --- LÓGICA DE VALIDAÇÃO ---
                erros = []
                
                # 1. Valida Textos (não podem ser vazios)
                if not nome_obra.strip(): erros.append("O 'Nome do Empreendimento' é obrigatório.")
                if not endereco.strip(): erros.append("O 'Endereço' é obrigatório.")
                if not prazo_entrega.strip(): erros.append("O 'Prazo' é obrigatório.")

                # 2. Valida Números (não podem ser zero)
                if valor_venda <= 0: erros.append("O 'Valor de Venda (VGV)' deve ser maior que zero.")
                if custo_previsto <= 0: erros.append("O 'Orçamento Previsto' deve ser maior que zero.")
                if area_const <= 0 and area_terr <= 0: erros.append("Preencha ao menos a Área Construída ou do Terreno.")

                if erros:
                    st.error("⚠️ Não foi possível salvar. Verifique os campos:")
                    for e in erros:
                        st.markdown(f"- {e}")
                else:
                    try:
                        conn = get_conn()
                        ws = conn.worksheet("Obras")
                        
                        ids_existentes = pd.to_numeric(df_obras["ID"], errors="coerce").fillna(0)
                        novo_id = int(ids_existentes.max()) + 1 if not ids_existentes.empty else 1

                        ws.append_row([
                            novo_id,
                            nome_obra.strip(),
                            endereco.strip(),
                            status,
                            float(valor_venda),
                            data_inicio.strftime("%Y-%m-%d"),
                            prazo_entrega.strip(),
                            float(area_const),
                            float(area_terr),
                            int(quartos),
                            float(custo_previsto)
                        ])
                        
                        st.toast(f"Sucesso! Obra '{nome_obra}' cadastrada.", icon="🏡")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro no Google Sheets: {e}")

    # 2. TABELA DE VISUALIZAÇÃO
    st.markdown("### 📋 Carteira de Obras")
    
    if not df_obras.empty:
        df_show = df_obras.copy()
        
        st.dataframe(
            df_show, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "ID": st.column_config.NumberColumn("#", width="small"),
                "Cliente": "Empreendimento",
                "Valor Total": st.column_config.NumberColumn("VGV (Venda)", format="R$ %.2f"),
                "Custo Previsto": st.column_config.NumberColumn("Budget (Custo)", format="R$ %.2f"),
                "Area Construida": st.column_config.NumberColumn("Área (m²)", format="%.0f m²"),
                "Data Início": st.column_config.DateColumn("Início", format="DD/MM/YYYY"),
                "Status": st.column_config.SelectboxColumn("Status", options=["Projeto", "Em Obras", "Vendida"], disabled=True)
            }
        )
    else:
        st.info("Nenhuma obra cadastrada.")
