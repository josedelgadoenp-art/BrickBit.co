"""Series de tiempo: raiz unitaria, ARIMA, VAR, cointegracion, ciclos, volatilidad."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...graph.spec import Columna, Esquema
from ...registry.base import (Ayuda, Ayudante, CampoColumna, CampoColumnas, EspecNodo,
                              Puerto, registrar, registrar_ayudante)

registrar_ayudante(Ayudante(
    nombre="pruebas_raiz_unitaria",
    imports=[("pandas", "pd")],
    fuente='''
def pruebas_raiz_unitaria(datos, columnas, regresion="c"):
    """ADF y KPSS sobre cada columna, con las hipotesis nulas al reves a proposito.

    ADF:  H0 = la serie TIENE raiz unitaria (no es estacionaria).
    KPSS: H0 = la serie ES estacionaria.

    Se corren las dos porque tienen poca potencia por separado y porque cuando
    coinciden la conclusion es mucho mas solida. Que las dos rechacen (o que
    ninguna lo haga) es informacion: suele indicar que la serie no es ni una
    cosa ni la otra, sino de memoria larga.
    """
    from statsmodels.tsa.stattools import adfuller, kpss

    filas = []
    for col in columnas:
        serie = datos[col].dropna()
        fila = {"variable": col}
        try:
            adf = adfuller(serie, regression=regresion, autolag="AIC")
            fila["adf_estadistico"] = float(adf[0])
            fila["adf_p"] = float(adf[1])
            fila["adf_rezagos"] = int(adf[2])
        except Exception:
            fila["adf_estadistico"] = fila["adf_p"] = fila["adf_rezagos"] = None
        try:
            k = kpss(serie, regression=regresion, nlags="auto")
            fila["kpss_estadistico"] = float(k[0])
            fila["kpss_p"] = float(k[1])
        except Exception:
            fila["kpss_estadistico"] = fila["kpss_p"] = None

        adf_est = fila["adf_p"] is not None and fila["adf_p"] < 0.05
        kpss_est = fila["kpss_p"] is not None and fila["kpss_p"] > 0.05
        if adf_est and kpss_est:
            fila["conclusion"] = "Estacionaria: las dos pruebas coinciden."
        elif not adf_est and not kpss_est:
            fila["conclusion"] = "Tiene raiz unitaria: diferenciala antes de modelar."
        elif adf_est and not kpss_est:
            fila["conclusion"] = "Ambiguo: ADF dice estacionaria, KPSS no. Puede ser memoria larga o un cambio de nivel."
        else:
            fila["conclusion"] = "Ambiguo: KPSS dice estacionaria, ADF no. Poca potencia; mira la grafica."
        filas.append(fila)
    return pd.DataFrame(filas)
''',
))

registrar_ayudante(Ayudante(
    nombre="tabla_impulso_respuesta",
    imports=[("pandas", "pd")],
    fuente='''
def tabla_impulso_respuesta(resultado_var, periodos=12, ortogonal=True):
    """Aplana las respuestas al impulso a una tabla larga, lista para graficar.

    Las bandas son el intervalo asintotico al 95%. Con muestras cortas quedan
    demasiado angostas: en ese caso conviene bootstrap, que tarda mas.
    """
    irf = resultado_var.irf(periodos)
    respuestas = irf.orth_irfs if ortogonal else irf.irfs
    try:
        bandas = irf.cov(orth=ortogonal)
        import numpy as _np
        error = _np.sqrt(_np.diagonal(bandas, axis1=1, axis2=2))
        error = error.reshape(respuestas.shape)
    except Exception:
        error = None

    nombres = list(resultado_var.names)
    filas = []
    for h in range(respuestas.shape[0]):
        for i, respuesta in enumerate(nombres):
            for j, choque in enumerate(nombres):
                ee = None if error is None else float(error[h, i, j])
                valor = float(respuestas[h, i, j])
                filas.append({
                    "periodo": h, "choque_en": choque, "respuesta_de": respuesta,
                    "efecto": valor,
                    "banda_baja": None if ee is None else valor - 1.96 * ee,
                    "banda_alta": None if ee is None else valor + 1.96 * ee,
                })
    return pd.DataFrame(filas)
''',
))


@registrar
class RaizUnitaria(EspecNodo):
    op = "series.estacionariedad"
    familia = "series"
    titulo = "Prueba de raiz unitaria (ADF y KPSS)"
    prefijo_var = "estacionariedad"
    terminal = True
    ayuda = Ayuda(
        que_hace="Revisa si una serie es estacionaria, es decir, si su media y su varianza se quedan "
                 "quietas a lo largo del tiempo.",
        cuando_usarlo="ANTES de cualquier modelo de series de tiempo. Es el primer paso, siempre.",
        interpretacion="ADF: p < 0.05 significa estacionaria. KPSS: p > 0.05 significa estacionaria. "
                       "Ojo, las hipotesis nulas estan al reves entre las dos pruebas, y por eso se corren "
                       "juntas. La columna «conclusion» ya resuelve la combinacion.",
        supuestos=["Las dos pruebas tienen poca potencia con series cortas: por debajo de 50 observaciones, "
                   "tomalas como indicio, no como veredicto."],
        advertencias=["Regresionar dos series con raiz unitaria produce una regresion espuria: R² altisimo, "
                      "t enormes y ninguna relacion real. Es el error mas caro de la econometria aplicada."],
        referencia="Granger y Newbold (1974); Enders, «Applied Econometric Time Series», cap. 4",
        equivalente={"stata": "dfuller y / kpss y", "r": "tseries::adf.test()", "eviews": "Unit Root Test"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="pruebas", tipo="tabla", titulo="Resultado de las pruebas")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        columnas: list[str] = CampoColumnas(tipo="numerica", default_factory=list)
        regresion: Literal["c", "ct", "n"] = "c"

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("pruebas_raiz_unitaria")
        ctx.nota({"c": "Se incluye constante (el caso normal).",
                  "ct": "Se incluye constante y tendencia: usalo si la serie crece de forma sostenida.",
                  "n": "Sin constante ni tendencia."}[ctx.p("regresion")])
        ctx.emitir("SAL = pruebas_raiz_unitaria(ENT, COLS, regresion=REG)",
                   SAL=ctx.salida("pruebas"), ENT=ctx.entrada("datos"),
                   COLS=ctx.plit("columnas"), REG=ctx.plit("regresion"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"pruebas": Esquema(columnas=[
            Columna(nombre="variable", tipo="texto"), Columna(nombre="adf_estadistico", tipo="numerica"),
            Columna(nombre="adf_p", tipo="numerica"), Columna(nombre="adf_rezagos", tipo="numerica"),
            Columna(nombre="kpss_estadistico", tipo="numerica"), Columna(nombre="kpss_p", tipo="numerica"),
            Columna(nombre="conclusion", tipo="texto")])}


@registrar
class ARIMA(EspecNodo):
    op = "series.arima"
    familia = "series"
    titulo = "ARIMA / SARIMAX"
    prefijo_var = "arima"
    terminal = True
    ayuda = Ayuda(
        que_hace="Modela una serie con su propio pasado (AR), con los errores pasados (MA) y con "
                 "diferencias (I), y produce un pronostico con su intervalo.",
        cuando_usarlo="Cuando quieres pronosticar una serie y no tienes (o no quieres usar) otras variables.",
        interpretacion="El pronostico viene con banda de confianza. Esa banda es lo importante: un "
                       "pronostico puntual sin banda es una opinion disfrazada de numero. Todo lo "
                       "pronosticado sale marcado en ambar, porque es estimacion y no dato.",
        supuestos=["La serie debe ser estacionaria despues de aplicar d diferencias",
                   "Los residuos deben quedar sin autocorrelacion: revisalos"],
        advertencias=["Un AIC mas bajo no garantiza mejor pronostico fuera de muestra. La unica prueba "
                      "honesta es guardar los ultimos periodos y ver que tan lejos cae."],
        referencia="Box y Jenkins; Hyndman y Athanasopoulos, «Forecasting: Principles and Practice»",
        equivalente={"stata": "arima y, arima(1,1,1)", "r": "forecast::Arima()", "eviews": "ARMA"},
    )
    entradas = [Puerto(nombre="datos", tipo="serie", descripcion="Pasa antes por «Definir serie temporal»")]
    salidas = [Puerto(nombre="modelo", tipo="modelo"),
               Puerto(nombre="pronostico", tipo="tabla", titulo="Pronostico", requerido=False)]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        variable: str = CampoColumna(tipo="numerica")
        p: int = Field(default=1, ge=0, le=12)
        d: int = Field(default=1, ge=0, le=2)
        q: int = Field(default=1, ge=0, le=12)
        estacional: bool = False
        P: int = Field(default=0, ge=0, le=4)
        D: int = Field(default=0, ge=0, le=1)
        Q: int = Field(default=0, ge=0, le=4)
        periodo_estacional: int = Field(default=4, ge=2, le=52)
        horizonte: int = Field(default=8, ge=0, le=60)

    def emit(self, ctx: Any) -> Any:
        ctx.importar("SARIMAX", desde="statsmodels.tsa.statespace.sarimax")
        ctx.importar("pandas", "pd")
        p, d, q = ctx.p("p"), ctx.p("d"), ctx.p("q")
        ctx.nota(f"ARIMA({p},{d},{q}): {p} rezago(s) de la serie, {d} diferencia(s), {q} rezago(s) del error."
                 + (f" Con parte estacional ({ctx.p('P')},{ctx.p('D')},{ctx.p('Q')})"
                    f"[{ctx.p('periodo_estacional')}]." if ctx.p("estacional") else ""))
        orden = ctx.lit((p, d, q))
        if ctx.p("estacional"):
            estacional = ctx.lit((ctx.p("P"), ctx.p("D"), ctx.p("Q"), ctx.p("periodo_estacional")))
            ctx.emitir("MOD = SARIMAX(ENT[VAR], order=ORDEN, seasonal_order=EST, "
                       "enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)",
                       MOD=ctx.salida("modelo"), ENT=ctx.entrada("datos"),
                       VAR=ctx.plit("variable"), ORDEN=orden, EST=estacional)
        else:
            ctx.emitir("MOD = SARIMAX(ENT[VAR], order=ORDEN).fit(disp=False)",
                       MOD=ctx.salida("modelo"), ENT=ctx.entrada("datos"),
                       VAR=ctx.plit("variable"), ORDEN=orden)
        if ctx.p("horizonte"):
            pron = ctx.temporal("pron")
            ctx.nota(f"Pronostico a {ctx.p('horizonte')} periodos, con intervalo al 95%. "
                     "Todo lo pronosticado es estimacion, no dato observado.")
            ctx.emitir("PR = MOD.get_forecast(steps=H)", PR=pron, MOD=ctx.ref_salida("modelo"),
                       H=ctx.plit("horizonte"))
            ctx.emitir("SAL = PR.summary_frame(alpha=0.05).rename(columns={"
                       "'mean': 'pronostico', 'mean_ci_lower': 'banda_baja', "
                       "'mean_ci_upper': 'banda_alta', 'mean_se': 'error_estandar'})",
                       SAL=ctx.salida("pronostico"), PR=pron)
            # El indice del pronostico llega sin nombre; se le pone el mismo de la
            # serie para poder graficarlo por su nombre, no por "index".
            ctx.emitir("SAL.index.name = NOMBRE", SAL=ctx.ref_salida("pronostico"),
                       NOMBRE=ctx.lit(ctx.esquema("datos").indice_temporal or "fecha"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        indice = entradas.get("datos", Esquema()).indice_temporal or "fecha"
        return {"pronostico": Esquema(indice_temporal=indice, columnas=[
            Columna(nombre="pronostico", tipo="numerica", es_estimado=True,
                    nota="Valor pronosticado: es una estimacion."),
            Columna(nombre="error_estandar", tipo="numerica", es_estimado=True),
            Columna(nombre="banda_baja", tipo="numerica", es_estimado=True),
            Columna(nombre="banda_alta", tipo="numerica", es_estimado=True)])}

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import modelo_a_json, tabla_a_json

        out: dict[str, Any] = {}
        if (m := salidas.get("modelo")) is not None:
            out["modelo"] = modelo_a_json(m, titulo="ARIMA")
        if (f := salidas.get("pronostico")) is not None:
            out["pronostico"] = tabla_a_json(
                f, titulo="Pronostico",
                estimadas=["pronostico", "error_estandar", "banda_baja", "banda_alta"])
        return out


@registrar
class VAR(EspecNodo):
    op = "series.var"
    familia = "series"
    titulo = "VAR: vectores autorregresivos"
    prefijo_var = "var"
    terminal = True
    ayuda = Ayuda(
        que_hace="Modela varias series a la vez, donde cada una se explica con el pasado de todas, y "
                 "calcula como responde el sistema a un choque en cualquiera de ellas.",
        cuando_usarlo="Cuando las variables se determinan entre si y no quieres imponer quien causa a "
                      "quien: tasa, inflacion y tipo de cambio, por ejemplo.",
        interpretacion="Lo que se lee no son los coeficientes (son demasiados y no significan nada por "
                       "separado), sino las funciones de impulso-respuesta: «si la tasa sube un punto, "
                       "¿que le pasa a la inflacion en los siguientes 12 trimestres?». Si la banda cruza "
                       "el cero, el efecto no es distinguible de cero.",
        supuestos=["Todas las series deben ser estacionarias. Si no lo son y estan cointegradas, "
                   "el modelo correcto es un VECM, no un VAR en diferencias.",
                   "La descomposicion ortogonal (Cholesky) impone un orden causal contemporaneo: "
                   "la primera variable afecta a todas en el mismo periodo y no recibe nada. "
                   "El orden importa y hay que justificarlo."],
        advertencias=["Cada rezago cuesta k² parametros. Con 4 variables y 8 rezagos son 128 coeficientes: "
                      "no hay serie trimestral en Mexico que aguante eso."],
        referencia="Sims (1980); Enders, cap. 5",
        equivalente={"stata": "var y1 y2, lags(1/4) / irf create", "r": "vars::VAR()", "eviews": "VAR"},
    )
    entradas = [Puerto(nombre="datos", tipo="serie")]
    salidas = [Puerto(nombre="modelo", tipo="modelo"),
               Puerto(nombre="impulso_respuesta", tipo="tabla", titulo="Impulso-respuesta", requerido=False),
               Puerto(nombre="causalidad", tipo="tabla", titulo="Causalidad de Granger", requerido=False)]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        variables: list[str] = CampoColumnas(tipo="numerica", default_factory=list)
        rezagos: int = Field(default=2, ge=1, le=12)
        elegir_rezagos: bool = Field(default=True, description="Elegir el numero de rezagos por AIC")
        periodos_irf: int = Field(default=12, ge=1, le=60)
        ortogonal: bool = True

    def emit(self, ctx: Any) -> Any:
        ctx.importar("VAR", desde="statsmodels.tsa.api")
        ctx.importar("pandas", "pd")
        ctx.usar_ayudante("tabla_impulso_respuesta")
        datos = ctx.temporal("y")
        ctx.emitir("Y = ENT[VARS].dropna()", Y=datos, ENT=ctx.entrada("datos"), VARS=ctx.plit("variables"))
        if ctx.p("elegir_rezagos"):
            ctx.nota(f"El numero de rezagos se elige por AIC, con un maximo de {ctx.p('rezagos')}.")
            ctx.emitir("MOD = VAR(Y).fit(maxlags=REZ, ic='aic')",
                       MOD=ctx.salida("modelo"), Y=datos, REZ=ctx.plit("rezagos"))
        else:
            ctx.nota(f"VAR con {ctx.p('rezagos')} rezago(s) fijos.")
            ctx.emitir("MOD = VAR(Y).fit(REZ)", MOD=ctx.salida("modelo"), Y=datos, REZ=ctx.plit("rezagos"))
        ctx.nota("Impulso-respuesta: efecto de un choque de una desviacion estandar, con banda al 95%.")
        if ctx.p("ortogonal"):
            ctx.nota(f"Identificacion de Cholesky en el orden {', '.join(ctx.p('variables'))}. "
                     "Ese orden es un supuesto sobre quien afecta a quien en el mismo periodo.")
        ctx.emitir("IRF = tabla_impulso_respuesta(MOD, periodos=H, ortogonal=ORT)",
                   IRF=ctx.salida("impulso_respuesta"), MOD=ctx.ref_salida("modelo"),
                   H=ctx.plit("periodos_irf"), ORT=ctx.plit("ortogonal"))
        ctx.emitir(
            "CAUS = pd.DataFrame([{'causa': c, 'efecto': e, "
            "'p_valor': float(MOD.test_causality(e, [c], kind='f').pvalue), "
            "'conclusion': ('Granger-causa' if MOD.test_causality(e, [c], kind='f').pvalue < 0.05 "
            "else 'no Granger-causa')} for c in VARS for e in VARS if c != e])",
            CAUS=ctx.salida("causalidad"), MOD=ctx.ref_salida("modelo"), VARS=ctx.plit("variables"))
        ctx.nota("«Granger-causa» significa que ayuda a predecir, no que cause. Es una prueba de "
                 "precedencia temporal, no de causalidad.")
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {
            "impulso_respuesta": Esquema(columnas=[
                Columna(nombre="periodo", tipo="numerica"), Columna(nombre="choque_en", tipo="texto"),
                Columna(nombre="respuesta_de", tipo="texto"),
                Columna(nombre="efecto", tipo="numerica", es_estimado=True),
                Columna(nombre="banda_baja", tipo="numerica", es_estimado=True),
                Columna(nombre="banda_alta", tipo="numerica", es_estimado=True)]),
            "causalidad": Esquema(columnas=[
                Columna(nombre="causa", tipo="texto"), Columna(nombre="efecto", tipo="texto"),
                Columna(nombre="p_valor", tipo="numerica"), Columna(nombre="conclusion", tipo="texto")]),
        }
