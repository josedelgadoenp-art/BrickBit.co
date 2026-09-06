"""Encolar, consultar y cancelar ejecuciones."""

from __future__ import annotations

from abak_core import GrafoSpec, compilar
from abak_core.runtime.almacen import ALMACEN
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from abak_worker.celery_app import EAGER
from abak_worker.tareas import ejecutar_grafo

from ..descargas import cabecera_descarga

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


@router.get("/{ejecucion_id}/informe")
def informe(ejecucion_id: str,
            nodo: str | None = Query(default=None, description="Sólo los resultados de ese bloque"),
            codigo: bool = Query(default=True, description="Incluir el apéndice con el código"),
            metodologia: bool = Query(default=True)) -> Response:
    """El informe en PDF, armado con los MISMOS artefactos que ve la interfaz.

    No se recalcula nada: un informe que vuelve a correr el análisis es un
    informe que puede contradecir a la pantalla.
    """
    from abak_core import GrafoSpec, a_texto, compilar, emitir
    from abak_core.runtime.informe import ErrorInforme, informe_pdf
    from abak_core.runtime.metodologia import nota_metodologica

    doc = ALMACEN.leer_ejecucion(ejecucion_id)
    if doc is None:
        raise HTTPException(404, "No existe esa ejecución.")
    if not doc.get("nodos"):
        raise HTTPException(409, "Esa ejecución todavía no tiene resultados.")

    grafo = GrafoSpec.model_validate(doc["grafo"])
    programa = compilar(grafo)

    try:
        pdf = informe_pdf(
            titulo=grafo.titulo,
            huella=programa.huella_grafo,
            semilla=grafo.semilla,
            nodos=doc["nodos"],
            orden=programa.orden,
            metodologia=nota_metodologica(programa) if metodologia else None,
            codigo=a_texto(emitir(programa)) if codigo else None,
            solo_nodo=nodo,
        )
    except ErrorInforme as exc:
        raise HTTPException(404, str(exc)) from exc

    sufijo = f"-{nodo}.pdf" if nodo else ".pdf"
    return Response(content=pdf, media_type="application/pdf",
                    headers=cabecera_descarga(grafo.titulo, sufijo, "informe"))


@router.post("/{ejecucion_id}/cancelar")
def cancelar(ejecucion_id: str) -> dict:
    """La cancelacion se atiende ENTRE bloques, sin matar el proceso."""
    if not ALMACEN.pedir_cancelacion(ejecucion_id):
        raise HTTPException(409, "Esa ejecucion ya termino.")
    return {"ok": True}
