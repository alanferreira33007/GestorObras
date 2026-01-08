import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import date, datetime
from streamlit_option_menu import option_menu
import io

# Bibliotecas PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas

# ----------------------------
# 1) CONFIGURAÇÃO DA PÁGINA & CSS (DESIGN SYSTEM)
# ----------------------------
st.set_page_config(
    page_title="GESTOR PRO | Enterprise", 
    layout="wide",
    page_icon="🏢",
    initial_sidebar_state="expanded"
)

# CSS AVANÇADO PARA VISUAL PROFISSIONAL
st.markdown("""
<style>
    /* Importando fonte profissional (Inter) */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Fundo geral da aplicação */
    .stApp {
        background-color: #F0F2F6;
    }

    /* Estilo dos Cards (Caixas brancas com sombra) */
    .css-card {
        background-color: #FFFFFF;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
        border: 1px solid #E0E0E0;
    }

    /* Métricas (KPIs) */
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        padding: 15px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        text-align: center;
    }
    
    [data-testid="stMetricLabel"] {
        color: #6B7280;
        font-size: 0.9rem !important;
        font-weight: 600;
    }
    
    [data-testid="stMetricValue"] {
        color: #1B4332;
        font-size: 1.6rem !important;
        font-weight: 700;
    }

    /* Botões */
    div.stButton > button {
        background-color: #1B4332 !important; /* Verde Escuro Profissional */
        color: white !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        height: 42px;
        border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: all 0.2s;
    }
    div.stButton > button:hover {
        background-color: #2D6A4F !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        transform: translateY(-1px);
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E0E0E0;
    }
    
    /* Títulos */
    h1, h2, h3 {
        color: #111827;
        font-weight: 700;
    }
    h4, h5, h6 {
        color: #374151;
        font-weight: 600;
    }

    /* Remove padding excessivo do topo */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------
# 2) FUNÇÕES UTILITÁRIAS (Python)
# ----------------------------
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

# ----------------------------
# 3) MOTOR PDF (REPORTLAB)
# ----------------------------
class NumberedCanvas(canvas.Canvas):
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

def _df_to_table(df: pd.DataFrame, max_rows=None):
    styles = getSampleStyleSheet()
    if df is None or df.empty:
        return Paragraph("<i>Sem dados.</i>", styles["BodyText"])
    
    df2 = df.copy()
    if max_rows and len(df2) > max_rows: df2 = df2.head(max_rows)
    
    data = [list(df2.columns)] + df2.astype(str).values.tolist()
    t = Table(data, hAlign="LEFT", repeatRows=1)
    t.splitByRow = 1
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B4332")),
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
    ]))
    return t

def gerar_relatorio_investimentos_pdf(obra, periodo, vgv, custos, lucro, roi, perc_vgv, df_cat, df_lanc):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()

    story.append(Paragraph("GESTOR PRO — Relatório Executivo", styles["Title"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>Obra:</b> {obra} <br/><b>Período:</b> {periodo} <br/><b>Emissão:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["BodyText"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Resumo Financeiro", styles["Heading2"]))
    resumo = pd.DataFrame([
        ["VGV (Contrato)", fmt_moeda(vgv)],
        ["Custo Realizado", fmt_moeda(custos)],
        ["Lucro Projetado", fmt_moeda(lucro)],
        ["ROI", f"{roi:.1f}%"],
        ["% Gasto do VGV", f"{perc_vgv:.2f}%"]
    ], columns=["Indicador", "Valor"])
    story.append(_df_to_table(resumo))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Custos por Categoria", styles["Heading2"]))
    if not df_cat.empty:
        df_cat_show = df_cat.copy()
        df_cat_show["Valor"] = df_cat_show["Valor"].apply(fmt_moeda)
        story.append(_df_to_table(df_cat_show))
    else: story.append(Paragraph("Sem dados.", styles["BodyText"]))
    
    story.append(Spacer(1, 14))
    story.append(Paragraph("Extrato de Lançamentos", styles["Heading2"]))
    if not df_lanc.empty:
        df_l = df_lanc.copy()
        if "Valor" in df_l.columns: df_l["Valor"] = df_l["Valor"].apply(fmt_moeda)
        story.append(_df_to_table(df_l))
    else: story.append(Paragraph("Sem lançamentos.", styles["BodyText"]))

    doc.build(story, canvasmaker=lambda *args, **kwargs: NumberedCanvas(*args, footer_left=f"Gestor Pro • {obra}", **kwargs))
    return buffer.getvalue()

# ----------------------------
# 4) CONEXÃO BANCO DE DADOS
# ----------------------------
OBRAS_COLS = ["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"]
FIN_COLS   = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]
CATEGORIAS_PADRAO = ["Geral", "Material", "Mão de Obra", "Serviços", "Impostos", "Outros"]

@st.cache_resource
def obter_db():
    creds_json = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    return gspread.authorize(creds).open("GestorObras_DB")

@st.cache_data(ttl=300)
def carregar_dados():
    try:
        db = obter_db()
        df_o = pd.DataFrame(db.worksheet("Obras").get_all_records())
        if df_o.empty: df_o = pd.DataFrame(columns=OBRAS_COLS)
        for col in OBRAS_COLS:
            if col not in df_o.columns: df_o[col] = None
        
        df_f = pd.DataFrame(db.worksheet("Financeiro").get_all_records())
        if df_f.empty: df_f = pd.DataFrame(columns=FIN_COLS)
        for col in FIN_COLS:
            if col not in df_f.columns: df_f[col] = None

        df_o["Valor Total"] = df_o["Valor Total"].apply(safe_float)
        df_f["Valor"] = df_f["Valor"].apply(safe_float)
        df_f["Data_DT"] = pd.to_datetime(df_f["Data"], errors="coerce")
        df_f["Data_BR"] = df_f["Data_DT"].dt.strftime("%d/%m/%Y").fillna("")
        
        return df_o, df_f
    except Exception as e:
        st.error(f"Erro ao conectar com Google Sheets: {e}")
        return pd.DataFrame(), pd.DataFrame()

# ----------------------------
# 5) AUTENTICAÇÃO
# ----------------------------
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if not st.session_state["authenticated"]:
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.write("")
        st.write("")
        with st.form("login"):
            st.markdown("<h2 style='text-align:center; color:#1B4332;'>🔐 GESTOR PRO</h2>", unsafe_allow_html=True)
            pwd = st.text_input("Senha", type="password")
            if st.form_submit_button("ENTRAR", type="primary"):
                if pwd == st.secrets["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else: st.error("Senha inválida.")
    st.stop()

# ----------------------------
# 6) LAYOUT PRINCIPAL
# ----------------------------
df_obras, df_fin = carregar_dados()
lista_obras = []
if not df_obras.empty and "Cliente" in df_obras.columns:
    lista_obras = df_obras["Cliente"].dropna().unique().tolist()

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/25/25694.png", width=50) # Ícone placeholder "Casa"
    st.markdown("### GESTOR PRO")
    sel = option_menu(
        None, 
        ["Dashboard", "Financeiro", "Insumos", "Obras"], 
        icons=["pie-chart-fill", "wallet-fill", "basket-fill", "building-fill"], 
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "#ffffff"},
            "nav-link": {"font-size": "14px", "text-align": "left", "margin":"5px", "--hover-color": "#F0F2F6"},
            "nav-link-selected": {"background-color": "#1B4332"},
        }
    )
    st.divider()
    if st.button("🔄 Atualizar Dados"):
        st.cache_data.clear()
        st.rerun()
    if st.button("🚪 Sair"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- TELA: DASHBOARD (INVESTIMENTOS) ---
if sel == "Dashboard":
    st.title("📊 Visão Geral da Obra")
    
    if not lista_obras:
        st.warning("Cadastre uma obra no menu 'Obras' para começar.")
        st.stop()
        
    # Topo: Filtros em um Card
    with st.container():
        c_top1, c_top2 = st.columns([3, 1])
        with c_top1:
            obra_sel = st.selectbox("Selecione a Obra:", lista_obras)
        with c_top2:
            st.write("") # Espaçamento

    # Processamento de Dados
    obra_dados = df_obras[df_obras["Cliente"] == obra_sel].iloc[0]
    vgv = float(obra_dados["Valor Total"])
    df_v = df_fin[df_fin["Obra Vinculada"] == obra_sel].copy()
    
    with st.expander("📅 Filtrar Período Específico", expanded=False):
        df_valid = df_v.dropna(subset=["Data_DT"]).copy()
        if not df_valid.empty:
            df_valid["Ano"] = df_valid["Data_DT"].dt.year
            anos_disp = sorted(df_valid["Ano"].unique())
            anos_sel = st.multiselect("Anos", anos_disp, default=anos_disp)
            meses_sel = st.multiselect("Meses", list(range(1,13)), default=list(range(1,13)))
            mask = (df_valid["Ano"].isin(anos_sel)) & (df_valid["Data_DT"].dt.month.isin(meses_sel))
            df_v = df_valid[mask]

    df_saidas = df_v[df_v["Tipo"].str.contains("Saída|Despesa", case=False, na=False)].copy()
    custos = df_saidas["Valor"].sum()
    lucro = vgv - custos
    roi = (lucro / custos * 100) if custos > 0 else 0
    perc_vgv = (custos / vgv * 100) if vgv > 0 else 0

    # KPIs Cards
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Valor Contrato (VGV)", fmt_moeda(vgv))
    k2.metric("Total Gasto", fmt_moeda(custos), delta=f"{perc_vgv:.1f}% consumido", delta_color="inverse")
    k3.metric("Lucro Estimado", fmt_moeda(lucro))
    k4.metric("ROI Atual", f"{roi:.1f}%")
    
    st.markdown("---")

    # Gráficos em Containers (Cards Visuais)
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.markdown("##### 🧾 Distribuição por Categoria")
        if not df_saidas.empty:
            df_cat = df_saidas.groupby("Categoria", as_index=False)["Valor"].sum().sort_values("Valor", ascending=False)
            fig = px.pie(df_cat, values="Valor", names="Categoria", hole=0.4, color_discrete_sequence=px.colors.sequential.Greens_r)
            fig.update_layout(showlegend=True, margin=dict(t=10, b=10, l=10, r=10), height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados.")

    with col_g2:
        st.markdown("##### 📈 Evolução de Gastos")
        if not df_saidas.empty:
            df_evo = df_saidas.sort_values("Data_DT")
            df_evo["Acumulado"] = df_evo["Valor"].cumsum()
            fig2 = px.area(df_evo, x="Data_DT", y="Acumulado", markers=True)
            fig2.update_traces(line_color='#1B4332', fillcolor="rgba(27, 67, 50, 0.1)")
            fig2.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300, yaxis_title=None, xaxis_title=None)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Sem dados.")

    # Tabela e Relatório
    st.markdown("---")
    c_list, c_act = st.columns([3, 1])
    
    with c_list:
        st.subheader("Últimos Lançamentos")
        cols_show = ["Data", "Categoria", "Descrição", "Valor"]
        df_show = df_saidas[cols_show].copy() if not df_saidas.empty else pd.DataFrame(columns=cols_show)
        
        # TABELA INTERATIVA MODERNA
        st.dataframe(
            df_show, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
                "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            }
        )

    with c_act:
        st.write("")
        st.write("")
        # Botão PDF
        if not df_saidas.empty:
            d_min = df_saidas["Data_DT"].min().strftime("%d/%m/%Y")
            d_max = df_saidas["Data_DT"].max().strftime("%d/%m/%Y")
            periodo_pdf = f"{d_min} a {d_max}"
        else: periodo_pdf = "-"

        pdf_bytes = gerar_relatorio_investimentos_pdf(
            obra=obra_sel, periodo=periodo_pdf, vgv=vgv, custos=custos, lucro=lucro, roi=roi,
            perc_vgv=perc_vgv, df_cat=df_cat if not df_saidas.empty else pd.DataFrame(), df_lanc=df_show
        )
        st.download_button("📄 Baixar Relatório PDF", data=pdf_bytes, file_name=f"Relatorio_{obra_sel}.pdf", mime="application/pdf")

# --- TELA: FINANCEIRO ---
elif sel == "Financeiro":
    st.title("💸 Fluxo de Caixa")
    
    # Formulário em Card
    st.markdown("#### Novo Lançamento")
    with st.container():
        with st.form("form_caixa", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            data_in = c1.date_input("Data do Lançamento", date.today())
            tipo_in = c2.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
            cat_in = c3.selectbox("Categoria", CATEGORIAS_PADRAO)
            
            c4, c5 = st.columns(2)
            obra_in = c4.selectbox("Vincular à Obra", lista_obras if lista_obras else ["Geral"])
            val_in = c5.number_input("Valor (R$)", min_value=0.0, step=10.0)
            desc_in = st.text_input("Descrição (Ex: Cimento, Pintura)")
            
            if st.form_submit_button("💾 REGISTRAR"):
                try:
                    conn = obter_db()
                    conn.worksheet("Financeiro").append_row([
                        data_in.strftime("%Y-%m-%d"), tipo_in, cat_in, desc_in, float(val_in), obra_in
                    ])
                    st.toast("Sucesso! Lançamento registrado.", icon="✅")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e: st.error(f"Erro: {e}")

    st.divider()
    st.markdown("#### Histórico Geral")
    if not df_fin.empty:
        df_exibe = df_fin[["Data_DT", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]].copy()
        df_exibe = df_exibe.sort_values("Data_DT", ascending=False)
        
        st.dataframe(
            df_exibe, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Data_DT": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                "Tipo": st.column_config.Column("Tipo", width="medium"),
            }
        )
    else: st.info("Sem registros.")

# --- TELA: INSUMOS ---
elif sel == "Insumos":
    st.title("🛒 Monitor de Inflação")
    st.markdown("*Monitoramento automático de variação de preço de materiais baseados no histórico de compras.*")
    
    df_saidas = df_fin[df_fin["Tipo"].str.contains("Saída", na=False)].copy()
    
    if df_saidas.empty:
        st.warning("É necessário ter lançamentos de saída para monitorar preços.")
    else:
        df_saidas["Item"] = df_saidas["Descrição"].apply(lambda x: str(x).split(":")[0].strip())
        df_saidas = df_saidas.sort_values("Data_DT")
        
        itens_unicos = df_saidas["Item"].unique()
        alerta = False
        
        col1, col2 = st.columns(2)
        
        for item in itens_unicos:
            hist = df_saidas[df_saidas["Item"] == item]
            if len(hist) >= 2:
                atual = hist.iloc[-1]
                ant = hist.iloc[-2]
                v_atual, v_ant = float(atual["Valor"]), float(ant["Valor"])
                
                if v_ant > 0 and v_atual > v_ant:
                    aumento = ((v_atual / v_ant) - 1) * 100
                    if aumento >= 2.0:
                        alerta = True
                        with col1:
                            st.error(f"🚨 **{item}**: +{aumento:.1f}% (Subiu de {fmt_moeda(v_ant)} para {fmt_moeda(v_atual)})")
        
        if not alerta: st.success("✅ Preços estáveis. Nenhuma variação brusca detectada recentemente.")

# --- TELA: OBRAS ---
elif sel == "Obras":
    st.title("🏗️ Gestão de Projetos")
    
    with st.expander("➕ Cadastrar Nova Obra", expanded=True):
        with st.form("form_obra"):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome da Obra")
            ender = c2.text_input("Localização")
            c3, c4, c5 = st.columns(3)
            status = c3.selectbox("Fase", ["Planejamento", "Fundação", "Estrutura", "Acabamento", "Entregue"])
            vgv_in = c4.number_input("Valor do Contrato (VGV)", min_value=0.0, step=1000.0)
            prazo = c5.text_input("Prazo Final")
            
            if st.form_submit_button("CADASTRAR"):
                if not nome: st.error("Nome obrigatório.")
                else:
                    try:
                        conn = obter_db()
                        max_id = pd.to_numeric(df_obras["ID"], errors='coerce').max()
                        if pd.isna(max_id): max_id = 0
                        conn.worksheet("Obras").append_row([
                            int(max_id)+1, nome, ender, status, float(vgv_in), date.today().strftime("%Y-%m-%d"), prazo
                        ])
                        st.success(f"Obra '{nome}' criada!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e: st.error(str(e))

    st.markdown("### Obras em Andamento")
    st.dataframe(
        df_obras, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Valor Total": st.column_config.NumberColumn("VGV", format="R$ %.2f"),
            "ID": None # Esconde ID
        }
    )
