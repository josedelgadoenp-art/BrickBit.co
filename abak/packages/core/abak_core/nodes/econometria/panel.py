"""Datos de panel: efectos fijos, aleatorios y la prueba de Hausman."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from ...graph.spec import Esquema
from ...registry.base import (Ayuda, Ayudante, CampoColumna, CampoColumnas, EspecNodo,
                              Puerto, registrar, registrar_ayudante)

# El ayudante viaja al script exportado. Es la razon por la que el .py corre sin
# tener Abak instalado: la prueba de Hausman va escrita ahi, a la vista.
registrar_ayudante(Ayudante(
    nombre="prueba_hausman",
    imports=[("numpy", "np"), ("scipy.stats", "stats")],
    fuente='''
def prueba_hausman(fijos, aleatorios):
    """Hausman: ¿los efectos individuales estan correlacionados con las explicativas?

    H0: los dos estimadores son consistentes, y aleatorios es ademas eficiente.
    Rechazar H0 significa que efectos aleatorios esta sesgado y hay que usar fijos.

    Se comparan solo los coeficientes que aparecen en ambos modelos (aleatorios
    incluye la constante, fijos no) y se usa la pseudo-inversa porque la
    diferencia de matrices de varianza suele salir casi singular.
    """
    comunes = [c for c in fijos.params.index if c in aleatorios.params.index]
    b_dif = fijos.params[comunes] - aleatorios.params[comunes]
    v_dif = fijos.cov.loc[comunes, comunes] - aleatorios.cov.loc[comunes, comunes]
    estadistico = float(b_dif.values @ np.linalg.pinv(v_dif.values) @ b_dif.values)
    gl = len(comunes)
    p = float(1 - stats.chi2.cdf(estadistico, gl))
    return {
        "estadistico_chi2": estadistico,
        "grados_libertad": gl,
        "p_valor": p,
        "conclusion": ("Se rechaza H0: usa efectos FIJOS (los aleatorios estan sesgados)."
                       if p < 0.05 else
                       "No se rechaza H0: efectos ALEATORIOS es valido y mas eficiente."),
    }
''',
))


@registrar
class Panel(EspecNodo):
    op = "econometria.panel"
    familia = "econometria"
    titulo = "Panel: efectos fijos o aleatorios"
    prefijo_var = "panel_mod"
    terminal = True
    ayuda = Ayuda(
        que_hace="Estima con datos que siguen a las mismas entidades a lo largo del tiempo, controlando "
                 "por lo que no cambia dentro de cada entidad.",
        cuando_usarlo="Cuando tienes varias entidades observadas en varios periodos y te preocupa que algo "
                      "que no mediste (cultura local, calidad institucional, geografia) este contaminando "
                      "el resultado.",
        interpretacion="Con efectos fijos, el coeficiente se estima SOLO con la variacion dentro de cada "
                       "entidad a lo largo del tiempo. Una variable que no cambia en el tiempo (la costa, "
                       "el area) no se puede estimar con efectos fijos: desaparece en la transformacion. "
                       "Eso no es un error, es la definicion del metodo.",
        supuestos=["Efectos fijos: los efectos individuales pueden estar correlacionados con las explicativas",
                   "Efectos aleatorios: se supone que NO lo estan. Es un supuesto fuerte, y la prueba de "
                   "Hausman es la que lo pone a prueba."],
        advertencias=["Agrupa los errores por entidad. Sin eso, los errores estandar salen demasiado chicos "
                      "y todo parece significativo (Bertrand, Duflo y Mullainathan, 2004)."],
        referencia="Wooldridge, «Econometric Analysis of Cross Section and Panel Data», cap. 10",
        equivalente={"stata": "xtreg y x, fe cluster(id)", "r": "plm(model='within')"},
    )
    entradas = [Puerto(nombre="datos", tipo="panel", titulo="Panel",
                       descripcion="Pasa antes por «Definir panel»")]
    salidas = [Puerto(nombre="modelo", tipo="modelo"),
               Puerto(nombre="hausman", tipo="escalar", titulo="Prueba de Hausman", requerido=False)]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        y: str = CampoColumna(tipo="numerica")
        x: list[str] = CampoColumnas(tipo="numerica", default_factory=list)
        efectos: Literal["fijos", "aleatorios", "primera_diferencia", "agrupado"] = "fijos"
        efectos_tiempo: bool = False
        errores: Literal["clasicos", "robustos", "agrupados_por_entidad"] = "agrupados_por_entidad"
        prueba_hausman: bool = True

    def emit(self, ctx: Any) -> Any:
        ctx.importar("PanelOLS", desde="linearmodels.panel")
        ctx.importar("RandomEffects", desde="linearmodels.panel")
        ctx.importar("statsmodels.api", "sm")
        efectos = ctx.p("efectos")
        y, X = ctx.temporal("y"), ctx.temporal("X")
        ctx.emitir("Y = ENT[DEP]", Y=y, ENT=ctx.entrada("datos"), DEP=ctx.plit("y"))
        ctx.emitir("X = sm.add_constant(ENT[INDEP], has_constant='add')",
                   X=X, ENT=ctx.entrada("datos"), INDEP=ctx.plit("x"))

        cov = {"clasicos": "cov_type='unadjusted'",
               "robustos": "cov_type='robust'",
               "agrupados_por_entidad": "cov_type='clustered', cluster_entity=True"}[ctx.p("errores")]

        if efectos == "fijos":
            ctx.nota("Efectos fijos: cada entidad tiene su propia constante. Lo que no cambia en el "
                     "tiempo dentro de una entidad no se puede estimar.")
            ctx.emitir(f"MOD = PanelOLS(Y, X, entity_effects=True, time_effects=TIEMPO, "
                       f"drop_absorbed=True).fit({cov})",
                       MOD=ctx.salida("modelo"), Y=y, X=X, TIEMPO=ctx.plit("efectos_tiempo"))
        elif efectos == "aleatorios":
            ctx.nota("Efectos aleatorios: los efectos individuales se tratan como parte del error y se "
                     "supone que no estan correlacionados con las explicativas.")
            ctx.emitir(f"MOD = RandomEffects(Y, X).fit({cov})", MOD=ctx.salida("modelo"), Y=y, X=X)
        elif efectos == "primera_diferencia":
            ctx.importar("FirstDifferenceOLS", desde="linearmodels.panel")
            ctx.nota("Primera diferencia: se estima sobre los cambios periodo a periodo. Con solo dos "
                     "periodos es identico a efectos fijos.")
            ctx.emitir("X = X.drop(columns=['const'])", X=X)
            ctx.emitir(f"MOD = FirstDifferenceOLS(Y, X).fit({cov})", MOD=ctx.salida("modelo"), Y=y, X=X)
        else:
            ctx.importar("PooledOLS", desde="linearmodels.panel")
            ctx.nota("Agrupado (pooled): ignora que las filas se repiten por entidad. Sirve de referencia "
                     "para ver cuanto cambian los resultados al agregar efectos.")
            ctx.emitir(f"MOD = PooledOLS(Y, X).fit({cov})", MOD=ctx.salida("modelo"), Y=y, X=X)

        if ctx.p("prueba_hausman") and efectos in ("fijos", "aleatorios"):
            ctx.usar_ayudante("prueba_hausman")
            fe, re = ctx.temporal("fe"), ctx.temporal("re")
            ctx.nota("La prueba de Hausman compara los dos estimadores para decidir cual usar.")
            ctx.emitir("FE = PanelOLS(Y, X, entity_effects=True, drop_absorbed=True).fit()",
                       FE=fe, Y=y, X=X)
            ctx.emitir("RE = RandomEffects(Y, X).fit()", RE=re, Y=y, X=X)
            ctx.emitir("H = prueba_hausman(FE, RE)", H=ctx.salida("hausman"), FE=fe, RE=re)

        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {}

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import _limpio, modelo_a_json

        out: dict[str, Any] = {}
        if (mod := salidas.get("modelo")) is not None:
            art = modelo_a_json(mod, titulo=f"Panel · efectos {params.efectos}")  # type: ignore[attr-defined]
            for etiqueta, attr in [("Observaciones", "nobs"), ("R² dentro", "rsquared_within"),
                                   ("R² entre", "rsquared_between"), ("R² total", "rsquared_overall"),
                                   ("Entidades", "entity_info")]:
                v = getattr(mod, attr, None)
                if v is not None and not callable(v):
                    art["diagnosticos"][etiqueta] = _limpio(getattr(v, "total", v))
            out["modelo"] = art
        if (h := salidas.get("hausman")) is not None:
            out["hausman"] = {"tipo": "detalle", "titulo": "Prueba de Hausman",
                              "datos": {k: _limpio(v) for k, v in h.items()}}
        return out
