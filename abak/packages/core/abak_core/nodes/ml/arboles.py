"""Machine learning: XGBoost con validacion honesta para series y panel.

La regla que organiza esta familia: en datos con fecha, la particion aleatoria
MIENTE. Si entrenas con 2023 y evaluas con 2019, tu modelo ya vio el futuro, y
el error que reportas no se parece al que vas a tener en produccion.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...graph.spec import Columna, Esquema
from ...registry.base import (Ayuda, Ayudante, CampoColumna, CampoColumnas, EspecNodo,
                              Puerto, registrar, registrar_ayudante)

registrar_ayudante(Ayudante(
    nombre="particion_temporal",
    imports=[("pandas", "pd"), ("numpy", "np")],
    fuente='''
def particion_temporal(datos, proporcion_prueba=0.2, columna_orden=None, aleatoria=False, semilla=42):
    """Parte en entrenamiento y prueba. Por tiempo salvo que se pida lo contrario.

    Con datos que tienen fecha, la particion aleatoria filtra el futuro hacia el
    pasado y produce metricas optimistas que no se repiten en produccion. Por eso
    el valor por omision es cortar por tiempo, no al azar.
    """
    if aleatoria:
        mezclado = datos.sample(frac=1.0, random_state=int(semilla))
        corte = int(len(mezclado) * (1 - proporcion_prueba))
        return mezclado.iloc[:corte].copy(), mezclado.iloc[corte:].copy()

    ordenado = datos.sort_values(columna_orden) if columna_orden else datos.sort_index()
    corte = int(len(ordenado) * (1 - proporcion_prueba))
    return ordenado.iloc[:corte].copy(), ordenado.iloc[corte:].copy()
''',
))

registrar_ayudante(Ayudante(
    nombre="metricas_regresion",
    imports=[("pandas", "pd"), ("numpy", "np")],
    fuente='''
def metricas_regresion(y_real, y_pred, etiqueta="prueba"):
    """RMSE, MAE, MAPE y R². El MAPE se omite si hay ceros: ahi no esta definido."""
    y_real = np.asarray(y_real, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    err = y_real - y_pred
    ss_res = float((err ** 2).sum())
    ss_tot = float(((y_real - y_real.mean()) ** 2).sum())
    fila = {
        "conjunto": etiqueta,
        "n": int(len(y_real)),
        "rmse": float(np.sqrt((err ** 2).mean())),
        "mae": float(np.abs(err).mean()),
        "r2": float(1 - ss_res / ss_tot) if ss_tot > 0 else None,
    }
    if (y_real != 0).all():
        fila["mape_pct"] = float(100 * np.abs(err / y_real).mean())
    return pd.DataFrame([fila])
''',
))

registrar_ayudante(Ayudante(
    nombre="validacion_origen_movil",
    imports=[("pandas", "pd"), ("numpy", "np")],
    depende_de=["metricas_regresion"],
    fuente='''
def validacion_origen_movil(datos, y, x, n_cortes=5, horizonte=4, params_modelo=None):
    """Validacion de origen movil: la unica honesta para series de tiempo.

    Se entrena con los primeros t periodos, se evalua en los siguientes h, se
    avanza el origen y se repite. Nunca se entrena con datos posteriores a los
    de evaluacion. Es lo que en scikit-learn hace TimeSeriesSplit, con el
    resultado en una tabla que se puede leer.
    """
    import xgboost as xgb

    params_modelo = dict(params_modelo or {})
    marco = datos[[y] + list(x)].dropna()
    n = len(marco)
    if n < (n_cortes + 1) * horizonte:
        raise ValueError(
            f"No alcanzan las observaciones: con {n} filas no se pueden hacer {n_cortes} cortes "
            f"de {horizonte} periodos. Baja los cortes o el horizonte."
        )

    inicio = n - n_cortes * horizonte
    filas = []
    for i in range(n_cortes):
        fin_entrena = inicio + i * horizonte
        entrena = marco.iloc[:fin_entrena]
        prueba = marco.iloc[fin_entrena:fin_entrena + horizonte]
        modelo = xgb.XGBRegressor(**params_modelo)
        modelo.fit(entrena[list(x)], entrena[y])
        pred = modelo.predict(prueba[list(x)])
        m = metricas_regresion(prueba[y], pred, etiqueta=f"corte {i + 1}")
        m["fin_entrenamiento"] = fin_entrena
        filas.append(m)

    tabla = pd.concat(filas, ignore_index=True)
    promedio = tabla.select_dtypes("number").mean().to_frame().T
    promedio["conjunto"] = "PROMEDIO"
    return pd.concat([tabla, promedio], ignore_index=True)
''',
))


@registrar
class Particion(EspecNodo):
    op = "ml.particion"
    familia = "ml"
    titulo = "Partir en entrenamiento y prueba"
    prefijo_var = "particion"
    ayuda = Ayuda(
        que_hace="Separa los datos en una parte para entrenar el modelo y otra, que el modelo nunca ve, "
                 "para medir que tan bien predice.",
        cuando_usarlo="Siempre, antes de entrenar cualquier modelo predictivo.",
        interpretacion="El error en el conjunto de prueba es el unico que se parece al error que vas a "
                       "tener con datos nuevos. El error de entrenamiento siempre es optimista.",
        advertencias=["En datos con fecha, la particion ALEATORIA miente: entrena con el futuro y evalua "
                      "con el pasado. Por eso el valor por omision es cortar por tiempo.",
                      "Estandariza o imputa DESPUES de partir, o el conjunto de prueba se filtra en el "
                      "de entrenamiento."],
        equivalente={"r": "rsample::initial_time_split()", "python": "TimeSeriesSplit"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="entrenamiento", tipo="tabla"), Puerto(nombre="prueba", tipo="tabla")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        proporcion_prueba: float = Field(default=0.2, gt=0.02, lt=0.6)
        aleatoria: bool = False
        columna_orden: str | None = CampoColumna(default=None)

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("particion_temporal")
        ctx.nota("Particion aleatoria." if ctx.p("aleatoria") else
                 "Particion por tiempo: se entrena con lo viejo y se evalua con lo reciente, "
                 "que es como funciona en la realidad.")
        ctx.emitir("ENTR, PRUE = particion_temporal(ENT, proporcion_prueba=P, "
                   "columna_orden=COL, aleatoria=ALE, semilla=42)",
                   ENTR=ctx.salida("entrenamiento"), PRUE=ctx.salida("prueba"),
                   ENT=ctx.entrada("datos"), P=ctx.plit("proporcion_prueba"),
                   COL=ctx.plit("columna_orden"), ALE=ctx.plit("aleatoria"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        base = entradas.get("datos", Esquema())
        return {"entrenamiento": base, "prueba": base}


@registrar
class XGBoost(EspecNodo):
    op = "ml.xgboost"
    familia = "ml"
    titulo = "XGBoost (arboles con refuerzo)"
    prefijo_var = "xgb"
    terminal = True
    ayuda = Ayuda(
        que_hace="Entrena un ensamble de arboles de decision donde cada arbol corrige los errores del "
                 "anterior. Suele ser lo mejor que hay para datos tabulares.",
        cuando_usarlo="Cuando tu objetivo es predecir bien y las relaciones no son lineales ni aditivas. "
                      "Para valuar inmuebles, estimar demanda o clasificar riesgo, gana casi siempre.",
        interpretacion="Compara el error de entrenamiento contra el de prueba. Si el de entrenamiento es "
                       "mucho mejor, el modelo se memorizo los datos y no va a generalizar: baja la "
                       "profundidad o sube la regularizacion.",
        supuestos=["No supone linealidad ni normalidad, y no le molestan las escalas distintas.",
                   "Necesita bastantes observaciones: con menos de unos cientos, MCO suele ganarle."],
        advertencias=["XGBoost predice, no explica. Sus «importancias» dicen que variable usa el modelo, "
                      "no que variable CAUSA el resultado. Para efectos causales, sigue haciendo falta "
                      "econometria.",
                      "No extrapola: fuera del rango de sus datos de entrenamiento devuelve el valor del "
                      "borde. Con series con tendencia hay que modelar las diferencias, no los niveles."],
        referencia="Chen y Guestrin (2016)",
        equivalente={"r": "xgboost::xgb.train()", "stata": "—"},
    )
    entradas = [Puerto(nombre="entrenamiento", tipo="tabla"),
                Puerto(nombre="prueba", tipo="tabla", requerido=False)]
    salidas = [Puerto(nombre="modelo", tipo="modelo"),
               Puerto(nombre="metricas", tipo="tabla", titulo="Que tan bien predice"),
               Puerto(nombre="importancias", tipo="tabla", titulo="Importancia de variables", requerido=False)]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        y: str = CampoColumna(puerto="entrenamiento")
        x: list[str] = CampoColumnas(puerto="entrenamiento", default_factory=list)
        objetivo: Literal["regresion", "clasificacion"] = "regresion"
        n_arboles: int = Field(default=300, ge=10, le=3000)
        profundidad: int = Field(default=4, ge=1, le=12)
        tasa_aprendizaje: float = Field(default=0.05, gt=0.001, le=0.5)
        submuestra: float = Field(default=0.8, gt=0.1, le=1.0)
        regularizacion_l2: float = Field(default=1.0, ge=0.0)

    def emit(self, ctx: Any) -> Any:
        ctx.importar("xgboost", "xgb")
        ctx.importar("pandas", "pd")
        ctx.usar_ayudante("metricas_regresion")
        clase = "XGBRegressor" if ctx.p("objetivo") == "regresion" else "XGBClassifier"
        ctx.nota(f"{ctx.p('n_arboles')} arboles de profundidad {ctx.p('profundidad')}, "
                 f"con tasa de aprendizaje {ctx.p('tasa_aprendizaje')}.")
        ctx.nota("La semilla queda fija: dos corridas con los mismos datos dan el mismo modelo.")
        ctx.emitir(f"MOD = xgb.{clase}(n_estimators=N, max_depth=D, learning_rate=LR, "
                   "subsample=SUB, reg_lambda=L2, random_state=42, n_jobs=1, tree_method='hist')",
                   MOD=ctx.salida("modelo"), N=ctx.plit("n_arboles"), D=ctx.plit("profundidad"),
                   LR=ctx.plit("tasa_aprendizaje"), SUB=ctx.plit("submuestra"),
                   L2=ctx.plit("regularizacion_l2"))
        ctx.emitir("MOD.fit(ENTR[X].astype(float), ENTR[Y])",
                   MOD=ctx.ref_salida("modelo"), ENTR=ctx.entrada("entrenamiento"),
                   X=ctx.plit("x"), Y=ctx.plit("y"))

        if ctx.p("objetivo") == "regresion":
            ctx.emitir("MET_ENTR = metricas_regresion(ENTR[Y], MOD.predict(ENTR[X].astype(float)), 'entrenamiento')",
                       MET_ENTR=ctx.temporal("met_entr"), ENTR=ctx.entrada("entrenamiento"),
                       MOD=ctx.ref_salida("modelo"), X=ctx.plit("x"), Y=ctx.plit("y"))
            if ctx.tiene_entrada("prueba"):
                ctx.emitir("MET_PRUE = metricas_regresion(PRUE[Y], MOD.predict(PRUE[X].astype(float)), 'prueba')",
                           MET_PRUE=ctx.temporal("met_prue"), PRUE=ctx.entrada("prueba"),
                           MOD=ctx.ref_salida("modelo"), X=ctx.plit("x"), Y=ctx.plit("y"))
                ctx.emitir("MET = pd.concat([A, B], ignore_index=True)",
                           MET=ctx.salida("metricas"), A=ctx.temporal("met_entr"), B=ctx.temporal("met_prue"))
            else:
                ctx.nota("Sin conjunto de prueba, el error reportado es optimista: el modelo esta "
                         "midiendose sobre los datos con los que aprendio.")
                ctx.emitir("MET = A", MET=ctx.salida("metricas"), A=ctx.temporal("met_entr"))
        else:
            ctx.importar("classification_report", desde="sklearn.metrics")
            fuente = "PRUE" if ctx.tiene_entrada("prueba") else "ENTR"
            ctx.emitir(f"MET = pd.DataFrame(classification_report({fuente}[Y], "
                       f"MOD.predict({fuente}[X].astype(float)), output_dict=True)).T.reset_index("
                       "names='clase')",
                       MET=ctx.salida("metricas"),
                       **({"PRUE": ctx.entrada("prueba")} if ctx.tiene_entrada("prueba")
                          else {"ENTR": ctx.entrada("entrenamiento")}),
                       MOD=ctx.ref_salida("modelo"), X=ctx.plit("x"), Y=ctx.plit("y"))

        ctx.emitir("IMP = pd.DataFrame({'variable': X, "
                   "'importancia': MOD.feature_importances_}).sort_values('importancia', ascending=False)",
                   IMP=ctx.salida("importancias"), MOD=ctx.ref_salida("modelo"), X=ctx.plit("x"))
        ctx.nota("La importancia dice cuanto USA el modelo cada variable para predecir. No es un efecto "
                 "causal ni un coeficiente.")
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {
            "metricas": Esquema(columnas=[
                Columna(nombre="conjunto", tipo="texto"), Columna(nombre="n", tipo="numerica"),
                Columna(nombre="rmse", tipo="numerica", es_estimado=True),
                Columna(nombre="mae", tipo="numerica", es_estimado=True),
                Columna(nombre="r2", tipo="numerica", es_estimado=True)]),
            "importancias": Esquema(columnas=[
                Columna(nombre="variable", tipo="texto"),
                Columna(nombre="importancia", tipo="numerica", es_estimado=True)]),
        }

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import tabla_a_json

        out: dict[str, Any] = {}
        for puerto, titulo in [("metricas", "Desempeno predictivo"),
                               ("importancias", "Importancia de las variables")]:
            if (t := salidas.get(puerto)) is not None:
                out[puerto] = tabla_a_json(t, titulo=titulo,
                                           estimadas=[c for c in t.columns
                                                      if c not in ("conjunto", "variable", "n", "clase")])
        return out


@registrar
class ValidacionTemporal(EspecNodo):
    op = "ml.validacion_temporal"
    familia = "ml"
    titulo = "Validacion de origen movil"
    prefijo_var = "validacion"
    terminal = True
    ayuda = Ayuda(
        que_hace="Evalua el modelo como se usaria de verdad: entrena con el pasado, predice el futuro "
                 "inmediato, avanza y repite.",
        cuando_usarlo="Siempre que vayas a pronosticar. Es la unica validacion honesta con datos que "
                      "tienen fecha.",
        interpretacion="Mira la fila PROMEDIO y, sobre todo, la variacion entre cortes. Un modelo que "
                       "predice muy bien en tres cortes y muy mal en dos no es un buen modelo: es un "
                       "modelo inestable, y el promedio lo esconde.",
        advertencias=["La validacion cruzada aleatoria (k-fold) sobre series de tiempo da metricas "
                      "optimistas que no se repiten en produccion. No la uses."],
        referencia="Hyndman y Athanasopoulos, «Forecasting», sec. 5.10",
        equivalente={"python": "sklearn.model_selection.TimeSeriesSplit"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="resultados", tipo="tabla", titulo="Error por corte")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        y: str = CampoColumna()
        x: list[str] = CampoColumnas(default_factory=list)
        n_cortes: int = Field(default=5, ge=2, le=20)
        horizonte: int = Field(default=4, ge=1, le=52)
        profundidad: int = Field(default=4, ge=1, le=12)
        n_arboles: int = Field(default=300, ge=10, le=2000)

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("validacion_origen_movil")
        ctx.nota(f"{ctx.p('n_cortes')} cortes, cada uno evaluado a {ctx.p('horizonte')} periodos. "
                 "En ningun corte se entrena con datos posteriores a los de evaluacion.")
        ctx.emitir("SAL = validacion_origen_movil(ENT, Y, X, n_cortes=K, horizonte=H, "
                   "params_modelo=PARAMS)",
                   SAL=ctx.salida("resultados"), ENT=ctx.entrada("datos"),
                   Y=ctx.plit("y"), X=ctx.plit("x"), K=ctx.plit("n_cortes"), H=ctx.plit("horizonte"),
                   PARAMS=ctx.lit({"n_estimators": ctx.p("n_arboles"), "max_depth": ctx.p("profundidad"),
                                   "learning_rate": 0.05, "random_state": 42, "n_jobs": 1}))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"resultados": Esquema(columnas=[
            Columna(nombre="conjunto", tipo="texto"), Columna(nombre="n", tipo="numerica"),
            Columna(nombre="rmse", tipo="numerica", es_estimado=True),
            Columna(nombre="mae", tipo="numerica", es_estimado=True),
            Columna(nombre="r2", tipo="numerica", es_estimado=True),
            Columna(nombre="fin_entrenamiento", tipo="numerica")])}
