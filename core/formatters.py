from __future__ import annotations
from datetime import datetime, date

def fmt_moeda(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"R$ {valor}"

def fmt_data_br(dt):
    if dt is None:
        return ""
    if isinstance(dt, str):
        # tenta YYYY-MM-DD
        try:
            dt = datetime.fromisoformat(dt).date()
        except Exception:
            return dt
    if isinstance(dt, datetime):
        dt = dt.date()
    if isinstance(dt, date):
        return dt.strftime("%d/%m/%Y")
    return str(dt)
