import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px  # Import global para evitar delay no dashboard
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

# CSS PARA PERFORMANCE E VISUAL
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    /* Otimização de renderização de métricas */
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
    
    /* Sidebar mais limpa e rápida */
    [data-testid="stSidebar"] { 
        background-color: #f8f9fa; 
        border-right: 1px solid #e9ecef; 
    }
    
    /* Esconde spinner padrão do topo para sensação de fluidez */
    .stSpinner { display: none; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. FUNÇÕES DE SUPORTE (LEVES)
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
# 3. CONEXÃO E DADOS (COM CACHE AGRESSIVO)
# ==============================================================================
# Configura o cache para não recarregar toda hora e manter a velocidade
@st.cache_resource
def get_conn():
    creds = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
    return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])).open("GestorObras_DB")

@st.cache_data(ttl=300) # Cache de 5 minutos para velocidade máxima
def get_data_cached():
    try:
        db = get_conn()
        
        # Busca Obras
        ws_o = db.worksheet("Obras")
        raw_o = ws_o.get_all_records()
        df_o = pd.DataFrame(raw_o)
        
        # Busca Financeiro
        ws_f = db.worksheet("Financeiro")
        raw_f = ws_f.get_all_records()
        df_f = pd.DataFrame(raw_f)
        
        # Estrutura vazia se falhar
        cols_obras = ["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo", "Area Construida", "Area Terreno", "Quartos", "Custo Previsto"]
        cols_fin = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]
        
        if df_o.empty: df_o = pd.DataFrame(columns=cols_obras)
        else:
            for c in cols_obras: 
                if c not in df_o.columns: df_o[c] = None
                
        if df_f.empty: df_f = pd.DataFrame(columns=cols_fin)
        else:
            for c in cols_fin: 
                if c not in df_f.columns: df_f[c] = None

        # Tratamento numérico rápido
        df_o["Valor Total"] = df_o["Valor Total"].apply(safe_float)
        if "Custo Previsto" in df_o.columns:
            df_o["Custo Previsto"] = df_o["Custo Previsto"].apply(safe_float)
            
        df_f["Valor"] = df_f["Valor"].apply(safe_float)
        df_f["Data_DT"] = pd.to_datetime(df_f["Data"], errors="coerce")
        
        return df_o, df_f
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

# ==============================================================================
# 4. GERAÇÃO DE PDF (LAZY LOADING EXTREMO)
# ==============================================================================
def gerar_pdf_empresarial(escopo, periodo, vgv, custos, lucro, roi, df_cat, df_lanc):
    # Importa APENAS quando clica no botão para não travar o app no início
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_RIGHT

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
                self.setStrokeColor(colors.lightgrey)
                self.line(30, 50, A4[0]-30, 50)
                self.setFillColor(colors.grey)
                self.setFont("Helvetica", 8)
                self.drawString(30, 35, "GESTOR PRO • Sistema Integrado")
                self.drawRightString(A4[0]-30, 35, datetime.now().strftime("%d/%m/%Y %H:%M"))
                self.drawRightString(A4[0]-30, 25, f"Pág {self.getPageNumber()}/{num_pages}")
                super().showPage()
            super().save()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=60)
    story = []
    styles = getSampleStyleSheet()
    
    # Cabeçalho
    story.append(Paragraph(f"RELATÓRIO: {escopo.upper()}", ParagraphStyle('T', parent=styles['Normal'], fontSize=14, textColor=colors.white, fontName='Helvetica-Bold')))
    story.append(Spacer(1, 20))
    
    # Resumo
    dados = [["VGV", "CUSTOS", "LUCRO", "ROI"], [fmt_moeda(vgv), fmt_moeda(custos), fmt_moeda(lucro), f"{roi:.1f}%"]]
    t = Table(dados, colWidths=[4.5*cm]*4)
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8f9fa")), ('TEXTCOLOR', (0,0), (-1,-1), colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('BOX', (0,0), (-1,-1), 0.5, colors.grey)]))
    story.append(t)
    story.append(Spacer(1, 20))
    
    # Tabela Simples
    if not df_lanc.empty:
        df_l = df_lanc.copy()
        df_l["Valor"] = df_l["Valor"].apply(fmt_moeda)
        data = [["Data", "Categoria", "Descrição", "Valor"]] + df_l[["Data", "Categoria", "Descrição", "Valor"]].values.tolist()
        t2 = Table(data, colWidths=[2.5*cm, 3.5*cm, 9*cm, 3*cm])
        t2.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2D6A4F")), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey), ('ALIGN', (-1,0), (-1,-1), 'RIGHT')]))
        story.append(t2)

    doc.build(story, canvasmaker=EnterpriseCanvas)
    return buffer.getvalue()

# ==============================================================================
# 5. AUTENTICAÇÃO (INSTANTÂNEA)
# ==============================================================================
if "auth" not in st.session_state: st.session_state.auth = False

def check_password():
    if st.session_state["pwd_input"] == st.secrets["password"]:
        st.session_state.auth = True
    else:
        st.error("Senha incorreta")

if not st.session_state.auth:
    _, c2, _ = st.columns([1,1,1])
    with c2:
        st.markdown("<br><h2 style='text-align:center; color:#2D6A4F'>GESTOR PRO</h2>", unsafe_allow_html=True)
        st.text_input("Senha", type="password", key="pwd_input", on_change=check_password)
        st.button("ENTRAR", use_container_width=True, on_click=check_password)
    st.stop()

# ==============================================================================
# 6. RENDERIZAÇÃO DA INTERFACE (SIDEBAR PRIMEIRO)
# ==============================================================================
# Renderiza a Sidebar ANTES de carregar dados para garantir sensação de instantaneidade
with st.sidebar:
    st.markdown("<h2 style='color: #2D6A4F; margin:0;'>GESTOR PRO</h2><p style='color:gray; font-size:12px;'>Incorporadora</p>", unsafe_allow_html=True)
    sel = option_menu(None, ["Dashboard", "Financeiro", "Obras"], icons=["pie-chart-fill", "wallet-fill", "building-fill"], default_index=0, styles={"nav-link-selected": {"background-color": "#2D6A4F"}})
    st.markdown("---")
    if st.button("Sair", use_container_width=True):
        st.session_state.auth = False
        st.rerun()

# ==============================================================================
# 7. CARREGAMENTO DE DADOS (CACHEADO)
# ==============================================================================
# Chama a função com cache. Na primeira vez demora 1s, nas próximas é instantâneo (0s).
df_obras, df_fin = get_data_cached()
lista_obras = df_obras["Cliente"].unique().tolist() if not df_obras.empty else []
CATS = ["Material", "Mão de Obra", "Serviços", "Administrativo", "Impostos", "Outros"]

# --- DASHBOARD ---
if sel == "Dashboard":
    c_tit, c_sel, c_btn = st.columns([1.5, 2, 1])
    with c_tit: st.title("Visão Geral")
    with c_sel:
        opcoes = ["Visão Geral (Todas as Obras)"] + lista_obras if lista_obras else []
        escopo = st.selectbox("Escopo", opcoes, label_visibility="collapsed") if opcoes else None
        
    with c_btn:
        if st.button("🔄 Atualizar", use_container_width=True):
            st.cache_data.clear() # Limpa cache para forçar nova busca
            st.rerun()

    if not df_obras.empty and escopo:
        # Filtros e Cálculos
        if "Visão Geral" in escopo:
            vgv = df_obras["Valor Total"].sum()
            df_show = df_fin[df_fin["Tipo"].astype(str).str.contains("Saída|Despesa", case=False, na=False)].copy()
        else:
            row = df_obras[df_obras["Cliente"] == escopo].iloc[0]
            vgv = row["Valor Total"]
            df_show = df_fin[(df_fin["Obra Vinculada"] == escopo) & (df_fin["Tipo"].astype(str).str.contains("Saída|Despesa", case=False, na=False))].copy()

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
            st.subheader("Evolução")
            if not df_show.empty:
                df_ev = df_show.sort_values("Data_DT")
                df_ev["Acumulado"] = df_ev["Valor"].cumsum()
                fig = px.area(df_ev, x="Data_DT", y="Acumulado", color_discrete_sequence=["#2D6A4F"])
                fig.update_layout(plot_bgcolor="white", margin=dict(t=10,l=10,r=10,b=10), height=250)
                st.plotly_chart(fig, use_container_width=True)
        with g2:
            st.subheader("Categorias")
            if not df_show.empty:
                df_cat = df_show.groupby("Categoria", as_index=False)["Valor"].sum()
                # CORRIGIDO: Cores distintas (Qualitative Bold)
                fig2 = px.pie(df_cat, values="Valor", names="Categoria", hole=0.6, color_discrete_sequence=px.colors.qualitative.Bold)
                fig2.update_layout(showlegend=False, margin=dict(t=0,l=0,r=0,b=0), height=200)
                st.plotly_chart(fig2, use_container_width=True)

        # PDF Download
        st.markdown("---")
        dmin = df_show["Data_DT"].min().strftime("%d/%m/%Y") if not df_show.empty else "-"
        dmax = df_show["Data_DT"].max().strftime("%d/%m/%Y") if not df_show.empty else "-"
        
        pdf_bytes = gerar_pdf_empresarial(escopo, f"{dmin} a {dmax}", vgv, custos, lucro, roi, df_cat if not df_show.empty else pd.DataFrame(), df_show)
        st.download_button("⬇️ Baixar Relatório PDF", data=pdf_bytes, file_name=f"Relatorio_{date.today()}.pdf", mime="application/pdf", use_container_width=True)
    else:
        st.info("Cadastre obras para visualizar o dashboard.")

# --- FINANCEIRO ---
elif sel == "Financeiro":
    st.title("Financeiro")
    
    # State managment seguro
    if "k_fin_valor" not in st.session_state: st.session_state.k_fin_valor = 0.0
    
    with st.expander("Novo Lançamento", expanded=True):
        with st.form("ffin", clear_on_submit=True):
            c1, c2 = st.columns(2)
            dt = c1.date_input("Data", date.today())
            tp = c1.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
            ct = c1.selectbox("Categoria", CATS)
            ob = c2.selectbox("Obra", [""] + lista_obras)
            
            # CORRIGIDO: Apenas números (bloqueia letras)
            vl = c2.number_input("Valor R$", min_value=0.0, format="%.2f", step=100.0)
            dc = c2.text_input("Descrição")
            
            if st.form_submit_button("Salvar", use_container_width=True):
                if ob and ct and vl > 0 and dc:
                    try:
                        conn = get_conn()
                        conn.worksheet("Financeiro").append_row([dt.strftime("%Y-%m-%d"), tp, ct, dc, vl, ob])
                        st.cache_data.clear() # Limpa cache para ver atualização
                        st.toast("✅ Salvo com sucesso!")
                        st.rerun()
                    except: st.error("Erro ao salvar")
                else:
                    st.warning("Preencha todos os campos obrigatórios")

    if not df_fin.empty:
        st.markdown("---")
        col_f1, col_f2 = st.columns(2)
        f_obra = col_f1.multiselect("Filtrar Obra", lista_obras)
        f_cat = col_f2.multiselect("Filtrar Categoria", CATS)
        
        df_v = df_fin.copy()
        if f_obra: df_v = df_v[df_v["Obra Vinculada"].isin(f_obra)]
        if f_cat: df_v = df_v[df_v["Categoria"].isin(f_cat)]
        
        st.dataframe(df_v.sort_values("Data_DT", ascending=False), use_container_width=True, hide_index=True, column_config={"Valor": st.column_config.NumberColumn(format="R$ %.2f")})

# --- OBRAS ---
elif sel == "Obras":
    st.title("Gestão de Obras")
    st.markdown("---")
    
    with st.expander("➕ Nova Obra", expanded=False):
        with st.form("f_obra"):
            c1, c2 = st.columns([3,2])
            nome = c1.text_input("Nome *")
            end = c2.text_input("Endereço *")
            
            c3, c4, c5, c6 = st.columns(4)
            # CORRIGIDO: number_input para travar letras
            ac = c3.number_input("Área Const. (m²)", min_value=0.0)
            at = c4.number_input("Área Terr. (m²)", min_value=0.0)
            qts = c5.number_input("Quartos", min_value=0, step=1)
            stt = c6.selectbox("Fase", ["Projeto", "Fundação", "Alvenaria", "Acabamento", "Concluída"])
            
            c7, c8, c9, c10 = st.columns(4)
            custo = c7.number_input("Orçamento *", min_value=0.0, step=1000.0)
            venda = c8.number_input("VGV (Venda) *", min_value=0.0, step=1000.0)
            dt_ini = c9.date_input("Início")
            prazo = c10.text_input("Prazo *")
            
            if st.form_submit_button("Salvar Obra", use_container_width=True):
                if nome and end and custo > 0 and venda > 0:
                    try:
                        conn = get_conn()
                        ws = conn.worksheet("Obras")
                        ids = pd.to_numeric(df_obras["ID"], errors="coerce").fillna(0)
                        new_id = int(ids.max()) + 1 if not ids.empty else 1
                        ws.append_row([new_id, nome, end, stt, float(venda), dt_ini.strftime("%Y-%m-%d"), prazo, float(ac), float(at), int(qts), float(custo)])
                        st.cache_data.clear()
                        st.toast("✅ Obra cadastrada!")
                        st.rerun()
                    except Exception as e: st.error(f"Erro: {e}")
                else: st.warning("Preencha campos obrigatórios")

    if not df_obras.empty:
        st.subheader("Carteira de Obras")
        # Editor limpo e funcional
        df_edit = df_obras.copy()
        edited = st.data_editor(
            df_edit, 
            use_container_width=True, 
            hide_index=True, 
            disabled=["ID"],
            column_config={
                "ID": st.column_config.NumberColumn(width="small"),
                "Valor Total": st.column_config.NumberColumn("VGV", format="R$ %.0f"),
                "Custo Previsto": st.column_config.NumberColumn("Custo", format="R$ %.0f"),
                "Area Construida": st.column_config.NumberColumn("Área", format="%.0f"),
                "Status": st.column_config.SelectboxColumn("Fase", options=["Projeto", "Fundação", "Alvenaria", "Acabamento", "Concluída", "Vendida"], required=True)
            }
        )
        
        # Botão salvar condicional (simples e robusto)
        if not edited.equals(df_obras):
            c_pwd, c_btn = st.columns([2,1])
            pwd = c_pwd.text_input("Senha para salvar", type="password", label_visibility="collapsed", placeholder="Senha ADM")
            if c_btn.button("💾 Salvar Alterações", type="primary"):
                if pwd == st.secrets["password"]:
                    try:
                        conn = get_conn()
                        ws = conn.worksheet("Obras")
                        # Lógica de update simplificada para performance
                        data_list = [edited.columns.tolist()] + edited.astype(str).values.tolist()
                        ws.update("A1", data_list) 
                        st.cache_data.clear()
                        st.toast("✅ Atualizado!")
                        st.rerun()
                    except Exception as e: st.error(f"Erro: {e}")
                else:
                    st.toast("⛔ Senha incorreta")
