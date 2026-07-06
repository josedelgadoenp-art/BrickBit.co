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


# Especies indicadoras por nombre de actividad SCIAN (nombre_act del DENUE):
# su apertura RECIENTE precede a la plusvalía 2-3 años (gentrificación).
INDICADORAS_ACT = {
    "☕ Café/neverías": ["CAFETERIAS"],
    "🍺 Bar/cantina": ["BARES, CANTINAS"],
    "🐕 Veterinaria": ["VETERINARIOS PARA MASCOTAS"],
    "💈 Estética/belleza": ["SALONES Y CLINICAS DE BELLEZA"],
    "🏋 Gimnasio": ["DEPORTIVOS", "GIMNASIO", "ACONDICIONAMIENTO FISICO"],
    "🎨 Galería/arte": ["GALERIAS", "OBRAS DE ARTE"],
}


def sismografo_altas(d: pd.DataFrame, salida_dir: str, sufijo: str) -> None:
    """
    🌡 SISMÓGRAFO desde UN corte del DENUE usando `fecha_alta`: mide, por
    calle, las aperturas recientes (últimos 2 cortes) y cuántas son ESPECIES
    INDICADORAS de gentrificación. Escribe data/sismografo_<sufijo>.json.
    """
    if "fecha_alta" not in d.columns or "nombre_act" not in d.columns:
        return
    fechas = sorted(d["fecha_alta"].dropna().unique())
    if len(fechas) < 2:
        return
    recientes_set = set(fechas[-2:])          # los 2 cortes más nuevos
    d = d.assign(reciente=d["fecha_alta"].isin(recientes_set))
    act = d["nombre_act"].fillna("").map(sin_acentos)

    def especie(a):
        return next((esp for esp, kws in INDICADORAS_ACT.items()
                     if any(k in a for k in kws)), None)
    d = d.assign(especie=[especie(a) for a in act])

    filas = []
    for calle, g in d.groupby("calle"):
        recientes = g[g["reciente"]]
        ind = recientes[recientes["especie"].notna()]
        especies = sorted(ind["especie"].dropna().unique())
        filas.append({
            "nombre": calle,
            "altas": int(len(recientes)),
            "bajas": 0,                        # un corte no observa cierres
            "indicadoras": int(len(ind)),
            "especies": ", ".join(especies[:4]) if especies else "—",
        })
    ruta = os.path.join(salida_dir, f"sismografo_{sufijo}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({"calles": filas, "fuente": "fecha_alta DENUE (1 corte)"},
                  f, ensure_ascii=False)
    print(f"✓ {ruta} ({len(filas)} calles · {int(d['reciente'].sum())} "
          f"altas recientes · especies indicadoras detectadas)")


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
                # el ZIP del DENUE trae varios CSV (diccionario, metadatos y
                # el dataset): elige el más grande = el conjunto de datos
                csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
                nombre = max(csvs, key=lambda n: z.getinfo(n).file_size)
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
    # nombre de calle = tipo + nombre de vialidad (Avenida X ≠ Calle X),
    # evitando duplicar el tipo cuando nom_vial ya lo incluye
    def _s(x):
        return "" if x is None or (isinstance(x, float) and pd.isna(x)) \
            else str(x).strip()

    nomv = [_s(x) for x in d[col("nom_vial", "nombre_vialidad")]]
    try:
        tipo_v = [_s(x) for x in d[col("tipo_vial")]]
        calle = [(n if (not t or n.upper().startswith(t.upper() + " "))
                  else f"{t} {n}") for t, n in zip(tipo_v, nomv)]
    except KeyError:
        calle = nomv
    d["calle"] = pd.Series(calle, index=d.index).str.title().str.strip()
    d["lat"] = pd.to_numeric(d[col("latitud", "lat")], errors="coerce")
    d["lng"] = pd.to_numeric(d[col("longitud", "lng", "lon")], errors="coerce")
    d["nombre"] = d[col("nom_estab", "nombre")].astype(str).str.title()
    try:                              # se conserva para el sismógrafo
        d["fecha_alta"] = d[col("fecha_alta")].astype(str)
        d["nombre_act"] = d[col("nombre_act", "nombre_actividad")].astype(str)
    except KeyError:
        pass
    d = d.dropna(subset=["lat", "lng"])
    d = d[d["calle"].str.len() > 2]

    # ── establecimientos ──────────────────────────────────────────────────────
    os.makedirs(salida_dir, exist_ok=True)
    # año de alta (para el sismógrafo y la validación de contagio espacial)
    if "fecha_alta" in d.columns:
        d["anio"] = pd.to_numeric(d["fecha_alta"].str[:4], errors="coerce")
    cols_e = ["nombre", "sector", "calle", "lat", "lng", "empleo"] \
        + (["anio"] if "anio" in d.columns else [])
    ruta_e = os.path.join(salida_dir, f"establecimientos_{sufijo}.csv.gz")
    with gzip.open(ruta_e, "wt", encoding="utf-8") as f:
        d[cols_e].to_csv(f, index=False)
    print(f"✓ {ruta_e} ({len(d):,} filas)")

    # ── calles: polilínea por nombre vial ordenando los puntos sobre su eje ──
    # En ciudades grandes un mismo nombre vial se repite en colonias lejanas;
    # para no trazar líneas que cruzan la ciudad, nos quedamos con el SEGMENTO
    # MÁS DENSO de cada calle (bloque 3×3 de la rejilla ~500 m con más puntos).
    def segmento_denso(pts: np.ndarray) -> np.ndarray:
        gx = np.round(pts[:, 0] / 0.005).astype(int)
        gy = np.round(pts[:, 1] / 0.005).astype(int)
        celdas, cuenta = np.unique(np.stack([gx, gy], 1), axis=0,
                                   return_counts=True)
        cx, cy = celdas[cuenta.argmax()]
        m = (np.abs(gx - cx) <= 1) & (np.abs(gy - cy) <= 1)
        return pts[m]

    calles = []
    for nombre, g in d.groupby("calle"):
        if len(g) < 4:                    # muy pocos puntos para trazar eje
            continue
        pts = segmento_denso(g[["lng", "lat"]].to_numpy())
        if len(pts) < 4:
            continue
        centro = pts.mean(axis=0)
        u, s, vt = np.linalg.svd(pts - centro)   # eje principal (PCA)
        proy = (pts - centro) @ vt[0]
        orden = np.argsort(proy)
        # muestrear ~12 vértices a lo largo del eje para una polilínea limpia
        idx = np.unique(np.linspace(0, len(orden) - 1, 12).astype(int))
        camino = [[round(float(pts[orden[i], 0]), 5),
                   round(float(pts[orden[i], 1]), 5)] for i in idx]
        calles.append({"nombre": nombre, "camino": camino})
    estado_nom = str(d[col("entidad", "nom_ent")].iloc[0]) \
        if ("entidad" in cols or "nom_ent" in cols) else ""
    ruta_c = os.path.join(salida_dir, f"calles_{sufijo}.json")
    with open(ruta_c, "w", encoding="utf-8") as f:
        json.dump({"municipio": municipio, "estado": estado_nom,
                   "calles": calles}, f, ensure_ascii=False)
    print(f"✓ {ruta_c} ({len(calles)} calles)")

    # 🌡 sismógrafo real desde fecha_alta (un solo corte del DENUE)
    sismografo_altas(d, salida_dir, sufijo)

    print("\nListo: reinicia la app (streamlit run app.py) y la escala "
          "'🛣 Calle · establecimiento' usará los datos reales del DENUE.")


# Palabras clave de ESPECIES INDICADORAS de gentrificación: su aparición
# entre dos cortes del DENUE anticipa la plusvalía 2-3 años.
INDICADORAS = {
    "Café de especialidad": ["CAFE", "COFFEE", "TOSTADOR", "ESPRESSO"],
    "Coworking": ["COWORK", "OFICINAS COMPARTIDAS", "WEWORK"],
    "Galería": ["GALERIA", "ARTE CONTEMPOR"],
    "Barbería premium": ["BARBER", "BARBERIA"],
    "Estudio de yoga": ["YOGA", "PILATES"],
    "Panadería artesanal": ["ARTESANAL", "SOURDOUGH", "MASA MADRE"],
    "Veterinaria": ["VETERINAR", "PET SHOP", "ESTETICA CANINA"],
    "Gym boutique": ["CROSSFIT", "BOX FIT", "CYCLING", "BARRE"],
}


def sismografo(df_nuevo: pd.DataFrame, df_viejo: pd.DataFrame,
               salida_dir: str, sufijo: str) -> None:
    """
    🌡 SISMÓGRAFO DE GENTRIFICACIÓN: compara dos cortes reales del DENUE y
    detecta por calle las altas, bajas y especies indicadoras. Escribe
    data/sismografo_<sufijo>.json (la pestaña 🌡 lo detecta sola).
    """
    def llaves(d):
        return d.assign(llave=d["nombre"].map(sin_acentos) + "|"
                        + d["calle"].map(sin_acentos))

    nuevo, viejo = llaves(df_nuevo), llaves(df_viejo)
    setv = set(viejo["llave"])
    setn = set(nuevo["llave"])
    altas_df = nuevo[~nuevo["llave"].isin(setv)]
    bajas_df = viejo[~viejo["llave"].isin(setn)]

    def especies_de(nombre_estab):
        n = sin_acentos(nombre_estab)
        return [esp for esp, kws in INDICADORAS.items()
                if any(k in n for k in kws)]

    filas = []
    for calle, g in altas_df.groupby("calle"):
        esp = sorted({e for n in g["nombre"] for e in especies_de(n)})
        filas.append({"nombre": calle, "altas": int(len(g)),
                      "bajas": int((bajas_df["calle"] == calle).sum()),
                      "indicadoras": int(sum(bool(especies_de(n))
                                             for n in g["nombre"])),
                      "especies": ", ".join(esp[:3]) if esp else "—"})
    ruta = os.path.join(salida_dir, f"sismografo_{sufijo}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({"calles": filas}, f, ensure_ascii=False)
    print(f"✓ {ruta} ({len(filas)} calles con actividad)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingesta DENUE → Morfogénesis")
    ap.add_argument("--estado", default="09",
                    help="clave INEGI de entidad (09 = CDMX)")
    ap.add_argument("--municipio", default="Azcapotzalco")
    ap.add_argument("--csv", default=None,
                    help="ruta a un CSV DENUE ya descargado (omite descarga)")
    ap.add_argument("--csv-anterior", default=None,
                    help="CSV DENUE de un corte anterior → activa el "
                         "sismógrafo de gentrificación (altas/bajas)")
    ap.add_argument("--salida", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
    args = ap.parse_args()

    df = pd.read_csv(args.csv, encoding="latin-1", low_memory=False) \
        if args.csv else descargar_denue(args.estado)
    sufijo = sin_acentos(args.municipio).lower().replace(" ", "_")
    procesar(df, args.municipio, args.salida, sufijo)

    if args.csv_anterior:
        viejo = pd.read_csv(args.csv_anterior, encoding="latin-1",
                            low_memory=False)
        # reusar el mismo pipeline de columnas del corte nuevo
        ruta_e = os.path.join(args.salida,
                              f"establecimientos_{sufijo}.csv.gz")
        nuevo_proc = pd.read_csv(ruta_e)
        procesar(viejo, args.municipio, args.salida, sufijo + "_anterior")
        viejo_proc = pd.read_csv(os.path.join(
            args.salida, f"establecimientos_{sufijo}_anterior.csv.gz"))
        sismografo(nuevo_proc, viejo_proc, args.salida, sufijo)


if __name__ == "__main__":
    main()
