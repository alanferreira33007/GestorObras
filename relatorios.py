import io
import base64
import pandas as pd
import streamlit as st
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas

def fmt_moeda(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return f"R$ {valor}"

def download_pdf_one_click(pdf_bytes, filename):
    b64 = base64.b64encode(pdf_bytes).decode()
    html = f'<a id="dl" href="data:application/pdf;base64,{b64}" download="{filename}"></a><script>document.getElementById("dl").click();</script>'
    st.components.v1.html(html, height=0)

# (Aqui você pode manter a classe NumberedCanvas e gerar_relatorio_investimentos_pdf que enviamos antes)
