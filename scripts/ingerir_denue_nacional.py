# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
 BrickBit · INGESTA NACIONAL DEL DENUE → vitalidad económica real por municipio
═══════════════════════════════════════════════════════════════════════════════
 Descarga las 32 entidades del DENUE (INEGI) — los ~5 millones de negocios del
 país — y agrega, para cada uno de los 2,436 municipios, la vitalidad económica
 REAL que alimenta el Motor de Morfogénesis a escala nacional:

   data/denue_municipal.csv   con columnas:
     cvegeo, estado, municipio, n_estab, empleo, comercio, servicios,
     industria, alimentos, resiliencia (entropía sectorial),
     altas_recientes, indicadoras (especies de gentrificación)

 Nunca guarda los 5M de registros crudos: procesa cada entidad en streaming y
 conserva solo los agregados municipales (archivo ligero, commiteable).

 Uso:
     python scripts/ingerir_denue_nacional.py            # las 32 entidades
     python scripts/ingerir_denue_nacional.py 09 19 14   # solo algunas

 Fuente: https://www.inegi.org.mx/app/descarga/ (DENUE, CSV por entidad).
═══════════════════════════════════════════════════════════════════════════════
"""

import io
import math
import os
import sys
import urllib.request
import zipfile

import numpy as np
import pandas as pd

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://www.inegi.org.mx/contenidos/masiva/denue/denue_{ee}_csv.zip"
SALIDA = os.path.join(_DIR, "data", "denue_municipal.csv")

# Sector (2 primeros dígitos SCIAN) → macro-sector
SCIAN = {"11": "industria", "21": "industria", "22": "industria",
         "23": "industria", "31": "industria", "32": "industria",
         "33": "industria", "43": "comercio", "46": "comercio",
         "48": "servicios", "49": "servicios", "51": "servicios",
         "52": "servicios", "53": "servicios", "54": "servicios",
         "55": "servicios", "56": "servicios", "61": "servicios",
         "62": "servicios", "71": "servicios", "81": "servicios",
         "93": "servicios", "72": "alimentos"}
EMPLEO = {"0 a 5 personas": 3, "6 a 10 personas": 8, "11 a 30 personas": 20,
          "31 a 50 personas": 40, "51 a 100 personas": 75,
          "101 a 250 personas": 175, "251 y más personas": 400}
# especies indicadoras de gentrificación (nombre_act SCIAN)
INDICADORAS = ["CAFETERIAS", "BARES, CANTINAS", "VETERINARIOS PARA MASCOTAS",
               "SALONES Y CLINICAS DE BELLEZA", "GIMNASIO",
               "ACONDICIONAMIENTO FISICO", "GALERIAS"]


URL_PARTE = ("https://www.inegi.org.mx/contenidos/masiva/denue/"
             "denue_{ee}_{p}_csv.zip")
COLS = ["cve_ent", "cve_mun", "entidad", "municipio",
        "codigo_act", "nombre_act", "per_ocu", "fecha_alta"]


def _leer_zip(datos: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        nombre = max((n for n in z.namelist() if n.lower().endswith(".csv")),
                     key=lambda n: z.getinfo(n).file_size)
        with z.open(nombre) as f:
            return pd.read_csv(f, encoding="latin-1", low_memory=False,
                               usecols=COLS)


def descargar(ee: str) -> pd.DataFrame:
    """
    Descarga y lee el DENUE de una entidad. Las entidades grandes (p. ej. el
    Estado de México) vienen PARTIDAS en denue_EE_1, denue_EE_2… — se
    detectan y concatenan automáticamente.
    """
    try:
        with urllib.request.urlopen(URL.format(ee=ee), timeout=600) as r:
            return _leer_zip(r.read())
    except zipfile.BadZipFile:
        partes = []
        for p in range(1, 9):
            try:
                with urllib.request.urlopen(URL_PARTE.format(ee=ee, p=p),
                                            timeout=600) as r:
                    partes.append(_leer_zip(r.read()))
            except (zipfile.BadZipFile, urllib.error.HTTPError):
                break
        if not partes:
            raise
        return pd.concat(partes, ignore_index=True)


def agregar_entidad(d: pd.DataFrame) -> pd.DataFrame:
    """Agrega una entidad del DENUE a nivel municipio."""
    d = d.copy()
    d["cvegeo"] = (d["cve_ent"].astype(str).str.zfill(2)
                   + d["cve_mun"].astype(str).str.zfill(3))
    d["sector"] = d["codigo_act"].astype(str).str[:2].map(SCIAN).fillna("servicios")
    d["empleo"] = d["per_ocu"].map(EMPLEO).fillna(3)
    act = d["nombre_act"].fillna("").str.upper()
    d["indicadora"] = act.apply(lambda a: any(k in a for k in INDICADORAS))
    fechas = sorted(d["fecha_alta"].dropna().unique())
    recientes = set(fechas[-2:]) if len(fechas) >= 2 else set()
    d["reciente"] = d["fecha_alta"].isin(recientes)

    filas = []
    for cvegeo, g in d.groupby("cvegeo"):
        sec = g["sector"].value_counts()
        n = len(g)
        p = (sec / n).clip(lower=1e-9)
        entropia = float(-(p * np.log(p)).sum() / math.log(4))
        filas.append({
            "cvegeo": cvegeo,
            "estado": g["entidad"].iloc[0],
            "municipio": g["municipio"].iloc[0],
            "n_estab": int(n),
            "empleo": int(g["empleo"].sum()),
            "comercio": int(sec.get("comercio", 0)),
            "servicios": int(sec.get("servicios", 0)),
            "industria": int(sec.get("industria", 0)),
            "alimentos": int(sec.get("alimentos", 0)),
            "resiliencia": round(entropia, 3),
            "altas_recientes": int(g["reciente"].sum()),
            "indicadoras": int((g["indicadora"] & g["reciente"]).sum()),
        })
    return pd.DataFrame(filas)


def main(entidades: list) -> None:
    acumulado = []
    if os.path.exists(SALIDA):                     # permite reanudar
        prev = pd.read_csv(SALIDA, dtype={"cvegeo": str})
        hechos = {c[:2] for c in prev["cvegeo"]}
        acumulado.append(prev)
        entidades = [e for e in entidades if e not in hechos]
        if hechos:
            print(f"↻ reanudando; ya procesadas: {sorted(hechos)}")

    for i, ee in enumerate(entidades, 1):
        try:
            print(f"[{i}/{len(entidades)}] entidad {ee} ⇣ …", flush=True)
            d = descargar(ee)
            agg = agregar_entidad(d)
            acumulado.append(agg)
            total = pd.concat(acumulado, ignore_index=True)
            total.to_csv(SALIDA, index=False)       # persiste tras cada entidad
            print(f"    ✓ {ee}: {len(agg)} municipios · "
                  f"{agg['n_estab'].sum():,} negocios · guardado incremental")
        except Exception as e:                        # noqa: BLE001
            print(f"    ✗ {ee}: {e}")

    if acumulado:
        total = pd.concat(acumulado, ignore_index=True).drop_duplicates("cvegeo")
        total.to_csv(SALIDA, index=False)
        print(f"\n✅ {SALIDA}: {len(total)} municipios · "
              f"{total['n_estab'].sum():,} establecimientos reales del DENUE")
        print("Reinicia la app: la escala '🏛 República · municipios' usará "
              "la vitalidad económica REAL de cada municipio.")


if __name__ == "__main__":
    ents = sys.argv[1:] or [f"{i:02d}" for i in range(1, 33)]
    main([e.zfill(2) for e in ents])
