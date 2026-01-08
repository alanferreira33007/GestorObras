import streamlit as st
from database import carregar_dados, salvar_financeiro, salvar_obra
from relatorios import fmt_moeda
from streamlit_option_menu import option_menu
from datetime import date

st.set_page_config(page_title="GESTOR PRO", layout="wide")

# Verificação de Senha (igual ao anterior)
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if not st.session_state["authenticated"]:
    with st.form("login"):
        pwd = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if pwd == st.secrets["password"]:
                st.session_state["authenticated"] = True
                st.rerun()
    st.stop()

# Carregamento de dados
df_obras, df_fin = carregar_dados()
lista_obras = df_obras["Cliente"].unique().tolist()

with st.sidebar:
    sel = option_menu("GESTOR PRO", ["Investimentos", "Caixa", "Projetos"], icons=["graph-up", "wallet2", "building"])

# --- TELA CAIXA (CADASTRO) ---
if sel == "Caixa":
    st.title("💸 Lançamento Financeiro")
    
    with st.form("form_financeiro", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        data_f = c1.date_input("Data", value=date.today())
        tipo_f = c2.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
        cat_f  = c3.selectbox("Categoria", ["Geral", "Material", "Mão de Obra", "Serviços", "Impostos", "Outros"])
        
        c4, c5 = st.columns(2)
        obra_f = c4.selectbox("Obra Vinculada", lista_obras if lista_obras else ["Geral"])
        valor_f = c5.number_input("Valor R$", min_value=0.0, step=0.01, format="%.2f")
        
        desc_f = st.text_input("Descrição")
        
        if st.form_submit_button("REGISTRAR NO GOOGLE SHEETS"):
            salvar_financeiro([data_f.strftime("%Y-%m-%d"), tipo_f, cat_f, desc_f, valor_f, obra_f])
            st.success("Lançamento salvo com sucesso!")
            st.rerun()

    st.divider()
    st.subheader("Histórico Recente")
    st.dataframe(df_fin.sort_values("Data_DT", ascending=False), use_container_width=True)

# --- TELA PROJETOS (CADASTRO DE OBRA) ---
elif sel == "Projetos":
    st.title("🏗️ Cadastro de Novas Obras")
    
    with st.form("form_obra", clear_on_submit=True):
        nome_o = st.text_input("Nome da Obra / Cliente")
        end_o  = st.text_input("Endereço")
        
        c1, c2 = st.columns(2)
        vgv_o = c1.number_input("Valor Total (VGV)", min_value=0.0, step=1000.0)
        status_o = c2.selectbox("Status", ["Planejamento", "Construção", "Finalizada"])
        
        if st.form_submit_button("CADASTRAR OBRA"):
            # Gera um ID simples baseado na quantidade de linhas
            novo_id = len(df_obras) + 1
            salvar_obra([novo_id, nome_o, end_o, status_o, vgv_o, date.today().strftime("%Y-%m-%d"), "A definir"])
            st.success("Obra cadastrada!")
            st.rerun()

    st.divider()
    st.subheader("Obras Ativas")
    st.dataframe(df_obras, use_container_width=True)

# --- TELA INVESTIMENTOS (RESUMO) ---
elif sel == "Investimentos":
    st.title("📊 Painel de Performance")
    if not lista_obras:
        st.info("Cadastre uma obra primeiro na tela 'Projetos'.")
    else:
        # (Aqui fica aquele código de métricas que já funcionava)
        st.write("Selecione a obra acima para ver o ROI.")
