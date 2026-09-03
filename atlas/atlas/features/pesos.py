"""
Matriz de pesos espaciales W, rezagos e I de Moran.

W es el núcleo de todo lo espacial: dice quién es vecino de quién y cuánto
pesa. El documento pide probar contigüidad, KNN y decaimiento por distancia, y
elegir con un criterio, no por gusto.

CRITERIO DE SELECCIÓN. Se elige el W que **maximiza la I de Moran** de la
variable objetivo. La razón: la I de Moran mide cuánta estructura espacial
captura esa definición de vecindad, y el W que más captura es el que deja
menos señal espacial en el residual —que es exactamente lo que se le pide—.
No es AICc (que exige ajustar un modelo por cada W y todavía no hay modelo en
la Fase 1), pero es un criterio explícito, reproducible y defendible, y se
declara como tal en vez de fingir que es otra cosa.

Todo W se estandariza por filas: así `W·y` es el PROMEDIO de los vecinos y es
directamente comparable con `y`.
"""
from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import pandas as pd
from libpysal.weights import KNN, DistanceBand, Queen, W

from ..config import Config, cargar
from ..geo import a_metrico


@dataclass
class Eleccion:
    """Qué W ganó, con qué número y contra quién. Se guarda en el informe."""

    tipo: str
    parametro: float | int
    moran_I: float
    moran_p: float
    candidatos: pd.DataFrame

    def texto(self) -> str:
        return (
            f"W elegido: {self.tipo}({self.parametro}) · "
            f"I de Moran {self.moran_I:.4f} (p={self.moran_p:.4g})"
        )


def knn(gdf: gpd.GeoDataFrame, k: int, cfg: Config | None = None) -> W:
    """k vecinos más cercanos, medidos en metros."""
    cfg = cfg or cargar()
    m = a_metrico(gdf, cfg)
    w = KNN.from_dataframe(m, k=int(k))
    w.transform = "r"     # estandarizado por filas
    return w


def banda(gdf: gpd.GeoDataFrame, umbral_m: float, cfg: Config | None = None) -> W:
    """
    Todos los vecinos dentro de `umbral_m`, con peso 1/d (decaimiento).
    Puede dejar islas —puntos sin ningún vecino dentro del umbral—; libpysal
    avisa y esas filas quedan con rezago 0, que es lo correcto: no tienen
    vecindario del que promediar.
    """
    cfg = cfg or cargar()
    m = a_metrico(gdf, cfg)
    # alpha=-1 hace 1/d; scipy avisa del 0 de la diagonal, que libpysal
    # descarta acto seguido. El aviso es ruido, no un problema real.
    with np.errstate(divide="ignore", invalid="ignore"):
        w = DistanceBand.from_dataframe(
            m, threshold=float(umbral_m), binary=False, alpha=-1.0, silence_warnings=True
        )
    w.transform = "r"
    return w


def contiguidad(gdf: gpd.GeoDataFrame) -> W:
    """Contigüidad Queen: comparten frontera o vértice. Sólo para polígonos."""
    w = Queen.from_dataframe(gdf, use_index=True, silence_warnings=True)
    w.transform = "r"
    return w


def rezago(w: W, y: np.ndarray | pd.Series) -> np.ndarray:
    """
    W·y — el promedio de los vecinos.

    Es LA variable que le permite ver el vecindario incluso a un modelo que no
    sabe nada de geografía, como el boosting. Los NaN se sustituyen por la
    media antes de multiplicar: un solo NaN en el vecindario propagaría NaN a
    toda la fila y perderíamos la observación entera.
    """
    v = pd.Series(y).astype(float)
    v = v.fillna(v.mean())
    return np.asarray(w.sparse @ v.to_numpy(), dtype=float)


def moran(w: W, y: np.ndarray | pd.Series, permutaciones: int = 999) -> tuple[float, float]:
    """
    I de Moran global y su p-valor por permutación.

    Bajo aleatoriedad E[I] = -1/(n-1) ≈ 0. Un I positivo y significativo
    confirma que hay estructura espacial y que un modelo no espacial estaría
    mal especificado. El documento pide correr esto ANTES de modelar.
    """
    from esda.moran import Moran

    v = pd.Series(y).astype(float)
    v = v.fillna(v.mean()).to_numpy()
    mi = Moran(v, w, permutations=int(permutaciones))
    return float(mi.I), float(mi.p_sim)


def lisa(w: W, y: np.ndarray | pd.Series, permutaciones: int = 999) -> pd.DataFrame:
    """
    Moran local (LISA): a qué tipo de clúster pertenece cada unidad.

    Los cuadrantes son la lectura de negocio:
      AA (alto-alto)   núcleo caro consolidado
      BB (bajo-bajo)   zona barata homogénea
      BA (bajo-alto)   BARATO RODEADO DE CARO — el frente de onda, donde la
                       plusvalía tiene más recorrido; es el cuadrante que
                       interesa para detectar oportunidad
      AB (alto-bajo)   caro aislado; suele ser una torre suelta o un dato malo
    """
    from esda.moran import Moran_Local

    v = pd.Series(y).astype(float)
    v = v.fillna(v.mean()).to_numpy()
    ml = Moran_Local(v, w, permutations=int(permutaciones))
    etiquetas = {1: "AA", 2: "BA", 3: "BB", 4: "AB"}
    return pd.DataFrame(
        {
            "lisa_I": ml.Is,
            "lisa_p": ml.p_sim,
            "lisa_cuadrante": [etiquetas.get(q, "?") for q in ml.q],
            # Significativo al 5%: lo demás es ruido y no debe pintarse como clúster.
            "lisa_sig": ml.p_sim < 0.05,
        },
        index=pd.RangeIndex(len(v)),
    )


def elegir(
    gdf: gpd.GeoDataFrame,
    y: np.ndarray | pd.Series,
    cfg: Config | None = None,
    permutaciones: int = 199,
) -> tuple[W, Eleccion]:
    """
    Prueba varios W y devuelve el que más estructura espacial captura.

    Se prueban los k de `config.yaml` y dos bandas de distancia. Las
    permutaciones van bajas a propósito durante la selección (es una
    comparación relativa); el W ganador se vuelve a medir con más.
    """
    cfg = cfg or cargar()
    ks = list(cfg["modelado"]["pesos_espaciales"]["k_candidatos"])

    filas, objetos = [], {}
    for k in ks:
        try:
            w = knn(gdf, k, cfg)
            I, p = moran(w, y, permutaciones)
            filas.append({"tipo": "knn", "parametro": k, "I": I, "p": p})
            objetos[("knn", k)] = w
        except Exception as e:      # una definición inviable no debe tumbar la selección
            filas.append({"tipo": "knn", "parametro": k, "I": np.nan, "p": np.nan,
                          "error": str(e)[:60]})
    for u in (500.0, 1000.0):
        try:
            w = banda(gdf, u, cfg)
            I, p = moran(w, y, permutaciones)
            filas.append({"tipo": "banda", "parametro": u, "I": I, "p": p})
            objetos[("banda", u)] = w
        except Exception as e:
            filas.append({"tipo": "banda", "parametro": u, "I": np.nan, "p": np.nan,
                          "error": str(e)[:60]})

    tabla = pd.DataFrame(filas)
    validos = tabla.dropna(subset=["I"])
    if validos.empty:
        raise RuntimeError(
            "Ninguna definición de W resultó viable. Revisa que el GeoDataFrame "
            "traiga geometría válida y suficientes puntos."
        )
    mejor = validos.loc[validos["I"].idxmax()]
    clave = (mejor["tipo"], mejor["parametro"])
    w = objetos[clave]
    I, p = moran(w, y, permutaciones=999)   # el ganador, medido en serio
    return w, Eleccion(str(mejor["tipo"]), mejor["parametro"], I, p, tabla)
