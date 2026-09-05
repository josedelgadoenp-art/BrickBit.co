"""Modelos espaciales: SAR, SEM, Durbin y las pruebas que deciden cual usar."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from ...graph.spec import Columna, Esquema
from ...registry.base import (Ayuda, Ayudante, CampoColumna, CampoColumnas, EspecNodo,
                              Puerto, registrar, registrar_ayudante)

registrar_ayudante(Ayudante(
    nombre="tabla_coeficientes_spreg",
    imports=[("pandas", "pd"), ("numpy", "np")],
    fuente='''
def tabla_coeficientes_spreg(modelo):
    """Coeficientes de un modelo de spreg en una tabla legible.

    spreg no comparte la interfaz de statsmodels (usa `betas`, `std_err`,
    `z_stat`), asi que se traduce aqui una sola vez en vez de en cada nodo.
    """
    nombres = list(getattr(modelo, "name_x", []) or [])
    betas = np.asarray(modelo.betas).flatten()
    errores = np.asarray(getattr(modelo, "std_err", [])).flatten()
    z = getattr(modelo, "z_stat", None)

    # El coeficiente espacial (rho o lambda) viene despues de los de X.
    for extra in ("rho", "lambda"):
        if hasattr(modelo, extra) and len(nombres) < len(betas):
            nombres.append("W_dependiente (rho)" if extra == "rho" else "error espacial (lambda)")

    filas = []
    for i, nombre in enumerate(nombres[:len(betas)]):
        est = float(z[i][0]) if z is not None and i < len(z) else None
        p = float(z[i][1]) if z is not None and i < len(z) else None
        filas.append({
            "variable": nombre,
            "coeficiente": float(betas[i]),
            "error_estandar": float(errores[i]) if i < len(errores) else None,
            "estadistico_z": est,
            "p_valor": p,
            "estrellas": ("***" if p is not None and p < 0.01 else
                          "**" if p is not None and p < 0.05 else
                          "*" if p is not None and p < 0.10 else ""),
        })
    return pd.DataFrame(filas)
''',
))

registrar_ayudante(Ayudante(
    nombre="diagnostico_espacial",
    imports=[("pandas", "pd")],
    fuente='''
def diagnostico_espacial(modelo_ols):
    """Multiplicadores de Lagrange: ¿SAR o SEM?

    La receta de Anselin y Florax: se miran primero las pruebas simples; si las
    dos rechazan, se miran las robustas, y gana la que rechace con mas fuerza.

      LM-lag  significativo -> falta el rezago espacial de la dependiente (SAR)
      LM-err  significativo -> la dependencia esta en el error (SEM)

    Si ninguna rechaza, no hace falta un modelo espacial y MCO alcanza.
    """
    filas = []
    for etiqueta, attr, lectura in [
        ("LM (rezago)", "lm_lag", "Sugiere un modelo SAR (rezago espacial de la dependiente)."),
        ("LM (error)", "lm_error", "Sugiere un modelo SEM (dependencia en el error)."),
        ("LM robusto (rezago)", "rlm_lag", "SAR, ya descontando la posible dependencia en el error."),
        ("LM robusto (error)", "rlm_error", "SEM, ya descontando el posible rezago espacial."),
        ("SARMA", "lm_sarma", "Hay dependencia espacial de algun tipo."),
    ]:
        v = getattr(modelo_ols, attr, None)
        if v is None:
            continue
        p = float(v[1])
        filas.append({
            "prueba": etiqueta, "estadistico": float(v[0]), "p_valor": p,
            "lectura": lectura if p < 0.05 else "No se rechaza: por esta via no hace falta.",
        })
    return pd.DataFrame(filas)
''',
))


class _BaseEspacial(EspecNodo):
    familia = "espacial"
    prefijo_var = "modelo_esp"
    terminal = True
    entradas = [Puerto(nombre="datos", tipo="tabla"), Puerto(nombre="pesos", tipo="pesos")]
    salidas = [Puerto(nombre="modelo", tipo="modelo"),
               Puerto(nombre="coeficientes", tipo="tabla", titulo="Coeficientes", requerido=False)]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        y: str = CampoColumna(tipo="numerica")
        x: list[str] = CampoColumnas(tipo="numerica", default_factory=list)

    def _diseno(self, ctx: Any) -> tuple[Any, Any]:
        y, X = ctx.temporal("y"), ctx.temporal("X")
        ctx.emitir("Y = ENT[[DEP]].to_numpy(float)", Y=y, ENT=ctx.entrada("datos"), DEP=ctx.plit("y"))
        ctx.emitir("X = ENT[INDEP].to_numpy(float)", X=X, ENT=ctx.entrada("datos"), INDEP=ctx.plit("x"))
        return y, X

    def _coeficientes(self, ctx: Any) -> None:
        ctx.usar_ayudante("tabla_coeficientes_spreg")
        ctx.emitir("COEF = tabla_coeficientes_spreg(MOD)",
                   COEF=ctx.salida("coeficientes"), MOD=ctx.ref_salida("modelo"))

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"coeficientes": Esquema(columnas=[
            Columna(nombre="variable", tipo="texto"),
            Columna(nombre="coeficiente", tipo="numerica", es_estimado=True),
            Columna(nombre="error_estandar", tipo="numerica", es_estimado=True),
            Columna(nombre="estadistico_z", tipo="numerica", es_estimado=True),
            Columna(nombre="p_valor", tipo="numerica", es_estimado=True),
            Columna(nombre="estrellas", tipo="texto")])}

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import _limpio, tabla_a_json

        out: dict[str, Any] = {}
        if (c := salidas.get("coeficientes")) is not None:
            out["coeficientes"] = tabla_a_json(c, titulo=self.titulo,
                                               estimadas=["coeficiente", "error_estandar",
                                                          "estadistico_z", "p_valor"])
        if (m := salidas.get("modelo")) is not None:
            diag = {}
            for etiqueta, attr in [("Observaciones", "n"), ("Pseudo R²", "pr2"),
                                   ("Log-verosimilitud", "logll"), ("AIC", "aic"),
                                   ("Schwarz", "schwarz"), ("Sigma²", "sig2")]:
                v = getattr(m, attr, None)
                if v is not None and not callable(v):
                    diag[etiqueta] = _limpio(v)
            out["modelo"] = {"tipo": "detalle", "titulo": f"{self.titulo} · ajuste", "datos": diag}
        return out


@registrar
class SAR(_BaseEspacial):
    op = "espacial.sar"
    titulo = "Modelo espacial autorregresivo (SAR)"
    ayuda = Ayuda(
        que_hace="Estima un modelo donde el valor de cada punto depende del promedio de sus vecinos: "
                 "y = ρWy + Xβ + ε.",
        cuando_usarlo="Cuando hay desbordamiento real entre ubicaciones. En vivienda es el caso normal: "
                      "el precio de una casa depende de lo que se pago por las de al lado, porque asi "
                      "valuan los avaluos y asi negocian los compradores.",
        interpretacion="ρ (rho) mide la fuerza del contagio espacial. Con ρ positivo y significativo, un "
                       "cambio en un punto se propaga a sus vecinos, y de ahi a los vecinos de sus "
                       "vecinos. Por eso el coeficiente β NO es el efecto total: el efecto total incluye "
                       "el efecto indirecto que regresa por la red.",
        supuestos=["El resultado depende de la matriz W. Cambiar de W puede cambiar ρ de forma importante.",
                   "ρ debe quedar entre -1 y 1 para que el sistema sea estable."],
        advertencias=["No leas β como en MCO. Para el efecto total hacen falta los impactos directo e "
                      "indirecto, que se calculan a partir de la inversa (I - ρW)⁻¹."],
        referencia="Anselin (1988); LeSage y Pace, «Introduction to Spatial Econometrics» (2009)",
        equivalente={"stata": "spregress y x, ml dvarlag(W)", "r": "spatialreg::lagsarlm()"},
    )

    def emit(self, ctx: Any) -> Any:
        ctx.importar("spreg")
        y, X = self._diseno(ctx)
        ctx.nota("SAR por maxima verosimilitud: el rezago espacial de la dependiente entra como explicativa.")
        ctx.nota("El coeficiente W_dependiente (rho) es la fuerza del contagio entre vecinos.")
        ctx.emitir("MOD = spreg.ML_Lag(Y, X, w=W, name_y=DEP, name_x=INDEP, name_w='W')",
                   MOD=ctx.salida("modelo"), Y=y, X=X, W=ctx.entrada("pesos"),
                   DEP=ctx.plit("y"), INDEP=ctx.plit("x"))
        self._coeficientes(ctx)
        return ctx.fin()


@registrar
class SEM(_BaseEspacial):
    op = "espacial.sem"
    titulo = "Modelo de error espacial (SEM)"
    ayuda = Ayuda(
        que_hace="Estima un modelo donde lo que se contagia entre vecinos no es la variable, sino lo que "
                 "el modelo no logro explicar: y = Xβ + u, con u = λWu + ε.",
        cuando_usarlo="Cuando la dependencia espacial viene de algo que no mediste y que esta repartido "
                      "en el territorio: calidad del barrio, acceso a servicios, percepcion de seguridad.",
        interpretacion="λ (lambda) mide cuanto se parecen los errores de puntos vecinos. A diferencia de "
                       "SAR, aqui los coeficientes β SI se leen como en MCO: son el efecto directo. Lo "
                       "que cambia es que los errores estandar quedan bien.",
        supuestos=["La dependencia esta en el error, no en la variable. Cual de los dos es el caso lo "
                   "decide la prueba de multiplicadores de Lagrange, no la intuicion."],
        referencia="Anselin (1988), cap. 6",
        equivalente={"stata": "spregress y x, ml errorlag(W)", "r": "spatialreg::errorsarlm()"},
    )

    def emit(self, ctx: Any) -> Any:
        ctx.importar("spreg")
        y, X = self._diseno(ctx)
        ctx.nota("SEM por maxima verosimilitud: la dependencia espacial se modela en el error.")
        ctx.nota("Aqui los coeficientes de X si se leen como en MCO; lo que se corrige es la inferencia.")
        ctx.emitir("MOD = spreg.ML_Error(Y, X, w=W, name_y=DEP, name_x=INDEP, name_w='W')",
                   MOD=ctx.salida("modelo"), Y=y, X=X, W=ctx.entrada("pesos"),
                   DEP=ctx.plit("y"), INDEP=ctx.plit("x"))
        self._coeficientes(ctx)
        return ctx.fin()


@registrar
class DiagnosticoEspacial(EspecNodo):
    op = "espacial.diagnostico"
    familia = "espacial"
    titulo = "¿SAR o SEM? (pruebas LM)"
    prefijo_var = "lm_espacial"
    terminal = True
    ayuda = Ayuda(
        que_hace="Corre un MCO con diagnostico espacial y te dice cual modelo espacial corresponde.",
        cuando_usarlo="ANTES de elegir entre SAR y SEM. Elegir por intuicion es como se llega a un "
                      "modelo que no se puede defender.",
        interpretacion="Receta de Anselin y Florax: si solo una de las LM simples rechaza, ese es tu "
                       "modelo. Si las dos rechazan, mira las robustas y quedate con la que rechace con "
                       "mas fuerza. Si ninguna rechaza, MCO alcanza y no necesitas un modelo espacial.",
        referencia="Anselin, Bera, Florax y Yoon (1996)",
        equivalente={"stata": "estat moran", "r": "spdep::lm.LMtests()"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla"), Puerto(nombre="pesos", tipo="pesos")]
    salidas = [Puerto(nombre="pruebas", tipo="tabla", titulo="Multiplicadores de Lagrange"),
               Puerto(nombre="modelo", tipo="modelo", titulo="MCO de referencia", requerido=False)]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        y: str = CampoColumna(tipo="numerica")
        x: list[str] = CampoColumnas(tipo="numerica", default_factory=list)

    def emit(self, ctx: Any) -> Any:
        ctx.importar("spreg")
        ctx.usar_ayudante("diagnostico_espacial")
        y, X = ctx.temporal("y"), ctx.temporal("X")
        ctx.emitir("Y = ENT[[DEP]].to_numpy(float)", Y=y, ENT=ctx.entrada("datos"), DEP=ctx.plit("y"))
        ctx.emitir("X = ENT[INDEP].to_numpy(float)", X=X, ENT=ctx.entrada("datos"), INDEP=ctx.plit("x"))
        ctx.nota("MCO con diagnostico espacial: las pruebas LM se calculan sobre sus residuos.")
        ctx.emitir("MOD = spreg.OLS(Y, X, w=W, spat_diag=True, moran=True, "
                   "name_y=DEP, name_x=INDEP, name_w='W')",
                   MOD=ctx.salida("modelo"), Y=y, X=X, W=ctx.entrada("pesos"),
                   DEP=ctx.plit("y"), INDEP=ctx.plit("x"))
        ctx.emitir("SAL = diagnostico_espacial(MOD)",
                   SAL=ctx.salida("pruebas"), MOD=ctx.ref_salida("modelo"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"pruebas": Esquema(columnas=[
            Columna(nombre="prueba", tipo="texto"), Columna(nombre="estadistico", tipo="numerica"),
            Columna(nombre="p_valor", tipo="numerica"), Columna(nombre="lectura", tipo="texto")])}
