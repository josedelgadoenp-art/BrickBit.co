"""
Geografía base: códigos postales de la CDMX y red vial.

Ambos salen de archivos que ya viven en el repo, así que esta ingesta corre
sin red. Los polígonos de CP son la unidad territorial más fina disponible sin
depender del Marco Geoestadístico del INEGI (que bloquea IP de nube); cuando
se ingieran los AGEB, se suman aquí como capa adicional, no en sustitución.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, shape

from ..config import Config, cargar


def cargar_cp(cfg: Config | None = None) -> gpd.GeoDataFrame:
    """1,182 polígonos de código postal de la CDMX."""
    cfg = cfg or cargar()
    ruta = cfg.ruta("cp_cdmx")
    if not ruta.exists():
        raise FileNotFoundError(f"Falta {ruta}")
    gj = json.loads(ruta.read_text(encoding="utf-8"))
    filas, geoms = [], []
    for f in gj.get("features", []):
        cp = str(f.get("properties", {}).get("cp", "")).strip()
        if not (cp.isdigit() and len(cp) == 5):
            continue
        try:
            g = shape(f["geometry"])
        except Exception:
            continue
        if g.is_empty:
            continue
        # Un polígono inválido revienta cualquier sjoin más adelante.
        if not g.is_valid:
            g = g.buffer(0)
        filas.append({"cp": cp})
        geoms.append(g)
    return gpd.GeoDataFrame(filas, geometry=geoms, crs=cfg.crs_geografico)


def cargar_calles(cfg: Config | None = None) -> gpd.GeoDataFrame:
    """
    Red vial de las alcaldías ingeridas, como líneas.

    Formato de origen (`data/calles_*.json`): {municipio, estado, calles:[{nombre, camino:[[lng,lat],...]}]}.
    Sirve para densidad de traza y, en la Fase 1, como base de las isócronas.
    """
    cfg = cfg or cargar()
    patron = str(cfg.ruta("raiz_datos_repo") / "calles_*.json")
    slugs = {a["slug"] for a in cfg.alcaldias}
    filas, geoms = [], []
    for p in sorted(glob.glob(patron)):
        nombre = Path(p).stem.replace("calles_", "")
        # `calles_benito_juarez_cdmx` y `calles_benito_juarez` son la misma
        # alcaldía capturada dos veces; ambas entran y se deduplican por geometría.
        if not any(nombre.startswith(s) for s in slugs):
            continue
        try:
            d = json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(d.get("estado", "")).lower() not in ("ciudad de mexico", "ciudad de méxico"):
            continue
        for c in d.get("calles", []):
            camino = c.get("camino") or []
            if len(camino) < 2:
                continue
            try:
                geoms.append(LineString([(float(x), float(y)) for x, y in camino]))
            except (TypeError, ValueError):
                continue
            filas.append({"nombre": c.get("nombre", ""), "alcaldia": nombre})
    if not filas:
        return gpd.GeoDataFrame(
            {"nombre": [], "alcaldia": []}, geometry=[], crs=cfg.crs_geografico
        )
    gdf = gpd.GeoDataFrame(filas, geometry=geoms, crs=cfg.crs_geografico)
    return gdf.drop_duplicates(subset=["nombre", "alcaldia"]).reset_index(drop=True)


def cobertura(cfg: Config | None = None) -> pd.DataFrame:
    """
    Qué hay y qué falta por alcaldía. Es el primer informe que se mira: dice
    dónde el Atlas puede hablar con datos y dónde tendría que callarse.
    """
    from . import denue

    cfg = cfg or cargar()
    hay_denue = denue.archivos_disponibles(cfg)
    calles = cargar_calles(cfg)
    con_calles = set(calles["alcaldia"].str.replace("_cdmx", "", regex=False)) if len(calles) else set()
    filas = []
    for a in cfg.alcaldias:
        filas.append(
            {
                "alcaldia": a["nombre"],
                "slug": a["slug"],
                "denue": a["slug"] in hay_denue,
                "calles": any(c.startswith(a["slug"]) for c in con_calles),
            }
        )
    return pd.DataFrame(filas)
