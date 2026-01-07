import io
import pandas as pd
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def _fmt_brl(v: float) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(v)


def _df_to_table(df: pd.DataFrame, max_rows: int = 25):
    """Converte um DataFrame em tabela do ReportLab (com limite de linhas)."""
    if df is None or df.empty:
        return Paragraph("<i>Sem dados.</i>", getSampleStyleSheet()["BodyText"])

    df2 = df.copy()
    if len(df2) > max_rows:
        df2 = df2.head(max_rows)

    data = [list(df2.columns)] + df2.astype(str).values.tolist()

    t = Table(data, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2D6A4F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def gerar_relatorio_investimentos_pdf(
    obra: str,
    periodo: str,
    vgv: float,
    custos: float,
    lucro: float,
    roi: float,
    perc_vgv: float,
    df_categorias: pd.DataFrame,
    df_lancamentos: pd.DataFrame,
) -> bytes:
    """
    Gera um PDF (bytes) para a aba Investimentos.
    - df_categorias: colunas esperadas: Categoria, Valor
    - df_lancamentos: pode ser a lista de despesas do período
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=24,
        leftMargin=24,
        topMargin=24,
        bottomMargin=24,
        title="Relatório - Investimentos",
    )

    styles = getSampleStyleSheet()
    story = []

    # Cabeçalho
    story.append(Paragraph("GESTOR PRO — Relatório de Investimentos", styles["Title"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>Obra:</b> {obra}", styles["BodyText"]))
    story.append(Paragraph(f"<b>Período:</b> {periodo}", styles["BodyText"]))
    story.append(Paragraph(f"<b>Gerado em:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["BodyText"]))
    story.append(Spacer(1, 12))

    # Métricas
    story.append(Paragraph("Resumo", styles["Heading2"]))
    resumo = pd.DataFrame(
        [
            ["VGV", _fmt_brl(vgv)],
            ["Custo (período)", _fmt_brl(custos)],
            ["Lucro estimado", _fmt_brl(lucro)],
            ["ROI (lucro/custo)", f"{roi:.1f}%"],
            ["% do VGV gasto", f"{perc_vgv:.2f}%"],
        ],
        columns=["Indicador", "Valor"],
    )
    story.append(_df_to_table(resumo, max_rows=20))
    story.append(Spacer(1, 14))

    # Categorias
    story.append(Paragraph("Custo por categoria (período)", styles["Heading2"]))
    df_cat = df_categorias.copy() if df_categorias is not None else pd.DataFrame()
    if not df_cat.empty and "Valor" in df_cat.columns:
        df_cat["Valor"] = df_cat["Valor"].apply(_fmt_brl)
    story.append(_df_to_table(df_cat, max_rows=25))
    story.append(Spacer(1, 14))

    # Lançamentos (despesas)
    story.append(Paragraph("Lançamentos (Saídas) no período", styles["Heading2"]))
    df_l = df_lancamentos.copy() if df_lancamentos is not None else pd.DataFrame()
    # Tenta reduzir colunas
    cols_pref = [c for c in ["Data_BR", "Categoria", "Descrição", "Valor"] if c in df_l.columns]
    if cols_pref:
        df_l = df_l[cols_pref]
    if not df_l.empty and "Valor" in df_l.columns:
        df_l["Valor"] = df_l["Valor"].apply(_fmt_brl)

    story.append(_df_to_table(df_l, max_rows=5000))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
