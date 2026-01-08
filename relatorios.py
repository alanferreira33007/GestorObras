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

class NumberedCanvas(canvas.Canvas):
    """Adiciona numeração de página e rodapé"""
    def __init__(self, *args, footer_left: str = "Gestor Pro", **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self.footer_left = footer_left

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        super().showPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(num_pages)
            super().showPage()
        super().save()

    def _draw_footer(self, page_count: int):
        width, height = A4
        page_num = self.getPageNumber()
        self.setStrokeColor(colors.lightgrey)
        self.line(24, 28, width - 24, 28)
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.grey)
        self.drawString(24, 14, self.footer_left[:120])
        self.drawRightString(width - 24, 14, f"Página {page_num} de {page_count}")

def fmt_moeda(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return f"R$ {valor}"

def _df_to_table(df):
    if df.empty: return Paragraph("Sem dados", getSampleStyleSheet()["BodyText"])
    # Limpa nomes de colunas para o PDF
    df_pdf = df.copy()
    data = [list(df_pdf.columns)] + df_pdf.astype(str).values.tolist()
    t = Table(data, hAlign="LEFT", repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2D6A4F")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))
    return t

def gerar_relatorio_investimentos_pdf(obra, vgv, custos, lucro, roi, df_saidas):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=30, bottomMargin=40)
    styles = getSampleStyleSheet()
    story = []
    
    # Cabeçalho
    story.append(Paragraph(f"GESTOR PRO - Relatório Financeiro", styles["Title"]))
    story.append(Paragraph(f"Obra: {obra}", styles["Heading2"]))
    story.append(Paragraph(f"Data de Emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["BodyText"]))
    story.append(Spacer(1, 15))
    
    # Tabela de Resumo
    story.append(Paragraph("Resumo Executivo", styles["Heading3"]))
    resumo_data = [
        ["Indicador", "Valor"],
        ["VGV (Venda)", fmt_moeda(vgv)],
        ["Custo Total", fmt_moeda(custos)],
        ["Lucro Estimado", fmt_moeda(lucro)],
        ["ROI", f"{roi:.1f}%"]
    ]
    t_resumo = Table(resumo_data, colWidths=[150, 150])
    t_resumo.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2D6A4F")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ]))
    story.append(t_resumo)
    story.append(Spacer(1, 20))
    
    # Tabela de Lançamentos
    story.append(Paragraph("Detalhamento de Saídas", styles["Heading3"]))
    if not df_saidas.empty:
        # Seleciona apenas colunas importantes para o PDF
        df_pdf = df_saidas[["Data_BR", "Categoria", "Descrição", "Valor"]].copy()
        df_pdf["Valor"] = df_pdf["Valor"].apply(fmt_moeda)
        story.append(_df_to_table(df_pdf))
    
    doc.build(story, canvasmaker=lambda *args, **kwargs: NumberedCanvas(*args, footer_left=f"Relatório de Obra: {obra}", **kwargs))
    return buffer.getvalue()

def download_pdf_one_click(pdf_bytes, filename):
    b64 = base64.b64encode(pdf_bytes).decode()
    html = f'<a id="dl" href="data:application/pdf;base64,{b64}" download="{filename}"></a><script>document.getElementById("dl").click();</script>'
    st.components.v1.html(html, height=0)
