# ui_components.py
import plotly.express as px
import streamlit as st

def grafico_categorias(df):
    fig = px.bar(df, x="Categoria", y="Valor")
    fig.update_layout(plot_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)
