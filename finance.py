# finance.py
def calcular_indicadores(vgv, custos):
    lucro = vgv - custos
    roi = (lucro / custos * 100) if custos > 0 else 0
    perc_vgv = (custos / vgv * 100) if vgv > 0 else 0
    return lucro, roi, perc_vgv


def custo_por_categoria(df):
    return (
        df.groupby("Categoria", as_index=False)["Valor"]
        .sum()
        .sort_values("Valor", ascending=False)
    )
