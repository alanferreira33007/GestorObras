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

    # Inicialização de variáveis de estado (sem alterações)
    if "k_fin_data" not in st.session_state: st.session_state.k_fin_data = date.today()
    if "k_fin_tipo" not in st.session_state: st.session_state.k_fin_tipo = "Saída (Despesa)"
    if "k_fin_cat" not in st.session_state: st.session_state.k_fin_cat = ""
    if "k_fin_obra" not in st.session_state: st.session_state.k_fin_obra = ""
    if "k_fin_valor" not in st.session_state: st.session_state.k_fin_valor = 0.0
    if "k_fin_desc" not in st.session_state: st.session_state.k_fin_desc = ""
    if "k_fin_forn" not in st.session_state: st.session_state.k_fin_forn = ""

    with st.expander("Novo Lançamento", expanded=True):
        with st.form("ffin", clear_on_submit=False):
            
            # --- LINHA 1: DATA | TIPO | VALOR ---
            c_row1_1, c_row1_2, c_row1_3 = st.columns([1, 1, 1])
            with c_row1_1:
                dt = st.date_input("Data", value=st.session_state.k_fin_data, key="k_fin_data")
            with c_row1_2:
                tp = st.selectbox("Tipo", ["Saída (Despesa)", "Entrada"], key="k_fin_tipo")
            with c_row1_3:
                vl = st.number_input("Valor R$ *", min_value=0.0, format="%.2f", step=100.0, value=st.session_state.k_fin_valor, key="k_fin_valor_input")

            # --- LINHA 2: OBRA | CATEGORIA ---
            c_row2_1, c_row2_2 = st.columns([1, 1])
            with c_row2_1:
                opcoes_obras = [""] + lista_obras
                ob = st.selectbox("Obra *", opcoes_obras, key="k_fin_obra")
            with c_row2_2:
                opcoes_cats = [""] + CATS
                ct = st.selectbox("Categoria *", opcoes_cats, key="k_fin_cat")

            # --- LINHA 3: FORNECEDOR | DESCRIÇÃO ---
            c_row3_1, c_row3_2 = st.columns([1, 1])
            with c_row3_1:
                # O placeholder ajuda a explicar a regra visualmente
                fn = st.text_input("Fornecedor", value=st.session_state.k_fin_forn, key="k_fin_forn", placeholder="Obrigatório se Categoria = Material")
            with c_row3_2:
                dc = st.text_input("Descrição *", value=st.session_state.k_fin_desc, key="k_fin_desc", placeholder="Detalhes do gasto")
            
            st.write("") # Espaçamento
            submitted_fin = st.form_submit_button("Salvar Lançamento", use_container_width=True)

            if submitted_fin:
                st.session_state.k_fin_valor = vl
                erros = []
                if not ob or ob == "": erros.append("Selecione a Obra Vinculada.")
                if not ct or ct == "": erros.append("Selecione a Categoria.")
                if vl <= 0: erros.append("O Valor deve ser maior que zero.")
                if not dc.strip(): erros.append("A Descrição é obrigatória.")
                
                # Validação condicional para Fornecedor
                if ct == "Material" and not fn.strip():
                    erros.append("Para a categoria 'Material', o campo Fornecedor é obrigatório.")

                if erros:
                    st.error("⚠️ Atenção:")
                    for e in erros: st.caption(f"- {e}")
                else:
                    try:
                        conn = get_conn()
                        # Grava na planilha
                        conn.worksheet("Financeiro").append_row([dt.strftime("%Y-%m-%d"),tp,ct,dc,vl,ob,fn])
                        
                        if "data_fin" in st.session_state: del st.session_state["data_fin"]
                        st.cache_data.clear()
                        
                        st.session_state["sucesso_fin"] = True
                        st.rerun() 
                    except Exception as e: st.error(f"Erro: {e}")

    st.markdown("---")
    # ... (Resto do código da tabela de consulta permanece igual)
