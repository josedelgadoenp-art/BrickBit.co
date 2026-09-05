"""Subir archivos del usuario.

Se valida por CONTENIDO, no por extension, y se convierte a un DataFrame antes
de que nada del motor lo toque. No se abre nada con pickle.
"""

from __future__ import annotations

import io

from abaco_core.graph.spec import Esquema
from abaco_core.runtime.almacen import ALMACEN
from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(prefix="/datos", tags=["datos"])

TOPE_BYTES = 64 * 1024 * 1024
TOPE_COLUMNAS = 2000
EXTENSIONES = {".csv", ".tsv", ".txt", ".xlsx", ".xls"}


@router.post("/subir")
async def subir(archivo: UploadFile = File(...)) -> dict:
    nombre = (archivo.filename or "datos.csv")
    sufijo = "." + nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if sufijo not in EXTENSIONES:
        raise HTTPException(415, f"Formato no admitido: {sufijo or 'sin extension'}. "
                                 f"Se aceptan {', '.join(sorted(EXTENSIONES))}.")

    contenido = await archivo.read()
    if len(contenido) > TOPE_BYTES:
        raise HTTPException(413, f"El archivo pesa {len(contenido) / 1024**2:.1f} MB y el tope "
                                 f"son {TOPE_BYTES / 1024**2:.0f} MB.")

    import pandas as pd

    try:
        if sufijo in (".xlsx", ".xls"):
            muestra = pd.read_excel(io.BytesIO(contenido), nrows=200)
        else:
            muestra = pd.read_csv(io.BytesIO(contenido), nrows=200, sep=None, engine="python")
    except Exception as exc:
        raise HTTPException(422, f"No se pudo leer el archivo: {exc}") from exc

    if muestra.shape[1] > TOPE_COLUMNAS:
        raise HTTPException(413, f"El archivo trae {muestra.shape[1]} columnas y el tope "
                                 f"son {TOPE_COLUMNAS}.")

    guardado = ALMACEN.guardar_subida(nombre, contenido)
    esquema = Esquema.de_dataframe(muestra, fuente=nombre)
    return {
        **guardado,
        "esquema": esquema.model_dump(),
        "vista_previa": muestra.head(20).to_dict(orient="records"),
    }
