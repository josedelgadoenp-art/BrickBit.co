"""Econometria clasica: MCO, variables instrumentales, eleccion discreta, cuantiles.

Ningun estimador se reimplementa. Abak orquesta statsmodels. Reimplementar
econometria es la forma mas rapida de perder la confianza que este producto
necesita: si un metodo no esta en una biblioteca respetada, no esta en Abak.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...graph.spec import Columna, Esquema
from ...registry.base import Ayuda, CampoColumna, CampoColumnas, EspecNodo, Puerto, registrar

ERRORES = {
    "clasicos": "Errores clasicos: suponen varianza constante. Casi nunca se cumple con datos economicos.",
    "HC1": "Errores robustos a heterocedasticidad (HC1). Es el valor por omision razonable.",
    "HC3": "Errores robustos HC3: mas conservadores que HC1, recomendados con muestras chicas.",
    "HAC": "Errores robustos a heterocedasticidad Y autocorrelacion (Newey-West). Para series de tiempo.",
    "cluster": "Errores agrupados: admiten correlacion arbitraria dentro de cada grupo.",
}


def _ajuste(ctx: Any) -> tuple[str, dict[str, Any]]:
    """La clausula `.fit(...)` segun el tipo de errores elegido."""
    tipo = ctx.p("errores")
    if tipo == "clasicos":
        return ".fit()", {}
    if tipo == "cluster":
        return (".fit(cov_type='cluster', cov_kwds={'groups': ENT[GRUPO]})",
                {"ENT": ctx.entrada("datos"), "GRUPO": ctx.lit(ctx.p("cluster_por"))})
    if tipo == "HAC":
        return ".fit(cov_type='HAC', cov_kwds={'maxlags': REZ}, use_t=True)", {"REZ": ctx.lit(ctx.p("rezagos_hac"))}
    return ".fit(cov_type=TIPO)", {"TIPO": ctx.lit(tipo)}


class _BaseRegresion(EspecNodo):
    """Lo comun a todo lo que estima y ~ X: armar el diseno y resumir."""

    familia = "econometria"
    prefijo_var = "modelo"
    terminal = True
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="modelo", tipo="modelo"),
               Puerto(nombre="residuos", tipo="tabla", titulo="Ajuste y residuos", requerido=False)]

    def _diseno(self, ctx: Any) -> None:
        """Emite la matriz de diseno. Comun a MCO, logit, probit y cuantiles."""
        ctx.importar("statsmodels.api", "sm")
        X = ctx.temporal("X")
        y = ctx.temporal("y")
        ctx.emitir("Y = ENT[DEP]", Y=y, ENT=ctx.entrada("datos"), DEP=ctx.plit("y"))
        if ctx.p("constante"):
            ctx.emitir("X = sm.add_constant(ENT[INDEP], has_constant='add')",
                       X=X, ENT=ctx.entrada("datos"), INDEP=ctx.plit("x"))
        else:
            ctx.emitir("X = ENT[INDEP]", X=X, ENT=ctx.entrada("datos"), INDEP=ctx.plit("x"))
        self._X, self._y = X, y

    def _residuos(self, ctx: Any) -> None:
        ctx.importar("pandas", "pd")
        ctx.emitir(
            "RES = pd.DataFrame({'observado': Y, 'ajustado': MOD.fittedvalues, "
            "'residuo': MOD.resid}, index=Y.index)",
            RES=ctx.salida("residuos"), Y=self._y, MOD=ctx.ref_salida("modelo"))

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"residuos": Esquema(columnas=[
            Columna(nombre="observado", tipo="numerica"),
            Columna(nombre="ajustado", tipo="numerica", es_estimado=True),
            Columna(nombre="residuo", tipo="numerica", es_estimado=True),
        ])}

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import modelo_a_json, tabla_a_json

        salida: dict[str, Any] = {}
        if (mod := salidas.get("modelo")) is not None:
            salida["modelo"] = modelo_a_json(mod, titulo=self.titulo)
        if (res := salidas.get("residuos")) is not None:
            salida["residuos"] = tabla_a_json(res, titulo="Ajuste y residuos",
                                              estimadas=["ajustado", "residuo"])
        return salida


@registrar
class MCO(_BaseRegresion):
    op = "econometria.mco"
    version = "1.0.0"
    titulo = "Minimos cuadrados (MCO)"
    ayuda = Ayuda(
        que_hace="Ajusta una recta que minimiza la suma de los errores al cuadrado. Es el punto de "
                 "partida de casi todo el analisis economico.",
        cuando_usarlo="Cuando quieres explicar una variable numerica continua con otras variables.",
        interpretacion="Cada coeficiente dice cuanto cambia la variable dependiente si esa explicativa "
                       "sube una unidad y las demas se quedan igual. Las estrellas marcan significancia: "
                       "*** al 1%, ** al 5%, * al 10%. Que un coeficiente sea significativo no lo vuelve "
                       "grande ni importante: mira tambien su tamano en las unidades del problema.",
        supuestos=["El efecto es lineal en los parametros",
                   "Las explicativas no estan correlacionadas con el error (si lo estan, MCO esta sesgado "
                   "y necesitas variables instrumentales)",
                   "Errores sin autocorrelacion (si no, usa errores HAC)",
                   "Varianza constante (si no, usa errores robustos HC1 o HC3)"],
        advertencias=["Correlacion no es causalidad. MCO mide asociacion condicional; para hablar de "
                      "efecto causal hace falta un argumento de identificacion, no un R² alto."],
        referencia="Wooldridge, «Introductory Econometrics», caps. 3-8",
        equivalente={"stata": "regress y x1 x2, robust", "r": "lm(y ~ x1 + x2)",
                     "eviews": "Quick > Estimate Equation", "spss": "Analizar > Regresion > Lineales"},
    )

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        y: str = CampoColumna(tipo="numerica")
        x: list[str] = CampoColumnas(tipo="numerica", default_factory=list)
        constante: bool = True
        errores: Literal["clasicos", "HC1", "HC3", "HAC", "cluster"] = "HC1"
        cluster_por: str | None = CampoColumna(default=None)
        rezagos_hac: int = Field(default=4, ge=1, le=48)

    def emit(self, ctx: Any) -> Any:
        self._diseno(ctx)
        fit, extra = _ajuste(ctx)
        ctx.nota(f"MCO de «{ctx.p('y')}» contra {', '.join(ctx.p('x'))}.")
        ctx.nota(ERRORES[ctx.p("errores")])
        ctx.emitir(f"MOD = sm.OLS(Y, X, missing='drop'){fit}",
                   MOD=ctx.salida("modelo"), Y=self._y, X=self._X, **extra)
        self._residuos(ctx)
        return ctx.fin()


@registrar
class VariablesInstrumentales(_BaseRegresion):
    op = "econometria.iv"
    titulo = "Variables instrumentales (MC2E)"
    ayuda = Ayuda(
        que_hace="Estima por minimos cuadrados en dos etapas cuando una explicativa esta correlacionada "
                 "con el error (endogeneidad).",
        cuando_usarlo="Cuando la causalidad va en las dos direcciones, hay una variable omitida importante, "
                      "o la explicativa se mide con error. El caso clasico: precio y cantidad se determinan juntos.",
        interpretacion="El coeficiente de la variable instrumentada es el efecto causal, SI los instrumentos "
                       "son validos. Revisa el estadistico F de la primera etapa: por debajo de 10, los "
                       "instrumentos son debiles y el remedio es peor que la enfermedad.",
        supuestos=["Relevancia: los instrumentos explican a la variable endogena (F de primera etapa > 10)",
                   "Exclusion: los instrumentos afectan a la dependiente SOLO a traves de la endogena. "
                   "Esto no se puede probar con datos: se defiende con un argumento."],
        advertencias=["Instrumentos debiles sesgan MC2E hacia MCO y ademas rompen la inferencia."],
        referencia="Angrist y Pischke, «Mostly Harmless Econometrics», cap. 4",
        equivalente={"stata": "ivregress 2sls y x (endog = instr)", "r": "AER::ivreg()"},
    )

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        y: str = CampoColumna(tipo="numerica")
        endogenas: list[str] = CampoColumnas(tipo="numerica", default_factory=list)
        instrumentos: list[str] = CampoColumnas(tipo="numerica", default_factory=list)
        exogenas: list[str] = CampoColumnas(tipo="numerica", default_factory=list)
        constante: bool = True

    def emit(self, ctx: Any) -> Any:
        ctx.importar("statsmodels.api", "sm")
        ctx.importar("statsmodels.sandbox.regression.gmm", "gmm")
        y, endo = ctx.temporal("y"), ctx.temporal("endo")
        X, Z = ctx.temporal("X"), ctx.temporal("Z")
        ctx.nota(f"Primera etapa: {', '.join(ctx.p('endogenas'))} se explica con los instrumentos "
                 f"{', '.join(ctx.p('instrumentos'))} y las exogenas.")
        ctx.nota("Segunda etapa: se usa el valor predicho de la endogena en lugar del observado.")
        ctx.emitir("Y = ENT[DEP]", Y=y, ENT=ctx.entrada("datos"), DEP=ctx.plit("y"))
        ctx.emitir("E = ENT[ENDO]", E=endo, ENT=ctx.entrada("datos"), ENDO=ctx.plit("endogenas"))
        cons = "sm.add_constant(V, has_constant='add')" if ctx.p("constante") else "V"
        ctx.emitir(f"X = {cons.replace('V', 'ENT[EXO].join(E)')}",
                   X=X, ENT=ctx.entrada("datos"), EXO=ctx.plit("exogenas"), E=endo)
        ctx.emitir(f"Z = {cons.replace('V', 'ENT[EXO].join(ENT[INSTR])')}",
                   Z=Z, ENT=ctx.entrada("datos"), EXO=ctx.plit("exogenas"), INSTR=ctx.plit("instrumentos"))
        ctx.emitir("MOD = gmm.IV2SLS(Y, X, instrument=Z).fit()",
                   MOD=ctx.salida("modelo"), Y=y, X=X, Z=Z)
        ctx.importar("pandas", "pd")
        ctx.emitir("RES = pd.DataFrame({'observado': Y, 'ajustado': MOD.fittedvalues, "
                   "'residuo': MOD.resid}, index=Y.index)",
                   RES=ctx.salida("residuos"), Y=y, MOD=ctx.ref_salida("modelo"))
        return ctx.fin()


@registrar
class EleccionDiscreta(_BaseRegresion):
    op = "econometria.eleccion_discreta"
    titulo = "Logit / Probit"
    ayuda = Ayuda(
        que_hace="Modela una variable que solo toma dos valores (si/no, 1/0): probabilidad de que ocurra.",
        cuando_usarlo="¿Que determina que un hogar tenga credito? ¿Que una empresa exporte? ¿Que alguien "
                      "compre en vez de rentar?",
        interpretacion="Los coeficientes crudos NO son el efecto sobre la probabilidad; solo su signo y su "
                       "significancia se leen directo. Para el tamano del efecto usa los efectos marginales "
                       "promedio, que este nodo calcula aparte: ahi si, «una unidad mas de X sube la "
                       "probabilidad en tantos puntos porcentuales».",
        supuestos=["La variable dependiente debe ser 0/1",
                   "Logit y probit dan casi siempre las mismas conclusiones; difieren en la cola"],
        advertencias=["Si una explicativa predice perfectamente el resultado, el modelo no converge. "
                      "Eso es informacion, no una falla del software."],
        referencia="Wooldridge, cap. 17",
        equivalente={"stata": "logit y x1 x2 / margins, dydx(*)", "r": "glm(family=binomial)"},
    )
    salidas = [Puerto(nombre="modelo", tipo="modelo"),
               Puerto(nombre="marginales", tipo="tabla", titulo="Efectos marginales", requerido=False)]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        y: str = CampoColumna()
        x: list[str] = CampoColumnas(tipo="numerica", default_factory=list)
        familia: Literal["logit", "probit"] = "logit"
        constante: bool = True
        errores: Literal["clasicos", "HC1", "HC3", "cluster"] = "HC1"
        cluster_por: str | None = CampoColumna(default=None)
        rezagos_hac: int = 4

    def emit(self, ctx: Any) -> Any:
        self._diseno(ctx)
        fit, extra = _ajuste(ctx)
        clase = "sm.Logit" if ctx.p("familia") == "logit" else "sm.Probit"
        ctx.nota(f"{ctx.p('familia').capitalize()} de «{ctx.p('y')}» (0/1) contra {', '.join(ctx.p('x'))}.")
        ctx.nota("Los efectos marginales promedio estan en la segunda salida: esos si se leen "
                 "como puntos porcentuales de probabilidad.")
        ctx.emitir(f"MOD = {clase}(Y, X, missing='drop'){fit}",
                   MOD=ctx.salida("modelo"), Y=self._y, X=self._X, **extra)
        ctx.emitir("MARG = MOD.get_margeff(at='overall', method='dydx').summary_frame()",
                   MARG=ctx.salida("marginales"), MOD=ctx.ref_salida("modelo"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"marginales": Esquema(columnas=[
            Columna(nombre="dy/dx", tipo="numerica", es_estimado=True),
            Columna(nombre="Std. Err.", tipo="numerica", es_estimado=True),
            Columna(nombre="Pr(>|z|)", tipo="numerica", es_estimado=True),
        ])}

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import modelo_a_json, tabla_a_json

        salida: dict[str, Any] = {}
        if (mod := salidas.get("modelo")) is not None:
            salida["modelo"] = modelo_a_json(mod, titulo=f"{params.familia.capitalize()}")  # type: ignore[attr-defined]
        if (m := salidas.get("marginales")) is not None:
            salida["marginales"] = tabla_a_json(m, titulo="Efectos marginales promedio")
        return salida


@registrar
class Cuantilica(_BaseRegresion):
    op = "econometria.cuantilica"
    titulo = "Regresion por cuantiles"
    ayuda = Ayuda(
        que_hace="Estima el efecto de las explicativas sobre un cuantil de la dependiente, no sobre su promedio.",
        cuando_usarlo="Cuando sospechas que el efecto es distinto arriba y abajo de la distribucion: "
                      "la escolaridad puede pesar mucho mas en los ingresos altos que en los bajos.",
        interpretacion="El coeficiente en el cuantil 0.9 dice como se mueve el percentil 90 de la "
                       "dependiente. Compara varios cuantiles: si los coeficientes cambian mucho, "
                       "el promedio estaba escondiendo la historia.",
        supuestos=["No supone varianza constante ni normalidad: es mas robusto que MCO ante valores extremos."],
        referencia="Koenker y Bassett (1978)",
        equivalente={"stata": "qreg y x, quantile(.9)", "r": "quantreg::rq()"},
    )

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        y: str = CampoColumna(tipo="numerica")
        x: list[str] = CampoColumnas(tipo="numerica", default_factory=list)
        cuantil: float = Field(default=0.5, gt=0.0, lt=1.0)
        constante: bool = True

    def emit(self, ctx: Any) -> Any:
        self._diseno(ctx)
        q = ctx.p("cuantil")
        ctx.nota(f"Cuantil {q:g}"
                 + (" (la mediana)." if abs(q - 0.5) < 1e-9 else f" (percentil {q * 100:g}).") )
        ctx.emitir("MOD = sm.QuantReg(Y, X, missing='drop').fit(q=Q)",
                   MOD=ctx.salida("modelo"), Y=self._y, X=self._X, Q=ctx.plit("cuantil"))
        self._residuos(ctx)
        return ctx.fin()
