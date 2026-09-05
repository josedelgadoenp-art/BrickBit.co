"""
¿El crecimiento de precios se contagia entre zonas vecinas?

Es la pregunta que decide si el "campo de crecimiento" del documento tiene
fundamento empírico o es una metáfora bonita. Y se puede contestar con datos
reales: el panel SHF trae 32 zonas × 22 años, o sea 32 series de crecimiento
observadas sobre el mismo periodo.

DOS PRUEBAS, Y LA SEGUNDA ES LA QUE IMPORTA.

  1. **¿Está agrupado?** I de Moran del crecimiento de cada año. Un I positivo
     dice que las zonas que crecen mucho están cerca de otras que crecen mucho.
     Es descriptivo y barato, pero NO prueba contagio: dos zonas vecinas pueden
     crecer igual porque comparten un choque común —una tasa hipotecaria, un
     ciclo nacional— sin que una empuje a la otra.

  2. **¿Predice?** Si el crecimiento del vecindario en t predice el crecimiento
     propio en t+1 *por encima* de lo que ya predice el crecimiento propio en t,
     entonces el término espacial aporta información y no sólo correlación. Se
     mide con validación hacia adelante: se ajusta con los años anteriores y se
     predice el siguiente, nunca al revés.

`data/forecast.json` afirma un modelo "50% momentum + 50% contagio espacial".
Este módulo existe para comprobar esa mitad, no para darla por buena. Si el
término espacial no mejora la predicción fuera de muestra, hay que decirlo.

AVISO SOBRE EL TAMAÑO. Son 22 observaciones anuales. Para una prueba de
cointegración o un VECM eso es MUY poco —Johansen con T=22 tiene poca potencia y
sus valores críticos son asintóticos—, así que el resultado se reporta como
indicio y no como conclusión. La validación hacia adelante, en cambio, sí es
honesta a este tamaño: son ~15 predicciones fuera de muestra por horizonte.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..config import Config, cargar
from .indice import Panel

MINIMO_ANIOS_AJUSTE = 6      # por debajo, el ajuste no tiene grados de libertad


def pesos_zonas(coords: pd.DataFrame, k: int = 4, cfg: Config | None = None):
    """
    W entre zonas por k vecinos más cercanos, medido en metros.

    KNN y no banda de distancia: las zonas de México están muy desigualmente
    espaciadas —el centro es denso, el norte y la península no— y una banda fija
    dejaría a Baja California Sur y a Quintana Roo sin ningún vecino.
    """
    import geopandas as gpd
    from libpysal.weights import KNN
    from shapely.geometry import Point

    cfg = cfg or cargar()
    g = gpd.GeoDataFrame(
        {"zona": coords.index},
        geometry=[Point(lo, la) for la, lo in zip(coords["lat"], coords["lng"])],
        crs=cfg.crs_geografico,
    ).to_crs(cfg.crs_metrico)
    w = KNN.from_dataframe(g, k=int(k))
    w.transform = "r"
    return w


@dataclass
class Agrupamiento:
    """I de Moran del crecimiento, año por año."""

    tabla: pd.DataFrame          # anio, I, p
    media_I: float
    anios_significativos: int

    def texto(self) -> str:
        return (
            f"    I de Moran medio {self.media_I:+.3f} · "
            f"significativo en {self.anios_significativos} de {len(self.tabla)} años"
        )


def agrupamiento(panel: Panel, w, permutaciones: int = 999) -> Agrupamiento:
    """¿El crecimiento de cada año está espacialmente agrupado?"""
    from ..features.pesos import moran

    filas = []
    for anio, fila in panel.crecimiento.iterrows():
        y = fila.reindex(panel.coords.index)
        if y.isna().all():
            continue
        I, p = moran(w, y.to_numpy(), permutaciones=permutaciones)
        filas.append({"anio": int(anio), "I": I, "p": p})
    t = pd.DataFrame(filas)
    return Agrupamiento(
        tabla=t,
        media_I=float(t["I"].mean()) if len(t) else float("nan"),
        anios_significativos=int((t["p"] < 0.05).sum()) if len(t) else 0,
    )


@dataclass
class Contagio:
    """Qué tanto aporta el vecindario a predecir el año siguiente."""

    n_predicciones: int
    mae_ingenuo: float           # predecir la media histórica de la zona
    mae_momentum: float          # sólo el crecimiento propio del año anterior
    mae_con_vecinos: float       # momentum + rezago espacial
    mejora_pct: float            # del espacial sobre el momentum
    coef_espacial: float         # coeficiente medio del término W·g
    detalle: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def aporta(self) -> bool:
        """El término espacial gana sólo si BAJA el error fuera de muestra."""
        return self.mae_con_vecinos < self.mae_momentum

    def texto(self) -> str:
        veredicto = (
            f"el vecindario SÍ aporta: {self.mejora_pct:+.1f}% de error"
            if self.aporta else
            f"el vecindario NO aporta ({self.mejora_pct:+.1f}% de error)"
        )
        return (
            f"    {self.n_predicciones} predicciones fuera de muestra\n"
            f"    error absoluto medio (puntos porcentuales de crecimiento anual):\n"
            f"      media histórica      {self.mae_ingenuo * 100:.2f}\n"
            f"      sólo momentum        {self.mae_momentum * 100:.2f}\n"
            f"      momentum + vecinos   {self.mae_con_vecinos * 100:.2f}\n"
            f"    {veredicto}\n"
            f"    coeficiente medio del rezago espacial: {self.coef_espacial:+.3f}"
        )


def contagio(panel: Panel, w, minimo_anios: int = MINIMO_ANIOS_AJUSTE) -> Contagio:
    """
    Validación hacia adelante: ¿el crecimiento del vecindario predice el propio?

    Para cada año t se ajusta con TODO lo anterior y se predice t. Nunca al
    revés: usar años futuros para ajustar y luego "predecirlos" es la fuga que
    hace que cualquier modelo de series parezca genial. Se comparan tres
    predictores sobre exactamente las mismas observaciones.
    """
    from sklearn.linear_model import LinearRegression

    g = panel.crecimiento.reindex(columns=panel.coords.index).dropna(how="all")
    anios = list(g.index)
    Wm = w.sparse

    filas = []
    for i in range(minimo_anios, len(anios)):
        objetivo = anios[i]
        historia = anios[:i]

        # Matriz de entrenamiento: pares (año t-1 → año t) de todos los años
        # anteriores al objetivo, apilando zonas.
        X, Y = [], []
        for j in range(1, len(historia)):
            prev = g.loc[historia[j - 1]].to_numpy(dtype=float)
            act = g.loc[historia[j]].to_numpy(dtype=float)
            if not (np.isfinite(prev).all() and np.isfinite(act).all()):
                continue
            X.append(np.column_stack([prev, Wm @ prev]))
            Y.append(act)
        if not X:
            continue
        X = np.vstack(X)
        Y = np.concatenate(Y)

        prev = g.loc[anios[i - 1]].to_numpy(dtype=float)
        real = g.loc[objetivo].to_numpy(dtype=float)
        if not (np.isfinite(prev).all() and np.isfinite(real).all()):
            continue
        Xp = np.column_stack([prev, Wm @ prev])

        m_mom = LinearRegression().fit(X[:, :1], Y)
        m_esp = LinearRegression().fit(X, Y)
        ingenuo = float(Y.mean())

        filas.append({
            "anio": int(objetivo),
            "err_ingenuo": float(np.mean(np.abs(real - ingenuo))),
            "err_momentum": float(np.mean(np.abs(real - m_mom.predict(Xp[:, :1])))),
            "err_espacial": float(np.mean(np.abs(real - m_esp.predict(Xp)))),
            "coef_espacial": float(m_esp.coef_[1]),
        })

    d = pd.DataFrame(filas)
    if d.empty:
        raise ValueError("No hubo años suficientes para validar hacia adelante.")
    mom, esp = float(d["err_momentum"].mean()), float(d["err_espacial"].mean())
    return Contagio(
        n_predicciones=len(d) * g.shape[1],
        mae_ingenuo=float(d["err_ingenuo"].mean()),
        mae_momentum=mom,
        mae_con_vecinos=esp,
        mejora_pct=(esp - mom) / mom * 100 if mom else float("nan"),
        coef_espacial=float(d["coef_espacial"].mean()),
        detalle=d,
    )


@dataclass
class Cointegracion:
    traza: float
    critico_95: float
    hay: bool
    n: int

    def texto(self) -> str:
        v = "SÍ" if self.hay else "no"
        return (
            f"    estadístico de traza {self.traza:.2f} contra {self.critico_95:.2f} al 95%: "
            f"{v} hay cointegración\n"
            f"    ⚠ con T={self.n} el resultado es un INDICIO, no una conclusión: los\n"
            f"      valores críticos de Johansen son asintóticos y con veintitantas\n"
            f"      observaciones anuales la prueba tiene poca potencia."
        )


def cointegracion(panel: Panel, zona: str = "Ciudad de México") -> Cointegracion:
    """
    ¿La zona y el agregado nacional comparten una tendencia de largo plazo?

    Si la comparten, sus niveles no pueden separarse indefinidamente y un
    desvío grande hoy anticipa una corrección: es el fundamento del término de
    corrección de error, y la razón por la que un pronóstico de largo plazo no
    debe extrapolar la tendencia local sin más.
    """
    from statsmodels.tsa.vector_ar.vecm import coint_johansen

    nacional = np.log(panel.nivel.mean(axis=1))
    propia = np.log(panel.nivel[zona])
    datos = pd.concat([propia, nacional], axis=1).dropna()
    r = coint_johansen(datos.to_numpy(), det_order=0, k_ar_diff=1)
    traza = float(r.lr1[0])
    critico = float(r.cvt[0, 1])       # columna del 95%
    return Cointegracion(traza=traza, critico_95=critico,
                         hay=traza > critico, n=len(datos))
