import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from datetime import date, datetime, timedelta
from streamlit_option_menu import option_menu
import io
import random
import re

# ... (MANTENHA A CONFIGURAÇÃO VISUAL E AS IMPORTAÇÕES IGUAIS ATÉ A PARTE DOS DADOS) ...

# ==============================================================================
# 4. DADOS E CONEXÃO
# ==============================================================================
OBRAS_COLS = [
    "ID", "Cliente", "Endereço", "Status", "Valor Total", 
    "Data Início", "Prazo", "Area Construida", "Area Terreno", 
    "Quartos", "Custo Previsto"
]
# ALTERAÇÃO AQUI: Adicionado "ID" no início
FIN_COLS = ["ID", "Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada", "Fornecedor"]
CATS = ["Material", "Mão de Obra", "Serviços", "Administrativo", "Impostos", "Outros"]

# ... (MANTENHA A FUNÇÃO get_conn IGUAL) ...

@st.cache_data(ttl=120)
def fetch_data_from_google():
    """Busca dados brutos do Google Sheets com Cache e LIMPEZA de STRINGS"""
    try:
        db = get_conn()
        
        # --- OBRAS ---
        ws_o = db.worksheet("Obras")
        raw_o = ws_o.get_all_records()
        df_o = pd.DataFrame(raw_o)
        if df_o.empty:
            df_o = pd.DataFrame(columns=OBRAS_COLS)
        else:
            for c in OBRAS_COLS: 
                if c not in df_o.columns: df_o[c] = None
        
        # --- FINANCEIRO ---
        ws_f = db.worksheet("Financeiro")
        raw_f = ws_f.get_all_records()
        df_f = pd.DataFrame(raw_f)

        if df_f.empty:
             df_f = pd.DataFrame(columns=FIN_COLS)
        else:
            for c in FIN_COLS:
                if c not in df_f.columns: df_f[c] = None
        
        # Conversão de Valores e IDs
        df_o["Valor Total"] = df_o["Valor Total"].apply(safe_float)
        if "Custo Previsto" in df_o.columns:
            df_o["Custo Previsto"] = df_o["Custo Previsto"].apply(safe_float)
            
        # Tratamento ID Financeiro
        if "ID" in df_f.columns:
            df_f["ID"] = pd.to_numeric(df_f["ID"], errors='coerce').fillna(0).astype(int)
            
        df_f["Valor"] = df_f["Valor"].apply(safe_float)
        df_f["Data_DT"] = pd.to_datetime(df_f["Data"], errors="coerce")
        
        # Limpeza de Strings (Strip)
        if "Obra Vinculada" in df_f.columns:
            df_f["Obra Vinculada"] = df_f["Obra Vinculada"].astype(str).str.strip()
        if "Categoria" in df_f.columns:
            df_f["Categoria"] = df_f["Categoria"].astype(str).str.strip()
        if "Cliente" in df_o.columns:
            df_o["Cliente"] = df_o["Cliente"].astype(str).str.strip()

        return df_o, df_f
    except Exception as e:
        st.error(f"Erro DB: {e}")
        return pd.DataFrame(), pd.DataFrame()

# ... (MANTENHA AS FUNÇÕES DE LOGIN/LOGOUT E SIDEBAR IGUAIS) ...

# ==============================================================================
# --- FINANCEIRO (LÓGICA ALTERADA) ---
# ==============================================================================
elif sel == "Financeiro":
    st.title("Financeiro")

    # Feedback de Ação
    if st.session_state.get("sucesso_fin"):
        st.success("✅ Operação realizada com sucesso!", icon="✅")
        # Limpa campos do formulário apenas se foi inclusão
        if st.session_state.get("tipo_operacao_fin") == "inclusao":
            st.session_state["k_fin_valor"] = 0.0
            st.session_state["k_fin_desc"] = ""
            st.session_state["k_fin_forn"] = ""
        st.session_state["sucesso_fin"] = False

    # Inicialização de Session States do Form
    if "k_fin_data" not in st.session_state: st.session_state.k_fin_data = date.today()
    if "k_fin_tipo" not in st.session_state: st.session_state.k_fin_tipo = "Saída (Despesa)"
    if "k_fin_cat" not in st.session_state: st.session_state.k_fin_cat = ""
    if "k_fin_obra" not in st.session_state: st.session_state.k_fin_obra = ""
    if "k_fin_valor" not in st.session_state: st.session_state.k_fin_valor = 0.0
    if "k_fin_desc" not in st.session_state: st.session_state.k_fin_desc = ""
    if "k_fin_forn" not in st.session_state: st.session_state.k_fin_forn = ""

    # --- FORMULÁRIO DE NOVO LANÇAMENTO (Mantido para validação rígida) ---
    with st.expander("Novo Lançamento", expanded=False):
        with st.form("ffin", clear_on_submit=False):
            c_row1_1, c_row1_2, c_row1_3 = st.columns([1, 1, 1])
            with c_row1_1: dt = st.date_input("Data", value=st.session_state.k_fin_data, key="k_fin_data")
            with c_row1_2: tp = st.selectbox("Tipo", ["Saída (Despesa)", "Entrada"], key="k_fin_tipo")
            with c_row1_3: vl = st.number_input("Valor R$ *", min_value=0.0, format="%.2f", step=100.0, value=st.session_state.k_fin_valor, key="k_fin_valor_input")

            c_row2_1, c_row2_2 = st.columns([1, 1])
            with c_row2_1: 
                opcoes_obras = [""] + lista_obras
                ob = st.selectbox("Obra *", opcoes_obras, key="k_fin_obra")
            with c_row2_2: 
                opcoes_cats = [""] + CATS
                ct = st.selectbox("Categoria *", opcoes_cats, key="k_fin_cat")

            c_row3_1, c_row3_2 = st.columns([1, 1])
            with c_row3_1: fn = st.text_input("Fornecedor", value=st.session_state.k_fin_forn, key="k_fin_forn")
            with c_row3_2: dc = st.text_input("Descrição *", value=st.session_state.k_fin_desc, key="k_fin_desc")
            
            st.write("") 
            submitted_fin = st.form_submit_button("Salvar Lançamento", use_container_width=True)

            if submitted_fin:
                st.session_state.k_fin_valor = vl
                erros = []
                if not ob: erros.append("Selecione a Obra Vinculada.")
                if not ct: erros.append("Selecione a Categoria.")
                if vl <= 0: erros.append("O Valor deve ser maior que zero.")
                if not dc.strip(): erros.append("A Descrição é obrigatória.")
                if ct == "Material" and not fn.strip(): erros.append("Para 'Material', Fornecedor é obrigatório.")

                if erros:
                    st.error("⚠️ Atenção:")
                    for e in erros: st.caption(f"- {e}")
                else:
                    try:
                        conn = get_conn()
                        # GERAÇÃO DE ID ÚNICO (Max ID + 1)
                        existing_ids = pd.to_numeric(df_fin["ID"], errors='coerce').fillna(0)
                        novo_id = int(existing_ids.max()) + 1 if not existing_ids.empty else 1
                        
                        # Salva na ordem das colunas FIN_COLS: ID, Data, Tipo, Categoria, Descrição, Valor, Obra, Fornecedor
                        conn.worksheet("Financeiro").append_row([
                            novo_id, dt.strftime("%Y-%m-%d"), tp, ct.strip(), dc, vl, ob.strip(), fn
                        ])
                        
                        if "data_fin" in st.session_state: del st.session_state["data_fin"]
                        st.cache_data.clear()
                        st.session_state["sucesso_fin"] = True
                        st.session_state["tipo_operacao_fin"] = "inclusao"
                        st.rerun() 
                    except Exception as e: st.error(f"Erro: {e}")

    st.markdown("---")
    st.markdown("### 📝 Gestão de Lançamentos")
    st.caption("Edite valores diretamente na tabela ou selecione linhas e pressione 'Delete' no teclado para excluir.")

    if not df_fin.empty:
        # Filtros
        with st.expander("Filtros de Busca", expanded=True):
            c_filter1, c_filter2 = st.columns(2)
            with c_filter1:
                opcoes_filtro_obra = ["Todas as Obras"] + lista_obras
                filtro_obra = st.selectbox("Filtrar por Obra", options=opcoes_filtro_obra)
            with c_filter2:
                opcoes_filtro_cat = ["Todas as Categorias"] + CATS
                filtro_cat = st.selectbox("Filtrar por Categoria", options=opcoes_filtro_cat)

        # Preparação do DataFrame para Edição
        df_view = df_fin.copy()
        
        # Aplicando Filtros
        if filtro_obra != "Todas as Obras":
            df_view = df_view[df_view["Obra Vinculada"].astype(str) == str(filtro_obra)]
        if filtro_cat != "Todas as Categorias":
            df_view = df_view[df_view["Categoria"].astype(str) == str(filtro_cat)]

        # Configuração das Colunas para o Editor
        # Ordenamos por data decrescente para visualização, mas mantemos o índice
        df_view = df_view.sort_values("Data", ascending=False)
        
        # Colunas editáveis
        cols_to_show = ["ID", "Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada", "Fornecedor"]
        
        # EDITOR DE DADOS
        edited_fin = st.data_editor(
            df_view[cols_to_show],
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic", # Permite deletar linhas
            disabled=["ID"], # ID não pode ser editado pelo usuário
            key="editor_financeiro",
            column_config={
                "ID": st.column_config.NumberColumn("#", width=50),
                "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Saída (Despesa)", "Entrada"], width="small"),
                "Categoria": st.column_config.SelectboxColumn("Categoria", options=CATS, width="medium"),
                "Descrição": st.column_config.TextColumn("Descrição", width="large", required=True),
                "Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f", min_value=0.01),
                "Obra Vinculada": st.column_config.SelectboxColumn("Obra", options=lista_obras, width="medium"),
                "Fornecedor": st.column_config.TextColumn("Fornecedor"),
            }
        )

        # LÓGICA DE DETECÇÃO DE MUDANÇAS E SALVAMENTO
        has_changes = not edited_fin.equals(df_view[cols_to_show])
        
        # Se houver mudanças (Edição ou Exclusão)
        if has_changes:
            with st.container(border=True):
                st.warning("⚠️ Alterações detectadas (Edição ou Exclusão).", icon="⚠️")
                c_pwd, c_btn = st.columns([2, 1])
                with c_pwd:
                    pwd_confirm = st.text_input("Senha para Confirmar", type="password", placeholder="Senha ADM", key="pwd_fin_edit")
                with c_btn:
                    if st.button("💾 SALVAR MUDANÇAS", type="primary", use_container_width=True):
                        if pwd_confirm == st.secrets["password"]:
                            try:
                                conn = get_conn()
                                ws = conn.worksheet("Financeiro")
                                
                                with st.spinner("Processando exclusões e atualizações..."):
                                    # 1. Identificar IDs Excluídos
                                    ids_originais = set(df_view["ID"].dropna().astype(int))
                                    ids_finais = set(edited_fin["ID"].dropna().astype(int))
                                    ids_excluidos = ids_originais - ids_finais
                                    
                                    # 2. Processar Exclusões
                                    if ids_excluidos:
                                        for id_del in ids_excluidos:
                                            try:
                                                # Encontrar a célula que contém o ID na coluna A (index 1)
                                                cell = ws.find(str(id_del), in_column=1)
                                                if cell:
                                                    ws.delete_rows(cell.row)
                                            except gspread.exceptions.CellNotFound:
                                                pass # Já foi deletado ou não encontrado
                                    
                                    # 3. Processar Edições (Apenas nos IDs que restaram)
                                    # Para otimizar, iteramos sobre o DF editado
                                    # Nota: O ideal seria update em batch, mas linha a linha é mais seguro para lógica complexa
                                    
                                    # Recarregamos o DF original completo para comparar linha a linha
                                    df_original_full = df_fin.set_index("ID")
                                    
                                    for index, row in edited_fin.iterrows():
                                        id_atual = int(row["ID"])
                                        
                                        # Verifica se houve mudança nesta linha específica comparando com original
                                        if id_atual in df_original_full.index:
                                            row_orig = df_original_full.loc[id_atual]
                                            
                                            # Checa se algo mudou nas colunas relevantes
                                            mudou = False
                                            cols_check = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada", "Fornecedor"]
                                            vals_novos = []
                                            
                                            for c in cols_check:
                                                val_novo = row[c]
                                                val_orig = row_orig[c]
                                                
                                                # Normalização para comparação
                                                if c == "Data":
                                                    v_n = pd.to_datetime(val_novo).strftime("%Y-%m-%d") if pd.notnull(val_novo) else ""
                                                    v_o = pd.to_datetime(val_orig).strftime("%Y-%m-%d") if pd.notnull(val_orig) else ""
                                                else:
                                                    v_n = str(val_novo).strip()
                                                    v_o = str(val_orig).strip()
                                                    if c == "Valor": # Comparação numérica
                                                        v_n = float(val_novo)
                                                        v_o = float(val_orig)

                                                if v_n != v_o:
                                                    mudou = True
                                                
                                                # Prepara valor para update (formatado)
                                                if isinstance(val_novo, (pd.Timestamp, date, datetime)):
                                                    vals_novos.append(val_novo.strftime("%Y-%m-%d"))
                                                else:
                                                    vals_novos.append(val_novo)

                                            if mudou:
                                                # Busca a linha no Google Sheets pelo ID
                                                cell = ws.find(str(id_atual), in_column=1)
                                                if cell:
                                                    # Monta a linha completa: [ID, Data, Tipo, Categoria, Desc, Valor, Obra, Forn]
                                                    full_row_data = [id_atual] + vals_novos
                                                    # Define o range (A:H)
                                                    rng = f"A{cell.row}:H{cell.row}"
                                                    ws.update(rng, [full_row_data])
                                    
                                    # Limpa cache e recarrega
                                    if "data_fin" in st.session_state: del st.session_state["data_fin"]
                                    if "data_obras" in st.session_state: del st.session_state["data_obras"]
                                    st.cache_data.clear()
                                    
                                    st.session_state["sucesso_fin"] = True
                                    st.session_state["tipo_operacao_fin"] = "edicao"
                                    st.rerun()

                            except Exception as e:
                                st.error(f"Erro ao salvar alterações: {e}")
                        else:
                            st.toast("Senha incorreta!", icon="⛔")

        # Botão de Relatório PDF (Mantido fora do form de edição)
        st.write("")
        if not df_view.empty:
            total_filtrado = df_view["Valor"].sum()
            escopo_pdf = filtro_obra if filtro_obra != "Todas as Obras" else "Visão Geral (Filtro)"
            dmin = df_view["Data_DT"].min().strftime("%d/%m/%Y")
            dmax = df_view["Data_DT"].max().strftime("%d/%m/%Y")
            
            pdf_data = gerar_pdf_empresarial(
                escopo_pdf, f"De {dmin} até {dmax}", 
                0.0, total_filtrado, 0.0, 0.0, 
                pd.DataFrame(), # Categoria opcional aqui
                df_view[["Data", "Categoria", "Descrição", "Fornecedor", "Valor"]]
            )
            
            st.download_button(
                label="⬇️ BAIXAR RELATÓRIO PDF",
                data=pdf_data,
                file_name=f"Extrato_Financeiro_{date.today()}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
    else:
        st.info("Nenhum lançamento registrado.")
