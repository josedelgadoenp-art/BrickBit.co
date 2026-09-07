"""El asistente de lenguaje natural."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..asistente import (ErrorAsistente, huella_llave, pedir_grafo, probar_conexion,
                         revisar)

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
    return {"disponible": listo, "motivo": motivo, "llave": huella_llave()}


@router.get("/prueba")
def prueba() -> dict:
    """Una llamada mínima a Anthropic, para saber si el problema es la llave,
    el acceso al modelo, o la forma de la petición grande."""
    return probar_conexion()


@router.post("")
def construir(cuerpo: Peticion) -> dict:
    try:
        return pedir_grafo(cuerpo.peticion, cuerpo.esquemas, cuerpo.grafo)
    except ErrorAsistente as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        # Sin esto, cualquier fallo inesperado —una validación de Pydantic sobre
        # el grafo propuesto, por ejemplo— sale como un 500 con «Internal Server
        # Error», que no le dice nada a nadie y esconde justo lo que hace falta.
        raise HTTPException(
            422, f"El asistente devolvió algo que no se pudo usar: "
                 f"{type(exc).__name__}: {exc}") from exc
