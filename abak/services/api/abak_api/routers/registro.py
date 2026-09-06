"""El catalogo de herramientas.

La paleta del frontend NO esta escrita en el frontend: se descarga de aqui. Una
herramienta nueva en el backend aparece en la interfaz sin tocar el frontend.
"""

from __future__ import annotations

from abak_core.registry import FAMILIAS, catalogo, obtener
from abak_core.registry.glosario import buscar, como_json
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["registro"])


@router.get("/registro")
def leer_registro() -> dict:
    """Familias, herramientas y tipos de puerto. Es lo que dibuja la paleta."""
    return catalogo()


@router.get("/glosario")
def leer_glosario() -> dict:
    """Qué es cada indicador que Abak pone en pantalla.

    La interfaz lo baja una vez y lo consulta al vuelo por el nombre de la
    columna o del diagnóstico. Un indicador sin ficha no muestra nada: no se
    inventa una explicación.
    """
    return como_json()


@router.get("/glosario/{clave}")
def leer_indicador(clave: str) -> dict:
    ficha = buscar(clave)
    if ficha is None:
        raise HTTPException(404, f"No hay ficha para «{clave}».")
    return ficha.model_dump()


@router.get("/registro/familias")
def leer_familias() -> list[dict]:
    return [f.model_dump() for f in sorted(FAMILIAS.values(), key=lambda f: f.orden)]


@router.get("/registro/{op}")
def leer_herramienta(op: str) -> dict:
    try:
        return obtener(op).descriptor()
    except Exception as exc:
        raise HTTPException(404, str(exc)) from exc
