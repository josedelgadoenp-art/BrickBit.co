"""Exportar: el analisis como un paquete que corre sin Abak.

Un `.py` que lee un CSV que no existe no es reproducible. Por eso exportar
entrega un `.zip` con el script, los datos que necesita y su nota metodologica.
Al descomprimirlo, `python analisis.py` corre tal cual.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from ..codegen.emisor import Emision, a_texto, emitir
from ..graph.compilador import Programa
from ..registry.base import obtener
from .metodologia import nota_metodologica


def archivos_del_programa(programa: Programa) -> dict[str, str]:
    """{ruta dentro del zip: ruta real en disco} para todo lo que el script lee."""
    archivos: dict[str, str] = {}
    for ins in programa.instrucciones:
        spec = obtener(ins.op)
        if not spec.necesita_datos:
            continue
        archivos.update(spec().archivos(ins.params))
    return archivos


LEEME = """# {titulo}

Este paquete lo genero Abak. Trae el analisis completo y todo lo que necesita
para volver a correr, sin Abak de por medio.

## Como correrlo

```bash
pip install -r requisitos.txt
python analisis.py
```

## Que hay aqui

- `analisis.py` — el codigo. Es **el mismo** que se ejecuto en el lienzo, no una
  reconstruccion ni un equivalente aproximado.
- `datos/` — los archivos que lee el script.
- `metodologia.md` — que se hizo, con que supuestos y con que advertencias.
- `requisitos.txt` — las bibliotecas que hacen falta.

## Huella

`{huella}` identifica esta version exacta del analisis. Si vuelves a exportar
despues de cambiar algo en el lienzo, la huella cambia.

Semilla de aleatoriedad: `{semilla}`. Con la misma semilla y los mismos datos,
el resultado se repite.
"""

# Se derivan de los imports que el programa emitio: no se lista lo que no usa.
PAQUETES = {
    "pandas": "pandas>=2.0", "numpy": "numpy>=1.26", "statsmodels": "statsmodels>=0.14",
    "sklearn": "scikit-learn>=1.4", "xgboost": "xgboost>=2.0", "libpysal": "libpysal>=4.9",
    "spreg": "spreg>=1.4", "esda": "esda>=2.5", "plotly": "plotly>=5.18",
    "linearmodels": "linearmodels>=6.0", "scipy": "scipy>=1.11", "arch": "arch>=6.3",
    "openpyxl": "openpyxl>=3.1",
}


def requisitos(emision: Emision) -> str:
    raices = {(i.desde or i.modulo).split(".")[0] for i in emision.imports}
    lineas = sorted({PAQUETES[r] for r in raices if r in PAQUETES})
    return "\n".join(["# Generado por Abak a partir de los imports del analisis.", *lineas, ""])


def paquete(programa: Programa, *, autor: str | None = None,
            emision: Emision | None = None) -> bytes:
    """El .zip completo, en memoria."""
    emision = emision or emitir(programa)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("analisis.py", a_texto(emision, autor=autor))
        z.writestr("metodologia.md", nota_metodologica(programa, autor=autor))
        z.writestr("requisitos.txt", requisitos(emision))
        z.writestr("LEEME.md", LEEME.format(
            titulo=programa.titulo, huella=programa.huella_grafo[:16], semilla=programa.semilla))
        for destino, origen in archivos_del_programa(programa).items():
            ruta = Path(origen)
            if ruta.exists():
                z.write(ruta, destino)
    return buffer.getvalue()
