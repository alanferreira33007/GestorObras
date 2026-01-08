import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# Definição das colunas padrão
OBRAS_COLS = ["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"]
FIN_COLS   = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]

@st.cache_resource
def obter_db():
    creds_json = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope))
    return client.open("GestorObras_DB")

@st.cache_data(ttl=5)
def carregar_dados():
    try:
        db = obter_db()
        # Obras
        ws_o = db.worksheet("Obras")
        df_o = pd.DataFrame(ws_o.get_all_records())
        if df_o.empty: df_o = pd.DataFrame(columns=OBRAS_COLS)
        df_o["Valor Total"] = pd.to_numeric(df_o["Valor Total"], errors="coerce").fillna(0)

        # Financeiro
        ws_f = db.worksheet("Financeiro")
        df_f = pd.DataFrame(ws_f.get_all_records())
        if df_f.empty: df_f = pd.DataFrame(columns=FIN_COLS)
        df_f["Valor"] = pd.to_numeric(df_f["Valor"], errors="coerce").fillna(0)
        df_f["Data_DT"] = pd.to_datetime(df_f["Data"], errors="coerce")
        df_f["Data_BR"] = df_f["Data_DT"].dt.strftime("%d/%m/%Y").fillna("")
        return df_o, df_f
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame(columns=OBRAS_COLS), pd.DataFrame(columns=FIN_COLS)

def salvar_financeiro(lista_dados):
    db = obter_db()
    db.worksheet("Financeiro").append_row(lista_dados, value_input_option="USER_ENTERED")
    st.cache_data.clear()

def salvar_obra(lista_dados):
    db = obter_db()
    db.worksheet("Obras").append_row(lista_dados, value_input_option="USER_ENTERED")
    st.cache_data.clear()

def excluir_obra(nome_obra):
    """
    Remove uma obra da aba OBRAS da planilha,
    regravando todas as linhas, exceto a obra excluída.
    """

    sh = client.open_by_key(SPREADSHEET_ID)
    ws_obras = sh.worksheet("OBRAS")

    dados = ws_obras.get_all_values()
    cabecalho = dados[0]
    linhas = dados[1:]

    novas_linhas = [
        linha for linha in linhas if linha[1] != nome_obra
    ]

    # Limpa tudo e regrava
    ws_obras.clear()
    ws_obras.append_row(cabecalho)
    ws_obras.append_rows(novas_linhas)

def excluir_lancamento(data, tipo, categoria, descricao, valor, obra):
    """
    Remove um lançamento financeiro específico da aba FINANCEIRO
    """

    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("FINANCEIRO")

    dados = ws.get_all_values()
    cabecalho = dados[0]
    linhas = dados[1:]

    novas_linhas = []
    removido = False

    for linha in linhas:
        if (
            linha[0] == data and
            linha[1] == tipo and
            linha[2] == categoria and
            linha[3] == descricao and
            str(linha[4]) == str(valor) and
            linha[5] == obra and
            not removido
        ):
            removido = True
            continue
        novas_linhas.append(linha)

    ws.clear()
    ws.append_row(cabecalho)
    ws.append_rows(novas_linhas)

