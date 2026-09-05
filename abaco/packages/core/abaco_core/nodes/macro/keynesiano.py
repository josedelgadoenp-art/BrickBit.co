"""Multiplicador keynesiano del gasto."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ...graph.spec import Columna, Esquema
from ...registry.base import Ayuda, Ayudante, EspecNodo, Puerto, registrar, registrar_ayudante

registrar_ayudante(Ayudante(
    nombre="multiplicador_keynesiano",
    imports=[("pandas", "pd")],
    fuente='''
def multiplicador_keynesiano(propension_consumo, tasa_impuestos=0.0,
                             propension_importar=0.0, gasto_adicional=0.0):
    """Multiplicador del gasto en una economia abierta con impuestos.

        k = 1 / (1 - c(1 - t) + m)

    c: propension marginal a consumir     t: tasa impositiva marginal
    m: propension marginal a importar

    Cada peso de gasto se vuelve ingreso de alguien; esa persona consume una
    fraccion c, pero antes paga impuestos (t) y parte de su consumo se va al
    extranjero (m). Esas dos filtraciones son las que frenan la cadena.
    """
    c, t, m = float(propension_consumo), float(tasa_impuestos), float(propension_importar)
    filtracion = 1 - c * (1 - t) + m
    if filtracion <= 0:
        raise ValueError(
            "Las filtraciones (ahorro, impuestos, importaciones) no alcanzan a frenar la cadena: "
            "con estos parametros el multiplicador seria infinito. Revisa la propension a consumir."
        )
    k = 1.0 / filtracion
    return pd.DataFrame([{
        "propension_consumo": c,
        "tasa_impuestos": t,
        "propension_importar": m,
        "filtracion_por_peso": filtracion,
        "multiplicador": k,
        "gasto_adicional": float(gasto_adicional),
        "efecto_total_sobre_pib": float(gasto_adicional) * k,
        "lectura": (f"Cada peso de gasto publico genera {k:.2f} pesos de producto. "
                    f"De cada peso de ingreso, {filtracion:.2f} se filtra fuera del circuito."),
    }])
''',
))


@registrar
class MultiplicadorKeynesiano(EspecNodo):
    op = "macro.multiplicador_keynesiano"
    familia = "macro"
    titulo = "Multiplicador keynesiano del gasto"
    prefijo_var = "multiplicador"
    terminal = True
    ayuda = Ayuda(
        que_hace="Calcula cuanto producto genera cada peso de gasto adicional, descontando lo que se "
                 "filtra en ahorro, impuestos e importaciones.",
        cuando_usarlo="Para dimensionar el efecto de un programa de gasto o de inversion publica.",
        interpretacion="Un multiplicador de 1.6 significa que 100 pesos de gasto generan 160 de producto. "
                       "Cuanto mas abierta la economia y mas alta la carga fiscal, mas chico el multiplicador.",
        supuestos=["Economia con capacidad ociosa: si esta en pleno empleo, el efecto se va a precios.",
                   "Sin respuesta de la politica monetaria: si el banco central sube la tasa para "
                   "compensar, el multiplicador real es menor.",
                   "Propensiones constantes en el rango del choque."],
        advertencias=["La evidencia empirica pone el multiplicador del gasto entre 0.5 y 2.5 segun el "
                      "pais y el momento del ciclo. Este calculo es el de libro de texto: sirve para "
                      "ordenar magnitudes, no para prometer resultados.",
                      "En recesion los multiplicadores son mas altos que en expansion (Auerbach y Gorodnichenko, 2012)."],
        referencia="Keynes (1936); Blanchard, «Macroeconomics», cap. 3",
    )
    salidas = [Puerto(nombre="resultado", tipo="tabla", titulo="Multiplicador")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        propension_consumo: float = Field(default=0.65, gt=0.0, lt=1.0)
        tasa_impuestos: float = Field(default=0.16, ge=0.0, lt=1.0)
        propension_importar: float = Field(default=0.30, ge=0.0, lt=1.0)
        gasto_adicional: float = Field(default=0.0, ge=0.0)

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("multiplicador_keynesiano")
        ctx.nota("k = 1 / (1 - c(1 - t) + m). Las filtraciones son ahorro, impuestos e importaciones.")
        ctx.emitir("SAL = multiplicador_keynesiano(C, tasa_impuestos=T, propension_importar=M, "
                   "gasto_adicional=G)",
                   SAL=ctx.salida("resultado"), C=ctx.plit("propension_consumo"),
                   T=ctx.plit("tasa_impuestos"), M=ctx.plit("propension_importar"),
                   G=ctx.plit("gasto_adicional"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"resultado": Esquema(columnas=[
            Columna(nombre="propension_consumo", tipo="numerica"),
            Columna(nombre="tasa_impuestos", tipo="numerica"),
            Columna(nombre="propension_importar", tipo="numerica"),
            Columna(nombre="filtracion_por_peso", tipo="numerica", es_estimado=True),
            Columna(nombre="multiplicador", tipo="numerica", es_estimado=True),
            Columna(nombre="gasto_adicional", tipo="numerica"),
            Columna(nombre="efecto_total_sobre_pib", tipo="numerica", es_estimado=True),
            Columna(nombre="lectura", tipo="texto")])}

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import tabla_a_json

        r = salidas.get("resultado")
        if r is None:
            return {}
        return {"resultado": tabla_a_json(
            r, titulo="Multiplicador keynesiano",
            estimadas=["multiplicador", "efecto_total_sobre_pib", "filtracion_por_peso"])}
