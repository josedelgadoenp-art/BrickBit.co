"""Que Abak arranque en Windows, no sólo en Linux.

Esto existe porque no arrancaba. `abak_worker.tareas` hacía `import resource`
en la cabecera del módulo; `resource` es de Unix, no existe en Windows, y el
router de ejecuciones importa ese módulo. Resultado: la API entera moría al
arrancar con «No module named 'resource'», y la interfaz sólo alcanzaba a
decir «no se pudo cargar el catálogo de herramientas». El tope de memoria es
una comodidad; la API no.

La revisión es estática a propósito. Fingir el fallo del import a lo bruto
—reemplazando `__import__`— da falsos positivos: las bibliotecas de terceros
que sí funcionan en Windows lo protegen con `try/except` o lo cargan sólo al
levantar un worker, y bloquear `posix` rompe hasta `os`. Leer el árbol de
sintaxis de NUESTRO código dice exactamente lo que importa: qué módulos
sólo-Unix se cargan al importar, que es lo que tumba el arranque.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Módulos de la biblioteca estándar que no existen en Windows.
SOLO_UNIX = {"resource", "fcntl", "pwd", "grp", "termios", "posix", "syslog", "crypt"}

RAIZ = Path(__file__).resolve().parents[3]
FUENTES = sorted(
    p for base in ("packages/core/abak_core", "services/api/abak_api", "services/worker/abak_worker")
    for p in (RAIZ / base).rglob("*.py")
)


def _importes_de_nivel_superior(arbol: ast.Module) -> set[str]:
    """Los módulos que se cargan con sólo importar el archivo.

    Un import dentro de una función o de un `try` no cuenta: ése se ejecuta (o
    falla de forma recuperable) cuando alguien lo pide, no al arrancar.
    """
    nombres: set[str] = set()
    for nodo in arbol.body:  # sólo el nivel superior, sin recorrer cuerpos
        if isinstance(nodo, ast.Import):
            nombres.update(a.name.split(".")[0] for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            nombres.add(nodo.module.split(".")[0])
    return nombres


def test_hay_fuentes_que_revisar():
    assert len(FUENTES) > 30, "la revisión no encontró el código; la ruta está mal"


@pytest.mark.parametrize("ruta", FUENTES, ids=lambda p: str(p.relative_to(RAIZ)))
def test_ningun_modulo_carga_algo_de_solo_unix_al_importarse(ruta):
    arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    prohibidos = _importes_de_nivel_superior(arbol) & SOLO_UNIX
    assert not prohibidos, (
        f"{ruta.relative_to(RAIZ)} importa {sorted(prohibidos)} al cargarse: "
        f"eso impide que Abak arranque en Windows. Muévelo adentro de la función "
        f"que lo usa, con su try/except ImportError."
    )


def test_el_tope_de_memoria_no_estalla_cuando_no_hay_resource(monkeypatch):
    """Sin `resource` se ejecuta igual, simplemente sin tope de memoria."""
    import sys

    from abak_worker import tareas

    # `import x` con sys.modules['x'] puesto a None levanta ImportError: es la
    # manera limpia de simular que el módulo no existe.
    monkeypatch.setitem(sys.modules, "resource", None)
    monkeypatch.setattr(tareas, "EAGER", False)
    monkeypatch.setattr(tareas, "LIMITE_MEMORIA_GB", 4.0)
    tareas._limitar_memoria()  # no debe lanzar


def test_la_api_entrega_el_catalogo():
    """El síntoma que vio el usuario: la interfaz pide el catálogo y llega vacío."""
    from fastapi.testclient import TestClient

    from abak_api.main import app

    cliente = TestClient(app)
    assert cliente.get("/api/v1/salud").status_code == 200
    catalogo = cliente.get("/api/v1/registro").json()
    assert len(catalogo["nodos"]) > 50, "el catálogo llegó vacío"
