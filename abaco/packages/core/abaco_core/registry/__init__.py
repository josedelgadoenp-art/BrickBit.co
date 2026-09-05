"""Registro de herramientas de Abaco."""

from __future__ import annotations

import importlib
import pkgutil

from .base import (AYUDANTES, FAMILIAS, REGISTRO, Ayuda, Ayudante, CampoColumna,
                   CampoColumnas, EspecNodo, ErrorRegistro, Familia, Puerto, catalogo,
                   obtener, registrar, registrar_ayudante, todos)

_cargado = False


def cargar_todos() -> int:
    """Importa cada modulo de `abaco_core.nodes`, que es donde vive el registro.

    Se hace por descubrimiento y no con una lista escrita a mano: agregar una
    herramienta tiene que ser crear un archivo, y nada mas. Una lista central
    seria un lugar donde olvidarse de dar de alta el nodo nuevo.
    """
    global _cargado
    if _cargado:
        return len(REGISTRO)
    from .. import nodes

    for info in pkgutil.walk_packages(nodes.__path__, prefix=f"{nodes.__name__}."):
        if info.name.rsplit(".", 1)[-1].startswith("_"):
            continue
        importlib.import_module(info.name)
    _cargado = True
    return len(REGISTRO)


__all__ = [
    "AYUDANTES", "FAMILIAS", "REGISTRO", "Ayuda", "Ayudante", "CampoColumna",
    "CampoColumnas", "EspecNodo", "ErrorRegistro", "Familia", "Puerto", "cargar_todos",
    "catalogo", "obtener", "registrar", "registrar_ayudante", "todos",
]
