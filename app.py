import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from streamlit_option_menu import option_menu
import io
import random

# PDF Libs
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas

# ==============================================================================
# 1. CONFIGURAÇÃO VISUAL (UI/UX)
# ==============================================================================
st.set_page_config(
    page_title="GESTOR PRO | Business",
    layout="wide",
    page_icon="🏗️",
    initial_sidebar_state="expanded"
)

# CSS: Botões Maiores e Mais Robustos
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700;
        color: #1a1a1a;
    }
    
    /* BOTÕES GRANDES E CHAMATIVOS */
    div.stButton > button {
        background-color: #2D6A4F;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 1rem; /* Mais altura */
        font-size: 1rem;       /* Texto maior */
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    div.stButton > button:hover {
        background-color: #1B4332;
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(45, 106, 79, 0.3);
    }
    
    /* Botão secundário (se houver) */
    div.stButton > button:active {
        background-color: #1B4332;
        transform: translateY(0px);
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #e9ecef;
    }
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

# --- MOTOR PDF ---
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
        self.line(30, 30, width-30, 30)
        self.setFillColor(colors.grey)
        self.setFont("Helvetica", 9)
        self.drawString(30, 15, self.footer_txt)
        self.drawRightString(width-30, 15, f"Pág. {self.getPageNumber()}/{page_count}")

def gerar_pdf(obra, periodo, vgv, custos, lucro, roi, df_cat, df_lanc):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=50)
    story = []
    styles = getSampleStyleSheet()
    
    story.append(Paragraph("RELATÓRIO DE PERFORMANCE", styles["Title"]))
    story.append(Paragraph(f"Escopo: {obra} | Período: {periodo}", styles["Normal"]))
    story.append(Spacer(1, 20))

    data_resumo = [
        ["INDICADOR", "VALOR"],
        ["VGV (Total)", fmt_moeda(vgv)],
        ["Custo Total", fmt_moeda(custos)],
        ["Lucro Líquido", fmt_moeda(lucro)],
        ["ROI", f"{roi:.2f}%"]
    ]
    t = Table(data_resumo, colWidths=[200, 150], hAlign="LEFT")
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2D6A4F")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('bottomPadding', (0,0), (-1,-1), 8),
        ('topPadding', (0,0), (-1,-1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 20))

    story.append(Paragraph("Detalhamento por Categoria", styles["Heading3"]))
    if not df_cat.empty:
        df_c = df_cat.copy()
        df_c["Valor"] = df_c["Valor"].apply(fmt_moeda)
        data_cat = [df_c.columns.to_list()] + df_c.values.tolist()
        t2 = Table(data_cat, hAlign="LEFT")
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#40916C")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
        ]))
        story.append(t2)
    
    doc.build(story, canvasmaker=lambda *a, **k: NumberedCanvas(*a, footer_txt=f"Gestor Pro - {date.today()}", **k))
    return buffer.getvalue()

# ==============================================================================
# 3. CONEXÃO E DADOS
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
            for i in range(10):
                fake_data.append({
                    "Data": (date.today() - timedelta(days=i*5)).strftime("%Y-%m-%d"),
                    "Tipo": "Saída (Despesa)",
                    "Categoria": random.choice(CATS),
                    "Descrição": f"Compra Simulação {i+1}",
                    "Valor": random.uniform(1000, 5000),
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
# 4. APLICAÇÃO PRINCIPAL
# ==============================================================================
if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; color: #2D6A4F;'>GESTOR PRO</h1>", unsafe_allow_html=True)
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
        menu_title=None,
        options=["Dashboard", "Financeiro", "Obras"],
        icons=["bar-chart-fill", "wallet-fill", "building-fill"],
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "#f8f9fa"},
            "nav-link": {"font-size": "14px", "margin":"5px", "--hover-color": "#e9ecef"},
            "nav-link-selected": {"background-color": "#2D6A4F"},
        }
    )
    st.markdown("---")
    if st.button("Sair"):
        st.session_state.auth = False
        st.rerun()

# --- DASHBOARD ---
if selected == "Dashboard":
    
    # ---------------------------------------------------------
    # LAYOUT DE TOPO: Título + Seletor + Botão Atualizar (GRANDE)
    # ---------------------------------------------------------
    col_tit, col_sel, col_upd = st.columns([1.5, 2, 0.8])
    
    with col_tit:
        st.title("Visão Geral")
        
    with col_sel:
        # Seletor centralizado
        if lista_obras:
            opcoes_dash = ["Visão Geral (Todas as Obras)"] + lista_obras
            selecao = st.selectbox("Selecione o Escopo:", opcoes_dash, label_visibility="collapsed")
        else:
            st.warning("Cadastre uma obra primeiro.")
            st.stop()
            
    with col_upd:
        # Botão ATUALIZAR no topo, grande e alinhado
        if st.button("🔄 Atualizar Dados", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # ---------------------------------------------------------
    # PROCESSAMENTO DE DADOS
    # ---------------------------------------------------------
    if selecao == "Visão Geral (Todas as Obras)":
        st.markdown("##### 🏢 Consolidado da Empresa")
        vgv = df_obras["Valor Total"].sum()
        df_saidas = df_fin[df_fin["Tipo"].astype(str).str.contains("Saída|Despesa", case=False, na=False)].copy()
    else:
        st.markdown(f"##### 🏗️ Obra: {selecao}")
        row_obra = df_obras[df_obras["Cliente"] == selecao].iloc[0]
        vgv = row_obra["Valor Total"]
        df_f_obra = df_fin[df_fin["Obra Vinculada"] == selecao].copy()
        df_saidas = df_f_obra[df_f_obra["Tipo"].astype(str).str.contains("Saída|Despesa", case=False, na=False)].copy()
    
    custos = df_saidas["Valor"].sum()
    lucro = vgv - custos
    roi = (lucro / custos * 100) if custos > 0 else 0
    progresso_fin = (custos / vgv) if vgv > 0 else 0
    
    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        with st.container(border=True): st.metric("VGV Total", fmt_moeda(vgv))
    with c2:
        with st.container(border=True): st.metric("Custo Realizado", fmt_moeda(custos), delta=f"{progresso_fin*100:.1f}% gasto", delta_color="inverse")
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
    
    # Tabela
    st.markdown("### Últimos Lançamentos")
    if not df_saidas.empty:
        df_show = df_saidas[["Data", "Categoria", "Descrição", "Valor"]].sort_values("Data", ascending=False)
        st.dataframe(
            df_show, use_container_width=True, hide_index=True, height=300,
            column_config={
                "Valor": st.column_config.ProgressColumn("Valor (R$)", format="R$ %.2f", min_value=0, max_value=float(df_show["Valor"].max())),
                "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")
            }
        )
    else: st.info("Nenhum lançamento registrado.")
            
    # ---------------------------------------------------------
    # BOTÃO PDF: FINAL DA PÁGINA (GRANDE E LARGO)
    # ---------------------------------------------------------
    st.write("")
    st.markdown("---")
    if not df_saidas.empty:
        # Gera o PDF em memória
        pdf_data = gerar_pdf(selecao, "Visão Atual", vgv, custos, lucro, roi, df_cat if 'df_cat' in locals() else pd.DataFrame(), df_show)
        
        # Coluna centralizada ou full width
        st.download_button(
            label="⬇️ BAIXAR RELATÓRIO PDF COMPLETO",
            data=pdf_data,
            file_name=f"Relatorio_{selecao}.pdf",
            mime="application/pdf",
            use_container_width=True,  # OCUPA A LARGURA TODA
            help="Clique para baixar o relatório detalhado deste período"
        )

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
            if st.form_submit_button("Salvar Lançamento", use_container_width=True):
                try:
                    conn = get_conn()
                    conn.worksheet("Financeiro").append_row([f_dt.strftime("%Y-%m-%d"), f_tp, f_ct, f_dc, f_vl, f_ob])
                    st.toast("Salvo!", icon="✅")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e: st.error(f"Erro: {e}")

    st.markdown("### Histórico Completo")
    if not df_fin.empty:
        cf1, cf2 = st.columns(2)
        fo = cf1.multiselect("Filtrar por Obra", lista_obras)
        dg = df_fin.copy()
        if fo: dg = dg[dg["Obra Vinculada"].isin(fo)]
        st.dataframe(dg.sort_values("Data_DT", ascending=False), use_container_width=True, hide_index=True, column_config={"Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"), "Data_DT": None, "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")})

# --- OBRAS ---
elif selected == "Obras":
    st.title("Portfólio de Obras")
    c_form, c_view = st.columns([1, 2])
    with c_form:
        with st.container(border=True):
            st.markdown("#### Cadastro")
            with st.form("new_obra"):
                nc = st.text_input("Nome Cliente")
                ne = st.text_input("Endereço")
                nv = st.number_input("VGV (R$)", min_value=0.0)
                ns = st.selectbox("Status", ["Planejamento", "Em Andamento", "Concluído"])
                np = st.text_input("Prazo")
                if st.form_submit_button("Criar Obra", use_container_width=True):
                    try:
                        conn = get_conn()
                        idx = len(lista_obras) + 1
                        conn.worksheet("Obras").append_row([idx, nc, ne, ns, nv, date.today().strftime("%Y-%m-%d"), np])
                        st.toast("Criado!", icon="🏗️")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e: st.error(f"Erro: {e}")
    with c_view:
        if not df_obras.empty:
            for i, r in df_obras.iterrows():
                with st.container(border=True):
                    ci, cnf, cv = st.columns([1, 3, 2])
                    with ci: st.markdown("# 🏠")
                    with cnf: st.markdown(f"**{r['Cliente']}**"); st.caption(f"{r['Endereço']} • {r['Status']}")
                    with cv: st.metric("VGV", fmt_moeda(r['Valor Total']))
