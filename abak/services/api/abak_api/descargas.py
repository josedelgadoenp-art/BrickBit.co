"""Nombres de archivo para las descargas.

Las cabeceras HTTP son latin-1. Un título como «Precio por m² y escolaridad»
revienta `Content-Disposition` si se manda tal cual, y el error aparece
DESPUÉS de haber empezado a mandar la respuesta, que es el peor momento.

La forma correcta es la de la RFC 6266: un `filename` en ASCII para los
clientes viejos y un `filename*` en UTF-8 para los que lo entienden, que son
todos los navegadores actuales. Así el usuario recibe el nombre con acentos y
nada se rompe.
"""

from __future__ import annotations

import unicodedata
from urllib.parse import quote


def nombre_archivo(titulo: str, sufijo: str, respaldo: str = "analisis") -> str:
    """«Precio por m² 2024» + «.pdf» -> «precio-por-m2-2024.pdf» (versión ASCII)."""
    normal = unicodedata.normalize("NFKD", titulo or "")
    ascii_ = "".join(c for c in normal if not unicodedata.combining(c))
    limpio = "".join(c if (c.isascii() and (c.isalnum() or c in " -_")) else " " for c in ascii_)
    partes = [p for p in limpio.lower().split() if p]
    return ("-".join(partes)[:60] or respaldo) + sufijo


def cabecera_descarga(titulo: str, sufijo: str, respaldo: str = "analisis") -> dict[str, str]:
    """`Content-Disposition` con las dos formas del nombre (RFC 6266)."""
    ascii_ = nombre_archivo(titulo, sufijo, respaldo)
    utf8 = quote(f"{(titulo or respaldo).strip()[:60]}{sufijo}", safe="")
    return {"Content-Disposition": f"attachment; filename=\"{ascii_}\"; filename*=UTF-8''{utf8}"}
