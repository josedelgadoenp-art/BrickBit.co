"""Poner a prueba los supuestos del modelo.

Aqui no se cambia el estimador en silencio cuando un supuesto falla: se dice
que fallo y que hacer. Adivinar la intencion del usuario es como se pierde la
capacidad de defender un resultado.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from ...graph.spec import Columna, Esquema
from ...registry.base import (Ayuda, Ayudante, CampoColumnas, EspecNodo, Puerto,
                              registrar, registrar_ayudante)

registrar_ayudante(Ayudante(
    nombre="diagnosticar_modelo",
    imports=[("pandas", "pd"), ("numpy", "np")],
    fuente='''
def diagnosticar_modelo(modelo, rezagos_bg=4):
    """Bateria de pruebas sobre los residuos de una regresion.

    Devuelve una tabla con estadistico, p-valor y una lectura en espanol. Cada
    prueba se envuelve por separado: que una no aplique al modelo no debe
    tumbar a las demas.
    """
    import statsmodels.stats.api as sms
    from statsmodels.stats.stattools import durbin_watson, jarque_bera

    filas = []

    def agregar(nombre, h0, stat, p, si_rechaza, si_no):
        filas.append({
            "prueba": nombre, "hipotesis_nula": h0,
            "estadistico": None if stat is None else float(stat),
            "p_valor": None if p is None else float(p),
            "lectura": (si_rechaza if (p is not None and p < 0.05) else si_no),
        })

    try:
        bp = sms.het_breuschpagan(modelo.resid, modelo.model.exog)
        agregar("Breusch-Pagan", "Varianza constante (homocedasticidad)", bp[0], bp[1],
                "Hay heterocedasticidad: usa errores robustos HC1 o HC3.",
                "No hay evidencia de heterocedasticidad.")
    except Exception:
        pass

    try:
        wh = sms.het_white(modelo.resid, modelo.model.exog)
        agregar("White", "Varianza constante (forma general)", wh[0], wh[1],
                "Hay heterocedasticidad o mala especificacion: revisa la forma funcional.",
                "No hay evidencia de heterocedasticidad.")
    except Exception:
        pass

    try:
        dw = float(durbin_watson(modelo.resid))
        lectura = ("Autocorrelacion positiva: usa errores HAC (Newey-West)." if dw < 1.5
                   else "Autocorrelacion negativa: revisa si sobre-diferenciaste." if dw > 2.5
                   else "Sin senales de autocorrelacion de primer orden.")
        filas.append({"prueba": "Durbin-Watson", "hipotesis_nula": "Sin autocorrelacion de orden 1",
                      "estadistico": dw, "p_valor": None, "lectura": lectura})
    except Exception:
        pass

    try:
        bg = sms.acorr_breusch_godfrey(modelo, nlags=rezagos_bg)
        agregar(f"Breusch-Godfrey ({rezagos_bg} rezagos)", "Sin autocorrelacion hasta ese orden",
                bg[0], bg[1],
                "Hay autocorrelacion: usa errores HAC, o agrega rezagos de la dependiente.",
                "Sin evidencia de autocorrelacion.")
    except Exception:
        pass

    try:
        jb = jarque_bera(modelo.resid)
        agregar("Jarque-Bera", "Los residuos son normales", jb[0], jb[1],
                "Los residuos no son normales. Con muestras grandes casi no importa; "
                "con muestras chicas los intervalos de confianza quedan mal.",
                "Los residuos parecen normales.")
    except Exception:
        pass

    try:
        reset = sms.linear_reset(modelo, power=2, use_f=True)
        agregar("RESET de Ramsey", "La forma funcional lineal es adecuada",
                reset.statistic, reset.pvalue,
                "La forma lineal se queda corta: prueba con logaritmos, cuadrados o interacciones.",
                "No hay evidencia de mala especificacion.")
    except Exception:
        pass

    return pd.DataFrame(filas)
''',
))

registrar_ayudante(Ayudante(
    nombre="factor_inflacion_varianza",
    imports=[("pandas", "pd"), ("numpy", "np")],
    fuente='''
def factor_inflacion_varianza(X):
    """VIF por variable: cuanto se infla la varianza del coeficiente por colinealidad.

    Regla practica: por arriba de 10 hay un problema serio; entre 5 y 10, vale
    la pena mirarlo. Un VIF alto no sesga los coeficientes: los vuelve
    imprecisos, y ese es un problema distinto.
    """
    from statsmodels.stats.outliers_influence import variance_inflation_factor

    columnas = [c for c in X.columns if c != "const"]
    datos = X[columnas].astype(float).dropna()
    filas = []
    for i, nombre in enumerate(columnas):
        try:
            v = float(variance_inflation_factor(datos.values, i))
        except Exception:
            v = float("nan")
        filas.append({
            "variable": nombre, "vif": v,
            "lectura": ("Colinealidad seria" if v > 10 else
                        "Vale la pena revisar" if v > 5 else "Sin problema"),
        })
    return pd.DataFrame(filas)
''',
))


@registrar
class Diagnosticos(EspecNodo):
    op = "econometria.diagnosticos"
    familia = "econometria"
    titulo = "Diagnosticos del modelo"
    prefijo_var = "diagnostico"
    terminal = True
    ayuda = Ayuda(
        que_hace="Corre las pruebas de siempre sobre los residuos: heterocedasticidad, autocorrelacion, "
                 "normalidad y forma funcional.",
        cuando_usarlo="Despues de estimar cualquier regresion. Es el paso que casi nadie hace y el que "
                      "separa un resultado defendible de uno que se cae en la primera pregunta.",
        interpretacion="Cada fila trae su lectura en espanol. Un p-valor por debajo de 0.05 significa que "
                       "se rechaza el supuesto de esa prueba.",
        advertencias=["Estas pruebas dicen que supuesto falla, no que el modelo este mal. Con muestras "
                      "grandes casi todo se rechaza; mira tambien el tamano del problema, no solo el p-valor."],
        referencia="Wooldridge, caps. 8 y 12",
        equivalente={"stata": "estat hettest / estat vif", "r": "lmtest::bptest()"},
    )
    entradas = [Puerto(nombre="modelo", tipo="modelo")]
    salidas = [Puerto(nombre="pruebas", tipo="tabla", titulo="Pruebas de supuestos")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        rezagos_autocorrelacion: int = 4

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("diagnosticar_modelo")
        ctx.nota("Cada prueba tiene su propia hipotesis nula; la columna «lectura» dice que hacer.")
        ctx.emitir("SAL = diagnosticar_modelo(MOD, rezagos_bg=REZ)",
                   SAL=ctx.salida("pruebas"), MOD=ctx.entrada("modelo"),
                   REZ=ctx.plit("rezagos_autocorrelacion"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"pruebas": Esquema(columnas=[
            Columna(nombre="prueba", tipo="texto"), Columna(nombre="hipotesis_nula", tipo="texto"),
            Columna(nombre="estadistico", tipo="numerica"), Columna(nombre="p_valor", tipo="numerica"),
            Columna(nombre="lectura", tipo="texto"),
        ])}


@registrar
class Colinealidad(EspecNodo):
    op = "econometria.colinealidad"
    familia = "econometria"
    titulo = "Colinealidad (VIF)"
    prefijo_var = "vif"
    terminal = True
    ayuda = Ayuda(
        que_hace="Mide cuanto se pisan entre si tus variables explicativas.",
        cuando_usarlo="Cuando un coeficiente sale con el signo contrario al esperado, o cuando el modelo "
                      "completo es significativo pero ninguna variable lo es por separado. Ese par de "
                      "sintomas juntos es colinealidad casi siempre.",
        interpretacion="VIF por arriba de 10 es problema serio; entre 5 y 10 conviene mirarlo. La "
                       "colinealidad no sesga los coeficientes: los vuelve imprecisos.",
        advertencias=["Quitar variables por VIF alto puede introducir sesgo por variable omitida, que es "
                      "peor. A veces la respuesta correcta es aceptar la imprecision y decirlo."],
        equivalente={"stata": "estat vif", "r": "car::vif()"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="vif", tipo="tabla", titulo="Factor de inflacion de varianza")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        columnas: list[str] = CampoColumnas(tipo="numerica", default_factory=list)

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("factor_inflacion_varianza")
        ctx.emitir("SAL = factor_inflacion_varianza(ENT[COLS])",
                   SAL=ctx.salida("vif"), ENT=ctx.entrada("datos"), COLS=ctx.plit("columnas"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"vif": Esquema(columnas=[Columna(nombre="variable", tipo="texto"),
                                         Columna(nombre="vif", tipo="numerica"),
                                         Columna(nombre="lectura", tipo="texto")])}
