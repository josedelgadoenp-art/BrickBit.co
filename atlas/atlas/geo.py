"""
Utilidades geográficas del Atlas.

La regla que este módulo hace cumplir: **nunca se calcula una distancia, un
área ni un buffer en grados**. En la latitud de la CDMX un grado de longitud
mide ~105 km y uno de latitud ~111 km; usar grados como si fueran metros mete
un error del orden del 6% en distancias este-oeste, y mucho mayor en áreas.
Y es un error silencioso: no revienta, sólo devuelve números equivocados.

Por eso `a_metrico()` es el único camino para pasar a coordenadas proyectadas,
y las funciones de distancia exigen que el GeoDataFrame ya venga proyectado.

SOBRE EL RENDIMIENTO. La primera versión de este módulo recorría los pares
origen×destino en Python. Con 16 mil celdas de malla y 351 mil establecimientos
DENUE eso son miles de millones de comparaciones: el pipeline no terminaba.
Ahora todo pasa por un árbol KD de scipy, que resuelve las mismas consultas en
C y en segundos. Es la misma matemática, no una aproximación.
"""
from __future__ import annotations

from typing import Iterable

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import Point

from .config import Config, cargar

RADIO_TIERRA_M = 6_371_008.8  # radio medio de la Tierra (IUGG)


# ---------------------------------------------------------------- proyección
def a_metrico(gdf: gpd.GeoDataFrame, cfg: Config | None = None) -> gpd.GeoDataFrame:
    """Reproyecta a EPSG:6372 (metros). Es el paso obligatorio antes de medir."""
    cfg = cfg or cargar()
    if gdf.crs is None:
        raise ValueError(
            "El GeoDataFrame no declara CRS. Reproyectar sin saber de dónde se "
            "parte produce coordenadas basura; declara el CRS de origen."
        )
    return gdf.to_crs(cfg.crs_metrico)


def a_geografico(gdf: gpd.GeoDataFrame, cfg: Config | None = None) -> gpd.GeoDataFrame:
    """Reproyecta a EPSG:4326, que es lo único que entienden los mapas web."""
    cfg = cfg or cargar()
    if gdf.crs is None:
        raise ValueError("El GeoDataFrame no declara CRS.")
    return gdf.to_crs(cfg.crs_geografico)


def es_metrico(gdf: gpd.GeoDataFrame, cfg: Config | None = None) -> bool:
    cfg = cfg or cargar()
    return gdf.crs is not None and gdf.crs.equals(gpd.GeoSeries(crs=cfg.crs_metrico).crs)


def exigir_metrico(gdf: gpd.GeoDataFrame, cfg: Config | None = None) -> None:
    """Guardia para funciones que miden. Falla ruidosamente, que es el punto."""
    cfg = cfg or cargar()
    if not es_metrico(gdf, cfg):
        raise ValueError(
            f"Se esperaba {cfg.crs_metrico} y llegó {gdf.crs}. "
            "Medir en grados da resultados incorrectos sin avisar: usa a_metrico()."
        )


# ------------------------------------------------------------------ armado
def puntos(
    df: pd.DataFrame,
    lat: str = "lat",
    lng: str = "lng",
    cfg: Config | None = None,
) -> gpd.GeoDataFrame:
    """
    DataFrame con lat/lng → GeoDataFrame en 4326, descartando lo que caiga
    fuera de la caja de la CDMX o traiga coordenadas ilegibles.
    """
    cfg = cfg or cargar()
    caja = cfg.caja
    la = pd.to_numeric(df[lat], errors="coerce")
    lo = pd.to_numeric(df[lng], errors="coerce")
    dentro = (
        la.between(caja.lat_min, caja.lat_max)
        & lo.between(caja.lng_min, caja.lng_max)
    )
    d = df.loc[dentro].copy()
    geom = gpd.points_from_xy(lo.loc[dentro], la.loc[dentro], crs=cfg.crs_geografico)
    return gpd.GeoDataFrame(d, geometry=geom, crs=cfg.crs_geografico)


def _xy(gdf: gpd.GeoDataFrame, cfg: Config) -> np.ndarray:
    """Coordenadas proyectadas como matriz (n, 2). Usa el centroide si son polígonos."""
    m = a_metrico(gdf, cfg)
    g = m.geometry
    if not (g.geom_type == "Point").all():
        g = g.representative_point()
    return np.column_stack([g.x.to_numpy(), g.y.to_numpy()])


# ---------------------------------------------------------------- distancias
def haversine_m(lat1, lng1, lat2, lng2) -> np.ndarray:
    """
    Distancia sobre la esfera, en metros. Vectorizada.
    Se usa sólo para comprobaciones rápidas y para validar la proyección;
    el trabajo serio va proyectado, que además es más rápido.
    """
    la1, lo1, la2, lo2 = map(np.radians, (lat1, lng1, lat2, lng2))
    dla, dlo = la2 - la1, lo2 - lo1
    h = np.sin(dla / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin(dlo / 2) ** 2
    return 2 * RADIO_TIERRA_M * np.arcsin(np.sqrt(np.clip(h, 0, 1)))


def distancia_al_mas_cercano(
    origen: gpd.GeoDataFrame,
    destino: gpd.GeoDataFrame,
    cfg: Config | None = None,
) -> np.ndarray:
    """
    Metros al elemento más cercano de `destino`, para cada fila de `origen`.
    Si `destino` viene vacío devuelve NaN, no cero: "no hay ninguno" y "hay uno
    pegado" son cosas distintas y confundirlas envenena cualquier modelo.
    """
    cfg = cfg or cargar()
    if len(destino) == 0 or len(origen) == 0:
        return np.full(len(origen), np.nan)
    o = _xy(origen, cfg)
    d = _xy(destino, cfg)
    dist, _ = cKDTree(d).query(o, k=1, workers=-1)
    return np.asarray(dist, dtype=float)


def conteo_en_radios(
    origen: gpd.GeoDataFrame,
    destino: gpd.GeoDataFrame,
    radios_m: Iterable[float],
    cfg: Config | None = None,
) -> pd.DataFrame:
    """
    Cuántos elementos de `destino` hay dentro de cada radio, por fila de origen.

    Se resuelve con consultas por bolas sobre un árbol KD, en bloques, que es
    lo que permite contar sobre cientos de miles de puntos sin materializar
    todos los pares ni quedarse sin memoria.
    """
    cfg = cfg or cargar()
    radios = sorted(float(r) for r in radios_m)
    salida = pd.DataFrame(index=origen.index)
    if len(destino) == 0 or len(origen) == 0:
        for r in radios:
            salida[f"n_{int(r)}m"] = 0
        return salida

    ao = cKDTree(_xy(origen, cfg))
    ad = cKDTree(_xy(destino, cfg))
    for r in radios:
        # count_neighbors agrega sobre todo el árbol; para el conteo POR FILA
        # hace falta la consulta por bolas. Va en bloques para acotar memoria.
        cuenta = np.empty(len(origen), dtype=np.int32)
        paso = 4000
        for i in range(0, len(origen), paso):
            vecinos = ad.query_ball_point(ao.data[i:i + paso], r=r, workers=-1)
            cuenta[i:i + paso] = [len(v) for v in vecinos]
        salida[f"n_{int(r)}m"] = cuenta
    return salida


def accesibilidad_gravitacional(
    origen: gpd.GeoDataFrame,
    destino: gpd.GeoDataFrame,
    atractivo: np.ndarray | None = None,
    beta: float = 1.5,
    corte_m: float = 5000.0,
    piso_m: float = 50.0,
    cfg: Config | None = None,
) -> np.ndarray:
    """
    A_i = Σ_j atractivo_j / d_ij^beta   (§6 del prompt maestro)

    `piso_m` evita que un destino encima del origen mande el índice a infinito.
    `corte_m` acota la suma: más allá el término es despreciable y el coste
    computacional no lo es.

    Se resuelve con `sparse_distance_matrix`, que devuelve sólo los pares
    dentro del corte. Con 16k orígenes y 351k destinos los pares completos
    serían 5.6 mil millones; dentro de 5 km son unos pocos millones.
    """
    cfg = cfg or cargar()
    if len(destino) == 0 or len(origen) == 0:
        return np.zeros(len(origen))
    o = _xy(origen, cfg)
    d = _xy(destino, cfg)
    w = np.ones(len(d)) if atractivo is None else np.asarray(atractivo, dtype=float)
    w = np.nan_to_num(w, nan=1.0)

    ao, ad = cKDTree(o), cKDTree(d)
    acc = np.zeros(len(o))
    # Por bloques de origen: la matriz dispersa completa puede ser grande.
    paso = 4000
    for i in range(0, len(o), paso):
        sub = cKDTree(o[i:i + paso])
        m = sub.sparse_distance_matrix(ad, max_distance=corte_m, output_type="coo_matrix")
        if m.nnz == 0:
            continue
        dist = np.maximum(m.data, piso_m)
        aporte = w[m.col] / dist ** beta
        acc[i:i + paso] = np.bincount(m.row, weights=aporte, minlength=min(paso, len(o) - i))
    return acc


# ------------------------------------------------------------------- H3
def a_h3(gdf: gpd.GeoDataFrame, resolucion: int) -> pd.Series:
    """Índice H3 por punto. La malla de la 'tela' y de los bloques de validación."""
    import h3

    g = a_geografico(gdf)
    pts = g.geometry.representative_point() if not (g.geometry.geom_type == "Point").all() else g.geometry
    return pd.Series(
        [h3.latlng_to_cell(p.y, p.x, resolucion) for p in pts],
        index=gdf.index,
        dtype="string",
    )


def centro_h3(celda: str) -> Point:
    import h3

    lat, lng = h3.cell_to_latlng(celda)
    return Point(lng, lat)
