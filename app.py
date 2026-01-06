import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import date

# --- 1. CONFIGURAÇÃO INICIAL (Obrigatório ser a primeira linha) ---
st.set_page_config(page_title="Gestor Construtivo Pro", layout="wide", page_icon="🔒")

# --- 2. SISTEMA DE LOGIN (A TRAVA DE SEGURANÇA) ---
def check_password():
    """Retorna True se o usuário acertar a senha."""
    # Se a chave 'logado' não existe na memória, cria ela como Falso
    if 'logado' not in st.session_state:
        st.session_state['logado'] = False

    # Se já estiver logado, libera o acesso
    if st.session_state['logado']:
        return True

    # --- TELA DE LOGIN ---
    st.markdown("## 🔒 Sistema Fechado")
    st.markdown("Este painel financeiro é restrito.")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        senha_digitada = st.text_input("Digite a Senha:", type="password")
        
        if st.button("Entrar no Sistema"):
            # === SUA SENHA ESTÁ AQUI ===
            if senha_digitada == "admin123":
                st.session_state['logado'] = True
                st.rerun() # Recarrega a página para entrar
            else:
                st.error("🚫 Senha Incorreta!")
    
    return False

# SE A SENHA NÃO FOR CORRETA, O CÓDIGO PARA AQUI
if not check_password():
    st.stop()

# =========================================================
# DAQUI PARA BAIXO, SÓ CARREGA SE TIVER A SENHA CORRETA
# =========================================================

# --- Estado da Mensagem ---
if 'msg_sucesso' not in st.session_state:
    st.session_state['msg_sucesso'] = None

# Arquivos
FILE_FINANCEIRO = 'dados_financeiro.csv'
FILE_OBRAS = 'dados_obras.csv'

# --- Funções ---
def carregar_dados():
    # OBRAS
    if os.path.exists(FILE_OBRAS):
        df_obras = pd.read_csv(FILE_OBRAS)
        if 'Valor Venda' not in df_obras.columns:
            df_obras['Valor Venda'] = 0.0
    else:
        df_obras = pd.DataFrame(columns=['Nome da Obra', 'Orçamento Previsto', 'Valor Venda', 'Área (m2)', 'Status'])
    
    # FINANCEIRO
    if os.path.exists(FILE_FINANCEIRO):
        df_fin = pd.read_csv(FILE_FINANCEIRO)
        if not df_fin.empty:
            df_fin['Data'] = pd.to_datetime(df_fin['Data']).dt.date
    else:
        df_fin = pd.DataFrame(columns=['Data', 'Obra', 'Tipo', 'Fase', 'Descrição', 'Valor', 'Fornecedor'])
        
    return df_obras, df_fin

def salvar_dados(df_obras, df_fin):
    df_obras.to_csv(FILE_OBRAS, index=False)
    df_fin.to_csv(FILE_FINANCEIRO, index=False)

df_obras, df_fin = carregar_dados()

# --- SIDEBAR (Só aparece se logado) ---
with st.sidebar:
    st.title("Gestor Construtivo")
    st.success("✅ Acesso Liberado")
    
    if st.button("Sair (Logout)"):
        st.session_state['logado'] = False
        st.rerun()
        
    st.markdown("---")
    st.header("📂 Exportar Relatórios")
    if df_fin.empty:
        st.info("Sem dados.")
    else:
        tipo = st.radio("Relatório:", ["Geral", "Por Obra"])
        df_exp = df_fin
        nome = "geral.csv"
        
        if tipo == "Por Obra":
            lista = df_obras['Nome da Obra'].unique()
            sel = st.selectbox("Escolha:", lista)
            df_exp = df_fin[df_fin['Obra'] == sel]
            nome = f"fin_{sel}.csv"
            
        csv = df_exp.to_csv(index=False).encode('utf-8-sig')
        st.download_button("⬇️ Baixar CSV", csv, nome, 'text/csv')

# --- Título ---
st.title("🏗️ Painel de Controle de Obras")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "💰 Lançamentos", "📝 Tabelas", "⚙️ Cadastrar Obras"])

# ABA 4
with tab4:
    st.header("Gestão de Obras")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("Nova Obra")
        with st.form("form_obra"):
            nome = st.text_input("Nome")
            status = st.selectbox("Status", ["Planejamento", "Fundação", "Estrutura", "Acabamento", "Venda", "Concluída"])
            orcamento = st.number_input("Orçamento (R$)", step=1000.0)
            venda = st.number_input("Venda Est. (R$)", step=5000.0)
            area = st.number_input("Área (m2)", step=10.0)
            if st.form_submit_button("Salvar"):
                if nome and nome not in df_obras['Nome da Obra'].values:
                    nova = pd.DataFrame({'Nome da Obra': [nome], 'Orçamento Previsto': [orcamento], 'Valor Venda': [venda], 'Área (m2)': [area], 'Status': [status]})
                    df_obras = pd.concat([df_obras, nova], ignore_index=True)
                    salvar_dados(df_obras, df_fin)
                    st.success("Salvo!")
                    st.rerun()
                else: st.error("Erro no nome.")
    with c2: 
        if not df_obras.empty: st.dataframe(df_obras, use_container_width=True)

# ABA 2
with tab2:
    if st.session_state['msg_sucesso']:
        st.success(st.session_state['msg_sucesso']); st.toast("Salvo!", icon="✅"); st.session_state['msg_sucesso'] = None
    
    lista = df_obras['Nome da Obra'].tolist()
    if not lista: st.warning("Cadastre obra antes.")
    else:
        st.subheader("Lançamento")
        with st.form("cx"):
            c1, c2, c3 = st.columns(3)
            dt = c1.date_input("Data", date.today())
            ob = c2.selectbox("Obra", lista)
            tp = c3.radio("Tipo", ["Despesa", "Receita"], horizontal=True)
            c4, c5, c6 = st.columns(3)
            fases = ["Admin", "Projetos", "Terreno", "Fundação", "Estrutura", "Instalações", "Acabamento", "Pintura", "Comissão"]
            fz = "Venda" if tp == "Receita" else c4.selectbox("Fase", fases)
            vl = c5.number_input("Valor", min_value=0.01)
            fr = c6.text_input("Fornecedor")
            dc = st.text_input("Descrição")
            if st.form_submit_button("Registrar"):
                vf = -vl if tp == "Despesa" else vl
                nv = pd.DataFrame({'Data': [dt], 'Obra': [ob], 'Tipo': [tp], 'Fase': [fz], 'Descrição': [dc], 'Valor': [vf], 'Fornecedor': [fr]})
                df_fin = pd.concat([df_fin, nv], ignore_index=True)
                salvar_dados(df_obras, df_fin)
                st.session_state['msg_sucesso'] = f"✅ {dc} - R$ {vl}"
                st.rerun()

# ABA 3
with tab3:
    if not df_fin.empty:
        df_ed = st.data_editor(df_fin, num_rows="dynamic", use_container_width=True, key='ed')
        if st.button("Salvar Tabela"):
            df_fin = df_ed; salvar_dados(df_obras, df_fin); st.rerun()

# ABA 1
with tab1:
    if not lista: st.info("Sem obras.")
    else:
        sel = st.selectbox("Filtrar:", ["Visão Geral"] + lista)
        if sel == "Visão Geral":
            df_d = df_fin.copy(); ve = df_obras['Valor Venda'].sum(); cp = df_obras['Orçamento Previsto'].sum()
        else:
            df_d = df_fin[df_fin['Obra'] == sel].copy()
            dd = df_obras[df_obras['Nome da Obra'] == sel].iloc[0]
            ve = dd['Valor Venda']; cp = dd['Orçamento Previsto']
        
        g = df_d[df_d['Valor'] < 0]['Valor'].sum() if not df_d.empty else 0
        r = df_d[df_d['Valor'] > 0]['Valor'].sum() if not df_d.empty else 0
        
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Saldo", f"R$ {g+r:,.2f}")
        k2.metric("Gasto", f"R$ {g:,.2f}", delta_color="inverse")
        k3.metric("Orçamento", f"R$ {cp:,.2f}")
        pc = (abs(g)/cp) if cp > 0 else 0
        k4.progress(min(pc, 1.0)); k4.metric("% Gasto", f"{pc*100:.0f}%")
        
        st.divider()
        if ve > 0:
            lc = ve - cp
            c1, c2 = st.columns(2)
            c1.metric("Venda Esperada", f"R$ {ve:,.2f}")
            c2.metric("Lucro Est.", f"R$ {lc:,.2f}", delta=f"{(lc/ve*100):.1f}%")
            
        g1, g2 = st.columns(2)
        if not df_d.empty and g < 0:
            pp = df_d[df_d['Valor'] < 0].copy(); pp['Valor'] = pp['Valor'].abs()
            with g1: st.plotly_chart(px.pie(pp, values='Valor', names='Fase', title="Custos", hole=0.4))
        if not df_d.empty:
            with g2: st.plotly_chart(px.line(df_d.sort_values('Data'), x='Data', y=df_d.sort_values('Data')['Valor'].cumsum(), title="Fluxo"))
