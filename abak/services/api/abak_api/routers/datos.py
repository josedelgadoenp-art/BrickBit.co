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
TABULARES = {".csv", ".tsv", ".txt", ".xlsx", ".xls", ".parquet"}
EXTENSIONES = TABULARES | {".zip"}
# Ruido de empaquetado que traen los zips hechos en Mac y en Windows.
BASURA_ZIP = ("__MACOSX/", ".DS_Store", "Thumbs.db")


def _extraer_del_zip(crudo: Path) -> tuple[Path, str, str]:
    """Saca el único archivo tabular de un .zip y devuelve (ruta, sufijo, nombre).

    Existe porque las fuentes oficiales mexicanas publican así: el DENUE, las
    series de la SHF y casi todo lo del INEGI se bajan comprimidos. Obligar a
    descomprimir a mano antes de subir es un paso de más en el trabajo que más
    se repite.

    Si el zip trae varios archivos tabulares NO se adivina cuál: se listan y se
    pide elegir. Adivinar aquí significaría analizar el archivo equivocado sin
    que nadie se entere, que es peor que fallar.
    """
    import zipfile

    try:
        with zipfile.ZipFile(crudo) as z:
            candidatos = []
            for info in z.infolist():
                if info.is_dir():
                    continue
                interno = info.filename
                if any(b in interno for b in BASURA_ZIP):
                    continue
                if Path(interno).name.startswith("."):
                    continue
                if Path(interno).suffix.lower() in TABULARES:
                    candidatos.append(info)

            if not candidatos:
                raise ErrorIngesta(
                    "El .zip no trae ningún archivo de datos. Se buscan "
                    f"{', '.join(sorted(TABULARES))}.")
            if len(candidatos) > 1:
                lista = ", ".join(sorted(Path(c.filename).name for c in candidatos)[:6])
                raise ErrorIngesta(
                    f"El .zip trae {len(candidatos)} archivos de datos ({lista}"
                    f"{', …' if len(candidatos) > 6 else ''}). Descomprímelo y sube el "
                    f"que quieras analizar: adivinar cuál es sería peor que preguntarte.")

            elegido = candidatos[0]
            # El nombre de adentro NUNCA se usa como ruta: un zip puede traer
            # «../../algo» y escribir fuera de su carpeta (zip slip). Se toma
            # sólo el nombre final y se escribe donde nosotros decidimos.
            nombre = Path(elegido.filename).name
            sufijo = Path(nombre).suffix.lower()
            destino = crudo.parent / nombre

            # El tamaño declarado en el zip puede mentir, así que el tope se
            # cuenta sobre los bytes que salen de verdad (bomba de descompresión).
            try:
                with z.open(elegido) as origen, destino.open("wb") as salida:
                    escrito = 0
                    while bloque := origen.read(TROZO):
                        escrito += len(bloque)
                        if escrito > TOPE_BYTES:
                            salida.close()
                            destino.unlink(missing_ok=True)
                            raise ErrorIngesta(
                                f"Descomprimido, «{nombre}» pasa de {TOPE_MB:,} MB.")
                        salida.write(bloque)
            except RuntimeError as exc:  # zip con contraseña
                raise ErrorIngesta(f"No se pudo abrir «{nombre}»: {exc}") from exc

            if escrito == 0:
                destino.unlink(missing_ok=True)
                raise ErrorIngesta(f"«{nombre}» venía vacío dentro del .zip.")
            return destino, sufijo, nombre
    except zipfile.BadZipFile as exc:
        raise ErrorIngesta("El archivo no es un .zip válido o está dañado.") from exc


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
        if sufijo == ".zip":
            crudo, sufijo, nombre = _extraer_del_zip(crudo)
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
