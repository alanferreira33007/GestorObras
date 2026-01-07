import streamlit as st

st.set_page_config(page_title="GESTOR PRO | DEBUG", layout="wide")

st.markdown("## 🛠️ Diagnóstico de imports")
st.info("Esta tela serve apenas para mostrar o erro real. Depois voltamos para o app normal.")

# 1) core.data
try:
    from core.data import carregar_dados
    st.success("✅ Import OK: from core.data import carregar_dados")
except Exception as e:
    st.error("❌ Falhou: from core.data import carregar_dados")
    st.code(repr(e))
    st.stop()

# 2) core.sheets
try:
    from core.sheets import ensure_schema
    st.success("✅ Import OK: from core.sheets import ensure_schema")
except Exception as e:
    st.error("❌ Falhou: from core.sheets import ensure_schema")
    st.code(repr(e))
    st.stop()

# 3) pages
try:
    from pages import investimentos, caixa, insumos, projetos, orcamento
    st.success("✅ Import OK: from pages import investimentos, caixa, insumos, projetos, orcamento")
except Exception as e:
    st.error("❌ Falhou: import das páginas (pages/*)")
    st.code(repr(e))
    st.stop()

st.success("🎉 Imports principais OK! Agora podemos restaurar o app normal.")
st.write("Se aparecer erro acima, copie e cole aqui o texto que apareceu no bloco (repr).")
