import streamlit as st

def ensure_auth():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

def login_screen():
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
