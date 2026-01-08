
import io
import pandas as pd
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas


# -----------------------------
# Canvas para rodapé + "Página X de Y"
# -----------------------------
class NumberedCanvas(canvas.Canvas):
    """
    Escreve rodapé em todas as páginas:
    - Esquerda: "Gestor Pro • <Obra> • <Período>"
    - Direita: "Página X de Y"
    """

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

        # linha sutil acima do rodapé
        self.setStrokeColor(colors.lightgrey)
        self.setLineWidth(0.5)
        self.line(24, 28, width - 24, 28)

        self.setFillColor(colors.grey)
        self.setFont("Helvetica", 9)

        # esquerda
        self.drawString(24, 14, self.footer_left[:120])

        # direita
        txt = f"Página {page_num} de {page_count}"
        self.drawRightString(width - 24, 14, txt)


def _fmt_brl(v: float) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(v)


def _to_float(x) -> float:
    """Converte valores que podem vir como string BR (R$ 1.234,56) para float."""
    if x is None:
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s:
        return 0.0
    s = s.replace("R$", "").replace(" ", "")
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def _df_to_table(df: pd.DataFrame, max_rows=None):
    """
    Converte DataFrame em tabela ReportLab.
    - repeatRows=1: repete cabeçalho em páginas seguintes
    - splitByRow=1: permite quebrar entre linhas em múltiplas páginas
    - max_rows: None = sem limite
    """
    styles = getSampleStyleSheet()

    if df is None or df.empty:
        return Paragraph("<i>Sem dados.</i>", styles["BodyText"])

    df2 = df.copy()
    if max_rows is not None and len(df2) > max_rows:
        df2 = df2.head(max_rows)

    data = [list(df2.columns)] + df2.astype(str).values.tolist()

    t = Table(data, hAlign="LEFT", repeatRows=1)
    t.splitByRow = 1  # quebra em várias páginas

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
    PDF (bytes) para a aba Investimentos.
    - Data sempre DD/MM/AAAA
    - Lançamentos: mais recente -> mais antigo
    - Rodapé: "Gestor Pro • Obra • Período" + "Página X de Y"
    - Tabelas longas quebram em várias páginas (cabeçalho repetido)
    - Lançamentos sem limite de linhas
    """
    buffer = io.BytesIO()

    footer_left = f"Gestor Pro • {obra} • {periodo}"

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=24,
        leftMargin=24,
        topMargin=24,
        bottomMargin=40,  # espaço pro rodapé
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

    # Resumo
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
    story.append(_df_to_table(resumo))
    story.append(Spacer(1, 14))

    # Categorias
    story.append(Paragraph("Custo por categoria (período)", styles["Heading2"]))
    df_cat_raw = df_categorias.copy() if df_categorias is not None else pd.DataFrame()

    if not df_cat_raw.empty:
        if "Categoria" not in df_cat_raw.columns:
            df_cat_raw["Categoria"] = "Sem categoria"
        if "Valor" in df_cat_raw.columns:
            df_cat_raw["Valor_num"] = df_cat_raw["Valor"].apply(_to_float)
        else:
            df_cat_raw["Valor_num"] = 0.0

        df_cat_raw["Categoria"] = df_cat_raw["Categoria"].fillna("Sem categoria").astype(str).str.strip()

        df_cat_agg = (
            df_cat_raw.groupby("Categoria", as_index=False)["Valor_num"]
            .sum()
            .sort_values("Valor_num", ascending=False)
        )

        df_cat_tbl = df_cat_agg.rename(columns={"Valor_num": "Valor"})
        df_cat_tbl["Valor"] = df_cat_tbl["Valor"].apply(_fmt_brl)
    else:
        df_cat_agg = pd.DataFrame(columns=["Categoria", "Valor_num"])
        df_cat_tbl = pd.DataFrame(columns=["Categoria", "Valor"])

    story.append(_df_to_table(df_cat_tbl))
    story.append(Spacer(1, 14))

    # Lançamentos (Saídas)
    story.append(Paragraph("Lançamentos (Saídas) no período", styles["Heading2"]))
    df_l = df_lancamentos.copy() if df_lancamentos is not None else pd.DataFrame()

    if not df_l.empty:
        if "Data_DT" in df_l.columns and df_l["Data_DT"].notna().any():
            df_l["_data_ord"] = pd.to_datetime(df_l["Data_DT"], errors="coerce")
        elif "Data" in df_l.columns and df_l["Data"].notna().any():
            df_l["_data_ord"] = pd.to_datetime(df_l["Data"], errors="coerce")
        elif "Data_BR" in df_l.columns and df_l["Data_BR"].notna().any():
            df_l["_data_ord"] = pd.to_datetime(df_l["Data_BR"], errors="coerce", dayfirst=True)
        else:
            df_l["_data_ord"] = pd.NaT

        df_l = df_l.sort_values("_data_ord", ascending=False, na_position="last")
        df_l["Data"] = df_l["_data_ord"].dt.strftime("%d/%m/%Y").fillna("")
    else:
        df_l["Data"] = ""

    cols = []
    if "Data" in df_l.columns: cols.append("Data")
    if "Categoria" in df_l.columns: cols.append("Categoria")
    if "Descrição" in df_l.columns: cols.append("Descrição")
    if "Valor" in df_l.columns: cols.append("Valor")

    df_l_show = df_l[cols].copy() if cols else df_l.copy()

    if not df_l_show.empty and "Valor" in df_l_show.columns:
        df_l_show["Valor"] = df_l_show["Valor"].apply(_fmt_brl)

    # ✅ sem limite
    story.append(_df_to_table(df_l_show, max_rows=None))
    story.append(Spacer(1, 14))

    # Fechamento
    story.append(Paragraph("Fechamento do período", styles["Heading2"]))

    total_lanc = (
        float(df_lancamentos["Valor"].apply(_to_float).sum())
        if (df_lancamentos is not None and not df_lancamentos.empty and "Valor" in df_lancamentos.columns)
        else float(custos)
    )
    qtd_lanc = int(len(df_lancamentos)) if (df_lancamentos is not None and not df_lancamentos.empty) else 0

    fechamento = pd.DataFrame(
        [
            ["Total de lançamentos (Saídas)", str(qtd_lanc)],
            ["Total gasto no período", _fmt_brl(total_lanc)],
        ],
        columns=["Item", "Valor"],
    )
    story.append(_df_to_table(fechamento))
    story.append(Spacer(1, 10))

    if not df_cat_agg.empty:
        top5 = df_cat_agg.head(5).copy()
        top5["Valor"] = top5["Valor_num"].apply(_fmt_brl)
        if total_lanc > 0:
            top5["% do total"] = (top5["Valor_num"] / total_lanc * 100).round(1).astype(str) + "%"
        else:
            top5["% do total"] = "0%"

        top5_tbl = top5[["Categoria", "Valor", "% do total"]].copy()
        story.append(Paragraph("Top 5 categorias", styles["Heading3"]))
        story.append(_df_to_table(top5_tbl))
    else:
        story.append(Paragraph("<i>Sem categorias para exibir Top 5.</i>", styles["BodyText"]))

    # Finaliza PDF com rodapé personalizado
    doc.build(
        story,
        canvasmaker=lambda *args, **kwargs: NumberedCanvas(*args, footer_left=footer_left, **kwargs),
    )

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
