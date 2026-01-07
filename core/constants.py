CATEGORIAS_PADRAO = [
    "Geral",
    "Material",
    "Mão de Obra",
    "Elétrica",
    "Hidráulica",
    "Acabamento",
    "Estrutura",
    "Ferramentas",
    "Frete/Transporte",
    "Taxas/Impostos",
    "Projeto/Engenharia",
    "Outros",
]

# Cabeçalhos mínimos esperados nas abas
FIN_HEADERS = ["ID", "Data", "Tipo", "Categoria", "Descrição", "Valor", "Obra Vinculada", "Anexo"]
OBRAS_HEADERS = ["ID", "Cliente", "Status", "Valor Total", "Data Início", "Observações"]
ORC_HEADERS = ["Obra", "Categoria", "Planejado"]

# Alertas
BUDGET_WARN = 0.80
BUDGET_FAIL = 1.00

# Normalização de insumos (chave -> lista de apelidos)
INSUMO_SYNONYMS = {
    "Cimento": ["cimento", "cp2", "cp ii", "cp-ii", "cp ii-f", "cp2-32", "cp2 32"],
    "Areia": ["areia", "areia lavada", "areia fina", "areia grossa"],
    "Brita": ["brita", "brita 0", "brita 1", "brita 2"],
    "Tijolo": ["tijolo", "tijolos", "tijolo 8 furos", "tijolo 6 furos"],
    "Bloco": ["bloco", "blocos", "bloco cerâmico", "bloco concreto"],
    "Aço": ["aco", "aço", "ferro", "vergalhão", "vergalhao"],
    "Cal": ["cal", "cal hidratada"],
    "Argamassa": ["argamassa", "massa pronta"],
    "Rejunte": ["rejunte"],
    "Cerâmica": ["ceramica", "cerâmica", "porcelanato"],
    "Tinta": ["tinta", "selador", "massa corrida"],
    "Madeira": ["madeira", "tábua", "tabua", "compensado", "mdf"],
}
