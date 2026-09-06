"""Artefactos: los objetos de Python vueltos JSON para la interfaz.

Todo esto corre FUERA del programa generado. Es presentacion pura: no puede
alterar el analisis y por lo tanto no puede causar divergencia entre lo que se
ejecuta y lo que se exporta. Es la unica asimetria del sistema, y esta del lado
inocuo a proposito.
"""

from __future__ import annotations

import math
from typing import Any

TOPE_FILAS = 500


def _limpio(v: Any) -> Any:
    """JSON no tiene NaN ni Infinity, y `json.dumps(allow_nan=False)` truena."""
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        # Se recorta a 12 CIFRAS SIGNIFICATIVAS, no a 12 decimales.
        #
        # Antes esto era `round(v, 10)`, y eso borraba magnitudes: un p-valor de
        # 1e-20 salía como 0.0 exacto —la pantalla decía «Prob(F): 0», que es
        # falso, ninguna probabilidad es cero— y un coeficiente de 3e-12 se
        # perdía entero. Recortar por cifras significativas quita el ruido del
        # flotante (0.30000000000000004 -> 0.3) sin tocar el orden de magnitud.
        #
        # `float(...)` fuerza el tipo de Python: `round()` sobre un np.float64
        # devuelve np.float64, y un tipo de numpy escondido en algo que va a
        # JSON y a un PDF es una fuga que aparece meses después.
        return float(f"{v:.12g}")
    if isinstance(v, (int, bool, str)):
        return v
    if hasattr(v, "item"):
        try:
            return _limpio(v.item())
        except Exception:
            pass
    if hasattr(v, "isoformat"):
        return v.isoformat()
    # Un objeto grande (un DataFrame, un modelo) convertido a texto son miles de
    # caracteres que no le sirven a nadie y que ensucian la interfaz y el PDF.
    texto = str(v)
    return texto if len(texto) <= 240 else texto[:237] + "..."


def tabla_a_json(df: Any, *, tope: int = TOPE_FILAS, titulo: str | None = None,
                 estimadas: list[str] | None = None) -> dict[str, Any]:
    """DataFrame -> artefacto de tabla.

    `estimadas` es la lista de columnas que vienen de una estimacion. Viaja
    hasta la interfaz para que se pinten en ambar: un dato estimado nunca se
    presenta como si fuera un hecho.
    """
    import pandas as pd

    if isinstance(df, pd.Series):
        df = df.to_frame()
    n = int(len(df))
    vista = df.head(tope)
    indice_nombres = [str(x) for x in (df.index.names or []) if x is not None]
    mostrar_indice = bool(indice_nombres) or not isinstance(df.index, pd.RangeIndex)
    columnas: list[dict[str, Any]] = []
    if mostrar_indice:
        etiqueta = " / ".join(indice_nombres) if indice_nombres else "indice"
        columnas.append({"nombre": etiqueta, "tipo": "indice", "estimada": False})
    for c in df.columns:
        columnas.append({
            "nombre": str(c),
            "tipo": "numerica" if pd.api.types.is_numeric_dtype(df[c]) else "texto",
            "estimada": str(c) in set(estimadas or []),
        })
    filas: list[list[Any]] = []
    for idx, fila in vista.iterrows():
        f: list[Any] = []
        if mostrar_indice:
            f.append(_limpio(idx if not isinstance(idx, tuple) else " · ".join(str(x) for x in idx)))
        f.extend(_limpio(v) for v in fila.tolist())
        filas.append(f)
    return {
        "tipo": "tabla", "titulo": titulo, "columnas": columnas, "filas": filas,
        "n_filas": n, "truncada": n > tope,
    }


def _es_multiecuacion(params: Any) -> bool:
    """Un VAR o un VECM traen una TABLA de coeficientes, no una serie.

    Es la diferencia entre `params[i]` y `params[variable][ecuacion]`. Tratarlos
    igual produce una comparacion de un nombre de columna contra un numero, que
    es como se descubrio esto: «'<' not supported between str and float».
    """
    return getattr(params, "ndim", 1) == 2


def _coeficientes_multiecuacion(res: Any) -> list[dict[str, Any]]:
    """Coeficientes de un modelo con varias ecuaciones, en formato largo."""
    params = res.params
    errores = getattr(res, "stderr", None)
    pvals = getattr(res, "pvalues", None)
    filas: list[dict[str, Any]] = []
    for ecuacion in list(params.columns):
        for variable in list(params.index):
            p = None
            if pvals is not None:
                try:
                    p = float(pvals.loc[variable, ecuacion])
                except Exception:
                    p = None
            ee = None
            if errores is not None:
                try:
                    ee = float(errores.loc[variable, ecuacion])
                except Exception:
                    ee = None
            coef = _limpio(params.loc[variable, ecuacion])
            filas.append({
                "variable": f"{ecuacion} <- {variable}",
                "coeficiente": coef,
                "error_estandar": _limpio(ee),
                "estadistico": _limpio(None if (ee in (None, 0) or coef is None)
                                       else coef / ee),
                "p_valor": _limpio(p),
                "ic_bajo": None, "ic_alto": None,
                "estrellas": _estrellas(p),
            })
    return filas


def _estrellas(p: float | None) -> str:
    if p is None:
        return ""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def modelo_a_json(res: Any, *, titulo: str | None = None) -> dict[str, Any]:
    """Resultados de statsmodels/spreg -> tabla de coeficientes + diagnosticos.

    Se toca cada atributo por separado y con tolerancia a que no exista: la
    superficie de statsmodels no es uniforme entre familias de modelos, y un
    `AttributeError` aqui no debe tumbar una estimacion que si corrio.
    """
    params = getattr(res, "params", None)

    if params is not None and _es_multiecuacion(params):
        coefs = _coeficientes_multiecuacion(res)
    else:
        coefs = []
        try:
            nombres = list(params.index)  # type: ignore[union-attr]
        except Exception:
            nombres = [str(i) for i in range(len(params or []))]

        def col(attr: str) -> list[Any]:
            v = getattr(res, attr, None)
            if v is None:
                return [None] * len(nombres)
            try:
                return list(v)
            except Exception:
                return [None] * len(nombres)

        valores, errores = col("params"), col("bse")
        tvals = col("tvalues") or col("z_stat")
        pvals = col("pvalues")
        try:
            ic = res.conf_int()
            bajo, alto = list(ic.iloc[:, 0]), list(ic.iloc[:, 1])
        except Exception:
            bajo = alto = [None] * len(nombres)

        for i, nombre in enumerate(nombres):
            crudo = pvals[i] if i < len(pvals) else None
            p = _limpio(crudo)
            coefs.append({
                "variable": str(nombre),
                "coeficiente": _limpio(valores[i] if i < len(valores) else None),
                "error_estandar": _limpio(errores[i] if i < len(errores) else None),
                "estadistico": _limpio(tvals[i] if i < len(tvals) else None),
                "p_valor": p,
                "ic_bajo": _limpio(bajo[i] if i < len(bajo) else None),
                "ic_alto": _limpio(alto[i] if i < len(alto) else None),
                "estrellas": _estrellas(p if isinstance(p, (int, float)) else None),
            })

    diagnosticos: dict[str, Any] = {}
    for etiqueta, attr in [
        ("Observaciones", "nobs"), ("R²", "rsquared"), ("R² ajustada", "rsquared_adj"),
        ("Log-verosimilitud", "llf"), ("AIC", "aic"), ("BIC", "bic"),
        ("F", "fvalue"), ("Prob(F)", "f_pvalue"), ("Pseudo R²", "prsquared"),
        ("Ecuaciones", "neqs"), ("Rezagos", "k_ar"),
    ]:
        v = getattr(res, attr, None)
        if v is None or callable(v):
            continue
        # Sólo escalares: en un modelo multiecuación varios de estos atributos
        # son vectores o matrices, y meterlos aquí produce un diagnóstico
        # ilegible.
        if getattr(v, "ndim", 0) != 0 and not isinstance(v, (int, float)):
            continue
        diagnosticos[etiqueta] = _limpio(v)

    # Los seis que EViews imprime siempre y statsmodels no expone como atributo
    # suelto. Se calculan aparte para que la salida de un MCO se pueda comparar
    # renglón por renglón contra la de EViews: quien llega de ahí necesita ver
    # los mismos números, no una selección nuestra.
    try:
        import numpy as _np

        if getattr(res, "df_resid", 0) and hasattr(res, "mse_resid"):
            diagnosticos["E.E. de la regresión"] = _limpio(float(_np.sqrt(res.mse_resid)))
        if hasattr(res, "ssr"):
            diagnosticos["Suma de residuos²"] = _limpio(float(res.ssr))
        y = getattr(getattr(res, "model", None), "endog", None)
        if y is not None and getattr(y, "ndim", 1) == 1 and len(y) > 1:
            diagnosticos["Media de la dependiente"] = _limpio(float(_np.mean(y)))
            diagnosticos["D.E. de la dependiente"] = _limpio(float(_np.std(y, ddof=1)))
        # Hannan-Quinn: -2·log L + 2·k·ln(ln n). statsmodels sólo lo trae en
        # algunos modelos, así que se calcula con la fórmula.
        llf, k, nobs = getattr(res, "llf", None), getattr(res, "df_model", None), getattr(res, "nobs", None)
        if llf is not None and k is not None and nobs and nobs > _np.e:
            hq = getattr(res, "hqic", None)
            if hq is None:
                hq = -2.0 * float(llf) + 2.0 * (float(k) + 1.0) * _np.log(_np.log(float(nobs)))
            diagnosticos["Hannan-Quinn"] = _limpio(float(hq))
        resid = getattr(res, "resid", None)
        if resid is not None and getattr(resid, "ndim", 1) == 1 and len(resid) > 1:
            from statsmodels.stats.stattools import durbin_watson
            diagnosticos["Durbin-Watson"] = _limpio(float(durbin_watson(_np.asarray(resid))))
    except Exception:
        # Un diagnóstico de adorno nunca puede tumbar el resultado del modelo.
        pass

    texto = None
    try:
        texto = str(res.summary())
    except Exception:
        try:
            texto = str(getattr(res, "summary", None) or "")
        except Exception:
            texto = None

    return {
        "tipo": "modelo", "titulo": titulo, "coeficientes": coefs,
        "diagnosticos": diagnosticos, "texto": texto,
        "tipo_errores": str(getattr(res, "cov_type", "") or ""),
    }


def figura_a_json(fig: Any, *, titulo: str | None = None) -> dict[str, Any]:
    import json as _json

    import plotly

    return {
        "tipo": "figura", "titulo": titulo,
        "figura": _json.loads(_json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)),
    }


def resumen_generico(salidas: dict[str, Any]) -> dict[str, Any]:
    """Resumen por omision, deducido del tipo real del objeto."""
    import pandas as pd

    artefactos: dict[str, Any] = {}
    for puerto, valor in salidas.items():
        if valor is None:
            continue
        if isinstance(valor, (pd.DataFrame, pd.Series)):
            artefactos[puerto] = tabla_a_json(valor, titulo=puerto)
        elif hasattr(valor, "to_plotly_json"):
            artefactos[puerto] = figura_a_json(valor, titulo=puerto)
        elif hasattr(valor, "params") or hasattr(valor, "betas"):
            artefactos[puerto] = modelo_a_json(valor, titulo=puerto)
        elif isinstance(valor, (int, float, str, bool)):
            artefactos[puerto] = {"tipo": "escalar", "titulo": puerto, "valor": _limpio(valor)}
        elif isinstance(valor, dict):
            artefactos[puerto] = {"tipo": "detalle", "titulo": puerto,
                                  "datos": {k: _limpio(v) for k, v in valor.items()}}
        else:
            artefactos[puerto] = {"tipo": "objeto", "titulo": puerto,
                                  "clase": type(valor).__name__, "texto": str(valor)[:4000]}
    return artefactos
