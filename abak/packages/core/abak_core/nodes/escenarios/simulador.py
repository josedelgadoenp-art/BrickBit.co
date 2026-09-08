"""«¿Que pasa si?»: recorrer una variable y proyectar el resultado.

Un modelo estimado contesta mas de lo que la tabla de coeficientes ensena. El
coeficiente dice cuanto cambia y por cada unidad de x, pero nadie piensa en
unidades: la pregunta real es «si el ingreso del hogar sube 20%, ¿donde queda el
precio por m² en una zona con doce anos de escolaridad?». Eso es una curva, no
un numero, y se lee moviendo un control.

Lo importante, y es lo que hace honesto al deslizador: **la rejilla completa se
calcula aqui, en el motor, y viaja entera al navegador**. El control no modela
nada; escoge cual de las curvas ya calculadas se ensena. Si el deslizador
estimara del lado del cliente, seria un modelo en la sombra que nadie puede
auditar ni exportar. Asi, cada punto del abanico esta en la tabla, en el script
exportado y en el informe.

Y todo lo que sale de aqui es ESTIMACION: la tabla marca sus columnas y la
grafica va en ambar.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...graph.spec import Columna, Esquema
from ...registry.base import (Ayuda, Ayudante, CampoColumna, EspecNodo, Puerto,
                              registrar, registrar_ayudante)

registrar_ayudante(Ayudante(
    nombre="rejilla_escenarios",
    fuente='''
def rejilla_escenarios(modelo, datos, variable, mover=None, puntos=25,
                       puntos_mover=5, centro="mediana", nivel=0.95):
    """Predice a lo largo de una variable, con las demas fijas en su centro.

    Devuelve una tabla larga: una fila por (valor recorrido, escenario), con la
    prediccion y su banda. Las demas variables NO se dejan en cero —eso es lo
    que hace casi todo el mundo y produce perfiles imposibles, como una vivienda
    con cero anos de escolaridad—: se dejan en la mediana observada.

    El recorrido va del percentil 5 al 95 y no del minimo al maximo, para no
    extrapolar sobre un solo caso extremo. Fuera del rango observado, un modelo
    lineal dice cualquier cosa con toda seguridad.
    """
    import numpy as np
    import pandas as pd

    nombres = list(getattr(getattr(modelo, "model", None), "exog_names", None) or [])
    if not nombres:
        raise ValueError(
            "Este modelo no expone los nombres de sus variables, asi que no se puede simular. "
            "Funciona con MCO, logit, probit y GLM."
        )
    constantes = {"const", "Intercept", "intercept"}

    def centro_de(col):
        v = pd.to_numeric(datos[col], errors="coerce").dropna()
        if not len(v):
            raise ValueError(f"La columna «{col}» no tiene valores numericos.")
        return float(v.median() if centro == "mediana" else v.mean())

    base = {}
    for n in nombres:
        if n in constantes:
            base[n] = 1.0
        elif n in datos.columns:
            base[n] = centro_de(n)
        else:
            raise ValueError(
                f"La columna «{n}» que uso el modelo no esta en los datos que llegan a este bloque."
            )
    for col in [variable] + ([mover] if mover else []):
        if col not in base or col in constantes:
            raise ValueError(f"«{col}» no es una de las variables explicativas del modelo.")

    def rejilla(col, k):
        v = pd.to_numeric(datos[col], errors="coerce").dropna()
        return list(np.linspace(float(v.quantile(0.05)), float(v.quantile(0.95)), int(k)))

    xs = rejilla(variable, puntos)
    escenarios = rejilla(mover, puntos_mover) if mover else [float("nan")]
    alfa = 1.0 - float(nivel)
    partes = []
    for m in escenarios:
        X = pd.DataFrame([dict(base) for _ in xs])[nombres]
        X[variable] = xs
        if mover:
            X[mover] = m
        marco = modelo.get_prediction(X).summary_frame(alpha=alfa)
        media = marco["mean"] if "mean" in marco else marco.iloc[:, 0]
        bajo = marco["mean_ci_lower"] if "mean_ci_lower" in marco else media
        alto = marco["mean_ci_upper"] if "mean_ci_upper" in marco else media
        partes.append(pd.DataFrame({
            "valor": xs,
            "escenario": [m] * len(xs),
            "prediccion": np.asarray(media, dtype=float),
            "banda_baja": np.asarray(bajo, dtype=float),
            "banda_alta": np.asarray(alto, dtype=float),
        }))
    tabla = pd.concat(partes, ignore_index=True)
    tabla.attrs["variable"] = variable
    tabla.attrs["mover"] = mover
    tabla.attrs["respuesta"] = str(getattr(getattr(modelo, "model", None), "endog_names", "") or "y")
    return tabla
'''))


@registrar
class QuePasaSi(EspecNodo):
    op = "escenarios.simular"
    familia = "escenarios"
    titulo = "¿Que pasa si? (proyeccion interactiva)"
    prefijo_var = "escenario"
    terminal = True
    ayuda = Ayuda(
        que_hace="Recorre una variable explicativa de punta a punta, deja las demas en su mediana y "
                 "proyecta la respuesta con su banda. Si eliges una segunda variable, calcula una "
                 "curva por cada valor de esa segunda y las entrega todas, para moverlas con un control.",
        cuando_usarlo="Cuando la pregunta no es «cuanto vale el coeficiente» sino «a donde llega el "
                      "precio si el ingreso sube». Un coeficiente en logaritmos no se lee; una curva si.",
        interpretacion="La banda es el intervalo del valor ESPERADO, no el de una vivienda concreta: "
                       "una sola propiedad puede caer bastante fuera. Fuera del rango observado el "
                       "modelo no sabe nada, por eso el recorrido se corta en los percentiles 5 y 95.",
        supuestos=["El modelo se toma como dado: si esta mal especificado, la proyeccion hereda el error.",
                   "Mover una variable dejando el resto fija supone que las demas NO responden. "
                   "Si el ingreso sube, la escolaridad tambien suele subir."],
        advertencias=["Esto es una proyeccion del modelo, no un pronostico del mercado. Todo lo que "
                      "sale aqui es estimacion y va marcado en ambar."],
        referencia="Long y Freese, «Regression Models for Categorical Dependent Variables», cap. 4",
        equivalente={"stata": "margins, at(x = (...))", "r": "ggeffects::ggpredict()",
                     "eviews": "Forecast / Scenario"},
    )
    entradas = [Puerto(nombre="modelo", tipo="modelo"),
                Puerto(nombre="datos", tipo="tabla",
                       descripcion="La misma tabla con la que se estimo el modelo")]
    salidas = [Puerto(nombre="escenarios", tipo="tabla", titulo="Proyeccion por escenario")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        variable: str = CampoColumna(tipo="numerica", title="Variable que se recorre (eje horizontal)")
        mover: str | None = CampoColumna(
            tipo="numerica", default=None, required=False,
            title="Variable del control deslizante (opcional)")
        puntos: int = Field(default=25, ge=5, le=200, title="Puntos del recorrido")
        puntos_mover: int = Field(default=5, ge=2, le=12, title="Escenarios del control")
        centro: Literal["mediana", "media"] = Field(
            default="mediana", title="Las demas variables se fijan en su…")

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("rejilla_escenarios")
        mover = ctx.p("mover")
        ctx.nota(
            f"Proyeccion de «{ctx.p('variable')}» en {ctx.p('puntos')} puntos, del percentil 5 al 95. "
            f"Las demas variables quedan fijas en su {ctx.p('centro')}."
            + (f" Un escenario por cada uno de {ctx.p('puntos_mover')} valores de «{mover}»."
               if mover else ""))
        ctx.nota("Todo lo que produce este bloque es estimacion del modelo, no dato observado.")
        ctx.emitir(
            "SAL = rejilla_escenarios(MOD, ENT, VAR, mover=MOV, puntos=N, "
            "puntos_mover=K, centro=C)",
            SAL=ctx.salida("escenarios"), MOD=ctx.entrada("modelo"), ENT=ctx.entrada("datos"),
            VAR=ctx.plit("variable"), MOV=ctx.plit("mover"), N=ctx.plit("puntos"),
            K=ctx.plit("puntos_mover"), C=ctx.plit("centro"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"escenarios": Esquema(columnas=[
            Columna(nombre="valor", tipo="numerica",
                    nota="El valor recorrido de la variable del eje horizontal."),
            Columna(nombre="escenario", tipo="numerica",
                    nota="El valor de la variable del control. Vacio si no se eligio ninguna."),
            Columna(nombre="prediccion", tipo="numerica", es_estimado=True),
            Columna(nombre="banda_baja", tipo="numerica", es_estimado=True),
            Columna(nombre="banda_alta", tipo="numerica", es_estimado=True)])}

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import _limpio, tabla_a_json

        tabla = salidas.get("escenarios")
        if tabla is None:
            return {}
        estimadas = ["prediccion", "banda_baja", "banda_alta"]
        # El orden de este diccionario es el orden en pantalla: primero la
        # grafica, que es la respuesta, y debajo la tabla que la respalda.
        out: dict[str, Any] = {}

        # El artefacto interactivo. Lleva las curvas YA calculadas: el control
        # del navegador escoge cual se ensena, no estima ninguna.
        try:
            variable = tabla.attrs.get("variable") or params.variable  # type: ignore[attr-defined]
            mover = tabla.attrs.get("mover")
            respuesta = tabla.attrs.get("respuesta") or "respuesta"
            escenarios = []
            claves = list(dict.fromkeys(tabla["escenario"].tolist()))
            for clave in claves:
                if clave != clave:      # NaN: no hay control, es una sola curva
                    t = tabla
                else:
                    t = tabla[tabla["escenario"] == clave]
                escenarios.append({
                    "escenario": None if clave != clave else _limpio(clave),
                    "y": [_limpio(v) for v in t["prediccion"]],
                    "bajo": [_limpio(v) for v in t["banda_baja"]],
                    "alto": [_limpio(v) for v in t["banda_alta"]],
                })
            primera = tabla[tabla["escenario"] == claves[0]] if claves[0] == claves[0] else tabla
            out["proyeccion"] = {
                "tipo": "proyeccion",
                "titulo": f"¿Qué pasa si cambia «{variable}»?",
                "x": {"nombre": variable, "valores": [_limpio(v) for v in primera["valor"]]},
                "control": ({"nombre": mover,
                             "valores": [_limpio(c) for c in claves]} if mover else None),
                "respuesta": respuesta,
                "series": escenarios,
                "nota": ("Todo lo dibujado es estimación del modelo. La banda es del valor esperado, "
                         "no la de un caso individual."),
            }
        except Exception:
            pass
        out["escenarios"] = tabla_a_json(tabla, titulo="Proyección por escenario",
                                         estimadas=estimadas)
        return out
