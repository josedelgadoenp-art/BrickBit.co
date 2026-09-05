"""Traducir, no ocultar.

`LinAlgError: Singular matrix` no le dice nada a un economista, y "hubo un
error" le dice menos. Este traductor mapea patrones a diagnosticos que se
pueden accionar.

El traceback completo SIEMPRE queda en la bitacora. Traducir no es esconder: el
economista lee el diagnostico, y quien tenga que depurar lee el traceback.
"""

from __future__ import annotations

import re
import traceback
from dataclasses import dataclass


@dataclass
class ErrorTraducido:
    titulo: str
    detalle: str
    sugerencia: str | None
    excepcion: str
    traceback: str
    nodo_id: str | None = None


_REGLAS: list[tuple[str, str, str, str | None]] = [
    (r"[Ss]ingular matrix",
     "Dos variables dicen lo mismo",
     "El modelo no se puede estimar porque hay colinealidad perfecta: alguna de tus "
     "variables explicativas es combinacion exacta de otras.",
     "Revisa si metiste una variable y su transformacion (por ejemplo, el total y todas sus partes), "
     "o todas las categorias de una dummy sin quitar una. Quita una de las dos."),
    (r"exog contains inf or nans|Input contains NaN|missing values",
     "Hay datos faltantes",
     "Las variables que le pasaste al modelo tienen huecos, y la estimacion no sabe que hacer con ellos.",
     "Agrega antes un nodo «Tratar faltantes», o revisa si la transformacion que aplicaste "
     "(un rezago, una diferencia, un logaritmo de numeros negativos) los genero."),
    (r"[Ii]nsufficient degrees of freedom|not enough|too few observations",
     "No alcanzan las observaciones",
     "Estas pidiendo estimar mas parametros de los que tus datos pueden sostener.",
     "Baja el numero de rezagos o de variables, o consigue mas historia."),
    (r"cannot convert|could not convert string to float|invalid literal",
     "Una columna de texto entro donde iba un numero",
     "El modelo necesita numeros y le llego texto.",
     "Si la columna es una categoria, conviertela con «Crear indicadoras (dummies)». "
     "Si son numeros mal leidos, revisa el separador decimal del archivo."),
    (r"[Ff]req|DatetimeIndex|PeriodIndex|no associated frequency",
     "Falta la frecuencia de la serie",
     "El modelo de series de tiempo necesita saber si tus datos son mensuales, trimestrales o anuales.",
     "Agrega un nodo «Definir serie temporal» y elige la columna de fecha y la frecuencia."),
    (r"[Pp]ositive definite|not positive semidefinite",
     "La matriz de varianzas no es valida",
     "El calculo de los errores estandar fallo porque la matriz resultante no es definida positiva.",
     "Suele pasar con muy pocas observaciones por grupo al usar errores por conglomerado. "
     "Prueba con errores robustos HC1 o agrupa a un nivel mas alto."),
    (r"[Mm]emory|Unable to allocate",
     "El analisis no cabe en memoria",
     "La operacion pidio mas memoria de la disponible.",
     "Filtra filas o columnas antes de este paso, o reduce el numero de vecinos de la matriz espacial."),
    (r"[Ii]sland|disconnected observations|zero neighbou?rs",
     "Hay observaciones sin vecinos",
     "Al construir la matriz de pesos espaciales quedaron puntos aislados, y los modelos espaciales no los admiten.",
     "Usa vecinos por cercania (KNN) en vez de contigüidad, o sube el radio de distancia."),
]


def traducir(exc: BaseException, nodo_id: str | None = None) -> ErrorTraducido:
    texto = f"{type(exc).__name__}: {exc}"
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    for patron, titulo, detalle, sugerencia in _REGLAS:
        if re.search(patron, texto) or re.search(patron, tb):
            return ErrorTraducido(titulo, detalle, sugerencia, texto, tb, nodo_id)
    return ErrorTraducido(
        titulo="Este paso fallo",
        detalle=str(exc) or type(exc).__name__,
        sugerencia="El detalle tecnico completo esta en la pestana Bitacora.",
        excepcion=texto, traceback=tb, nodo_id=nodo_id,
    )
