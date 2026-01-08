import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# =================================================
# DEFINIÇÃO DAS COLUNAS PADRÃO
# =================================================
OBRAS_COLS = [
    "ID",
    "Cliente",
    "Endereço",
    "Status",
    "Valor Total",
    "Data Início",
    "Prazo"
]

FIN_COLS = [
    "Data",
    "Tipo",
    "Categoria",
    "Descrição",
    "Valor",
    "Obra Vinculada"
]

# =================================================
# CONEXÃO COM GOOGLE SHEETS
# =================================================
@st.cache_resource
def obter_db():
    creds_json = json.loads(
        st.secrets["gcp_service_account"]["json_content"],
        strict=False
    )

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    client = gspread.authorize(
        ServiceAccountCredentials.from_json_keyfile_dict(
            creds_json, scope
        )
    )

    return client.open("GestorObras_DB")

# =================================================
# CARREGAMENTO DOS DADOS
# =================================================
@st.cache_data(ttl=5)
def carregar_dados():
    try:
        db = obter_db()

        # -------------------------
        # OBRAS
        # -------------------------
        ws_o = db.worksheet("Obras")
        df_o = pd.DataFrame(ws_o.get_all_records())

        if df_o.empty:
            df_o = pd.DataFrame(columns=OBRAS_COLS)

        df_o["Valor Total"] = pd.to_numeric(
            df_o.get("Valor Total", 0),
            errors="coerce"
        ).fillna(0)

        # -------------------------
        # FINANCEIRO
        # -------------------------
        ws_f = db.worksheet("Financeiro")
        df_f = pd.DataFrame(ws_f.get_all_records())

        if df_f.empty:
            df_f = pd.DataFrame(columns=FIN_COLS)

        df_f["Valor"] = pd.to_numeric(
            df_f.get("Valor", 0),
            errors="coerce"
        ).fillna(0)

        df_f["Data_DT"] = pd.to_datetime(
            df_f.get("Data"),
            errors="coerce"
        )

        df_f["Data_BR"] = (
            df_f["Data_DT"]
            .dt.strftime("%d/%m/%Y")
            .fillna("")
        )

        return df_o, df_f

    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return (
            pd.DataFrame(columns=OBRAS_COLS),
            pd.DataFrame(columns=FIN_COLS)
        )

# =================================================
# SALVAR DADOS
# =================================================
def salvar_financeiro(lista_dados):
    db = obter_db()
    db.worksheet("Financeiro").append_row(
        lista_dados,
        value_input_option="USER_ENTERED"
    )
    st.cache_data.clear()

def salvar_obra(lista_dados):
    db = obter_db()
    db.worksheet("Obras").append_row(
        lista_dados,
        value_input_option="USER_ENTERED"
    )
    st.cache_data.clear()

# =================================================
# EXCLUSÃO DE OBRA
# =================================================
def excluir_obra(nome_obra):
    """
    Remove uma obra da aba Obras,
    regravando todas as linhas, exceto a obra excluída.
    """
    db = obter_db()
    ws = db.worksheet("Obras")

    dados = ws.get_all_values()
    cabecalho = dados[0]
    linhas = dados[1:]

    novas_linhas = [
        linha for linha in linhas
        if linha[1] != nome_obra
    ]

    ws.clear()
    ws.append_row(cabecalho)
    if novas_linhas:
        ws.append_rows(novas_linhas)

    st.cache_data.clear()

# =================================================
# EXCLUSÃO DE LANÇAMENTO FINANCEIRO
# =================================================
def excluir_lancamento(data, tipo, categoria, descricao, valor, obra):
    """
    Remove UM lançamento financeiro específico da aba Financeiro.
    Remove apenas a primeira ocorrência encontrada.
    """
    db = obter_db()
    ws = db.worksheet("Financeiro")

    dados = ws.get_all_values()
    cabecalho = dados[0]
    linhas = dados[1:]

    novas_linhas = []
    removido = False

    for linha in linhas:
        if (
            linha[0] == str(data)
            and linha[1] == tipo
            and linha[2] == categoria
            and linha[3] == descricao
            and str(linha[4]) == str(valor)
            and linha[5] == obra
            and not removido
        ):
            removido = True
            continue

        novas_linhas.append(linha)

    ws.clear()
    ws.append_row(cabecalho)
    if novas_linhas:
        ws.append_rows(novas_linhas)

    st.cache_data.clear()

def editar_obra(id_obra, cliente, endereco, status, valor_total, data_inicio, prazo):
    """
    Atualiza uma obra existente na aba Obras, pelo ID.
    """
    db = obter_db()
    ws = db.worksheet("Obras")

    dados = ws.get_all_values()
    cabecalho = dados[0]
    linhas = dados[1:]

    novas_linhas = []

    for linha in linhas:
        if str(linha[0]) == str(id_obra):
            novas_linhas.append([
                id_obra,
                cliente,
                endereco,
                status,
                valor_total,
                data_inicio,
                prazo
            ])
        else:
            novas_linhas.append(linha)

    ws.clear()
    ws.append_row(cabecalho)
    ws.append_rows(novas_linhas)

    st.cache_data.clear()
