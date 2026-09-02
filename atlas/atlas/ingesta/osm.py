"""
Ingesta OpenStreetMap vía Overpass: parques, plazas, transporte y amenidades.

SE CORRE EN TU MÁQUINA. Overpass rechaza las IP de nube (comprobado: la
petición desde el contenedor recibe un reset de conexión), igual que INEGI y
que el portal de datos de la CDMX. Mismo patrón que `tools/riesgos_local.py`.

    python -m atlas.pipelines.fase0 --osm

Guarda el resultado en el lago; las fases siguientes leen de ahí y ya no
necesitan red. Overpass es infraestructura de voluntarios: este módulo pide
una sola vez por categoría, con pausa entre peticiones y reintento con espera
creciente, y cachea en disco para no repetir la consulta.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

from ..config import Config, cargar

# Cada categoría es una consulta Overpass QL. `{caja}` se sustituye por la
# extensión de la CDMX. Se piden nodos, vías y relaciones: un parque grande es
# una relación, no un nodo, y omitirlas dejaría fuera Chapultepec.
CATEGORIAS: dict[str, str] = {
    "parques": '["leisure"~"^(park|garden|nature_reserve)$"]',
    "plazas": '["highway"="pedestrian"]["area"="yes"];way["place"="square"]',
    "metro": '["railway"="station"]["station"="subway"]',
    "metrobus": '["amenity"="bus_station"];node["highway"="bus_stop"]["network"~"Metrob",i]',
    "cablebus": '["aerialway"~"^(station|gondola)$"]',
    "hospitales": '["amenity"~"^(hospital|clinic)$"]',
    "escuelas": '["amenity"~"^(school|college|university|kindergarten)$"]',
    "mercados": '["amenity"="marketplace"];way["shop"="supermarket"]',
}


def _consulta(filtro: str, cfg: Config) -> str:
    c = cfg.caja
    caja = f"{c.lat_min},{c.lng_min},{c.lat_max},{c.lng_max}"
    partes = []
    for f in filtro.split(";"):
        f = f.strip()
        if not f:
            continue
        if f.startswith(("node", "way", "rel")):
            partes.append(f"{f}({caja});")
        else:
            for tipo in ("node", "way", "relation"):
                partes.append(f"{tipo}{f}({caja});")
    cuerpo = "".join(partes)
    # `out center` devuelve un punto representativo de vías y relaciones, que
    # es justo lo que se necesita para medir distancias.
    return f"[out:json][timeout:{cfg['ingesta']['overpass_timeout']}];({cuerpo});out center;"


def _pedir(consulta: str, cfg: Config) -> dict:
    url = cfg["ingesta"]["overpass_url"]
    intentos = int(cfg["ingesta"]["overpass_reintentos"])
    ultimo: Exception | None = None
    for i in range(intentos):
        try:
            r = requests.post(
                url,
                data={"data": consulta},
                timeout=cfg["ingesta"]["overpass_timeout"] + 30,
                headers={"User-Agent": "BrickBit-Atlas/0.1 (contacto: jose.delgado@brickbit.co)"},
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:  # red, 429, 504…
            ultimo = e
            time.sleep(2 ** i * 5)   # espera creciente: 5s, 10s, 20s
    raise RuntimeError(
        f"Overpass no respondió tras {intentos} intentos ({ultimo}). "
        "Si estás en un servidor o contenedor, Overpass bloquea IP de nube: "
        "corre esta ingesta desde tu máquina."
    ) from ultimo


def _a_puntos(datos: dict, categoria: str, cfg: Config) -> gpd.GeoDataFrame:
    filas, geoms = [], []
    caja = cfg.caja
    for el in datos.get("elements", []):
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if lat is None or lon is None or not caja.contiene(lat, lon):
            continue
        etiquetas = el.get("tags", {}) or {}
        filas.append(
            {
                "osm_id": f"{el.get('type','?')}/{el.get('id','?')}",
                "categoria": categoria,
                "nombre": etiquetas.get("name", ""),
            }
        )
        geoms.append(Point(float(lon), float(lat)))
    if not filas:
        return gpd.GeoDataFrame(
            {"osm_id": [], "categoria": [], "nombre": []}, geometry=[], crs=cfg.crs_geografico
        )
    return gpd.GeoDataFrame(filas, geometry=geoms, crs=cfg.crs_geografico)


def descargar(
    categorias: list[str] | None = None,
    cfg: Config | None = None,
    usar_cache: bool = True,
) -> gpd.GeoDataFrame:
    """Descarga (o lee de caché) las categorías pedidas y las devuelve unidas."""
    cfg = cfg or cargar()
    cats = categorias or list(CATEGORIAS)
    cache = cfg.lago / "cache_osm"
    cache.mkdir(parents=True, exist_ok=True)

    trozos = []
    for i, cat in enumerate(cats):
        if cat not in CATEGORIAS:
            raise KeyError(f"Categoría desconocida: {cat}. Válidas: {list(CATEGORIAS)}")
        crudo = cache / f"{cat}.json"
        if usar_cache and crudo.exists():
            datos = json.loads(crudo.read_text(encoding="utf-8"))
        else:
            if i:
                time.sleep(2)   # cortesía con un servidor de voluntarios
            datos = _pedir(_consulta(CATEGORIAS[cat], cfg), cfg)
            crudo.write_text(json.dumps(datos), encoding="utf-8")
        trozos.append(_a_puntos(datos, cat, cfg))

    if not trozos:
        return gpd.GeoDataFrame(
            {"osm_id": [], "categoria": [], "nombre": []}, geometry=[], crs=cfg.crs_geografico
        )
    return gpd.GeoDataFrame(
        pd.concat(trozos, ignore_index=True), crs=cfg.crs_geografico
    )
