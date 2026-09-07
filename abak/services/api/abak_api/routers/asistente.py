"""El asistente de lenguaje natural."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..asistente import ErrorAsistente, pedir_grafo, revisar

router = APIRouter(prefix="/asistente", tags=["asistente"])


class Peticion(BaseModel):
    peticion: str = Field(min_length=3, max_length=4000)
    esquemas: list[dict[str, Any]] | None = None
    grafo: dict[str, Any] | None = None


@router.get("/estado")
def estado() -> dict:
    """¿Se puede usar el asistente? Y si no, qué falta.

    El `motivo` viaja a la interfaz para que en pantalla diga qué hacer, en vez
    de esconder el asistente sin explicación — que es lo que hacía antes y deja
    a la persona sin manera de saber si le falta algo o si no existe.
    """
    listo, motivo = revisar()
    return {"disponible": listo, "motivo": motivo}


@router.post("")
def construir(cuerpo: Peticion) -> dict:
    try:
        return pedir_grafo(cuerpo.peticion, cuerpo.esquemas, cuerpo.grafo)
    except ErrorAsistente as exc:
        raise HTTPException(422, str(exc)) from exc
