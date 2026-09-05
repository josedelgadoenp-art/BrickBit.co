"""
Comparables: a qué precio se ofrece lo que está alrededor.

Es la señal que un valuador usa primero y la que al Atlas le faltaba. Hasta
ahora el modelo conocía las amenidades de la zona —cuánto comercio, qué tan
lejos el hospital— y los atributos del inmueble, pero no sabía a qué precio se
ofrecen los inmuebles de al lado. Un perito nunca valúa así: abre los
comparables antes que nada.

EL PELIGRO ES LA FUGA, Y AQUÍ TIENE DOS FORMAS DISTINTAS.

**La obvia**: si los comparables de un inmueble incluyen su propio anuncio, el
modelo aprende a copiar la respuesta. Se evita excluyendo la fila de sus propias
fuentes.

**La sutil, y la que de verdad muerde**: si a los inmuebles de ENTRENAMIENTO se
les dan comparables de su misma cuadra, pero a los de PRUEBA —que están en
bloques que el modelo nunca vio— les tocan comparables de otro barrio, entonces
la variable no significa lo mismo en los dos lados. El modelo se apoya en un
comparable a 200 m que en producción no va a existir, y el desempeño se cae al
desplegar sin que la evaluación lo haya avisado.

La solución es simétrica: **a cada fila se le buscan comparables fuera de su
propio bloque espacial**. Un inmueble de entrenamiento se compara con otros
barrios igual que uno de prueba. La variable pierde algo de fuerza y gana lo
único que importa, que es significar lo mismo al entrenar y al valuar.

LAS FUENTES SON SIEMPRE EL CONJUNTO DE ENTRENAMIENTO. Es también lo que pasa en
producción: cuando llega un inmueble nuevo, los comparables salen de la base que
ya se tiene, no de él mismo ni del futuro.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

# Cuántos comparables mirar. Tres escalas a propósito: 5 es "los de la cuadra",
# 25 es "los del barrio". Cuál importa lo decide el modelo, no yo.
KS = (5, 15, 40)
RADIOS_M = (1000.0, 3000.0)


def variables(
    objetivo_xy: np.ndarray,
    fuente_xy: np.ndarray,
    fuente_y: np.ndarray,
    bloque_objetivo: np.ndarray | None = None,
    bloque_fuente: np.ndarray | None = None,
    ks: tuple[int, ...] = KS,
    radios_m: tuple[float, ...] = RADIOS_M,
) -> pd.DataFrame:
    """
    Precio de los comparables de cada punto, excluyendo su propio bloque.

    Devuelve, por cada k: la mediana del ln(precio/m²) de los k más cercanos, su
    distancia mediana, y la dispersión entre ellos —que dice si la zona es
    homogénea o revuelta, y es tan informativa como el nivel—. Más el conteo de
    comparables dentro de cada radio, que es una medida directa de cuánta
    evidencia hay: valuar con tres comparables no es lo mismo que con cincuenta,
    y el modelo debería poder notarlo.

    Todas las columnas pueden salir NaN si un punto no tiene ningún comparable
    fuera de su bloque. Se deja NaN a propósito: el boosting los maneja de forma
    nativa, e imputarlos con la media diría "aquí el barrio vale lo promedio",
    que es justo lo que no se sabe.
    """
    objetivo_xy = np.asarray(objetivo_xy, float)
    fuente_xy = np.asarray(fuente_xy, float)
    fuente_y = np.asarray(fuente_y, float)
    n = len(objetivo_xy)
    out = pd.DataFrame(index=pd.RangeIndex(n))

    if len(fuente_xy) == 0:
        for k in ks:
            out[f"comp{k}_ln_precio_m2"] = np.nan
            out[f"comp{k}_dist_m"] = np.nan
            out[f"comp{k}_dispersion"] = np.nan
        for r in radios_m:
            out[f"comp_n_{int(r)}m"] = 0
        return out

    mismo_bloque = bloque_objetivo is not None and bloque_fuente is not None
    bo = np.asarray(bloque_objetivo, dtype=object) if mismo_bloque else None
    bf = np.asarray(bloque_fuente, dtype=object) if mismo_bloque else None

    arbol = cKDTree(fuente_xy)
    # Se piden de más para poder descartar los del propio bloque y aun así
    # quedarse con k. El tope evita pedir más vecinos de los que existen.
    k_max = min(len(fuente_xy), max(ks) * 6 + 50)
    dist, idx = arbol.query(objetivo_xy, k=k_max, workers=-1)
    if k_max == 1:
        dist, idx = dist[:, None], idx[:, None]

    valido = np.isfinite(dist)
    if mismo_bloque:
        valido &= bf[idx] != bo[:, None]

    for k in ks:
        med = np.full(n, np.nan)
        dm = np.full(n, np.nan)
        disp = np.full(n, np.nan)
        for i in range(n):
            j = idx[i][valido[i]][:k]
            if len(j) == 0:
                continue
            v = fuente_y[j]
            med[i] = float(np.median(v))
            dm[i] = float(np.median(dist[i][valido[i]][:k]))
            if len(j) > 2:
                disp[i] = float(np.subtract(*np.percentile(v, [75, 25])))
        out[f"comp{k}_ln_precio_m2"] = med
        out[f"comp{k}_dist_m"] = dm
        out[f"comp{k}_dispersion"] = disp

    for r in radios_m:
        dentro = (dist <= r) & valido
        out[f"comp_n_{int(r)}m"] = dentro.sum(axis=1).astype(np.int32)

    return out


def cobertura(X: pd.DataFrame) -> dict:
    """Cuántas filas se quedaron sin comparables. Va al informe, no se esconde."""
    cols = [c for c in X.columns if c.startswith("comp") and c.endswith("ln_precio_m2")]
    if not cols:
        return {}
    principal = cols[0]
    return {
        "con_comparables": int(X[principal].notna().sum()),
        "sin_comparables": int(X[principal].isna().sum()),
        "pct_sin": round(100 * float(X[principal].isna().mean()), 1),
    }
