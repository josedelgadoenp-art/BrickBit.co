"""Abak — motor de analisis economico sin codigo.

El nucleo es Python puro: no importa FastAPI ni Celery, y se puede usar como
biblioteca desde un cuaderno. Esa regla se prueba (`test_nucleo_puro`), porque
si el compilador solo se puede ejercitar levantando un servidor, en la practica
no se prueba.

    from abak_core import compilar, ejecutar, a_texto, cargar_todos

    cargar_todos()
    programa = compilar(grafo)
    print(a_texto(emitir(programa)))     # el script exportable
    resultado = ejecutar(programa)       # el mismo codigo, ejecutado
"""

from __future__ import annotations

from .codegen.emisor import VERSION_ABAK, Emision, a_texto, emitir
from .graph.compilador import Diagnostico, Instruccion, Programa, compilar
from .graph.spec import AristaSpec, Columna, Esquema, GrafoSpec, NodoSpec
from .registry import cargar_todos, catalogo
from .runtime.cache import CacheDisco, CacheMemoria, SinCache
from .runtime.ejecutor import Ejecutor, ResultadoEjecucion

__version__ = VERSION_ABAK


def ejecutar(programa: Programa, **kw) -> ResultadoEjecucion:
    """Atajo: compila la emision y la corre con caché en memoria."""
    return Ejecutor(**kw).ejecutar(programa)


__all__ = [
    "AristaSpec", "CacheDisco", "CacheMemoria", "Columna", "Diagnostico", "Ejecutor",
    "Emision", "Esquema", "GrafoSpec", "Instruccion", "NodoSpec", "Programa",
    "ResultadoEjecucion", "SinCache", "VERSION_ABAK", "__version__", "a_texto",
    "cargar_todos", "catalogo", "compilar", "ejecutar", "emitir",
]
