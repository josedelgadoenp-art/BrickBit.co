"""Subir archivos del usuario.

Dos decisiones que sólo importan cuando el archivo es grande:

**El archivo nunca se carga completo en memoria.** Se escribe a disco por
trozos mientras llega. `await archivo.read()` sin argumentos —que es lo que se
escribe por costumbre— mete el archivo entero en RAM y tumba el proceso de la
API con un CSV de 2 GB, antes siquiera de empezar a analizarlo.

**Se convierte a Parquet al subirlo, no al usarlo.** Es columnar y tipado, así
que después leer 6 de 200 columnas cuesta 6 columnas de disco. La conversión
se paga una vez; leerlo se paga en cada ejecución.

Se valida por CONTENIDO, no por extensión, y no se abre nada con pickle.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from abak_core.runtime.almacen import ALMACEN
from abak_core.runtime.ingesta import ErrorIngesta, csv_a_parquet, revisar_memoria
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

router = APIRouter(prefix="/datos", tags=["datos"])

TOPE_MB = int(os.environ.get("ABAK_TOPE_SUBIDA_MB", "2048"))
TOPE_BYTES = TOPE_MB * 1024 * 1024
TOPE_COLUMNAS = 4096
TROZO = 4 * 1024 * 1024
EXTENSIONES = {".csv", ".tsv", ".txt", ".xlsx", ".xls", ".parquet"}


@router.post("/subir")
async def subir(
    archivo: UploadFile = File(...),
    separador: str = Form(default=","),
    decimal: str = Form(default="."),
    codificacion: str = Form(default="utf-8"),
    columnas_fecha: str = Form(default=""),
) -> dict:
    nombre = Path(archivo.filename or "datos.csv").name
    sufijo = ("." + nombre.rsplit(".", 1)[-1].lower()) if "." in nombre else ""
    if sufijo not in EXTENSIONES:
        raise HTTPException(415, f"Formato no admitido: {sufijo or 'sin extensión'}. "
                                 f"Se aceptan {', '.join(sorted(EXTENSIONES))}.")
    if separador not in (",", ";", "\t", "|") or decimal not in (".", ","):
        raise HTTPException(422, "Separador o decimal no admitido.")

    guardado = ALMACEN.guardar_subida(nombre, b"")
    archivo_id = guardado["archivo_id"]
    crudo = ALMACEN.ruta_subida(archivo_id, nombre)

    # --- a disco por trozos: el archivo nunca está entero en memoria --------
    total = 0
    try:
        with crudo.open("wb") as destino:
            while bloque := await archivo.read(TROZO):
                total += len(bloque)
                if total > TOPE_BYTES:
                    raise HTTPException(
                        413, f"El archivo pasa de {TOPE_MB:,} MB. Súbelo por partes, o filtra "
                             f"las filas que no necesitas antes de subirlo.")
                destino.write(bloque)
    except HTTPException:
        shutil.rmtree(crudo.parent, ignore_errors=True)
        raise
    if total == 0:
        shutil.rmtree(crudo.parent, ignore_errors=True)
        raise HTTPException(422, "El archivo llegó vacío.")

    fechas = [c.strip() for c in columnas_fecha.split(",") if c.strip()]
    parquet = ALMACEN.dir_subidas() / f"{archivo_id}.parquet"

    try:
        if sufijo in (".xlsx", ".xls"):
            info = await _excel_a_parquet(crudo, parquet, fechas)
        elif sufijo == ".parquet":
            info = _parquet_directo(crudo, parquet)
        else:
            info = csv_a_parquet(crudo, parquet, separador=separador, decimal=decimal,
                                 codificacion=codificacion, fechas=fechas)
    except ErrorIngesta as exc:
        shutil.rmtree(crudo.parent, ignore_errors=True)
        parquet.unlink(missing_ok=True)
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        shutil.rmtree(crudo.parent, ignore_errors=True)
        parquet.unlink(missing_ok=True)
        raise HTTPException(422, f"No se pudo leer el archivo: {exc}") from exc

    if info.n_columnas > TOPE_COLUMNAS:
        parquet.unlink(missing_ok=True)
        raise HTTPException(413, f"El archivo trae {info.n_columnas:,} columnas y el tope "
                                 f"son {TOPE_COLUMNAS:,}.")

    # El original ya no hace falta: el Parquet es lo que se lee.
    crudo.unlink(missing_ok=True)

    avisos = list(info.avisos)
    if (problema := revisar_memoria(info.n_filas, info.columnas)):
        avisos.append(problema)

    import pandas as pd

    vista = pd.read_parquet(parquet).head(20) if info.n_filas <= 20 else \
        pd.read_parquet(parquet).head(20)

    return {
        "archivo_id": archivo_id,
        "nombre": nombre,
        "n_filas": info.n_filas,
        "n_columnas": info.n_columnas,
        "bytes_origen": info.bytes_origen,
        "bytes_parquet": info.bytes_parquet,
        "compresion": round(info.compresion, 1),
        "sha256": info.sha256,
        "columnas": info.columnas,
        "avisos": avisos,
        "vista_previa": vista.astype(object).where(vista.notna(), None).to_dict(orient="records"),
    }


async def _excel_a_parquet(origen: Path, destino: Path, fechas: list[str]):
    """Excel no se puede leer por trozos: entra completo o no entra.

    Es una limitación del formato, no del código, y se dice tal cual en vez de
    fingir que se maneja igual que un CSV.
    """
    import pandas as pd

    from abak_core.runtime.ingesta import Ingesta, sha256_archivo

    marco = pd.read_excel(origen, parse_dates=fechas or None)
    marco.to_parquet(destino, compression="zstd", index=False)
    import pyarrow.parquet as pq

    esquema = pq.read_schema(destino)
    return Ingesta(
        ruta_parquet=str(destino), n_filas=len(marco), n_columnas=len(marco.columns),
        bytes_origen=origen.stat().st_size, bytes_parquet=destino.stat().st_size,
        sha256=sha256_archivo(origen),
        columnas=[{"nombre": n, "tipo_arrow": str(t),
                   "faltantes": int(marco[n].isna().sum()) if n in marco else 0}
                  for n, t in zip(esquema.names, esquema.types)],
        avisos=["Un Excel se lee completo en memoria: el formato no admite lectura por trozos. "
                "Para archivos muy grandes, conviértelo a CSV antes de subirlo."],
    )


def _parquet_directo(origen: Path, destino: Path):
    """Ya viene en el formato bueno: sólo se valida y se mueve."""
    import pyarrow.parquet as pq

    from abak_core.runtime.ingesta import Ingesta, sha256_archivo

    archivo = pq.ParquetFile(origen)
    esquema = archivo.schema_arrow
    shutil.move(str(origen), str(destino))
    return Ingesta(
        ruta_parquet=str(destino), n_filas=archivo.metadata.num_rows,
        n_columnas=len(esquema.names),
        bytes_origen=destino.stat().st_size, bytes_parquet=destino.stat().st_size,
        sha256=sha256_archivo(destino),
        columnas=[{"nombre": n, "tipo_arrow": str(t), "faltantes": 0}
                  for n, t in zip(esquema.names, esquema.types)],
    )
