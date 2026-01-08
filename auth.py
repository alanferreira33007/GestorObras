# auth.py
import streamlit as st
import hashlib

def autenticar():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if st.session_state["authenticated"]:
        return

    _, col, _ = st.columns([1, 1, 1])
    with col:
        with st.form("login"):
            st.markdown("<h2 style='text-align:center;color:#2D6A4F'>GESTOR PRO</h2>", unsafe_allow_html=True)
            pwd = st.text_input("Senha de acesso", type="password")
            if st.form_submit_button("Entrar"):
                if hashlib.sha256(pwd.encode()).hexdigest() == st.secrets["password_hash"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Senha incorreta")

    st.stop()
