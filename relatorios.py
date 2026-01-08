import io
import base64
import pandas as pd
import streamlit as st
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfgen import canvas

# --- AJUSTES DE CORES ---
COR_PRIMARIA = colors.HexColor("#1B4332") # Verde Escuro
COR_SECUNDARIA = colors.HexColor("#2D6A4F") # Verde Médio
COR_FUNDO_ZEBRA = colors.HexColor("#F8F9FA") # Cinza claro para linhas

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
        self.setLineWidth(0.5)
        self.line(30, 35, width - 30, 35) # Linha decorativa no rodapé
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.grey)
        self.drawString(30, 20, f"{self.footer_left} | Gerado em {datetime.now().strftime('%d/%m/%Y')}")
        self.drawRightString(width - 30, 20, f"Página {page_num} de {page_count}")

def fmt_moeda(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return f"R$ {valor}"

def _estilizar_tabela(data, colWidths=None):
    """Cria uma tabela com visual profissional zebrado"""
    t = Table(data, colWidths=colWidths, hAlign='LEFT', repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COR_PRIMARIA), # Cabeçalho
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COR_FUNDO_ZEBRA, colors.white]), # Efeito Zebra
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    return t

def gerar_relatorio_investimentos_pdf(obra, vgv, custos, lucro, roi, df_saidas):
    buffer = io.BytesIO()
    # Margens ajustadas para ficar mais limpo
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4, 
        rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=50
    )
    
    styles = getSampleStyleSheet()
    
    # Estilos customizados
    style_titulo = ParagraphStyle('Titulo', parent=styles['Title'], fontSize=18, textColor=COR_PRIMARIA, spaceAfter=20)
    style_subtitulo = ParagraphStyle('Sub', parent=styles['Heading2'], fontSize=14, textColor=COR_SECUNDARIA, spaceBefore=15, spaceAfter=10)
    style_texto = ParagraphStyle('Texto', parent=styles['BodyText'], fontSize=10, leading=12)

    story = []
    
    # --- CABEÇALHO ---
    story.append(Paragraph(f"Relatório de Performance de Obra", style_titulo))
    story.append(Paragraph(f"<b>Obra/Cliente:</b> {obra}", style_texto))
    story.append(Paragraph(f"<b>Data do Relatório:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", style_texto))
    story.append(Spacer(1, 20))
    
    # --- QUADRO DE MÉTRICAS (RESUMO) ---
    story.append(Paragraph("Resumo Financeiro", style_subtitulo))
    
    resumo_dados = [
        ["Descrição do Indicador", "Valor Calculado"],
        ["Valor Total do Contrato (VGV)", fmt_moeda(vgv)],
        ["Custo Acumulado no Período", fmt_moeda(custos)],
        ["Lucro Estimado Atual", fmt_moeda(lucro)],
        ["Retorno sobre Investimento (ROI)", f"{roi:.2f}%"]
    ]
    story.append(_estilizar_tabela(resumo_dados, colWidths=[300, 200]))
    story.append(Spacer(1, 25))
    
    # --- TABELA DE LANÇAMENTOS ---
    story.append(Paragraph("Detalhamento de Saídas (Custos)", style_subtitulo))
    
    if not df_saidas.empty:
        # Preparando os dados da tabela
        df_pdf = df_saidas[["Data_BR", "Categoria", "Descrição", "Valor"]].copy()
        df_pdf["Valor"] = df_pdf["Valor"].apply(fmt_moeda)
        
        # Cabeçalhos da tabela
        dados_saidas = [["Data", "Categoria", "Descrição", "Valor"]] + df_pdf.values.tolist()
        
        # Larguras das colunas (Total = 535 pontos para A4 com margens)
        larguras = [70, 100, 265, 100]
        story.append(_estilizar_tabela(dados_saidas, colWidths=larguras))
    else:
        story.append(Paragraph("<i>Nenhum lançamento registrado para esta obra.</i>", style_texto))
    
    # Gerar PDF
    doc.build(story, canvasmaker=lambda *args, **kwargs: NumberedCanvas(*args, footer_left=f"Obra: {obra}", **kwargs))
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def download_pdf_one_click(pdf_bytes, filename):
    b64 = base64.b64encode(pdf_bytes).decode()
    html = f'''
        <a id="dl" href="data:application/pdf;base64,{b64}" download="{filename}"></a>
        <script>
            var link = document.getElementById("dl");
            link.click();
        </script>
    '''
    st.components.v1.html(html, height=0)
