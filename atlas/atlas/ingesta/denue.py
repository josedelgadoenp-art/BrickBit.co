"""
Ingesta DENUE (INEGI) — densidad comercial y de servicios georreferenciada.

NO descarga nada. El repositorio ya trae los establecimientos ingeridos por
`scripts/ingerir_denue.py`, que se corre en local porque INEGI bloquea las IP
de nube (documentado en CLAUDE.md). Este módulo los lee y los normaliza.

CUIDADO CON LOS HOMÓNIMOS — y por qué esto se verifica y no se supone.
`data/` guarda 171 municipios de todo el país con el nombre en el archivo, y
varios se llaman igual que una alcaldía de la CDMX:

    establecimientos_benito_juarez.csv.gz       → Benito Juárez, QUINTANA ROO
    establecimientos_benito_juarez_cdmx.csv.gz  → Benito Juárez, CDMX
    establecimientos_juarez.csv.gz              → Juárez, Chihuahua/NL

Emparejar por nombre metía Cancún en el Atlas de la CDMX, y como `glob` no
garantiza orden, el resultado además cambiaba entre corridas. La selección es
ahora GEOGRÁFICA: se acepta un archivo sólo si sus puntos caen de verdad
dentro de la caja de la CDMX. El nombre sirve para buscar candidatos; los
datos deciden. Medido así, entran 9 alcaldías con 351,631 establecimientos.
"""
from __future__ import annotations

import glob
import gzip
import json
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
import pandas as pd

from ..config import Config, cargar
from ..geo import puntos

# Fracción mínima de puntos dentro de la caja para aceptar un archivo como CDMX.
# Un municipio ajeno da ~0%; uno de la CDMX da ~100%. El umbral es holgado a
# propósito: no hay zona gris real, y si la hubiera queremos enterarnos.
UMBRAL_DENTRO = 0.80
MUESTRA = 3000          # filas que se leen para decidir; suficiente y barato
CACHE = "_denue_cdmx.json"

# Familias DENUE.
#
# OJO CON EL VOCABULARIO. El DENUE crudo del INEGI trae ~20 sectores SCIAN,
# pero los CSV que `scripts/ingerir_denue.py` dejó en el repo vienen ya
# agregados a CUATRO: Servicios, Comercio, Alimentos e Industria. Verificado
# contando los valores distintos de la columna `sector`.
#
# La primera versión de este módulo definía familias de salud, educación y
# ocio que ese vocabulario no puede producir: generaban columnas enteras de
# NaN y una falsa sensación de cobertura. Las familias son ahora exactamente
# las que la fuente sabe distinguir.
#
# Salud y educación NO se pierden: llegan de OSM (categorías `hospitales` y
# `escuelas`), que es la fuente que sí las tiene georreferenciadas una por una.
FAMILIAS = {
    "abasto": ("comercio",),        # tiendas, abarrotes, supermercados
    "alimentos": ("alimentos",),    # restaurantes, cafés, fondas
    "servicios": ("servicios",),    # oficinas, profesionales, financieros
    "industria": ("industria",),    # manufactura y construcción
}

def _familia(sector: str) -> str:
    s = str(sector or "").lower()
    for fam, claves in FAMILIAS.items():
        if any(k in s for k in claves):
            return fam
    return "otro"


def _fraccion_en_cdmx(ruta: Path, cfg: Config) -> float:
    """Lee una muestra y devuelve qué proporción cae dentro de la CDMX."""
    caja = cfg.caja
    try:
        with gzip.open(ruta, "rt", encoding="utf-8", errors="ignore") as fh:
            d = pd.read_csv(fh, usecols=["lat", "lng"], nrows=MUESTRA)
    except (ValueError, KeyError, OSError):
        return 0.0
    if d.empty:
        return 0.0
    la = pd.to_numeric(d["lat"], errors="coerce")
    lo = pd.to_numeric(d["lng"], errors="coerce")
    dentro = la.between(caja.lat_min, caja.lat_max) & lo.between(caja.lng_min, caja.lng_max)
    return float(dentro.mean())


@lru_cache(maxsize=1)
def _verificados(raiz: str, lago: str) -> dict[str, str]:
    """
    slug de alcaldía → ruta del archivo VERIFICADO como CDMX.
    El resultado se cachea en el lago: la verificación lee ~171 archivos y no
    tiene por qué repetirse en cada corrida.
    """
    cfg = cargar()
    cache = Path(lago) / CACHE
    if cache.exists():
        try:
            guardado = json.loads(cache.read_text(encoding="utf-8"))
            if all(Path(v).exists() for v in guardado.values()):
                return guardado
        except json.JSONDecodeError:
            pass

    elegidos: dict[str, str] = {}
    for a in cfg.alcaldias:
        slug = a["slug"]
        # Candidatos: el slug exacto y sus variantes con sufijo (…_cdmx).
        patrones = [
            f"{raiz}/establecimientos_{slug}.csv.gz",
            f"{raiz}/establecimientos_{slug}_*.csv.gz",
        ]
        candidatos = sorted({p for pat in patrones for p in glob.glob(pat)})
        mejor, mejor_frac = None, 0.0
        for p in candidatos:
            f = _fraccion_en_cdmx(Path(p), cfg)
            # Ante empate, gana el más específico (el que trae sufijo _cdmx).
            if f > mejor_frac or (f == mejor_frac and mejor and len(p) > len(mejor)):
                mejor, mejor_frac = p, f
        if mejor and mejor_frac >= UMBRAL_DENTRO:
            elegidos[slug] = mejor

    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(elegidos, ensure_ascii=False, indent=1), encoding="utf-8")
    return elegidos


def archivos_disponibles(cfg: Config | None = None) -> dict[str, Path]:
    """slug → archivo, sólo para alcaldías con datos verificados de la CDMX."""
    cfg = cfg or cargar()
    d = _verificados(str(cfg.ruta("raiz_datos_repo")), str(cfg.lago))
    return {k: Path(v) for k, v in sorted(d.items())}


def faltantes(cfg: Config | None = None) -> list[str]:
    cfg = cfg or cargar()
    hay = archivos_disponibles(cfg)
    return [a["slug"] for a in cfg.alcaldias if a["slug"] not in hay]


def cargar_denue(cfg: Config | None = None) -> gpd.GeoDataFrame:
    """
    Establecimientos de la CDMX con columnas:
    nombre, sector, familia, empleo, anio, alcaldia, geometry.
    """
    cfg = cfg or cargar()
    archivos = archivos_disponibles(cfg)
    if not archivos:
        raise FileNotFoundError(
            "No hay establecimientos verificados de la CDMX en data/. Córrelos con "
            "`python scripts/ingerir_denue.py` (en tu máquina: INEGI bloquea IP de nube)."
        )

    trozos = []
    for slug, ruta in archivos.items():   # ya viene ordenado: determinista
        with gzip.open(ruta, "rt", encoding="utf-8", errors="ignore") as fh:
            d = pd.read_csv(fh)
        d["alcaldia"] = slug
        trozos.append(d)

    df = pd.concat(trozos, ignore_index=True)
    df["familia"] = df.get("sector", pd.Series(dtype=str)).map(_familia)
    df["empleo"] = pd.to_numeric(df.get("empleo"), errors="coerce").fillna(1.0)
    gdf = puntos(df, cfg=cfg)
    return gdf[["nombre", "sector", "familia", "empleo", "anio", "alcaldia", "geometry"]]
