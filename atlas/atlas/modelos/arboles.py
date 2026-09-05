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


# Rejilla para el ajuste por validación cruzada ESPACIAL. Es pequeña a
# propósito: con ~1,000 filas de entrenamiento y 25 bloques, una rejilla grande
# encuentra el mejor pliegue por casualidad y no el mejor modelo. Cuatro
# combinaciones bien elegidas separan lo que hay que separar —cuánto puede
# curvarse el modelo y cuánto se le penaliza— sin invitar a sobreajustar la
# propia validación.
REJILLA = [
    dict(max_leaf_nodes=7,  min_samples_leaf=40, l2_regularization=5.0, learning_rate=0.05, max_iter=500),
    dict(max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1.0, learning_rate=0.05, max_iter=400),
    dict(max_leaf_nodes=31, min_samples_leaf=10, l2_regularization=0.1, learning_rate=0.05, max_iter=400),
    dict(max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1.0, learning_rate=0.02, max_iter=900),
]


def elegir_hiperparametros(X: pd.DataFrame, y: pd.Series, bloque: pd.Series,
                           semilla: int, n_pliegues: int = 5):
    """
    Elige la configuración del boosting por validación cruzada POR BLOQUE.

    Estaban puestos a mano y ahí se habían quedado. Ajustarlos al azar sería
    peor que no ajustarlos: con vecinos repartidos a los dos lados, la
    validación premia al modelo que mejor memoriza la cuadra, que es
    exactamente el que peor generaliza a un barrio nuevo. Con GroupKFold sobre
    los bloques, gana el que de verdad transfiere.

    Se mide con el error absoluto mediano en logaritmos, no con el cuadrático:
    unos pocos anuncios mal capturados dominan el MSE y elegirían el modelo que
    mejor persigue outliers.
    """
    from sklearn.model_selection import GroupKFold

    g = bloque.to_numpy()
    k = int(min(n_pliegues, pd.Series(g).nunique()))
    if k < 2:
        return dict(BASE), []

    filas = []
    for i, cfg in enumerate(REJILLA):
        errores = []
        for tr, va in GroupKFold(n_splits=k).split(X, y, groups=g):
            m = HistGradientBoostingRegressor(
                random_state=int(semilla), early_stopping=False, **cfg)
            m.fit(X.iloc[tr], y.iloc[tr])
            errores.append(float(np.median(np.abs(y.iloc[va] - m.predict(X.iloc[va])))))
        filas.append({"i": i, "mediana_abs_log": float(np.mean(errores)), **cfg})
    tabla = pd.DataFrame(filas).sort_values("mediana_abs_log")
    mejor = dict(REJILLA[int(tabla.iloc[0]["i"])])
    return {**mejor, "early_stopping": False}, tabla


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


# La dispersión se ajusta MÁS SUAVE que la media, y no por descuido.
#
# σ̂ es un parámetro de estorbo: su trabajo no es acertar sino dar la FORMA del
# ancho. Y el ruido en σ̂ sale carísimo. Medido en simulación: con la misma
# cobertura, una σ̂ ruidosa infla la corrección conforme de 1.92 a 3.44 y casi
# DUPLICA el ancho del intervalo. El mecanismo es que el score |y−ŷ|/σ̂ tiene
# colas gruesas cuando σ̂ se equivoca hacia abajo, y unos pocos puntos así
# arrastran el cuantil conforme —que luego se le aplica a todo el mundo—.
#
# Se vio en producción: al pasar de 56 a 137 variables el error puntual mejoró
# (mediana 24.7% → 22.0%) y el intervalo se ENSANCHÓ (±107% → ±126%), porque
# σ̂ con 137 variables y 953 filas se volvió más ruidosa.
DISPERSION = dict(
    learning_rate=0.05,
    max_iter=200,
    max_leaf_nodes=7,
    min_samples_leaf=40,
    l2_regularization=5.0,
    early_stopping=False,
)


def dispersion(X: pd.DataFrame, y: pd.Series, pred_fuera: np.ndarray,
               semilla: int, piso: float = 0.02):
    """
    Modelo de cuánto SUELE equivocarse la predicción en cada punto.

    Es la pieza que permite un intervalo conforme localmente adaptativo sin
    estimar cuantiles extremos. La diferencia importa mucho con pocos datos:
    ajustar el cuantil 2.5% con pérdida de pinball apoya la estimación en el
    2.5% de las observaciones —unas 24 de 953—, mientras que |residual| se
    ajusta con las 953. Medido sobre la CDMX, el intervalo por cuantiles salía
    al doble de ancho de lo que el error justificaba.

    Se modela log(|residual|) y no |residual| para que la predicción no pueda
    salir negativa —una dispersión negativa no significa nada— y porque el error
    inmobiliario es multiplicativo: equivocarse 300 mil pesos en Iztapalapa y en
    Polanco no es lo mismo.

    `pred_fuera` DEBE ser fuera de muestra. Con predicciones sobre sus propios
    datos de entrenamiento los residuales salen pequeños y el modelo aprendería
    que el sistema es más preciso de lo que es: intervalos estrechos y falsos.
    """
    r = np.abs(np.asarray(y, float) - np.asarray(pred_fuera, float))
    ok = np.isfinite(r)
    m = HistGradientBoostingRegressor(random_state=int(semilla), **DISPERSION)
    m.fit(X[ok], np.log(r[ok] + piso))
    return _Dispersion(m, piso, escala=float(np.median(r[ok])))


class _Dispersion:
    """
    Envuelve el modelo para deshacer el logaritmo y estabilizar la predicción.

    `gamma` es la estabilización aditiva de Lei, G'Sell, Rinaldo, Tibshirani y
    Wasserman (2018): el score se calcula sobre σ̂(x) + γ en vez de σ̂(x) a secas.
    Con γ = 0 el intervalo es todo lo adaptativo que σ̂ permita, y también todo
    lo frágil: donde σ̂ se equivoca hacia abajo, el score explota y arrastra el
    cuantil conforme para todos. Con γ grande el intervalo tiende al de ancho
    constante: estable y poco informativo. γ se ELIGE midiendo (ver
    `conforme.elegir_estabilizador`), no a ojo.

    `escala` es la mediana de |residual| en entrenamiento, y sirve para que γ se
    exprese en múltiplos de ella: así el mismo valor significa lo mismo en venta
    y en renta, cuyos residuales viven en escalas distintas.
    """

    def __init__(self, modelo, piso: float, escala: float, gamma: float = 0.0):
        self.modelo, self.piso, self.escala = modelo, piso, max(escala, 1e-6)
        self.gamma = float(gamma)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        base = np.maximum(np.exp(self.modelo.predict(X)) - self.piso, 1e-4)
        return base + self.gamma * self.escala


def cuantiles_fuera_de_muestra(
    X: pd.DataFrame, y: pd.Series, bloque: pd.Series, alpha: float,
    semilla: int, n_pliegues: int = 5,
):
    """Los dos modelos de cuantil, evaluados en bloques que no entrenaron."""
    from sklearn.model_selection import GroupKFold

    g = bloque.to_numpy()
    k = int(min(n_pliegues, pd.Series(g).nunique()))
    lo = np.full(len(y), np.nan)
    hi = np.full(len(y), np.nan)
    for tr, va in GroupKFold(n_splits=k).split(X, y, groups=g):
        a, b = banda(X.iloc[tr], y.iloc[tr], alpha, semilla)
        lo[va] = a.predict(X.iloc[va])
        hi[va] = b.predict(X.iloc[va])
    return lo, hi


def dispersion_fuera_de_muestra(
    X: pd.DataFrame, y: pd.Series, pred_fuera: np.ndarray, bloque: pd.Series,
    semilla: int, n_pliegues: int = 5,
) -> np.ndarray:
    """
    σ̂ evaluada sobre datos que el propio modelo de σ̂ no vio.

    Existe para elegir γ sin que σ̂ SE JUZGUE A SÍ MISMA. La primera versión
    elegía γ midiendo el ancho sobre las predicciones fuera de muestra del
    entrenamiento —pero σ̂ se había ajustado sobre esos mismos residuales—. En
    esos datos σ̂ acierta por construcción, así que γ=0 salía siempre ganador; y
    después, en barrios nuevos, σ̂ se quedaba corta y la corrección conforme se
    disparaba. Medido en producción: γ=0 elegido, corrección 4.35, cobertura
    98.4% contra un 95% pedido. Sobrecubrir no es prudencia: es ancho tirado.

    Con los bloques espaciales como grupos, además, la evaluación imita la
    condición real: σ̂ se juzga en barrios que no vio.
    """
    from sklearn.model_selection import GroupKFold

    g = bloque.to_numpy()
    k = int(min(n_pliegues, pd.Series(g).nunique()))
    if k < 2:
        raise ValueError("Hacen falta al menos 2 bloques para evaluar σ̂ fuera de muestra.")
    sigma = np.full(len(y), np.nan)
    for tr, va in GroupKFold(n_splits=k).split(X, y, groups=g):
        m = dispersion(X.iloc[tr], y.iloc[tr], np.asarray(pred_fuera)[tr], semilla)
        sigma[va] = m.predict(X.iloc[va])
    return sigma


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
