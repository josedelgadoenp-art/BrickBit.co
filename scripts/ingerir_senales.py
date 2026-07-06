# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
 BrickBit · INGESTA DE SEÑALES ALTERNATIVAS → capas sensoriales del organismo
═══════════════════════════════════════════════════════════════════════════════
 Descarga señales públicas complementarias al DENUE y las agrega por código
 postal de CDMX, listas para fusionarse con el potencial del motor:

   · AIRBNB (InsideAirbnb, público): densidad y precio medio de listados →
     proxy de turistificación/presión de renta corta.
     Salida: data/senal_airbnb_cdmx.csv  (cp, n_listados, precio_noche)

 REQUIERE red con acceso a insideairbnb.com (bloqueado en algunos entornos
 de Claude Code — ejecútalo en tu máquina y commitea la salida).

 Uso:
     python scripts/ingerir_senales.py airbnb

 Próximas señales (misma mecánica de archivo detectable):
   · GTFS Metro/Metrobús → accesibilidad por tiempo de viaje
   · Permisos de construcción (datos.cdmx.gob.mx) → pipeline de desarrollo
   · VIIRS luminosidad nocturna → actividad económica no registrada
═══════════════════════════════════════════════════════════════════════════════
"""

import gzip
import io
import json
import os
import sys
import urllib.request

import numpy as np
import pandas as pd

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_CP = os.path.join(_DIR, "data", "cdmx_codigos_postales.json")

# InsideAirbnb publica extracciones trimestrales; el segmento de fecha rota.
URLS_AIRBNB = [
    "https://data.insideairbnb.com/mexico/df/mexico-city/2025-12-25/data/listings.csv.gz",
    "https://data.insideairbnb.com/mexico/df/mexico-city/2025-09-24/data/listings.csv.gz",
    "https://data.insideairbnb.com/mexico/df/mexico-city/2025-06-29/data/listings.csv.gz",
]


def ingerir_airbnb() -> None:
    """Descarga listados de Airbnb CDMX y los agrega por código postal."""
    import geopandas as gpd
    from shapely.geometry import Point

    datos = None
    for url in URLS_AIRBNB:
        try:
            print(f"⇣ intentando {url} …")
            with urllib.request.urlopen(url, timeout=300) as r:
                datos = r.read()
            break
        except Exception as e:              # noqa: BLE001
            print(f"  ✗ {e}")
    if datos is None:
        print("✗ Sin acceso a insideairbnb.com — ejecuta en otra red o "
              "descarga listings.csv.gz manualmente de insideairbnb.com y "
              "colócalo como data/airbnb_bruto.csv.gz")
        sys.exit(1)

    df = pd.read_csv(io.BytesIO(gzip.decompress(datos)), low_memory=False)
    df["precio"] = pd.to_numeric(
        df["price"].astype(str).str.replace(r"[$,]", "", regex=True),
        errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"])
    print(f"✓ {len(df):,} listados Airbnb")

    with open(RUTA_CP, encoding="utf-8") as f:
        cp = gpd.GeoDataFrame.from_features(json.load(f)["features"],
                                            crs="EPSG:4326")
    col_cp = "cp" if "cp" in cp.columns else "d_codigo"
    puntos = gpd.GeoDataFrame(
        df[["precio"]],
        geometry=[Point(x, y) for x, y in zip(df["longitude"],
                                              df["latitude"])],
        crs="EPSG:4326")
    join = gpd.sjoin(puntos, cp[[col_cp, "geometry"]], predicate="within")
    agg = join.groupby(col_cp).agg(n_listados=("precio", "size"),
                                   precio_noche=("precio", "median")) \
        .reset_index().rename(columns={col_cp: "cp"})
    salida = os.path.join(_DIR, "data", "senal_airbnb_cdmx.csv")
    agg.to_csv(salida, index=False)
    print(f"✓ {salida} ({len(agg)} códigos postales con señal)")


if __name__ == "__main__":
    señal = sys.argv[1] if len(sys.argv) > 1 else "airbnb"
    if señal == "airbnb":
        ingerir_airbnb()
    else:
        print(f"Señal desconocida: {señal}. Disponibles: airbnb")
