"""
Explicabilidad: SHAP, con permutación como respaldo.

Un AVM que no puede decir POR QUÉ dio un número no sirve para lo que se necesita
—defender una valuación ante un comité, un cliente o una autoridad—. SHAP reparte
la predicción entre las variables de forma aditiva y con una propiedad que las
otras medidas no tienen: las contribuciones suman exactamente la diferencia
entre la predicción y el valor base. Eso permite explicar UN inmueble concreto,
no sólo el modelo en promedio.

Si `shap` no está instalado se usa importancia por permutación de scikit-learn.
No es lo mismo y no se presenta como si lo fuera: la permutación mide cuánto
empeora el modelo al romper una variable —una medida global, del modelo— y no
descompone predicciones individuales. El informe declara cuál de las dos se usó,
porque leer una como la otra llevaría a conclusiones distintas.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# SHAP sobre miles de filas y cientos de columnas es caro y no hace falta: la
# importancia global se estabiliza mucho antes.
MUESTRA = 500


@dataclass
class Importancia:
    tabla: pd.DataFrame       # variable, importancia
    metodo: str               # "shap" | "permutacion"

    def texto(self, top: int = 12) -> str:
        t = self.tabla.head(top)
        ancho = max((len(v) for v in t["variable"]), default=10)
        maximo = float(t["importancia"].max()) or 1.0
        filas = []
        for r in t.itertuples():
            barra = "█" * max(1, int(round(20 * r.importancia / maximo)))
            filas.append(f"    {r.variable:<{ancho}}  {barra} {r.importancia:.4f}")
        return "\n".join(filas)


def calcular(modelo, X: pd.DataFrame, y: pd.Series | None = None,
             semilla: int = 0) -> Importancia:
    """Importancia global de cada variable, por SHAP si se puede."""
    n = min(MUESTRA, len(X))
    Xs = X.sample(n, random_state=int(semilla)) if len(X) > n else X

    try:
        import shap

        ex = shap.TreeExplainer(modelo)
        v = ex.shap_values(Xs, check_additivity=False)
        imp = np.abs(np.asarray(v)).mean(axis=0)
        metodo = "shap"
    except Exception:
        # Puede fallar por ausencia del paquete o porque el modelo no es un
        # árbol soportado. En cualquiera de los dos casos el respaldo sirve.
        from sklearn.inspection import permutation_importance

        if y is None:
            raise ValueError("La importancia por permutación necesita `y`.")
        ys = y.loc[Xs.index]
        r = permutation_importance(modelo, Xs, ys, n_repeats=5,
                                   random_state=int(semilla), n_jobs=-1)
        imp = r.importances_mean
        metodo = "permutacion"

    tabla = (
        pd.DataFrame({"variable": list(X.columns), "importancia": np.asarray(imp, float).ravel()})
        .sort_values("importancia", ascending=False)
        .reset_index(drop=True)
    )
    return Importancia(tabla, metodo)


def explicar_uno(modelo, X: pd.DataFrame, i: int) -> pd.DataFrame | None:
    """
    Descomposición de UNA predicción: cuánto sumó o restó cada variable.

    Es lo que se le enseña a un cliente —"tu departamento vale más por la
    accesibilidad al comercio y menos por la antigüedad"—. Devuelve None si SHAP
    no está disponible, porque la permutación no puede responder esta pregunta y
    fabricar una respuesta aproximada sería peor que no darla.
    """
    try:
        import shap
    except ImportError:
        return None
    ex = shap.TreeExplainer(modelo)
    v = np.asarray(ex.shap_values(X.iloc[[i]], check_additivity=False)).ravel()
    return (
        pd.DataFrame({"variable": list(X.columns), "aporte": v})
        .assign(abs_=lambda d: d["aporte"].abs())
        .sort_values("abs_", ascending=False)
        .drop(columns="abs_")
        .reset_index(drop=True)
    )
