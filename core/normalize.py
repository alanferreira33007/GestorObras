import re
from core.constants import INSUMO_SYNONYMS


def normalizar_texto(s: str) -> str:
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("ç", "c").replace("á", "a").replace("à", "a").replace("ã", "a").replace("â", "a")
    s = s.replace("é", "e").replace("ê", "e")
    s = s.replace("í", "i")
    s = s.replace("ó", "o").replace("ô", "o").replace("õ", "o")
    s = s.replace("ú", "u")
    return s


def extrair_insumo(descricao: str) -> str:
    """
    Usa padrão:
    - Se tiver "Insumo: detalhe", pega antes de ":"
    - Senão tenta mapear por sinônimos
    """
    if not descricao:
        return "Sem descrição"

    base = descricao.split(":")[0].strip()
    base_norm = normalizar_texto(base)

    # tenta casar com sinônimos
    for canon, syns in INSUMO_SYNONYMS.items():
        for s in syns:
            if normalizar_texto(s) in base_norm:
                return canon

    # fallback: capitaliza o que veio
    return base.strip().title()
