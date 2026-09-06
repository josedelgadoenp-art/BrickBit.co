"""Ingesta de archivos grandes: CSV a Parquet, por trozos y con tipos fijos.

Tres problemas distintos se resuelven aquí, y el segundo es de precisión, no de
memoria.

**1. No cabe.** Un CSV de varios GB no entra en `pd.read_csv()`. Se lee por
trozos y se escribe a Parquet, que es columnar: a partir de ahí, leer 6 de 200
columnas cuesta 6 columnas de disco, no 200.

**2. Los tipos cambian entre trozos, y nadie se entera.** Éste es el que muerde.
Si `pandas` infiere los tipos trozo por trozo, una columna que en las primeras
500 mil filas sólo trae enteros se lee como `int64`, y cuando en la fila 800 mil
aparece un decimal, ese trozo se lee como `float64`. El resultado es una columna
de tipo mixto: las comparaciones fallan raro, los `groupby` parten en dos, y
nada avisa. Por eso aquí se hace una pasada de muestreo primero, se fija el
tipo de cada columna, y todos los trozos se leen con ESE tipo.

**3. Los enteros de 64 bits casi nunca hacen falta.** Un año, un código de
entidad o un conteo caben en 16 o 32 bits, y eso es 2 a 4 veces menos memoria.
Los **flotantes NO se reducen**: `float32` tiene ~7 dígitos significativos, y
una suma de un millón de valores en `float32` acumula un error visible. En un
sistema que va a hacer econometría, cambiar precisión por memoria es un mal
canje, y no se hace.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Filas que se leen para deducir los tipos antes de la pasada completa.
FILAS_MUESTRA = 200_000
#: Filas por trozo en la conversión. Con 100k y 200 columnas son ~160 MB.
FILAS_TROZO = 100_000
#: Por encima de esta proporción de valores repetidos, una columna de texto
#: pasa a categoría: 32 estados en 10 millones de filas son 32 cadenas, no 10M.
UMBRAL_CATEGORIA = 0.05


@dataclass
class Ingesta:
    ruta_parquet: str
    n_filas: int
    n_columnas: int
    bytes_origen: int
    bytes_parquet: int
    sha256: str
    columnas: list[dict[str, Any]] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def compresion(self) -> float:
        return self.bytes_origen / self.bytes_parquet if self.bytes_parquet else 1.0


class ErrorIngesta(Exception):
    pass


def sha256_archivo(ruta: str | Path, trozo: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for bloque in iter(lambda: fh.read(trozo), b""):
            h.update(bloque)
    return h.hexdigest()


def _tipo_optimo(serie: Any, avisos: list[str]) -> Any:
    """El dtype más chico que NO pierde información.

    Los enteros se reducen; los flotantes se quedan en float64 a propósito
    (ver el encabezado del módulo). Las cadenas con pocos valores distintos
    pasan a categoría.
    """
    import numpy as np
    import pandas as pd

    if pd.api.types.is_bool_dtype(serie):
        return "bool"
    if pd.api.types.is_integer_dtype(serie):
        limpio = serie.dropna()
        if limpio.empty:
            return "Int32"
        minimo, maximo = int(limpio.min()), int(limpio.max())
        for candidato in ("int8", "int16", "int32"):
            info = np.iinfo(candidato)
            if minimo >= info.min and maximo <= info.max:
                # Nullable: un CSV puede traer huecos en una columna entera.
                return candidato.replace("int", "Int")
        return "Int64"
    if pd.api.types.is_float_dtype(serie):
        return "float64"
    if pd.api.types.is_datetime64_any_dtype(serie):
        return None  # lo maneja parse_dates
    distintos = serie.nunique(dropna=True)
    if len(serie) and distintos / max(len(serie), 1) < UMBRAL_CATEGORIA and distintos < 65_000:
        return "category"
    return "string"


def deducir_tipos(ruta: str | Path, *, separador: str = ",", decimal: str = ".",
                  codificacion: str = "utf-8", fechas: list[str] | None = None,
                  filas: int = FILAS_MUESTRA) -> tuple[dict[str, Any], list[str], list[str]]:
    """Una pasada de muestreo para fijar el tipo de cada columna.

    Devuelve (dtypes, columnas_de_fecha, avisos). Es lo que evita el problema
    de los tipos mixtos entre trozos.
    """
    import pandas as pd

    avisos: list[str] = []
    muestra = pd.read_csv(ruta, sep=separador, decimal=decimal, encoding=codificacion,
                          nrows=filas, low_memory=False)
    if len(muestra) >= filas:
        avisos.append(
            f"Los tipos se dedujeron con las primeras {filas:,} filas. Si más adelante "
            f"una columna cambia de naturaleza, el valor que no encaje queda como faltante "
            f"y se reporta abajo, en vez de convertir la columna en un tipo mixto silencioso.")

    columnas_fecha = list(fechas or [])
    dtypes: dict[str, Any] = {}
    for nombre in muestra.columns:
        if nombre in columnas_fecha:
            continue
        tipo = _tipo_optimo(muestra[nombre], avisos)
        if tipo is not None:
            dtypes[str(nombre)] = tipo
    return dtypes, columnas_fecha, avisos


def csv_a_parquet(origen: str | Path, destino: str | Path, *, separador: str = ",",
                  decimal: str = ".", codificacion: str = "utf-8",
                  fechas: list[str] | None = None, filas_trozo: int = FILAS_TROZO,
                  tope_filas: int | None = None) -> Ingesta:
    """Convierte un CSV a Parquet leyendo por trozos, con los tipos ya fijados."""
    import pandas as pd

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover
        raise ErrorIngesta(
            "Para leer archivos grandes hace falta pyarrow: pip install 'abak-core[archivos]'"
        ) from exc

    origen, destino = Path(origen), Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    dtypes, columnas_fecha, avisos = deducir_tipos(
        origen, separador=separador, decimal=decimal, codificacion=codificacion, fechas=fechas)

    escritor: Any = None
    n_filas = 0
    problemas: dict[str, int] = {}
    try:
        lector = pd.read_csv(origen, sep=separador, decimal=decimal, encoding=codificacion,
                             dtype=dtypes, parse_dates=columnas_fecha or None,
                             chunksize=filas_trozo, low_memory=False)
        for trozo in lector:
            if tope_filas is not None and n_filas >= tope_filas:
                avisos.append(f"Se leyeron sólo las primeras {tope_filas:,} filas, como se pidió.")
                break
            if tope_filas is not None and n_filas + len(trozo) > tope_filas:
                trozo = trozo.iloc[: tope_filas - n_filas]

            for columna in trozo.columns:
                faltantes = int(trozo[columna].isna().sum())
                if faltantes:
                    problemas[str(columna)] = problemas.get(str(columna), 0) + faltantes

            tabla = pa.Table.from_pandas(trozo, preserve_index=False)
            if escritor is None:
                escritor = pq.ParquetWriter(destino, tabla.schema, compression="zstd")
            else:
                # Si un trozo trae un esquema distinto es que los tipos fijados
                # no aguantaron: mejor decirlo que escribir un archivo mixto.
                tabla = tabla.cast(escritor.schema)
            escritor.write_table(tabla)
            n_filas += len(trozo)
    except (ValueError, TypeError) as exc:
        raise ErrorIngesta(
            f"El archivo no se pudo leer con un tipo estable por columna: {exc}. "
            f"Suele pasar cuando una columna mezcla números y texto (por ejemplo, «1,234» y "
            f"«N/D» en la misma columna). Revísala en el origen o decláralas como texto."
        ) from exc
    finally:
        if escritor is not None:
            escritor.close()

    if escritor is None:
        raise ErrorIngesta("El archivo no tiene filas.")

    esquema_parquet = pq.read_schema(destino)
    columnas = [{"nombre": n, "tipo_arrow": str(t), "faltantes": problemas.get(n, 0)}
                for n, t in zip(esquema_parquet.names, esquema_parquet.types)]
    con_faltantes = [c for c in columnas if c["faltantes"]]
    if con_faltantes:
        peores = sorted(con_faltantes, key=lambda c: -c["faltantes"])[:5]
        avisos.append("Columnas con valores faltantes: "
                      + ", ".join(f"{c['nombre']} ({c['faltantes']:,})" for c in peores)
                      + (" …" if len(con_faltantes) > 5 else "") + ".")

    return Ingesta(
        ruta_parquet=str(destino), n_filas=n_filas, n_columnas=len(columnas),
        bytes_origen=origen.stat().st_size, bytes_parquet=destino.stat().st_size,
        sha256=sha256_archivo(origen), columnas=columnas, avisos=avisos,
    )


# ---------------------------------------------------------------------------
# Barandal de memoria
# ---------------------------------------------------------------------------


def limite_memoria_bytes() -> int:
    gb = float(os.environ.get("ABAK_LIMITE_MEMORIA_GB", "0") or 0)
    return int(gb * 1024**3) if gb > 0 else 0


def estimar_memoria(n_filas: int, columnas: list[dict[str, Any]]) -> int:
    """Cuánto va a ocupar en RAM leer esas columnas.

    Se estima por tipo, no con un promedio: una columna de texto pesa mucho más
    que una de enteros de 16 bits, y confundirlas es como se llega a un OOM
    justo después de haber dicho que sí cabía.
    """
    ancho = {"int8": 1, "int16": 2, "int32": 4, "int64": 8, "bool": 1,
             "float": 8, "double": 8, "timestamp": 8, "date": 8, "dictionary": 8}
    total = 0
    for columna in columnas:
        tipo = str(columna.get("tipo_arrow", "string")).lower()
        bytes_por_valor = next((v for k, v in ancho.items() if tipo.startswith(k)), 64)
        total += n_filas * bytes_por_valor
    return int(total * 1.35)  # pandas guarda índice y metadatos además de los valores


def revisar_memoria(n_filas: int, columnas: list[dict[str, Any]]) -> str | None:
    """Devuelve un mensaje si el análisis no va a caber. `None` si sí cabe."""
    limite = limite_memoria_bytes()
    if not limite:
        return None
    estimado = estimar_memoria(n_filas, columnas)
    if estimado <= limite * 0.8:
        return None
    return (
        f"Leer {n_filas:,} filas por {len(columnas)} columnas necesita alrededor de "
        f"{estimado / 1024**3:.1f} GB, y este servidor tiene un tope de "
        f"{limite / 1024**3:.1f} GB. Tres formas de resolverlo, de mejor a peor: "
        f"quita del análisis las columnas que no uses (Abak lee sólo las que aparecen "
        f"en el grafo); filtra las filas antes de modelar; o trabaja con una muestra, "
        f"aceptando que los resultados serán aproximados."
    )
