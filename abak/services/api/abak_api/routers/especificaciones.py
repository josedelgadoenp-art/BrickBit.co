"""Cuántas especificaciones probaste antes de reportar una."""

from __future__ import annotations

from fastapi import APIRouter, Query

from abak_core.runtime.especificaciones import libro_por_omision

router = APIRouter(prefix="/especificaciones", tags=["especificaciones"])


@router.get("")
def listar() -> dict:
    """Qué variables has intentado explicar, y cuántas veces cada una."""
    return {"resultados": libro_por_omision().resultados_registrados()}


@router.get("/{resultado}")
def resumen(resultado: str, nodo: str | None = Query(default=None)) -> dict:
    """La distribución de cada coeficiente entre todas las especificaciones.

    `nodo` es el bloque que se está mirando, para poder decir dónde cae el
    número que se va a reportar dentro de todo lo que se probó.
    """
    return libro_por_omision().resumen(resultado, actual=nodo)
