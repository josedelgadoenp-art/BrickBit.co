"""Compilar, validar, generar codigo y exportar. Todo sincrono: son milisegundos."""

from __future__ import annotations

from abaco_core import GrafoSpec, a_texto, compilar, emitir
from abaco_core.runtime.almacen import ALMACEN
from abaco_core.runtime.exportar import paquete
from abaco_core.runtime.metodologia import nota_metodologica
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter(prefix="/grafos", tags=["grafos"])


class PeticionGrafo(BaseModel):
    grafo: GrafoSpec
    objetivo: str | None = None


def _compilar(peticion: PeticionGrafo):
    return compilar(peticion.grafo, objetivo=peticion.objetivo)


@router.post("/validar")
def validar(peticion: PeticionGrafo) -> dict:
    """Diagnosticos y esquemas propagados. Se llama en cada cambio del lienzo.

    Los esquemas son lo que hace que los desplegables de «variable dependiente»
    muestren las columnas que de verdad existen en ese punto del grafo, y no las
    del archivo original.
    """
    programa = _compilar(peticion)
    return {
        "ok": not programa.hay_errores,
        "diagnosticos": [d.model_dump() for d in programa.diagnosticos],
        "orden": programa.orden,
        "podados": programa.podados,
        "huella": programa.huella_grafo,
        "esquemas": {
            nodo: {puerto: esquema.model_dump() for puerto, esquema in puertos.items()}
            for nodo, puertos in programa.esquemas.items()
        },
    }


@router.post("/codigo")
def codigo(peticion: PeticionGrafo) -> dict:
    """El shadow code. Es el MISMO objeto AST que se ejecuta, no una reconstruccion."""
    programa = _compilar(peticion)
    if programa.hay_errores:
        return {"ok": False, "codigo": None,
                "diagnosticos": [d.model_dump() for d in programa.diagnosticos]}
    emision = emitir(programa)
    return {
        "ok": True,
        "codigo": a_texto(emision),
        "lineas": len(a_texto(emision).splitlines()),
        "imports": sorted({i.desde or i.modulo for i in emision.imports}),
        "ayudantes": emision.ayudantes,
        "diagnosticos": [d.model_dump() for d in programa.diagnosticos],
    }


@router.post("/metodologia")
def metodologia(peticion: PeticionGrafo) -> dict:
    """La nota metodologica: que se hizo, con que supuestos y con que advertencias."""
    programa = _compilar(peticion)
    if programa.hay_errores:
        raise HTTPException(400, "El analisis todavia tiene errores.")
    return {"markdown": nota_metodologica(programa)}


@router.post("/exportar")
def exportar(peticion: PeticionGrafo) -> Response:
    """Un .zip con el script, sus datos, la metodologia y los requisitos."""
    programa = _compilar(peticion)
    if programa.hay_errores:
        raise HTTPException(400, "El analisis todavia tiene errores.")
    contenido = paquete(programa)
    nombre = (programa.titulo or "analisis").lower().replace(" ", "-")[:60]
    return Response(
        content=contenido, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{nombre}.zip"'},
    )


@router.post("")
def guardar(peticion: PeticionGrafo, grafo_id: str | None = None) -> dict:
    return {"id": ALMACEN.guardar_grafo(peticion.grafo.model_dump(), grafo_id)}


@router.get("")
def listar() -> list[dict]:
    return ALMACEN.listar_grafos()


@router.get("/{grafo_id}")
def leer(grafo_id: str) -> dict:
    doc = ALMACEN.leer_grafo(grafo_id)
    if doc is None:
        raise HTTPException(404, "No existe ese analisis.")
    return doc
