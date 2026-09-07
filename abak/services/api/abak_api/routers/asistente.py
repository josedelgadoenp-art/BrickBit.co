"""El asistente de lenguaje natural."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..asistente import ErrorAsistente, pedir_grafo

router = APIRouter(prefix="/asistente", tags=["asistente"])


class Peticion(BaseModel):
    peticion: str = Field(min_length=3, max_length=4000)
    esquemas: list[dict[str, Any]] | None = None
    grafo: dict[str, Any] | None = None


@router.get("/estado")
def estado() -> dict:
    """¿Está configurada la llave? La interfaz lo pregunta antes de ofrecerlo."""
    import os
    return {"disponible": bool(os.environ.get("ANTHROPIC_API_KEY"))}


@router.post("")
def construir(cuerpo: Peticion) -> dict:
    try:
        return pedir_grafo(cuerpo.peticion, cuerpo.esquemas, cuerpo.grafo)
    except ErrorAsistente as exc:
        raise HTTPException(422, str(exc)) from exc
