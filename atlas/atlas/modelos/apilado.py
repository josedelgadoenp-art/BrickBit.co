"""
Apilado (stacking): combinar el hedónico con el boosting.

Los dos modelos se equivocan de forma distinta y ahí está la ganancia. La
regresión extrapola con sensatez —fuera del rango de los datos sigue la
tendencia lineal— pero no ve interacciones. El boosting captura interacciones y
no linealidades, pero fuera del rango de entrenamiento se queda plano: nunca
predice un precio mayor que el máximo que vio. En la CDMX eso pesa, porque el
inventario de las alcaldías caras es justo el que falta.

EL META-MODELO ES UNA REGRESIÓN CON PESOS NO NEGATIVOS. No un tercer boosting.
Con ~1,300 observaciones, un meta-modelo flexible sobre dos columnas encuentra
estructura donde no la hay. Los pesos no negativos, además, mantienen la
combinación interpretable: se puede decir "60% boosting, 40% hedónico" y que
signifique algo.

LAS PREDICCIONES DEL NIVEL BASE SON FUERA DE MUESTRA POR BLOQUE. Si el meta se
entrenara con predicciones que los modelos hicieron sobre sus propios datos de
entrenamiento, vería al boosting casi perfecto y le daría todo el peso. Es el
error clásico del apilado y produce un modelo que se derrumba en producción.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Apilado:
    nombres: list[str]
    pesos: np.ndarray
    intercepto: float

    def predecir(self, columnas: dict[str, np.ndarray]) -> np.ndarray:
        M = np.column_stack([np.asarray(columnas[n], float) for n in self.nombres])
        return self.intercepto + M @ self.pesos

    def texto(self) -> str:
        partes = [f"{n} {w * 100:.0f}%" for n, w in zip(self.nombres, self.pesos)]
        return "    " + "  ·  ".join(partes)


def ajustar(base: dict[str, np.ndarray], y: np.ndarray) -> Apilado:
    """
    Mínimos cuadrados no negativos sobre las predicciones fuera de muestra.

    Se centra y y las columnas para estimar un intercepto sin obligar a que los
    pesos lo absorban, y los pesos se normalizan a suma 1 cuando su suma es
    positiva: así se leen como una mezcla y no como una escala arbitraria.
    """
    from scipy.optimize import nnls

    nombres = list(base)
    M = np.column_stack([np.asarray(base[n], float) for n in nombres])
    y = np.asarray(y, float)
    ok = np.isfinite(y) & np.isfinite(M).all(axis=1)
    M, y = M[ok], y[ok]
    if len(y) == 0:
        raise ValueError("No quedó ninguna fila válida para ajustar el apilado.")

    mu_y = float(y.mean())
    mu_M = M.mean(axis=0)
    w, _ = nnls(M - mu_M, y - mu_y)
    s = float(w.sum())
    if s > 0:
        w = w / s
    else:
        # Ningún modelo aportó señal: se reparte por igual en vez de devolver
        # ceros, que darían una predicción constante.
        w = np.full(len(nombres), 1.0 / len(nombres))
    return Apilado(nombres, w, float(mu_y - mu_M @ w))
