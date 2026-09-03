"""
Variables de amenidad y accesibilidad: los motores explícitos del valor.

Para cada punto —una celda de la malla o un inmueble— se construye:
  · distancia en metros a la amenidad más cercana de cada familia
  · cuántas hay dentro de 300 / 500 / 1000 m
  · índice de accesibilidad gravitacional  A_i = Σ_j atractivo_j / d_ij^β

Las tres dicen cosas distintas y por eso van las tres. La distancia al más
cercano capta el "tengo uno al lado"; el conteo capta la densidad (una calle
con veinte cafés no es una con uno); el índice gravitacional pondera por
tamaño y decae suave, que es como funciona de verdad la accesibilidad.

El atractivo de un establecimiento DENUE es su empleo: un hospital de 400
empleados no genera el mismo flujo que un consultorio de 2. Es el proxy que
hay y se declara como proxy.
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

from ..config import Config, cargar
from ..geo import accesibilidad_gravitacional, conteo_en_radios, distancia_al_mas_cercano

# Familias DENUE que se convierten en variables. Son las cuatro que la fuente
# del repo sabe distinguir (ver ingesta/denue.py). Se separan porque su efecto
# sobre el valor tiene signos distintos: abasto y alimentos suman, industria
# tiende a restar. Salud y educación llegan de OSM, no de aquí.
FAMILIAS_DENUE = ("abasto", "alimentos", "servicios", "industria")

# Categorías OSM, cuando la capa exista (se baja en local).
CATEGORIAS_OSM = ("parques", "plazas", "metro", "metrobus", "cablebus",
                  "hospitales", "escuelas", "mercados")


def _bloque(
    origen: gpd.GeoDataFrame,
    destino: gpd.GeoDataFrame,
    prefijo: str,
    radios: list[float],
    peso: np.ndarray | None,
    beta: float,
    cfg: Config,
) -> pd.DataFrame:
    """Distancia + conteos + accesibilidad para un conjunto de destinos."""
    out = pd.DataFrame(index=origen.index)
    if destino is None or len(destino) == 0:
        # Ausencia declarada: NaN en distancia (no hay ninguno) y 0 en conteo.
        out[f"dist_{prefijo}_m"] = np.nan
        for r in radios:
            out[f"n_{prefijo}_{int(r)}m"] = 0
        out[f"acc_{prefijo}"] = 0.0
        return out

    out[f"dist_{prefijo}_m"] = distancia_al_mas_cercano(origen, destino, cfg)
    conteos = conteo_en_radios(origen, destino, radios, cfg)
    for c in conteos.columns:
        out[f"n_{prefijo}_{c.split('_')[1]}"] = conteos[c].to_numpy()
    out[f"acc_{prefijo}"] = accesibilidad_gravitacional(
        origen, destino, atractivo=peso, beta=beta, cfg=cfg
    )
    return out


def desde_denue(
    origen: gpd.GeoDataFrame,
    denue: gpd.GeoDataFrame,
    cfg: Config | None = None,
    beta: float = 1.5,
) -> pd.DataFrame:
    """Un bloque de variables por familia DENUE, ponderando por empleo."""
    cfg = cfg or cargar()
    radios = [float(r) for r in cfg["ingesta"]["radios_conteo"]]
    partes = []
    for fam in FAMILIAS_DENUE:
        sub = denue.loc[denue["familia"] == fam]
        peso = sub["empleo"].to_numpy() if len(sub) else None
        partes.append(_bloque(origen, sub, fam, radios, peso, beta, cfg))
    # Densidad total: la suma de todo, útil como control agregado.
    partes.append(_bloque(origen, denue, "denue", radios,
                          denue["empleo"].to_numpy() if len(denue) else None, beta, cfg))
    return pd.concat(partes, axis=1)


def desde_osm(
    origen: gpd.GeoDataFrame,
    osm: gpd.GeoDataFrame | None,
    cfg: Config | None = None,
    beta: float = 1.5,
) -> pd.DataFrame:
    """
    Variables de parques, plazas y transporte.

    Si la capa no existe (OSM se baja en local), devuelve el bloque completo
    con ausencia declarada en vez de omitir las columnas: así la matriz de
    variables tiene siempre la misma forma y un modelo entrenado con OSM no
    revienta al encontrarse una matriz sin esas columnas.
    """
    cfg = cfg or cargar()
    radios = [float(r) for r in cfg["ingesta"]["radios_conteo"]]
    partes = []
    for cat in CATEGORIAS_OSM:
        sub = (
            osm.loc[osm["categoria"] == cat]
            if osm is not None and len(osm) and "categoria" in osm.columns
            else None
        )
        partes.append(_bloque(origen, sub, cat, radios, None, beta, cfg))
    # El transporte masivo pesa junto: al mercado le importa "tengo transporte",
    # no de qué modo es exactamente.
    if osm is not None and len(osm) and "categoria" in osm.columns:
        masivo = osm.loc[osm["categoria"].isin(["metro", "metrobus", "cablebus"])]
    else:
        masivo = None
    partes.append(_bloque(origen, masivo, "transporte", radios, None, beta, cfg))
    return pd.concat(partes, axis=1)


def resumen_cobertura(feats: pd.DataFrame) -> pd.DataFrame:
    """
    Qué variables quedaron vacías. Es lo que distingue "medí y da cero" de
    "no tengo con qué medir", y el documento exige no confundirlas.
    """
    filas = []
    for c in feats.columns:
        s = feats[c]
        filas.append(
            {
                "variable": c,
                "nulos_%": round(100 * s.isna().mean(), 1),
                "ceros_%": round(100 * (s == 0).mean(), 1) if s.dtype.kind in "if" else np.nan,
                "media": round(float(s.mean()), 3) if s.dtype.kind in "if" else np.nan,
            }
        )
    return pd.DataFrame(filas)
