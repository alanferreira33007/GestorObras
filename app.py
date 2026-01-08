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

# Bibliotecas PDF (ReportLab)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

# ==============================================================================
# 1. CONFIGURAÇÃO VISUAL E CSS
# ==============================================================================
st.set_page_config(
    page_title="GESTOR PRO | Enterprise",
    layout="wide",
    page_icon="🏗️",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    /* Métricas e Títulos */
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 700; color: #1a1a1a; }
    h1, h2, h3 { color: #1B4332; }
    
    /* Botões Grandes e Profissionais */
    div.stButton > button {
        background-color: #2D6A4F;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        font-size: 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    div.stButton > button:hover {
        background-color: #1B4332;
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(45, 106, 79, 0.3);
    }

    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #e9ecef; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. FUNÇÕES AUXILIARES
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
# 3. MOTOR PDF (AVANÇADO E ELEGANTE)
# ==============================================================================
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, footer_txt="Gestor Pro", **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self.footer_txt = footer_txt

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
        self.line(30, 40, width-30, 40)
        self.setFillColor(colors.darkgrey)
        self.setFont("Helvetica", 8)
        self.drawString(30, 25, f"{self.footer_txt} • Documento gerado eletronicamente em {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
        self.drawRightString(width-30, 25, f"Pág. {self.getPageNumber()} de {page_count}")

def gerar_pdf_detalhado(nome_escopo, periodo_str, vgv, custos, lucro, roi, df_cat, df_lanc):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4, 
        rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=50
    )
    story = []
    
    # Estilos Customizados
    styles = getSampleStyleSheet()
    style_title = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.white, alignment=TA_LEFT, leading=20)
    style_subtitle = ParagraphStyle('CustomSub', parent=styles['Normal'], fontSize=10, textColor=colors.whitesmoke, alignment=TA_LEFT)
    style_section = ParagraphStyle('Section', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor("#2D6A4F"), spaceBefore=15, spaceAfter=10)
    style_normal = ParagraphStyle('NormalAdj', parent=styles['Normal'], fontSize=9, leading=12)

    # 1. CABEÇALHO COLORIDO
    titulo_relatorio = "RELATÓRIO DE PORTFÓLIO (CONSOLIDADO)" if "Visão Geral" in nome_escopo else f"RELATÓRIO FINANCEIRO: {nome_escopo.upper()}"
    
    header_data = [[
        Paragraph(f"<b>{titulo_relatorio}</b>", style_title),
        Paragraph(f"Período de Análise:<br/>{periodo_str}", style_subtitle)
    ]]
    
    t_head = Table(header_data, colWidths=[12*cm, 5*cm])
    t_head.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#1B4332")),
        ('TOPPADDING', (0,0), (-1,-1), 15),
        ('BOTTOMPADDING', (0,0), (-1,-1), 15),
        ('LEFTPADDING', (0,0), (-1,-1), 15),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
    ]))
    story.append(t_head)
    story.append(Spacer(1, 15))

    # 2. CARTÕES DE RESUMO (KPIs)
    story.append(Paragraph("Resumo Executivo", style_section))
    perc_gasto = (custos/vgv*100) if vgv > 0 else 0
    kpi_data = [
        ["VGV (Contrato)", "Custo Realizado", "Lucro Estimado", "ROI", "% Executado"],
        [fmt_moeda(vgv), fmt_moeda(custos), fmt_moeda(lucro), f"{roi:.1f}%", f"{perc_gasto:.1f}%"]
    ]
    
    t_kpi = Table(kpi_data, colWidths=[3.6*cm]*5)
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E9ECEF")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('FONTSIZE', (0,1), (-1,1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.white),
        ('BOX', (0,0), (-1,-1), 0.5, colors.lightgrey),
    ]))
    story.append(t_kpi)
    story.append(Spacer(1, 15))

    # 3. CATEGORIAS
    if not df_cat.empty:
        story.append(Paragraph("Detalhamento por Categoria de Custo", style_section))
        df_c = df_cat.copy()
        df_c["Valor"] = df_c["Valor"].apply(fmt_moeda)
        cat_data = [["Categoria", "Total Gasto"]] + df_c.values.tolist()
        
        t_cat = Table(cat_data, colWidths=[12*cm, 5*cm], hAlign='LEFT')
        t_cat.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#40916C")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.white]),
            ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('ALIGN', (1,0), (1,-1), 'RIGHT'),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(t_cat)
        story.append(Spacer(1, 15))

    # 4. EXTRATO DE LANÇAMENTOS
    story.append(Paragraph(f"Extrato Detalhado ({len(df_lanc)} registros)", style_section))
    
    if not df_lanc.empty:
        df_l = df_lanc.copy()
        if "Valor" in df_l.columns: df_l["Valor"] = df_l["Valor"].apply(fmt_moeda)
        cols_pdf = ["Data", "Categoria", "Descrição", "Valor"]
        cols_final = [c for c in cols_pdf if c in df_l.columns]
        data_lanc = [cols_final] + df_l[cols_final].values.tolist()
        
        t_lanc = Table(data_lanc, colWidths=[2.5*cm, 3.5*cm, 8*cm, 3*cm])
        t_lanc.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2D6A4F")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.white]),
            ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('ALIGN', (-1,0), (-1,-1), 'RIGHT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(t_lanc)
    else:
        story.append(Paragraph("Nenhum lançamento registrado no período.", style_normal))

    story.append(Spacer(1, 20))

    # =========================================================
    # 5. FECHAMENTO FINANCEIRO E ASSINATURAS (NOVO)
    # =========================================================
    
    # Caixa Total
    total_data = [
        ["FECHAMENTO DO PERÍODO", ""],
        ["TOTAL ACUMULADO GASTO ATÉ A DATA DE EMISSÃO:", fmt_moeda(custos)]
    ]
    
    t_total = Table(total_data, colWidths=[12*cm, 5*cm], hAlign='RIGHT')
    t_total.setStyle(TableStyle([
        # Linha 1 (Título invisível ou discreto)
        ('FONTSIZE', (0,0), (-1,0), 6),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        # Linha 2 (O Total pra valer)
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor("#1a1a1a")), # Fundo Preto/Cinza Escuro
        ('TEXTCOLOR', (0,1), (-1,1), colors.white),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,1), (-1,1), 12),
        ('ALIGN', (1,1), (1,1), 'RIGHT'), # Valor à direita
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_total)
    
    story.append(Spacer(1, 40))

    # Campos de Assinatura
    sig_data = [
        ["_______________________________________", "_______________________________________"],
        ["Gestor Responsável", "Aprovação Financeira"],
        [f"Data: {date.today().strftime('%d/%m/%Y')}", "Data: ____/____/________"]
    ]
    t_sig = Table(sig_data, colWidths=[8.5*cm, 8.5*cm])
    t_sig.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,1), (-1,-1), 9),
        ('TOPPADDING', (0,1), (-1,-1), 5),
    ]))
    story.append(t_sig)

    # Termo legal
    story.append(Spacer(1, 20))
    story.append(Paragraph("<i>* Este relatório é gerado automaticamente pelo sistema GESTOR PRO com base nos lançamentos efetuados até o momento da emissão. Valores sujeitos a conferência.</i>", ParagraphStyle('Legal', parent=styles['Normal'], fontSize=7, textColor=colors.grey, alignment=TA_CENTER)))

    doc.build(
        story, 
        canvasmaker=lambda *args, **kwargs: NumberedCanvas(*args, footer_txt="Gestor Pro Enterprise", **kwargs)
    )
    return buffer.getvalue()

# ==============================================================================
# 4. CONEXÃO E DADOS
# ==============================================================================
OBRAS_COLS = ["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"]
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
        df_o = pd.DataFrame(db.worksheet("Obras").get_all_records())
        if df_o.empty:
            df_o = pd.DataFrame([{
                "ID": 1, "Cliente": "Obra Modelo (Demo)", "Endereço": "Rua Exemplo, 100", 
                "Status": "Em Andamento", "Valor Total": 500000.0, "Data Início": "2024-01-01", "Prazo": "2024-12-31"
            }])
        else: 
            for c in OBRAS_COLS: 
                if c not in df_o.columns: df_o[c] = None
        
        df_f = pd.DataFrame(db.worksheet("Financeiro").get_all_records())
        if df_f.empty or len(df_f) < 2:
            st.toast("Modo Demo: Dados fictícios ativos", icon="ℹ️")
            fake_data = []
            obra_nome = df_o.iloc[0]["Cliente"]
            for i in range(15):
                fake_data.append({
                    "Data": (date.today() - timedelta(days=i*3)).strftime("%Y-%m-%d"),
                    "Tipo": "Saída (Despesa)",
                    "Categoria": random.choice(CATS),
                    "Descrição": f"Material / Serviço {i+1}",
                    "Valor": random.uniform(500, 3000),
                    "Obra Vinculada": obra_nome
                })
            df_f = pd.DataFrame(fake_data)
        else:
            for c in FIN_COLS: 
                if c not in df_f.columns: df_f[c] = None
        
        df_o["Valor Total"] = df_o["Valor Total"].apply(safe_float)
        df_f["Valor"] = df_f["Valor"].apply(safe_float)
        df_f["Data_DT"] = pd.to_datetime(df_f["Data"], errors="coerce")
        return df_o, df_f
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return pd.DataFrame(), pd.DataFrame()

# ==============================================================================
# 5. APLICAÇÃO PRINCIPAL
# ==============================================================================
if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.markdown("<br><br><h1 style='text-align: center; color: #2D6A4F;'>GESTOR PRO</h1>", unsafe_allow_html=True)
        pwd = st.text_input("Senha de Acesso", type="password")
        if st.button("ACESSAR PAINEL", use_container_width=True):
            if pwd == st.secrets["password"]:
                st.session_state.auth = True
                st.rerun()
            else: st.error("Acesso negado.")
    st.stop()

df_obras, df_fin = load_data()
lista_obras = df_obras["Cliente"].unique().tolist() if not df_obras.empty else []

with st.sidebar:
    st.markdown("### 🏢 GESTOR PRO")
    selected = option_menu(
        None, ["Dashboard", "Financeiro", "Obras"], 
        icons=["bar-chart-fill", "wallet-fill", "building-fill"], 
        default_index=0,
        styles={"container": {"padding": "0!important", "background-color": "#f8f9fa"}, "nav-link-selected": {"background-color": "#2D6A4F"}}
    )
    st.markdown("---")
    if st.button("Sair"): st.session_state.auth = False; st.rerun()

# --- DASHBOARD ---
if selected == "Dashboard":
    col_tit, col_sel, col_upd = st.columns([1.5, 2, 0.8])
    with col_tit: st.title("Visão Geral")
    with col_sel:
        if lista_obras:
            opcoes_dash = ["Visão Geral (Todas as Obras)"] + lista_obras
            selecao = st.selectbox("Selecione o Escopo:", opcoes_dash, label_visibility="collapsed")
        else: st.warning("Cadastre uma obra primeiro."); st.stop()
    with col_upd:
        if st.button("🔄 Atualizar Dados", use_container_width=True): st.cache_data.clear(); st.rerun()

    # Filtro e Lógica
    if selecao == "Visão Geral (Todas as Obras)":
        vgv = df_obras["Valor Total"].sum()
        df_saidas = df_fin[df_fin["Tipo"].astype(str).str.contains("Saída|Despesa", case=False, na=False)].copy()
    else:
        row_obra = df_obras[df_obras["Cliente"] == selecao].iloc[0]
        vgv = row_obra["Valor Total"]
        df_saidas = df_fin[(df_fin["Obra Vinculada"] == selecao) & (df_fin["Tipo"].astype(str).str.contains("Saída|Despesa", case=False, na=False))].copy()
    
    custos = df_saidas["Valor"].sum()
    lucro = vgv - custos
    roi = (lucro / custos * 100) if custos > 0 else 0
    perc = (custos / vgv) if vgv > 0 else 0
    
    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    with c1: 
        with st.container(border=True): st.metric("VGV Total", fmt_moeda(vgv))
    with c2: 
        with st.container(border=True): st.metric("Custo Realizado", fmt_moeda(custos), delta=f"{perc*100:.1f}%", delta_color="inverse")
    with c3: 
        with st.container(border=True): st.metric("Lucro Estimado", fmt_moeda(lucro))
    with c4: 
        with st.container(border=True): st.metric("ROI", f"{roi:.1f}%")

    # Gráficos
    col_main, col_side = st.columns([2, 1])
    with col_main:
        with st.container(border=True):
            st.subheader("Curva de Custos")
            if not df_saidas.empty:
                df_evo = df_saidas.sort_values("Data_DT")
                df_evo["Acumulado"] = df_evo["Valor"].cumsum()
                fig = px.area(df_evo, x="Data_DT", y="Acumulado", color_discrete_sequence=["#2D6A4F"])
            else: fig = px.area(title="Sem dados")
            fig.update_layout(plot_bgcolor="white", margin=dict(t=20, l=10, r=10, b=10), height=350)
            st.plotly_chart(fig, use_container_width=True)
    with col_side:
        with st.container(border=True):
            st.subheader("Categorias")
            if not df_saidas.empty:
                df_cat = df_saidas.groupby("Categoria", as_index=False)["Valor"].sum()
                fig2 = px.pie(df_cat, values="Valor", names="Categoria", hole=0.6, color_discrete_sequence=px.colors.sequential.Greens_r)
                fig2.update_layout(showlegend=False, margin=dict(t=0, l=0, r=0, b=0), height=250)
                st.plotly_chart(fig2, use_container_width=True)
                st.dataframe(df_cat.sort_values("Valor", ascending=False).head(3), use_container_width=True, hide_index=True, column_config={"Valor": st.column_config.NumberColumn(format="R$ %.2f")})
            else: st.info("Sem categorias")
            
    # Tabela + PDF
    st.markdown("### Detalhamento Financeiro")
    if not df_saidas.empty:
        df_show = df_saidas[["Data", "Categoria", "Descrição", "Valor"]].sort_values("Data", ascending=False)
        st.dataframe(
            df_show, use_container_width=True, hide_index=True, height=300,
            column_config={
                "Valor": st.column_config.ProgressColumn("Valor", format="R$ %.2f", min_value=0, max_value=float(df_show["Valor"].max())),
                "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")
            }
        )
        
        # Define período para o relatório
        d_min = df_saidas["Data_DT"].min().strftime("%d/%m/%Y")
        d_max = df_saidas["Data_DT"].max().strftime("%d/%m/%Y")
        periodo_pdf = f"De {d_min} até {d_max}"
        
        st.write("")
        st.markdown("---")
        
        pdf_bytes = gerar_pdf_detalhado(
            nome_escopo=selecao,
            periodo_str=periodo_pdf,
            vgv=vgv, custos=custos, lucro=lucro, roi=roi,
            df_cat=df_cat if 'df_cat' in locals() else pd.DataFrame(),
            df_lanc=df_show
        )
        
        st.download_button(
            label="📄 BAIXAR RELATÓRIO DETALHADO (PDF)",
            data=pdf_bytes,
            file_name=f"Relatorio_{selecao.replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    else:
        st.info("Sem dados para gerar relatório.")

# --- FINANCEIRO ---
elif selected == "Financeiro":
    st.title("Movimentações")
    with st.expander("➕ Novo Lançamento", expanded=True):
        with st.form("form_fin", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                f_dt = st.date_input("Data", date.today())
                f_tp = st.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
                f_ct = st.selectbox("Categoria", CATS)
            with c2:
                f_ob = st.selectbox("Obra", lista_obras if lista_obras else ["Geral"])
                f_vl = st.number_input("Valor", min_value=0.0, step=100.0)
                f_dc = st.text_input("Descrição")
            if st.form_submit_button("Salvar", use_container_width=True):
                try:
                    conn = get_conn()
                    conn.worksheet("Financeiro").append_row([f_dt.strftime("%Y-%m-%d"), f_tp, f_ct, f_dc, f_vl, f_ob])
                    st.toast("Salvo!", icon="✅"); st.cache_data.clear(); st.rerun()
                except Exception as e: st.error(f"Erro: {e}")
    if not df_fin.empty:
        cf1, cf2 = st.columns(2)
        fo = cf1.multiselect("Filtrar por Obra", lista_obras)
        dg = df_fin.copy()
        if fo: dg = dg[dg["Obra Vinculada"].isin(fo)]
        st.dataframe(dg.sort_values("Data_DT", ascending=False), use_container_width=True, hide_index=True, column_config={"Valor": st.column_config.NumberColumn(format="R$ %.2f")})

# --- OBRAS ---
elif selected == "Obras":
    st.title("Obras")
    c_form, c_view = st.columns([1, 2])
    with c_form:
        with st.container(border=True):
            st.markdown("#### Nova Obra")
            with st.form("new_obra"):
                nc = st.text_input("Cliente")
                ne = st.text_input("Endereço")
                nv = st.number_input("VGV", min_value=0.0)
                ns = st.selectbox("Status", ["Planejamento", "Em Andamento", "Concluído"])
                np = st.text_input("Prazo")
                if st.form_submit_button("Cadastrar", use_container_width=True):
                    try:
                        conn = get_conn()
                        conn.worksheet("Obras").append_row([len(lista_obras)+1, nc, ne, ns, nv, date.today().strftime("%Y-%m-%d"), np])
                        st.toast("Sucesso!"); st.cache_data.clear(); st.rerun()
                    except Exception as e: st.error(f"Erro: {e}")
    with c_view:
        if not df_obras.empty:
            for i, r in df_obras.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.markdown(f"**{r['Cliente']}**<br><span style='color:grey'>{r['Status']}</span>", unsafe_allow_html=True)
                    c2.metric("VGV", fmt_moeda(r['Valor Total']))
