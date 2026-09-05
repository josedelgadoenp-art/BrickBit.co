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
        return None if (math.isnan(v) or math.isinf(v)) else round(v, 10)
    if isinstance(v, (int, bool, str)):
        return v
    if hasattr(v, "item"):
        try:
            return _limpio(v.item())
        except Exception:
            pass
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


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


def modelo_a_json(res: Any, *, titulo: str | None = None) -> dict[str, Any]:
    """Resultados de statsmodels/spreg -> tabla de coeficientes + diagnosticos.

    Se toca cada atributo por separado y con tolerancia a que no exista: la
    superficie de statsmodels no es uniforme entre familias de modelos, y un
    `AttributeError` aqui no debe tumbar una estimacion que si corrio.
    """
    coefs: list[dict[str, Any]] = []
    try:
        nombres = list(getattr(res, "params", {}).index)  # type: ignore[union-attr]
    except Exception:
        nombres = [str(i) for i in range(len(getattr(res, "params", []) or []))]

    def col(attr: str) -> list[Any]:
        v = getattr(res, attr, None)
        if v is None:
            return [None] * len(nombres)
        try:
            return list(v)
        except Exception:
            return [None] * len(nombres)

    params, errores = col("params"), col("bse")
    tvals = col("tvalues") or col("z_stat")
    pvals = col("pvalues")
    try:
        ic = res.conf_int()
        bajo, alto = list(ic.iloc[:, 0]), list(ic.iloc[:, 1])
    except Exception:
        bajo = alto = [None] * len(nombres)

    for i, nombre in enumerate(nombres):
        p = _limpio(pvals[i] if i < len(pvals) else None)
        coefs.append({
            "variable": str(nombre),
            "coeficiente": _limpio(params[i] if i < len(params) else None),
            "error_estandar": _limpio(errores[i] if i < len(errores) else None),
            "estadistico": _limpio(tvals[i] if i < len(tvals) else None),
            "p_valor": p,
            "ic_bajo": _limpio(bajo[i] if i < len(bajo) else None),
            "ic_alto": _limpio(alto[i] if i < len(alto) else None),
            "estrellas": "***" if p is not None and p < 0.01 else
                         "**" if p is not None and p < 0.05 else
                         "*" if p is not None and p < 0.10 else "",
        })

    diagnosticos: dict[str, Any] = {}
    for etiqueta, attr in [
        ("Observaciones", "nobs"), ("R²", "rsquared"), ("R² ajustada", "rsquared_adj"),
        ("Log-verosimilitud", "llf"), ("AIC", "aic"), ("BIC", "bic"),
        ("F", "fvalue"), ("Prob(F)", "f_pvalue"), ("Pseudo R²", "prsquared"),
    ]:
        v = getattr(res, attr, None)
        if v is not None and not callable(v):
            diagnosticos[etiqueta] = _limpio(v)

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
