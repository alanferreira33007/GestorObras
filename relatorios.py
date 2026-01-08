import io
import base64
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
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
    data = [list(df.columns)] + df.astype(str).values.tolist()
    t = Table(data, hAlign="LEFT")
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2D6A4F")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
    ]))
    return t

def gerar_relatorio_investimentos_pdf(obra, periodo, vgv, custos, lucro, roi, perc_vgv, df_categorias, df_lancamentos):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    story.append(Paragraph(f"Relatório de Investimentos - {obra}", styles["Title"]))
    story.append(Paragraph(f"Período: {periodo}", styles["BodyText"]))
    story.append(Spacer(1, 12))
    
    # Resumo
    resumo_data = [
        ["VGV", fmt_moeda(vgv)],
        ["Custos", fmt_moeda(custos)],
        ["Lucro", fmt_moeda(lucro)],
        ["ROI", f"{roi:.1f}%"]
    ]
    story.append(_df_to_table(pd.DataFrame(resumo_data, columns=["Indicador", "Valor"])))
    
    doc.build(story, canvasmaker=lambda *args, **kwargs: NumberedCanvas(*args, footer_left=f"Gestor Pro - {obra}", **kwargs))
    return buffer.getvalue()

def download_pdf_one_click(pdf_bytes, filename):
    b64 = base64.b64encode(pdf_bytes).decode()
    html = f'<a id="dl" href="data:application/pdf;base64,{b64}" download="{filename}"></a><script>document.getElementById("dl").click();</script>'
    st.components.v1.html(html, height=0)
