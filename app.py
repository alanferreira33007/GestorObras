import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import plotly.express as px
from datetime import date
from streamlit_option_menu import option_menu

# ----------------------------
# 1) CONFIG UI
# ----------------------------
st.set_page_config(page_title="GESTOR PRO | Master v26", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F8F9FA; color: #1A1C1E; font-family: 'Inter', sans-serif; }
    [data-testid="stMetric"] { background-color: #FFFFFF; border: 1px solid #E9ECEF; border-radius: 12px; padding: 20px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
    div.stButton > button { background-color: #2D6A4F !important; color: white !important; border-radius: 6px !important; font-weight: 600 !important; width: 100%; height: 45px; }
    .alert-card { background-color: #FFFFFF; border-left: 5px solid #E63946; padding: 20px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
    header, footer, #MainMenu {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ----------------------------
# 2) CONSTANTES (SCHEMA)
# ----------------------------
OBRAS_COLS = ["ID", "Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"]
FIN_COLS   = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]

CATEGORIAS_PADRAO = ["Geral", "Material", "Mão de Obra", "Serviços", "Impostos", "Outros"]

# ----------------------------
# 3) HELPERS
# ----------------------------
def fmt_moeda(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return f"R$ {valor}"

def ensure_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Garante que df tenha todas as colunas e retorna na ordem desejada."""
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]

@st.cache_resource
def obter_db():
    """Conexão/cliente é recurso: cache_resource."""
    creds_json = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope))
    return client.open("GestorObras_DB")

@st.cache_data(ttl=10)
def carregar_dados():
    """Dados mudam: cache_data com TTL curto."""
    try:
        db = obter_db()

        # Obras
        ws_o = db.worksheet("Obras")
        df_o = pd.DataFrame(ws_o.get_all_records())
        if df_o.empty:
            df_o = pd.DataFrame(columns=OBRAS_COLS)
        df_o = ensure_cols(df_o, OBRAS_COLS)
        df_o["ID"] = pd.to_numeric(df_o["ID"], errors="coerce")
        df_o["Valor Total"] = pd.to_numeric(df_o["Valor Total"], errors="coerce").fillna(0)

        # Financeiro
        ws_f = db.worksheet("Financeiro")
        df_f = pd.DataFrame(ws_f.get_all_records())
        if df_f.empty:
            df_f = pd.DataFrame(columns=FIN_COLS)
        df_f = ensure_cols(df_f, FIN_COLS)
        df_f["Valor"] = pd.to_numeric(df_f["Valor"], errors="coerce").fillna(0)
        df_f["Data_DT"] = pd.to_datetime(df_f["Data"], errors="coerce")
        df_f["Data_BR"] = df_f["Data_DT"].dt.strftime("%d/%m/%Y")
        df_f.loc[df_f["Data_DT"].isna(), "Data_BR"] = ""

        return df_o, df_f

    except Exception as e:
        st.error(f"Erro de Conexão: {e}")
        return pd.DataFrame(columns=OBRAS_COLS), pd.DataFrame(columns=FIN_COLS + ["Data_DT", "Data_BR"])

# ----------------------------
# 4) AUTH
# ----------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        with st.form("login"):
            st.markdown("<h2 style='text-align:center; color:#2D6A4F;'>GESTOR PRO</h2>", unsafe_allow_html=True)
            pwd = st.text_input("Senha de Acesso", type="password")
            if st.form_submit_button("Acessar Painel"):
                if pwd == st.secrets["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
    st.stop()

# ----------------------------
# 5) LOAD
# ----------------------------
df_obras, df_fin = carregar_dados()

# lista de obras (sem duplicatas e sem vazios)
lista_obras = (
    df_obras["Cliente"]
    .dropna()
    .astype(str)
    .str.strip()
    .replace("", pd.NA)
    .dropna()
    .unique()
    .tolist()
)

# ----------------------------
# 6) SIDEBAR
# ----------------------------
with st.sidebar:
    sel = option_menu(
        "GESTOR PRO",
        ["Investimentos", "Caixa", "Insumos", "Projetos"],
        icons=["graph-up-arrow", "wallet2", "cart-check", "building"],
        default_index=0,
    )
    if st.button("Sair"):
        st.session_state["authenticated"] = False
        st.rerun()

# ----------------------------
# 7) TELAS
# ----------------------------
if sel == "Investimentos":
    st.markdown("### 📊 Performance e ROI por Obra")

    if not lista_obras:
        st.info("Cadastre uma obra para iniciar a análise.")
        st.stop()

    # melhor que option_menu horizontal quando crescer: selectbox com busca
    obra_sel = st.selectbox("Selecione a obra", lista_obras)

    obra_row = df_obras[df_obras["Cliente"].astype(str).str.strip() == obra_sel].iloc[0]
    vgv = float(obra_row["Valor Total"] or 0)

    df_v = df_fin[df_fin["Obra Vinculada"].astype(str).str.strip() == obra_sel].copy()
    custos = df_v[df_v["Tipo"].astype(str).str.contains("Saída", case=False, na=False)]["Valor"].sum()
    lucro = vgv - custos
    roi = (lucro / custos * 100) if custos > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VGV Venda", fmt_moeda(vgv))
    c2.metric("Custo Total", fmt_moeda(custos))
    c3.metric("Lucro Estimado", fmt_moeda(lucro))
    c4.metric("ROI Atual", f"{roi:.1f}%")

    # gráfico de custo acumulado
    df_plot = df_v[df_v["Tipo"].astype(str).str.contains("Saída", case=False, na=False)].copy()
    df_plot = df_plot.dropna(subset=["Data_DT"]).sort_values("Data_DT")
    if not df_plot.empty:
        df_plot["Custo Acumulado"] = df_plot["Valor"].cumsum()
        fig = px.line(df_plot, x="Data_DT", y="Custo Acumulado", markers=True)
        fig.update_layout(plot_bgcolor="white", xaxis_title="Data", yaxis_title="Custo acumulado (R$)")
        st.plotly_chart(fig, use_container_width=True)

elif sel == "Caixa":
    st.markdown("### 💸 Lançamento Financeiro")

    with st.form("f_caixa", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        dt_input = c1.date_input("Data", value=date.today(), format="DD/MM/YYYY")
        tp_input = c2.selectbox("Tipo", ["Saída (Despesa)", "Entrada"])
        cat_input = c3.selectbox("Categoria", CATEGORIAS_PADRAO)

        c4, c5 = st.columns(2)
        ob_input = c4.selectbox("Obra Vinculada", lista_obras if lista_obras else ["Geral"])
        vl_input = c5.number_input("Valor R$", format="%.2f", step=0.01, min_value=0.0)

        ds_input = st.text_input("Descrição")

        if st.form_submit_button("REGISTRAR LANÇAMENTO"):
            try:
                db = obter_db()
                db.worksheet("Financeiro").append_row(
                    [
                        dt_input.strftime("%Y-%m-%d"),
                        tp_input,
                        cat_input,
                        ds_input,
                        float(vl_input),
                        ob_input,
                    ],
                    value_input_option="USER_ENTERED",
                )
                st.cache_data.clear()
                st.success("Lançamento realizado!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

    if not df_fin.empty:
        st.markdown("#### Histórico de Lançamentos")
        df_display = df_fin[["Data_BR", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada"]].copy()
        df_display = df_display.assign(_dt=df_fin["Data_DT"]).sort_values("_dt", ascending=False).drop(columns="_dt")
        df_display["Valor"] = df_display["Valor"].apply(fmt_moeda)
        df_display.columns = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra"]
        st.dataframe(df_display, use_container_width=True, hide_index=True)

elif sel == "Insumos":
    st.markdown("### 🛒 Monitor de Preços (Inflação)")

    if df_fin.empty:
        st.info("Sem dados para monitoramento.")
        st.stop()

    df_g = df_fin[df_fin["Tipo"].astype(str).str.contains("Saída", case=False, na=False)].copy()
    if df_g.empty:
        st.info("Sem despesas registradas.")
        st.stop()

    # insumo = parte antes do ":"
    df_g["Insumo"] = df_g["Descrição"].astype(str).apply(lambda x: x.split(":")[0].strip() if ":" in x else x.strip())
    df_g = df_g.dropna(subset=["Data_DT"]).sort_values("Data_DT")

    alertas = False
    for item in df_g["Insumo"].dropna().unique():
        historico = df_g[df_g["Insumo"] == item].sort_values("Data_DT")
        if len(historico) >= 2:
            atual = historico.iloc[-1]
            ant = historico.iloc[-2]
            if float(ant["Valor"]) > 0 and float(atual["Valor"]) > float(ant["Valor"]):
                var = ((float(atual["Valor"]) / float(ant["Valor"])) - 1) * 100
                # filtro simples para evitar “micro-alertas”
                if var >= 2:
                    alertas = True
                    st.markdown(f"""
                    <div class='alert-card'>
                        <strong>{item}</strong> <span style='color:#E63946; float:right;'>+{var:.1f}%</span><br>
                        <small>Anterior: {fmt_moeda(ant['Valor'])} ({ant['Data_BR']})</small><br>
                        <strong>Atual: {fmt_moeda(atual['Valor'])} ({atual['Data_BR']})</strong>
                    </div>
                    """, unsafe_allow_html=True)

    if not alertas:
        st.success("Nenhum aumento relevante detectado nos insumos (>= 2%).")

elif sel == "Projetos":
    st.markdown("### 📁 Gestão de Obras")

    with st.form("f_obra", clear_on_submit=True):
        c1, c2 = st.columns(2)
        n_obra = c1.text_input("Cliente / Nome da Obra")
        end_obra = c2.text_input("Endereço")

        c3, c4, c5 = st.columns(3)
        st_obra = c3.selectbox("Status", ["Planejamento", "Construção", "Finalizada"])
        v_obra = c4.number_input("Valor Total (VGV)", format="%.2f", step=1000.0, min_value=0.0)
        prazo = c5.text_input("Prazo", value="A definir")

        if st.form_submit_button("CADASTRAR OBRA"):
            try:
                db = obter_db()
                ws = db.worksheet("Obras")

                # novo ID (seguro)
                max_id = pd.to_numeric(df_obras["ID"], errors="coerce").max()
                novo_id = int(max_id) + 1 if pd.notna(max_id) else 1

                ws.append_row(
                    [
                        novo_id,
                        n_obra.strip(),
                        end_obra.strip(),
                        st_obra,
                        float(v_obra),
                        date.today().strftime("%Y-%m-%d"),
                        prazo.strip(),
                    ],
                    value_input_option="USER_ENTERED",
                )
                st.cache_data.clear()
                st.success("Obra cadastrada!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")

    if not df_obras.empty:
        df_o_ex = df_obras[["Cliente", "Endereço", "Status", "Valor Total", "Data Início", "Prazo"]].copy()
        df_o_ex["Valor Total"] = df_o_ex["Valor Total"].apply(fmt_moeda)
        st.dataframe(df_o_ex, use_container_width=True, hide_index=True)
