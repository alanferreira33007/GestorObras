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
# CONFIGURAÇÃO INICIAL (Deve ser a primeira linha)
# ----------------------------
st.set_page_config(
    page_title="GESTOR PRO | Master v27", 
    layout="wide",
    page_icon="🏗️"
)

# Estilos CSS
st.markdown("""
<style>
    .stApp { background-color: #F8F9FA; color: #1A1C1E; font-family: 'Inter', sans-serif; }
    [data-testid="stMetric"] { background-color: #FFFFFF; border: 1px solid #E9ECEF; border-radius: 12px; padding: 15px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    div.stButton > button { background-color: #2D6A4F !important; color: white !important; border-radius: 8px !important; font-weight: 600 !important; width: 100%; height: 45px; transition: all 0.3s; }
    div.stButton > button:hover { background-color: #1B4332 !important; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
    .alert-card { background-color: #FFFFFF; border-left: 5px solid #E63946; padding: 20px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
    header, footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ----------------------------
# 1) FUNÇÕES UTILITÁRIAS
# ----------------------------
def fmt_moeda(valor):
    """Formata float para BRL de forma segura."""
    if pd.isna(valor) or valor == "":
        return "R$ 0,00"
    try:
        val = float(valor)
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return f"R$ {valor}"

def safe_float(x) -> float:
    """Converte string suja em float."""
    if isinstance(x, (int, float)):
        return float(x)
    if x is None:
        return 0.0
    s = str(x).strip()
    if not s:
        return 0.0
    # Remove R$, espaços e ajusta pontuação
    s = s.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0

# ----------------------------
# 2) MOTOR PDF (REPORTLAB)
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
    if max_rows and len(df2) > max_rows:
        df2 = df2.head(max_rows)
    
    data = [list(df2.columns)] + df2.astype(str).values.tolist()
    t = Table(data, hAlign="LEFT", repeatRows=1)
    t.splitByRow = 1
    t.setStyle(TableStyle([
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
    ]))
    return t

def gerar_relatorio_investimentos_pdf(obra, periodo, vgv, custos, lucro, roi, perc_vgv, df_cat, df_lanc):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()

    story.append(Paragraph("GESTOR PRO — Relatório de Investimentos", styles["Title"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>Obra:</b> {obra} <br/><b>Período:</b> {periodo} <br/><b>Gerado em:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["BodyText"]))
    story.append(Spacer(1, 12))

    # Resumo
    story.append(Paragraph("Resumo Financeiro", styles["Heading2"]))
    resumo = pd.DataFrame([
        ["VGV (Valor Geral de Vendas)", fmt_moeda(vgv)],
        ["Custo Total (Período)", fmt_moeda(custos)],
        ["Lucro Estimado", fmt_moeda(lucro)],
        ["ROI", f"{roi:.1f}%"],
        ["Consumo do Orçamento", f"{perc_vgv:.2f}%"]
    ], columns=["Indicador", "Valor"])
    story.append(_df_to_table(resumo))
    story.append(Spacer(1, 14))

    # Tabela Categorias
    story.append(Paragraph("Custos por Categoria", styles["Heading2"]))
    if not df_cat.empty:
        # Prepara tabela para PDF
        df_cat_show = df_cat.copy()
        df_cat_show["Valor"] = df_cat_show["Valor"].apply(fmt_moeda)
        story.append(_df_to_table(df_cat_show))
    else:
        story.append(Paragraph("Sem dados de categorias.", styles["BodyText"]))
    
    story.append(Spacer(1, 14))
    
    # Detalhamento
    story.append(Paragraph("Extrato de Lançamentos", styles["Heading2"]))
    if not df_lanc.empty:
        df_lanc_show = df_lanc.copy()
        if "Valor" in df_lanc_show.columns:
            df_lanc_show["Valor"] = df_lanc_show["Valor"].apply(fmt_moeda)
        story.append(_df_to_table(df_lanc_show))
    else:
        story.append(Paragraph("Sem lançamentos no período.", styles["BodyText"]))

    doc.build(story, canvasmaker=lambda *args, **kwargs: NumberedCanvas(*args, footer_left=f"Gestor Pro • {obra}", **kwargs))
    return buffer.getvalue()

# ----------------------------
# 3) CONEXÃO BANCO DE DADOS
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

# MELHORIA DE PERFORMANCE: TTL aumentado para 300s (5 min) para não travar o Google
@st.cache_data(ttl=300)
def carregar_dados():
    try:
        db = obter_db()
        
        # Obras
        df_o = pd.DataFrame(db.worksheet("Obras").get_all_records())
        if df_o.empty: df_o = pd.DataFrame(columns=OBRAS_COLS)
        for col in OBRAS_COLS:
            if col not in df_o.columns: df_o[col] = None
        
        # Financeiro
        df_f = pd.DataFrame(db.worksheet("Financeiro").get_all_records())
        if df_f.empty: df_f = pd.DataFrame(columns=FIN_COLS)
        for col in FIN_COLS:
            if col not in df_f.columns: df_f[col] = None

        # Tratamento de Tipos
        df_o["Valor Total"] = df_o["Valor Total"].apply(safe_float)
        df_f["Valor"] = df_f["Valor"].apply(safe_float)
        
        df_f["Data_DT"] = pd.to_datetime(df_f["Data"], errors="coerce")
        df_f["Data_BR"] = df_f["Data_DT"].dt.strftime("%d/%m/%Y").fillna("")
        
        return df_o, df_f

    except Exception as e:
        st.error(f"Erro ao conectar com Google Sheets: {e}")
        return pd.DataFrame(), pd.DataFrame()

# ----------------------------
# 4) AUTENTICAÇÃO
# ----------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.write("")
        st.write("")
        with st.form("login"):
            st.markdown("<h2 style='text-align:center; color:#2D6A4F;'>🔐 GESTOR PRO</h2>", unsafe_allow_html=True)
            pwd = st.text_input("Senha", type="password")
            if st.form_submit_button("ENTRAR"):
                if pwd == st.secrets["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Senha inválida.")
    st.stop()

# ----------------------------
# 5) LAYOUT PRINCIPAL
# ----------------------------
# Carrega dados
df_obras, df_fin = carregar_dados()

lista_obras = []
if not df_obras.empty and "Cliente" in df_obras.columns:
    lista_obras = df_obras["Cliente"].dropna().unique().tolist()

with st.sidebar:
    st.markdown("<h3 style='color:#2D6A4F'>MENU</h3>", unsafe_allow_html=True)
    sel = option_menu(
        None, 
        ["Investimentos", "Caixa", "Insumos", "Projetos"], 
        icons=["graph-up-arrow", "wallet2", "cart-check", "building"], 
        default_index=0,
        styles={"nav-link-selected": {"background-color": "#2D6A4F"}}
    )
    
    st.divider()
    # Botão manual para forçar atualização do cache
    if st.button("🔄 Atualizar Dados"):
        st.cache_data.clear()
        st.rerun()
        
    if st.button("🚪 Sair"):
        st.session_state["authenticated"] = False
        st.rerun()

# ----------------------------
# TELA: INVESTIMENTOS
# ----------------------------
if sel == "Investimentos":
    st.title("📊 BI - Performance da Obra")
    
    if not lista_obras:
        st.warning("⚠️ Nenhuma obra cadastrada. Vá em 'Projetos' para começar.")
        st.stop()
        
    c_top1, c_top2 = st.columns([3, 1])
    with c_top1:
        obra_sel = st.selectbox("Selecione a Obra:", lista_obras)
    
    # Filtra dados da obra
    obra_dados = df_obras[df_obras["Cliente"] == obra_sel].iloc[0]
    vgv = float(obra_dados["Valor Total"])
    df_v = df_fin[df_fin["Obra Vinculada"] == obra_sel].copy()
    
    # Filtros de Data
    with st.expander("📅 Filtrar Período", expanded=False):
        df_valid = df_v.dropna(subset=["Data_DT"]).copy()
        if not df_valid.empty:
            df_valid["Ano"] = df_valid["Data_DT"].dt.year
            anos_disp = sorted(df_valid["Ano"].unique())
            anos_sel = st.multiselect("Selecione os Anos", anos_disp, default=anos_disp)
            
            meses_sel = st.multiselect("Selecione os Meses", list(range(1,13)), default=list(range(1,13)))
            
            # Aplica filtro
            mask = (df_valid["Ano"].isin(anos_sel)) & (df_valid["Data_DT"].dt.month.isin(meses_sel))
            df_v = df_valid[mask]
        else:
            st.info("Sem datas válidas para filtrar.")

    # Cálculos Financeiros
    # Considera 'Saída' e 'Despesa'
    df_saidas = df_v[df_v["Tipo"].str.contains("Saída|Despesa", case=False, na=False)].copy()
    custos = df_saidas["Valor"].sum()
    lucro = vgv - custos
    roi = (lucro / custos * 100) if custos > 0 else 0
    perc_vgv = (custos / vgv * 100) if vgv > 0 else 0
    
    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("VGV (Contrato)", fmt_moeda(vgv))
    k2.metric("Custo Realizado", fmt_moeda(custos), delta=f"{perc_vgv:.1f}% do VGV", delta_color="inverse")
    k3.metric("Lucro Projetado", fmt_moeda(lucro))
    k4.metric("ROI Atual", f"{roi:.1f}%")
    
    st.markdown("---")
    
    # Gráficos
    g1, g2 = st.columns(2)
    
    # Gráfico de Categorias
    with g1:
        st.subheader("Gastos por Categoria")
        if not df_saidas.empty:
            df_cat = df_saidas.groupby("Categoria", as_index=False)["Valor"].sum().sort_values("Valor", ascending=False)
            fig = px.bar(df_cat, x="Categoria", y="Valor", text_auto=".2s", color_discrete_sequence=["#2D6A4F"])
            fig.update_layout(xaxis_title=None, yaxis_title=None, plot_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados neste período.")
            df_cat = pd.DataFrame(columns=["Categoria", "Valor"])

    # Gráfico de Evolução
    with g2:
        st.subheader("Curva de Gastos")
        if not df_saidas.empty:
            df_evo = df_saidas.sort_values("Data_DT")
            df_evo["Acumulado"] = df_evo["Valor"].cumsum()
            fig2 = px.line(df_evo, x="Data_DT", y="Acumulado", markers=True, color_discrete_sequence=["#E63946"])
            fig2.update_layout(xaxis_title=None, yaxis_title="R$ Acumulado", plot_bgcolor="white")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Sem evolução temporal.")

    # TABELA E DOWNLOAD
    st.markdown("---")
    c_tab, c_btn = st.columns([3, 1])
    
    with c_tab:
        st.subheader("Detalhamento dos Lançamentos")
        cols_show = ["Data_BR", "Categoria", "Descrição", "Valor"]
        df_show = df_saidas[cols_show].copy() if not df_saidas.empty else pd.DataFrame(columns=cols_show)
        df_show["Valor"] = df_show["Valor"].apply(fmt_moeda)
        st.dataframe(df_show, use_container_width=True, hide_index=True, height=300)

    with c_btn:
        st.write("") # Espaço para alinhar
        st.write("") 
        
        # PREPARA DADOS PARA PDF
        # Define string do período
        if not df_saidas.empty:
            d_min = df_saidas["Data_DT"].min().strftime("%d/%m/%Y")
            d_max = df_saidas["Data_DT"].max().strftime("%d/%m/%Y")
            periodo_pdf = f"{d_min} a {d_max}"
        else:
            periodo_pdf = "Período Vazio"

        # Gera Bytes
        pdf_bytes = gerar_relatorio_investimentos_pdf(
            obra=obra_sel,
            periodo=periodo_pdf,
            vgv=vgv,
            custos=custos,
            lucro=lucro,
            roi=roi,
            perc_vgv=perc_vgv,
            df_cat=df_cat, # Já agrupado
            df_lanc=df_show # Já formatado
        )
        
        # BOTÃO NATIVO DO STREAMLIT (Muito mais estável)
        st.download_button(
            label="⬇️ Baixar Relatório PDF",
            data=pdf_bytes,
            file_name=f"Relatorio_{obra_sel}_{date.today()}.pdf",
            mime="application/pdf"
        )

# ----------------------------
# TELA: CAIXA
# ----------------------------
elif sel == "Caixa":
    st.title("💸 Fluxo de Caixa")
    
    with st.container():
        st.markdown("### Novo Lançamento")
        with st.form("form_caixa", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            data_in = c1.date_input("Data", date.today())
            tipo_in = c2.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
            cat_in = c3.selectbox("Categoria", CATEGORIAS_PADRAO)
            
            c4, c5 = st.columns(2)
            obra_in = c4.selectbox("Vincular Obra", lista_obras if lista_obras else ["Geral"])
            val_in = c5.number_input("Valor (R$)", min_value=0.0, step=10.0)
            desc_in = st.text_input("Descrição / Fornecedor")
            
            if st.form_submit_button("💾 SALVAR LANÇAMENTO"):
                try:
                    conn = obter_db()
                    ws = conn.worksheet("Financeiro")
                    ws.append_row([
                        data_in.strftime("%Y-%m-%d"),
                        tipo_in,
                        cat_in,
                        desc_in,
                        float(val_in),
                        obra_in
                    ])
                    st.toast("Lançamento Salvo com Sucesso!", icon="✅")
                    # Limpa cache para mostrar novo dado imediatamente
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

    st.markdown("---")
    st.markdown("### Últimos Lançamentos")
    if not df_fin.empty:
        df_exibe = df_fin[["Data_BR", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]].copy()
        # Ordenar pelo índice reverso (últimos primeiro)
        df_exibe = df_exibe.iloc[::-1]
        df_exibe["Valor"] = df_exibe["Valor"].apply(fmt_moeda)
        st.dataframe(df_exibe, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum lançamento no banco de dados.")

# ----------------------------
# TELA: INSUMOS (Monitor de Preços)
# ----------------------------
elif sel == "Insumos":
    st.title("🛒 Monitor de Inflação de Materiais")
    st.info("O sistema compara o preço do último lançamento com o penúltimo do mesmo item.")
    
    df_saidas = df_fin[df_fin["Tipo"].str.contains("Saída", na=False)].copy()
    
    if df_saidas.empty:
        st.warning("Sem dados de saídas para analisar.")
    else:
        # Cria coluna simplificada de Insumo (pega texto antes de ':')
        df_saidas["Item"] = df_saidas["Descrição"].apply(lambda x: str(x).split(":")[0].strip())
        df_saidas = df_saidas.sort_values("Data_DT")
        
        itens_unicos = df_saidas["Item"].unique()
        alerta_encontrado = False
        
        col1, col2 = st.columns(2)
        
        for item in itens_unicos:
            hist = df_saidas[df_saidas["Item"] == item]
            if len(hist) >= 2:
                atual = hist.iloc[-1]
                anterior = hist.iloc[-2]
                
                v_atual = float(atual["Valor"])
                v_ant = float(anterior["Valor"])
                
                if v_ant > 0 and v_atual > v_ant:
                    aumento = ((v_atual / v_ant) - 1) * 100
                    if aumento >= 2.0: # Só mostra se aumentar mais de 2%
                        alerta_encontrado = True
                        msg = f"""
                        <div class='alert-card'>
                            <h4>🚨 {item}</h4>
                            <p>Subiu <b>{aumento:.1f}%</b></p>
                            <small>
                                📅 {anterior['Data_BR']}: {fmt_moeda(v_ant)}<br>
                                📅 {atual['Data_BR']}: <b>{fmt_moeda(v_atual)}</b>
                            </small>
                        </div>
                        """
                        col1.markdown(msg, unsafe_allow_html=True)

        if not alerta_encontrado:
            st.success("✅ Nenhum aumento abusivo (>2%) detectado nos insumos recentes.")

# ----------------------------
# TELA: PROJETOS
# ----------------------------
elif sel == "Projetos":
    st.title("🏗️ Cadastro de Obras")
    
    with st.form("form_obra"):
        c1, c2 = st.columns(2)
        nome = c1.text_input("Nome da Obra / Cliente")
        ender = c2.text_input("Endereço")
        
        c3, c4, c5 = st.columns(3)
        status = c3.selectbox("Status", ["Planejamento", "Fundação", "Estrutura", "Acabamento", "Entregue"])
        vgv_in = c4.number_input("Valor Total (VGV)", min_value=0.0, step=1000.0)
        prazo = c5.text_input("Prazo de Entrega")
        
        if st.form_submit_button("CADASTRAR OBRA"):
            if not nome:
                st.error("Nome da obra é obrigatório")
            else:
                try:
                    conn = obter_db()
                    ws = conn.worksheet("Obras")
                    # Gera ID
                    max_id = 0
                    if not df_obras.empty:
                        max_id = pd.to_numeric(df_obras["ID"], errors='coerce').max()
                        if pd.isna(max_id): max_id = 0
                    
                    ws.append_row([
                        int(max_id) + 1,
                        nome,
                        ender,
                        status,
                        float(vgv_in),
                        date.today().strftime("%Y-%m-%d"),
                        prazo
                    ])
                    st.success(f"Obra '{nome}' cadastrada!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

    st.markdown("### Obras Ativas")
    st.dataframe(df_obras, use_container_width=True, hide_index=True)
