"""Cointegracion y descomposicion en tendencia y ciclo."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...graph.spec import Columna, Esquema
from ...registry.base import (Ayuda, Ayudante, CampoColumna, CampoColumnas, EspecNodo,
                              Puerto, registrar, registrar_ayudante)

registrar_ayudante(Ayudante(
    nombre="tabla_johansen",
    imports=[("pandas", "pd")],
    fuente='''
def tabla_johansen(datos, columnas, det_order=0, k_ar_diff=1):
    """Prueba de la traza de Johansen: cuantas relaciones de largo plazo hay.

    Se recorre r = 0, 1, 2... y se compara el estadistico de la traza contra su
    valor critico al 5%. El primer r que NO se rechaza es el numero de
    relaciones de cointegracion.
    """
    from statsmodels.tsa.vector_ar.vecm import coint_johansen

    y = datos[columnas].dropna()
    res = coint_johansen(y, det_order, k_ar_diff)
    filas = []
    for i in range(len(columnas)):
        traza = float(res.lr1[i])
        critico = float(res.cvt[i, 1])  # columna 1 = 5%
        filas.append({
            "hipotesis_nula": f"r <= {i}" if i else "r = 0 (ninguna relacion)",
            "estadistico_traza": traza,
            "valor_critico_5pct": critico,
            "rechaza": bool(traza > critico),
            "lectura": ("Se rechaza: hay al menos una relacion mas." if traza > critico
                        else f"No se rechaza: hay {i} relacion(es) de cointegracion."),
        })
    return pd.DataFrame(filas)
''',
))

registrar_ayudante(Ayudante(
    nombre="descomponer_hp",
    imports=[("pandas", "pd")],
    fuente='''
def descomponer_hp(serie, lamb=1600):
    """Filtro de Hodrick-Prescott: separa tendencia de ciclo.

    lambda por convencion: 1600 trimestral, 129600 mensual, 6.25 anual
    (Ravn y Uhlig, 2002).

    Hamilton (2018) argumenta que el HP genera dinamicas espurias en los
    extremos y que casi nadie deberia usarlo. Se incluye porque sigue siendo el
    estandar de facto en bancos centrales, no porque sea el mejor filtro; el
    nodo tambien ofrece la alternativa de Hamilton.
    """
    from statsmodels.tsa.filters.hp_filter import hpfilter

    ciclo, tendencia = hpfilter(serie.dropna(), lamb=lamb)
    return pd.DataFrame({"observado": serie.dropna(), "tendencia": tendencia, "ciclo": ciclo})
''',
))


@registrar
class Cointegracion(EspecNodo):
    op = "series.cointegracion"
    familia = "series"
    titulo = "Cointegracion (Johansen)"
    prefijo_var = "cointegracion"
    terminal = True
    ayuda = Ayuda(
        que_hace="Busca si varias series que individualmente tienen raiz unitaria se mueven juntas en el "
                 "largo plazo.",
        cuando_usarlo="Cuando teoricamente esperas una relacion de equilibrio: consumo e ingreso, precios "
                      "y salarios, tipo de cambio y diferencial de precios.",
        interpretacion="La tabla recorre r = 0, 1, 2... El primer renglon que NO se rechaza dice cuantas "
                       "relaciones de largo plazo hay. Si hay cointegracion, la regresion en niveles NO "
                       "es espuria, y el modelo correcto es un VECM, no un VAR en diferencias.",
        supuestos=["Todas las series deben ser integradas del mismo orden, normalmente I(1). "
                   "Compruebalo antes con la prueba de raiz unitaria."],
        advertencias=["La prueba es sensible al numero de rezagos y al termino deterministico. "
                      "Reporta que elegiste, o el resultado no es reproducible."],
        referencia="Johansen (1991); Enders, cap. 6",
        equivalente={"stata": "vecrank", "r": "urca::ca.jo()", "eviews": "Johansen Cointegration Test"},
    )
    entradas = [Puerto(nombre="datos", tipo="serie")]
    salidas = [Puerto(nombre="traza", tipo="tabla", titulo="Prueba de la traza"),
               Puerto(nombre="modelo", tipo="modelo", titulo="VECM", requerido=False)]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        variables: list[str] = CampoColumnas(tipo="numerica", default_factory=list)
        rezagos: int = Field(default=1, ge=1, le=8)
        termino_deterministico: Literal["ninguno", "constante", "tendencia"] = "constante"
        estimar_vecm: bool = True
        relaciones: int = Field(default=1, ge=1, le=8)

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("tabla_johansen")
        orden = {"ninguno": -1, "constante": 0, "tendencia": 1}[ctx.p("termino_deterministico")]
        ctx.nota(f"Johansen con {ctx.p('rezagos')} rezago(s) en diferencias y termino "
                 f"«{ctx.p('termino_deterministico')}».")
        ctx.emitir("SAL = tabla_johansen(ENT, VARS, det_order=DET, k_ar_diff=REZ)",
                   SAL=ctx.salida("traza"), ENT=ctx.entrada("datos"), VARS=ctx.plit("variables"),
                   DET=ctx.lit(orden), REZ=ctx.plit("rezagos"))
        if ctx.p("estimar_vecm"):
            ctx.importar("VECM", desde="statsmodels.tsa.vector_ar.vecm")
            det = {"ninguno": "n", "constante": "co", "tendencia": "ci"}[ctx.p("termino_deterministico")]
            ctx.nota(f"VECM con {ctx.p('relaciones')} relacion(es) de cointegracion. El coeficiente de "
                     "ajuste (alpha) dice que tan rapido vuelve el sistema al equilibrio tras desviarse.")
            ctx.emitir("MOD = VECM(ENT[VARS].dropna(), k_ar_diff=REZ, coint_rank=R, deterministic=DET).fit()",
                       MOD=ctx.salida("modelo"), ENT=ctx.entrada("datos"), VARS=ctx.plit("variables"),
                       REZ=ctx.plit("rezagos"), R=ctx.plit("relaciones"), DET=ctx.lit(det))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"traza": Esquema(columnas=[
            Columna(nombre="hipotesis_nula", tipo="texto"),
            Columna(nombre="estadistico_traza", tipo="numerica"),
            Columna(nombre="valor_critico_5pct", tipo="numerica"),
            Columna(nombre="rechaza", tipo="booleana"), Columna(nombre="lectura", tipo="texto")])}


@registrar
class TendenciaCiclo(EspecNodo):
    op = "series.ciclo"
    familia = "series"
    titulo = "Separar tendencia y ciclo"
    prefijo_var = "ciclo"
    ayuda = Ayuda(
        que_hace="Parte una serie en su tendencia de largo plazo y su ciclo alrededor de ella.",
        cuando_usarlo="Para medir la brecha del producto, el componente ciclico del empleo o del credito.",
        interpretacion="El ciclo es la desviacion respecto a la tendencia. Positivo significa por encima "
                       "de su nivel de largo plazo. Es una construccion, no un dato observado, y por eso "
                       "sale marcado en ambar.",
        supuestos=["Lambda del filtro HP por convencion: 1600 trimestral, 129600 mensual, 6.25 anual."],
        advertencias=["Hamilton (2018) mostro que el filtro HP inventa dinamicas que no estan en los datos, "
                      "sobre todo al final de la muestra, que es justo donde se toman las decisiones. "
                      "Por eso este nodo ofrece tambien su alternativa, y por eso conviene comparar las dos."],
        referencia="Hodrick y Prescott (1997); Hamilton, «Why You Should Never Use the HP Filter» (2018)",
        equivalente={"stata": "tsfilter hp", "r": "mFilter::hpfilter()", "eviews": "Hodrick-Prescott Filter"},
    )
    entradas = [Puerto(nombre="datos", tipo="serie")]
    salidas = [Puerto(nombre="datos", tipo="serie", titulo="Tendencia y ciclo")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        variable: str = CampoColumna(tipo="numerica")
        metodo: Literal["hp", "hamilton", "estacional"] = "hp"
        lamb: float = Field(default=1600.0, gt=0)
        periodo_estacional: int = Field(default=4, ge=2, le=52)

    def emit(self, ctx: Any) -> Any:
        metodo = ctx.p("metodo")
        if metodo == "hp":
            ctx.usar_ayudante("descomponer_hp")
            ctx.nota(f"Filtro de Hodrick-Prescott con lambda = {ctx.p('lamb'):g}.")
            ctx.emitir("SAL = descomponer_hp(ENT[VAR], lamb=LAMB)",
                       SAL=ctx.salida("datos"), ENT=ctx.entrada("datos"),
                       VAR=ctx.plit("variable"), LAMB=ctx.plit("lamb"))
        elif metodo == "hamilton":
            ctx.importar("hpfilter", desde="statsmodels.tsa.filters.hp_filter")
            ctx.importar("statsmodels.api", "sm")
            ctx.importar("pandas", "pd")
            ctx.nota("Regresion de Hamilton: la serie a h periodos adelante se explica con sus ultimos "
                     "cuatro valores. El residuo es el ciclo. No sufre el sesgo de fin de muestra del HP.")
            ctx.emitir("SAL = _hamilton_filtro(ENT[VAR], H)", SAL=ctx.salida("datos"),
                       ENT=ctx.entrada("datos"), VAR=ctx.plit("variable"),
                       H=ctx.lit(2 * ctx.p("periodo_estacional")))
            ctx.usar_ayudante("_hamilton_filtro")
        else:
            ctx.importar("seasonal_decompose", desde="statsmodels.tsa.seasonal")
            ctx.importar("pandas", "pd")
            ctx.nota(f"Descomposicion clasica en tendencia, estacionalidad y residuo, con periodo "
                     f"{ctx.p('periodo_estacional')}.")
            d = ctx.temporal("desc")
            ctx.emitir("D = seasonal_decompose(ENT[VAR].dropna(), model='additive', period=P)",
                       D=d, ENT=ctx.entrada("datos"), VAR=ctx.plit("variable"), P=ctx.plit("periodo_estacional"))
            ctx.emitir("SAL = pd.DataFrame({'observado': D.observed, 'tendencia': D.trend, "
                       "'estacional': D.seasonal, 'ciclo': D.resid})",
                       SAL=ctx.salida("datos"), D=d)
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        base = entradas.get("datos", Esquema())
        cols = [Columna(nombre="observado", tipo="numerica"),
                Columna(nombre="tendencia", tipo="numerica", es_estimado=True,
                        nota="La tendencia es una construccion del filtro, no un dato."),
                Columna(nombre="ciclo", tipo="numerica", es_estimado=True)]
        if params.metodo == "estacional":  # type: ignore[attr-defined]
            cols.append(Columna(nombre="estacional", tipo="numerica", es_estimado=True))
        return {"datos": Esquema(columnas=cols, indice_temporal=base.indice_temporal)}

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import tabla_a_json

        d = salidas.get("datos")
        if d is None:
            return {}
        return {"datos": tabla_a_json(d, titulo="Tendencia y ciclo",
                                      estimadas=["tendencia", "ciclo", "estacional"])}


registrar_ayudante(Ayudante(
    nombre="_hamilton_filtro",
    imports=[("pandas", "pd"), ("statsmodels.api", "sm")],
    fuente='''
def _hamilton_filtro(serie, h=8, p=4):
    """Alternativa de Hamilton (2018) al filtro HP.

    y(t+h) se regresa contra y(t), y(t-1), ..., y(t-p+1). El valor ajustado es
    la tendencia y el residuo es el ciclo. No usa informacion del futuro, asi
    que no tiene el sesgo de fin de muestra que hace peligroso al HP justo
    donde se toman las decisiones.
    """
    s = serie.dropna()
    X = pd.concat([s.shift(h + i) for i in range(p)], axis=1)
    X.columns = [f"rez_{h + i}" for i in range(p)]
    X = sm.add_constant(X)
    marco = pd.concat([s.rename("y"), X], axis=1).dropna()
    ajuste = sm.OLS(marco["y"], marco.drop(columns="y")).fit()
    return pd.DataFrame({
        "observado": marco["y"],
        "tendencia": ajuste.fittedvalues,
        "ciclo": ajuste.resid,
    })
''',
))
