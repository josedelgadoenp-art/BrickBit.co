# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
 BrickBit · INGESTA DENUE (INEGI) → escala Calle · Establecimiento
═══════════════════════════════════════════════════════════════════════════════
 Descarga el Directorio Estadístico Nacional de Unidades Económicas (DENUE)
 de INEGI, filtra un municipio/alcaldía y genera los dos archivos que el
 Motor de Morfogénesis detecta automáticamente:

   · data/establecimientos_azcapotzalco.csv.gz
        nombre, sector, calle, lat, lng, empleo
   · data/calles_azcapotzalco.json
        {"calles": [{nombre, camino: [[lng,lat]…]}, …]}

 REQUIERE red con acceso a inegi.org.mx (la política de red de algunos
 entornos de Claude Code lo bloquea — ejecútalo en tu máquina y commitea
 los archivos resultantes, o habilita el dominio en la política de red).

 Uso:
     python scripts/ingerir_denue.py                       # Azcapotzalco
     python scripts/ingerir_denue.py --estado 09 --municipio Azcapotzalco
     python scripts/ingerir_denue.py --estado 19 --municipio Monterrey

 Fuente: https://www.inegi.org.mx/app/descarga/ (DENUE, CSV por entidad).
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse
import gzip
import io
import json
import os
import sys
import unicodedata
import urllib.request
import zipfile

import numpy as np
import pandas as pd

# Patrones históricos de URL de descarga masiva del DENUE (INEGI los rota;
# el script intenta cada uno y reporta cuál respondió).
PATRONES_URL = [
    "https://www.inegi.org.mx/contenidos/masiva/denue/denue_{ee}_csv.zip",
    "https://www.inegi.org.mx/contenidos/masiva/denue/denue_{ee}_shp_csv.zip",
    "https://www.inegi.org.mx/contenidos/masiva/denue/{fecha}/denue_{ee}_csv.zip",
]

# Sector (2 primeros dígitos SCIAN) → macro-sector del motor
SCIAN_SECTOR = {
    "11": "Industria", "21": "Industria", "22": "Industria",
    "23": "Industria", "31": "Industria", "32": "Industria",
    "33": "Industria", "43": "Comercio", "46": "Comercio",
    "48": "Servicios", "49": "Servicios", "51": "Servicios",
    "52": "Servicios", "53": "Servicios", "54": "Servicios",
    "55": "Servicios", "56": "Servicios", "61": "Servicios",
    "62": "Servicios", "71": "Servicios", "81": "Servicios",
    "93": "Servicios", "72": "Alimentos",
}

# Marcas de empleo del DENUE → estimación puntual
EMPLEO = {"0 a 5 personas": 3, "6 a 10 personas": 8, "11 a 30 personas": 20,
          "31 a 50 personas": 40, "51 a 100 personas": 75,
          "101 a 250 personas": 175, "251 y más personas": 400}


def sin_acentos(s: str) -> str:
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore") \
        .decode().upper().strip()


def descargar_denue(estado: str) -> pd.DataFrame:
    """Intenta descargar el CSV masivo del DENUE para la entidad `estado`."""
    errores = []
    for patron in PATRONES_URL:
        url = patron.format(ee=estado, fecha="")
        try:
            print(f"⇣ intentando {url} …")
            with urllib.request.urlopen(url, timeout=300) as r:
                datos = r.read()
            with zipfile.ZipFile(io.BytesIO(datos)) as z:
                nombre = next(n for n in z.namelist()
                              if n.lower().endswith(".csv"))
                with z.open(nombre) as f:
                    df = pd.read_csv(f, encoding="latin-1", low_memory=False)
            print(f"✓ {len(df):,} establecimientos descargados")
            return df
        except Exception as e:            # noqa: BLE001 — probar siguiente patrón
            errores.append(f"  {url} → {e}")
    print("✗ No se pudo descargar el DENUE. Intentos:\n" + "\n".join(errores))
    print("\nDescarga manual: https://www.inegi.org.mx/app/descarga/ → DENUE"
          "\nColoca el CSV como data/denue_bruto.csv y reejecuta con --csv")
    sys.exit(1)


def procesar(df: pd.DataFrame, municipio: str, salida_dir: str,
             sufijo: str) -> None:
    """Filtra el municipio, sintetiza calles desde los puntos y escribe salidas."""
    cols = {c.lower().strip(): c for c in df.columns}

    def col(*candidatas):
        for c in candidatas:
            if c in cols:
                return cols[c]
        raise KeyError(f"columna no encontrada: {candidatas}")

    c_mun = col("municipio", "nom_mun")
    mask = df[c_mun].map(sin_acentos) == sin_acentos(municipio)
    d = df[mask].copy()
    print(f"→ {len(d):,} establecimientos en {municipio}")
    if d.empty:
        print("Municipios disponibles:",
              sorted(df[c_mun].dropna().unique())[:30])
        sys.exit(1)

    d["sector"] = d[col("codigo_act", "cod_actividad")].astype(str).str[:2] \
        .map(SCIAN_SECTOR).fillna("Servicios")
    d["empleo"] = d[col("per_ocu", "personal_ocupado")].map(EMPLEO).fillna(3)
    d["calle"] = d[col("nom_vial", "nombre_vialidad")].astype(str).str.title()
    d["lat"] = pd.to_numeric(d[col("latitud", "lat")], errors="coerce")
    d["lng"] = pd.to_numeric(d[col("longitud", "lng", "lon")], errors="coerce")
    d["nombre"] = d[col("nom_estab", "nombre")].astype(str).str.title()
    d = d.dropna(subset=["lat", "lng"])
    d = d[d["calle"].str.len() > 2]

    # ── establecimientos ──────────────────────────────────────────────────────
    os.makedirs(salida_dir, exist_ok=True)
    ruta_e = os.path.join(salida_dir, f"establecimientos_{sufijo}.csv.gz")
    with gzip.open(ruta_e, "wt", encoding="utf-8") as f:
        d[["nombre", "sector", "calle", "lat", "lng", "empleo"]] \
            .to_csv(f, index=False)
    print(f"✓ {ruta_e} ({len(d):,} filas)")

    # ── calles: polilínea por nombre vial ordenando los puntos sobre su eje ──
    calles = []
    for nombre, g in d.groupby("calle"):
        if len(g) < 4:                    # muy pocos puntos para trazar eje
            continue
        pts = g[["lng", "lat"]].to_numpy()
        centro = pts.mean(axis=0)
        u, s, vt = np.linalg.svd(pts - centro)   # eje principal (PCA)
        proy = (pts - centro) @ vt[0]
        orden = np.argsort(proy)
        # muestrear ~12 vértices a lo largo del eje para una polilínea limpia
        idx = np.unique(np.linspace(0, len(orden) - 1, 12).astype(int))
        camino = [[round(float(pts[orden[i], 0]), 5),
                   round(float(pts[orden[i], 1]), 5)] for i in idx]
        calles.append({"nombre": nombre, "camino": camino})
    ruta_c = os.path.join(salida_dir, f"calles_{sufijo}.json")
    with open(ruta_c, "w", encoding="utf-8") as f:
        json.dump({"calles": calles}, f, ensure_ascii=False)
    print(f"✓ {ruta_c} ({len(calles)} calles)")
    print("\nListo: reinicia la app (streamlit run app.py) y la escala "
          "'🛣 Calle · establecimiento' usará los datos reales del DENUE.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingesta DENUE → Morfogénesis")
    ap.add_argument("--estado", default="09",
                    help="clave INEGI de entidad (09 = CDMX)")
    ap.add_argument("--municipio", default="Azcapotzalco")
    ap.add_argument("--csv", default=None,
                    help="ruta a un CSV DENUE ya descargado (omite descarga)")
    ap.add_argument("--salida", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
    args = ap.parse_args()

    df = pd.read_csv(args.csv, encoding="latin-1", low_memory=False) \
        if args.csv else descargar_denue(args.estado)
    procesar(df, args.municipio, args.salida,
             sin_acentos(args.municipio).lower().replace(" ", "_"))


if __name__ == "__main__":
    main()
