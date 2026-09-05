"""El núcleo tiene que poder usarse sin API y sin worker."""

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "abak_core"
PROHIBIDOS = {"fastapi", "starlette", "celery", "uvicorn", "redis", "abak_api", "abak_worker"}


def test_nucleo_puro():
    """`abak_core` no importa nada de la capa web.

    Si el compilador sólo se puede ejercitar levantando un servidor, en la
    práctica no se prueba. Esta regla es lo que mantiene el núcleo usable desde
    un cuaderno, y por lo tanto probable.
    """
    culpables = []
    for archivo in RAIZ.rglob("*.py"):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            modulos = []
            if isinstance(nodo, ast.Import):
                modulos = [a.name for a in nodo.names]
            elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                modulos = [nodo.module]
            for m in modulos:
                if m.split(".")[0] in PROHIBIDOS:
                    culpables.append(f"{archivo.relative_to(RAIZ)}: {m}")
    assert not culpables, "El núcleo importa la capa web:\n" + "\n".join(culpables)


def test_se_importa_sin_dependencias_opcionales():
    """Importar el paquete no puede exigir libpysal, xgboost ni linearmodels."""
    assert "abak_core" in sys.modules or __import__("abak_core")
