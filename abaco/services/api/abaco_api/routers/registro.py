"""El catalogo de herramientas.

La paleta del frontend NO esta escrita en el frontend: se descarga de aqui. Una
herramienta nueva en el backend aparece en la interfaz sin tocar el frontend.
"""

from __future__ import annotations

from abaco_core.registry import FAMILIAS, catalogo, obtener
from abaco_core.runtime.metodologia import _valor_legible  # noqa: F401
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["registro"])


@router.get("/registro")
def leer_registro() -> dict:
    """Familias, herramientas y tipos de puerto. Es lo que dibuja la paleta."""
    return catalogo()


@router.get("/registro/familias")
def leer_familias() -> list[dict]:
    return [f.model_dump() for f in sorted(FAMILIAS.values(), key=lambda f: f.orden)]


@router.get("/registro/{op}")
def leer_herramienta(op: str) -> dict:
    try:
        return obtener(op).descriptor()
    except Exception as exc:
        raise HTTPException(404, str(exc)) from exc
