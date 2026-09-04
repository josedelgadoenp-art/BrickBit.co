"""
Boosting de gradiente: media condicional y cuantiles.

Es el motor predictivo. A diferencia del hedónico, aquí sí entran las ~130
variables de la malla: los árboles toleran la redundancia y las interacciones
—"cerca del Metro **y** en zona de oficinas"— que una regresión lineal sólo
capturaría si alguien las escribiera a mano.

Se usa `HistGradientBoostingRegressor` de scikit-learn y no LightGBM ni
CatBoost. Motivo: ya está instalado, maneja NaN de forma nativa (importa, porque
antigüedad y niveles faltan en muchos anuncios) y soporta pérdida de cuantil,
que es lo que hace falta para el intervalo. Meter dos dependencias más para un
par de puntos de MAE no compensa en un proyecto que corre en la máquina de una
persona.

SIN PARO TEMPRANO, A PROPÓSITO. `early_stopping` de sklearn separa una fracción
de validación AL AZAR, y al azar significa que un departamento del mismo
edificio queda a los dos lados. El modelo pararía de entrenar mirando datos
contaminados por fuga espacial: el número de iteraciones se elegiría con
información que en producción no existe. Se prefiere un número fijo de
iteraciones con regularización, y la validación honesta la hace la partición por
bloques de `datos.particion`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

# Hiperparámetros conservadores. Con ~1,300 filas de entrenamiento un modelo
# profundo memoriza: hojas pocas, hojas pobladas y regularización explícita.
BASE = dict(
    learning_rate=0.05,
    max_iter=400,
    max_leaf_nodes=15,
    min_samples_leaf=20,
    l2_regularization=1.0,
    early_stopping=False,
)


def media(X: pd.DataFrame, y: pd.Series, semilla: int, **extra) -> HistGradientBoostingRegressor:
    """Modelo de la media condicional: la predicción puntual de ln(precio/m²)."""
    m = HistGradientBoostingRegressor(random_state=int(semilla), **{**BASE, **extra})
    m.fit(X, y)
    return m


def cuantil(X: pd.DataFrame, y: pd.Series, q: float, semilla: int, **extra):
    """
    Modelo del cuantil q.

    Estos dos modelos (q bajo y q alto) son la materia prima del intervalo. Por
    sí solos NO tienen garantía de cobertura —un cuantil estimado es sólo una
    estimación—, y por eso el resultado pasa después por la conformalización.
    """
    m = HistGradientBoostingRegressor(
        loss="quantile", quantile=float(q), random_state=int(semilla), **{**BASE, **extra}
    )
    m.fit(X, y)
    return m


def banda(X: pd.DataFrame, y: pd.Series, alpha: float, semilla: int):
    """
    Par de modelos de cuantil para un intervalo (1−alpha).

    Con alpha=0.05 son los cuantiles 2.5% y 97.5%. Se devuelven ambos porque el
    intervalo conforme necesita las dos puntas para calcular su corrección.
    """
    return (
        cuantil(X, y, alpha / 2.0, semilla),
        cuantil(X, y, 1.0 - alpha / 2.0, semilla),
    )


def fuera_de_muestra_por_bloque(
    X: pd.DataFrame, y: pd.Series, bloque: pd.Series, semilla: int, n_pliegues: int = 5
) -> np.ndarray:
    """
    Predicciones fuera de muestra respetando los bloques espaciales.

    Sirven para dos cosas: entrenar el apilado sin que aprenda de predicciones
    que ya vieron su propia observación, y estimar el desempeño sin gastar el
    conjunto de prueba. `GroupKFold` garantiza que un bloque nunca esté a la vez
    dentro y fuera.
    """
    from sklearn.model_selection import GroupKFold

    g = bloque.to_numpy()
    k = int(min(n_pliegues, pd.Series(g).nunique()))
    if k < 2:
        raise ValueError("Hacen falta al menos 2 bloques para validar sin fuga espacial.")

    fuera = np.full(len(y), np.nan)
    for entrena, valida in GroupKFold(n_splits=k).split(X, y, groups=g):
        m = media(X.iloc[entrena], y.iloc[entrena], semilla)
        fuera[valida] = m.predict(X.iloc[valida])
    return fuera
