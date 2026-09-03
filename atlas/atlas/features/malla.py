"""
Malla H3 de la Ciudad de México: el sustrato de la "tela".

Toda superficie continua del Atlas —valor por m², apreciación, incertidumbre—
se calcula sobre esta malla. H3 en vez de una rejilla cuadrada por dos razones
prácticas: las celdas hexagonales tienen los seis vecinos a la misma distancia
(una cuadrada tiene cuatro a un paso y cuatro a 1.41), lo que hace que los
rezagos espaciales y la difusión no tengan sesgo direccional; y el índice es
jerárquico, así que la misma malla sirve para la tela fina (res 9) y para los
bloques de validación espacial (res 6) sin recalcular nada.

Resolución 9 ≈ 174 m de arista, ~0.10 km² por celda. La CDMX entera son unas
16 mil celdas: suficiente detalle para una colonia y lo bastante ligero para
que el mapa no se arrastre.
"""
from __future__ import annotations

import geopandas as gpd
import h3
import pandas as pd
from shapely.geometry import Polygon

from ..config import Config, cargar


def celdas_de_poligono(poly: Polygon, resolucion: int) -> list[str]:
    """Celdas H3 que cubren un polígono (API de h3 v4)."""
    gj = {"type": "Polygon", "coordinates": [list(poly.exterior.coords)]}
    forma = h3.geo_to_cells(gj, resolucion)
    return list(forma)


def malla(
    resolucion: int | None = None,
    recorte: gpd.GeoDataFrame | None = None,
    cfg: Config | None = None,
) -> gpd.GeoDataFrame:
    """
    Malla H3 que cubre la CDMX.

    `recorte` acota la malla a una geometría real (por defecto, los polígonos
    de código postal). Sin recorte, la caja rectangular mete celdas en el
    Estado de México y en zonas sin ciudad, y la tela acabaría dibujando
    superficie donde no hay nada que estimar.
    """
    cfg = cfg or cargar()
    res = int(resolucion if resolucion is not None else cfg["modelado"]["h3"]["resolucion_malla"])

    if recorte is None:
        from ..ingesta import base_geo

        try:
            recorte = base_geo.cargar_cp(cfg)
        except FileNotFoundError:
            recorte = None

    if recorte is not None and len(recorte):
        r = recorte.to_crs(cfg.crs_geografico)
        # union_all da un multipolígono; se recorren sus partes porque
        # h3.geo_to_cells trabaja sobre polígonos simples.
        unido = r.geometry.union_all()
        partes = getattr(unido, "geoms", [unido])
        celdas: set[str] = set()
        for p in partes:
            if p.is_empty:
                continue
            celdas |= set(celdas_de_poligono(p, res))
    else:
        c = cfg.caja
        caja = Polygon(
            [
                (c.lng_min, c.lat_min), (c.lng_max, c.lat_min),
                (c.lng_max, c.lat_max), (c.lng_min, c.lat_max),
                (c.lng_min, c.lat_min),
            ]
        )
        celdas = set(celdas_de_poligono(caja, res))

    if not celdas:
        return gpd.GeoDataFrame(
            {"h3": [], "lat": [], "lng": []}, geometry=[], crs=cfg.crs_geografico
        )

    orden = sorted(celdas)   # orden estable: el pipeline es determinista
    centros = [h3.cell_to_latlng(c) for c in orden]
    lat = [p[0] for p in centros]
    lng = [p[1] for p in centros]
    geom = [Polygon([(x, y) for y, x in h3.cell_to_boundary(c)]) for c in orden]
    g = gpd.GeoDataFrame(
        {"h3": orden, "lat": lat, "lng": lng}, geometry=geom, crs=cfg.crs_geografico
    )
    return g


def centros(g: gpd.GeoDataFrame, cfg: Config | None = None) -> gpd.GeoDataFrame:
    """
    Los centroides de la malla, como puntos.

    Las distancias a amenidades se miden desde el centro de la celda, no desde
    su borde: es la convención que hace comparables todas las celdas entre sí.
    """
    cfg = cfg or cargar()
    return gpd.GeoDataFrame(
        g.drop(columns="geometry"),
        geometry=gpd.points_from_xy(g["lng"], g["lat"], crs=cfg.crs_geografico),
        crs=cfg.crs_geografico,
    )


def bloques(g: gpd.GeoDataFrame, cfg: Config | None = None) -> pd.Series:
    """
    Bloque espacial de cada celda, para la validación con bloqueo (§10).

    Es la celda padre en una resolución más gruesa. Como H3 es jerárquico, dos
    celdas vecinas casi siempre comparten padre y por tanto caen en el MISMO
    pliegue: eso es justo lo que impide que un comparable vecino esté a la vez
    en entrenamiento y en prueba, que es la fuga que infla el desempeño.
    """
    cfg = cfg or cargar()
    res_b = int(cfg["modelado"]["h3"]["resolucion_bloques"])
    return pd.Series(
        [h3.cell_to_parent(c, res_b) for c in g["h3"]], index=g.index, dtype="string"
    )
