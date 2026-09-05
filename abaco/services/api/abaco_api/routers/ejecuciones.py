"""Encolar, consultar y cancelar ejecuciones."""

from __future__ import annotations

from abaco_core import GrafoSpec, compilar
from abaco_core.runtime.almacen import ALMACEN
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from abaco_worker.celery_app import EAGER
from abaco_worker.tareas import ejecutar_grafo

router = APIRouter(prefix="/ejecuciones", tags=["ejecuciones"])


class PeticionEjecucion(BaseModel):
    grafo: GrafoSpec
    objetivo: str | None = None


@router.post("")
def crear(peticion: PeticionEjecucion) -> dict:
    """Valida primero y encola despues: un grafo invalido nunca llega al worker."""
    programa = compilar(peticion.grafo, objetivo=peticion.objetivo)
    if programa.hay_errores:
        raise HTTPException(400, {
            "mensaje": "El analisis tiene errores que hay que corregir antes de ejecutarlo.",
            "diagnosticos": [d.model_dump() for d in programa.diagnosticos
                             if d.severidad == "error"],
        })

    ejecucion_id = ALMACEN.nueva_ejecucion(peticion.grafo.model_dump())
    ejecutar_grafo.delay(ejecucion_id, peticion.grafo.model_dump(), peticion.objetivo)
    return {
        "id": ejecucion_id,
        "pasos": len(programa.instrucciones),
        "modo": "en proceso" if EAGER else "en cola",
    }


@router.get("/{ejecucion_id}")
def leer(ejecucion_id: str) -> dict:
    doc = ALMACEN.leer_ejecucion(ejecucion_id)
    if doc is None:
        raise HTTPException(404, "No existe esa ejecucion.")
    doc.pop("grafo", None)   # la interfaz ya lo tiene; no hace falta devolverlo
    return doc


@router.post("/{ejecucion_id}/cancelar")
def cancelar(ejecucion_id: str) -> dict:
    """La cancelacion se atiende ENTRE bloques, sin matar el proceso."""
    if not ALMACEN.pedir_cancelacion(ejecucion_id):
        raise HTTPException(409, "Esa ejecucion ya termino.")
    return {"ok": True}
