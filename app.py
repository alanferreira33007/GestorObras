# --- OBRAS ---
elif sel == "Obras":
    st.title("📂 Gestão de Incorporação e Obras")
    st.markdown("---")

    if st.session_state.get("sucesso_obra"):
        st.success(f"✅ Dados atualizados com sucesso!", icon="🏡")
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
            with c1: nome_obra = st.text_input("Nome do Empreendimento *", placeholder="Ex: Res. Vila Verde - Casa 04", value=st.session_state.k_ob_nome, key="k_ob_nome")
            with c2: endereco = st.text_input("Endereço *", placeholder="Rua, Bairro...", value=st.session_state.k_ob_end, key="k_ob_end")

            st.markdown("#### 2. Características Físicas (Produto)")
            c4, c5, c6, c7 = st.columns(4)
            with c4: area_const = st.number_input("Área Construída (m²)", min_value=0.0, format="%.2f", value=st.session_state.k_ob_area_c, key="k_ob_area_c")
            with c5: area_terr = st.number_input("Área Terreno (m²)", min_value=0.0, format="%.2f", value=st.session_state.k_ob_area_t, key="k_ob_area_t")
            with c6: quartos = st.number_input("Qtd. Quartos", min_value=0, step=1, value=st.session_state.k_ob_quartos, key="k_ob_quartos")
            with c7: status = st.selectbox("Fase Atual", ["Projeto", "Fundação", "Alvenaria", "Acabamento", "Concluída", "Vendida"], key="k_ob_status")

            st.markdown("#### 3. Viabilidade Financeira e Prazos")
            c8, c9, c10, c11 = st.columns(4)
            with c8: custo_previsto = st.number_input("Orçamento (Custo) *", min_value=0.0, format="%.2f", step=1000.0, value=st.session_state.k_ob_custo, key="k_ob_custo_input")
            with c9: valor_venda = st.number_input("VGV (Venda) *", min_value=0.0, format="%.2f", step=1000.0, value=st.session_state.k_ob_vgv, key="k_ob_vgv_input")
            with c10: data_inicio = st.date_input("Início da Obra", value=st.session_state.k_ob_data, key="k_ob_data")
            with c11: prazo_entrega = st.text_input("Prazo / Entrega *", placeholder="Ex: dez/2025", value=st.session_state.k_ob_prazo, key="k_ob_prazo")

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
                        ws.append_row([novo_id, nome_obra.strip(), endereco.strip(), status, float(valor_venda), data_inicio.strftime("%Y-%m-%d"), prazo_entrega.strip(), float(area_const), float(area_terr), int(quartos), float(custo_previsto)])
                        
                        if "data_obras" in st.session_state: del st.session_state["data_obras"]
                        st.cache_data.clear()
                        
                        st.session_state["sucesso_obra"] = True
                        st.rerun()
                    except Exception as e: st.error(f"Erro no Google Sheets: {e}")

    st.markdown("### 📋 Carteira de Obras")
    if not df_obras.empty:
        cols_order = ["ID", "Cliente", "Status", "Prazo", "Valor Total", "Custo Previsto", "Area Construida", "Area Terreno", "Quartos"]
        valid_cols = [c for c in cols_order if c in df_obras.columns]
        df_to_edit = df_obras[valid_cols].copy().reset_index(drop=True)
        num_cols = ["Valor Total", "Custo Previsto", "Area Construida", "Area Terreno", "Quartos", "ID"]
        for c in df_to_edit.columns:
            if c in num_cols: df_to_edit[c] = pd.to_numeric(df_to_edit[c], errors='coerce').fillna(0)
            else: df_to_edit[c] = df_to_edit[c].fillna("")

        edited_df = st.data_editor(df_to_edit, use_container_width=True, hide_index=True, num_rows="fixed", disabled=["ID"],
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
            })
        
        st.write("")
        has_changes = not edited_df.equals(df_to_edit)
        if has_changes:
            with st.container(border=True):
                c_alert, c_pwd, c_btn = st.columns([2, 1.5, 1])
                with c_alert: st.warning("⚠️ Alterações pendentes. Confirme para salvar.", icon="⚠️")
                with c_pwd: pwd_confirm = st.text_input("Senha", type="password", placeholder="Senha ADM", label_visibility="collapsed")
                with c_btn:
                    if st.button("💾 SALVAR", type="primary", use_container_width=True):
                        if pwd_confirm == st.secrets["password"]:
                            try:
                                conn = get_conn()
                                ws = conn.worksheet("Obras")
                                with st.spinner("Salvando..."):
                                    sheet_data = ws.get_all_records()
                                    for index, row in edited_df.iterrows():
                                        id_obra = row["ID"]
                                        found_cell = ws.find(str(id_obra), in_column=1) 
                                        if found_cell:
                                            original_row = df_obras[df_obras["ID"] == id_obra].iloc[0]
                                            update_values = []
                                            for col in OBRAS_COLS:
                                                if col in row: val = row[col]
                                                else: val = original_row[col]
                                                if isinstance(val, (pd.Timestamp, date, datetime)): val = val.strftime("%Y-%m-%d")
                                                elif pd.isna(val): val = ""
                                                update_values.append(val)
                                            ws.update(f"A{found_cell.row}:K{found_cell.row}", [update_values])
                                
                                if "data_obras" in st.session_state: del st.session_state["data_obras"]
                                st.cache_data.clear()
                                st.session_state["sucesso_obra"] = True
                                st.rerun()
                            except Exception as e: st.error(f"Erro ao salvar: {e}")
                        else: st.toast("Senha incorreta!", icon="⛔")
        else: st.caption("💡 Edite diretamente na tabela acima. O botão de salvar aparecerá automaticamente.")

        # --- ÁREA DE EXCLUSÃO (Agora indentada corretamente) ---
        st.write("")
        st.markdown("### 🗑️ Zona de Exclusão")
        with st.expander("Excluir Obra Definitivamente", expanded=False):
            # Lista formatada para facilitar seleção
            obra_options = df_obras.apply(lambda x: f"{x['ID']} | {x['Cliente']}", axis=1).tolist()
            selected_obra_delete = st.selectbox("Selecione a obra para excluir:", obra_options)

            st.warning(f"⚠️ Atenção: Ao excluir '{selected_obra_delete}', todos os dados desta obra serão perdidos na tabela de cadastro. Lançamentos financeiros vinculados ficarão órfãos.")

            col_del_1, col_del_2 = st.columns([2, 1])
            with col_del_1:
                pwd_del = st.text_input("Senha de Administrador para Exclusão", type="password", key="pwd_del")
            with col_del_2:
                st.write("") # Espaçamento visual
                btn_del = st.button("🚫 CONFIRMAR EXCLUSÃO", type="primary", use_container_width=True)

            if btn_del:
                if pwd_del == st.secrets["password"]:
                    try:
                        id_del = selected_obra_delete.split(" | ")[0]
                        conn = get_conn()
                        ws = conn.worksheet("Obras")
                        cell = ws.find(id_del, in_column=1) # Procura ID na coluna A

                        if cell:
                            ws.delete_rows(cell.row)
                            st.toast("Obra excluída com sucesso!", icon="🗑️")

                            # Limpa cache e estado
                            if "data_obras" in st.session_state: del st.session_state["data_obras"]
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("ID não encontrado na planilha.")
                    except Exception as e:
                        st.error(f"Erro ao excluir: {e}")
                else:
                    st.error("Senha incorreta.")
    
    else:
        st.info("Nenhuma obra cadastrada.")
