from __future__ import annotations
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

from core.formatters import fmt_moeda, fmt_data_br

def gerar_pdf_relatorio(obra: str, periodo_txt: str, resumo: dict, lancamentos_df):
    """
    resumo: dict com chaves: vgv, custo, lucro, roi
    lancamentos_df: df com colunas Data_DT ou Data_BR, Categoria, Descrição, Valor
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    y = h - 2*cm
    c.setFont("Helvetica-Bold", 20)
    c.drawString(2*cm, y, "Relatório (Investimentos)")
    y -= 0.8*cm

    c.setFont("Helvetica", 11)
    c.drawString(2*cm, y, f"Obra: {obra}")
    y -= 0.6*cm
    c.drawString(2*cm, y, f"Período: {periodo_txt}")
    y -= 1.0*cm

    # Resumo
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2*cm, y, "Resumo do período")
    y -= 0.6*cm

    c.setFont("Helvetica", 11)
    c.drawString(2*cm, y, f"VGV: {fmt_moeda(resumo['vgv'])}")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Custo: {fmt_moeda(resumo['custo'])}")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Lucro estimado: {fmt_moeda(resumo['lucro'])}")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"ROI: {resumo['roi']:.1f}%")
    y -= 1.0*cm

    # Tabela lançamentos (limitada)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2*cm, y, "Lançamentos (Saídas) no período")
    y -= 0.8*cm

    # Cabeçalho tabela
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2*cm, y, "Data")
    c.drawString(6*cm, y, "Categoria")
    c.drawString(10*cm, y, "Descrição")
    c.drawString(17*cm, y, "Valor")
    y -= 0.5*cm

    c.setFont("Helvetica", 10)

    max_rows = 18
    rows = lancamentos_df.head(max_rows).to_dict("records")

    for r in rows:
        # data no formato 07/01/2026
        dt = r.get("Data_DT", None)
        data_br = r.get("Data_BR") or fmt_data_br(dt)
        cat = str(r.get("Categoria", ""))
        desc = str(r.get("Descrição", ""))
        val = fmt_moeda(r.get("Valor", 0))

        c.drawString(2*cm, y, data_br)
        c.drawString(6*cm, y, cat[:18])
        c.drawString(10*cm, y, desc[:35])
        c.drawRightString(19*cm, y, val)
        y -= 0.5*cm

        if y < 3*cm:
            c.showPage()
            y = h - 2*cm

    c.setFont("Helvetica-Oblique", 11)
    c.drawString(2*cm, 2*cm, "Obs.: se houver muitos lançamentos, o PDF traz apenas as primeiras linhas.")

    c.save()
    buf.seek(0)
    return buf.getvalue()
