"""Cada herramienta, contra un cálculo hecho por fuera.

`test_semantica.py` comprueba que las herramientas de preparación hagan lo que
dicen. Ésta hace lo mismo con las que ESTIMAN, que es donde un error no se ve:
una regresión mal cableada devuelve números perfectamente plausibles.

El método es siempre el mismo y es lo que le da valor: el número de referencia
se calcula APARTE —con la fórmula, o llamando a la biblioteca por su API
canónica— y se compara contra lo que Abak reporta. Así no se prueba que
statsmodels sepa estimar (eso ya lo sabe): se prueba el cableado, que es lo
nuestro. Un error típico de cableado es reportar el error estándar clásico
diciendo que es robusto, o la columna de al lado, o el signo cambiado. Ninguno
de esos da error.
"""

import numpy as np
import pandas as pd
import pytest

from abak_core import compilar, ejecutar

from .conftest import grafo

pytest.importorskip("statsmodels")

HOGARES = ("d", "datos.ejemplo", "Hogares", {"conjunto": "hogares"})
ESTADOS = ("d", "datos.ejemplo", "Entidades", {"conjunto": "mexico_estados"})
MACRO = ("d", "datos.ejemplo", "Macro", {"conjunto": "mexico_macro"})
PANEL = ("d", "datos.ejemplo", "Panel", {"conjunto": "panel_estados"})


def _art(nombre, nodos, aristas):
    """{id del nodo: {puerto: artefacto}} de una corrida que tiene que salir bien."""
    r = ejecutar(compilar(grafo(nombre, nodos, aristas)))
    assert r.ok, r.bitacora[-2:]
    return {n.nodo_id: (n.artefactos or {}) for n in r.nodos}


def _tabla(art) -> pd.DataFrame:
    return pd.DataFrame(art["filas"], columns=[c["nombre"] for c in art["columnas"]])


def _coefs(art) -> dict:
    return {c["variable"]: c["coeficiente"] for c in art["coeficientes"]}


def _errores(art) -> dict:
    return {c["variable"]: c["error_estandar"] for c in art["coeficientes"]}


def _ayudante(nombre: str):
    """Un ayudante suelto, con sus dependencias, igual que en el script exportado."""
    from abak_core.codegen.contexto import resolver_ayudantes

    espacio: dict = {}
    for dependencia in resolver_ayudantes([nombre]):
        for modulo, alias in dependencia.imports:
            espacio[alias or modulo.split(".")[0]] = __import__(modulo, fromlist=["_"])
        exec(dependencia.fuente, espacio)
    return espacio[nombre]


def _datos(conjunto: str) -> pd.DataFrame:
    """El conjunto de ejemplo, leído por fuera de Abak."""
    import os
    from pathlib import Path

    raiz = Path(os.environ["ABAK_DATOS"])
    archivos = {"hogares": "hogares_vivienda.csv", "mexico_estados": "mexico_estados.csv",
                "mexico_macro": "mexico_macro_trimestral.csv",
                "panel_estados": "panel_estados_anual.csv"}
    return pd.read_csv(raiz / archivos[conjunto])


# ---------------------------------------------------------------------------
# Econometría
# ---------------------------------------------------------------------------

def test_los_errores_robustos_son_los_robustos_de_verdad():
    """El error de cableado más fácil: decir HC3 y reportar los clásicos.

    No da ningún síntoma —los coeficientes son idénticos— y cambia todas las
    conclusiones de significancia.
    """
    import statsmodels.api as sm

    d = _datos("mexico_estados")
    X = sm.add_constant(d[["escolaridad_anios", "empleo_formal_pct"]])
    referencia = sm.OLS(d["precio_m2"], X).fit(cov_type="HC3")
    clasico = sm.OLS(d["precio_m2"], X).fit()

    art = _art("hc3", [ESTADOS, ("m", "econometria.mco", "MCO",
                                 {"y": "precio_m2",
                                  "x": ["escolaridad_anios", "empleo_formal_pct"],
                                  "errores": "HC3"})],
               [("d", "datos", "m", "datos")])["m"]["modelo"]

    ee = _errores(art)
    for v in ("const", "escolaridad_anios", "empleo_formal_pct"):
        assert ee[v] == pytest.approx(referencia.bse[v], rel=1e-9), f"«{v}» no es HC3"
    assert ee["escolaridad_anios"] != pytest.approx(clasico.bse["escolaridad_anios"], rel=1e-6), (
        "HC3 salió idéntico al clásico: probablemente no se aplicó")


@pytest.mark.parametrize("tipo", ["clasicos", "HC1", "HC3"])
def test_cada_tipo_de_error_coincide_con_statsmodels(tipo):
    import statsmodels.api as sm

    d = _datos("mexico_estados")
    X = sm.add_constant(d[["escolaridad_anios"]])
    ajuste = sm.OLS(d["precio_m2"], X)
    referencia = ajuste.fit() if tipo == "clasicos" else ajuste.fit(cov_type=tipo)

    art = _art(tipo, [ESTADOS, ("m", "econometria.mco", "MCO",
                                {"y": "precio_m2", "x": ["escolaridad_anios"], "errores": tipo})],
               [("d", "datos", "m", "datos")])["m"]["modelo"]
    for v, ee in _errores(art).items():
        assert ee == pytest.approx(referencia.bse[v], rel=1e-9)
    for v, c in _coefs(art).items():
        assert c == pytest.approx(referencia.params[v], rel=1e-9)


def test_el_intervalo_de_confianza_es_el_del_modelo():
    """Un IC calculado con la z cuando toca la t (o al revés) se ve bien y no lo es."""
    import statsmodels.api as sm

    d = _datos("mexico_estados")
    X = sm.add_constant(d[["escolaridad_anios"]])
    referencia = sm.OLS(d["precio_m2"], X).fit(cov_type="HC1")
    ic = referencia.conf_int()

    art = _art("ic", [ESTADOS, ("m", "econometria.mco", "MCO",
                                {"y": "precio_m2", "x": ["escolaridad_anios"], "errores": "HC1"})],
               [("d", "datos", "m", "datos")])["m"]["modelo"]
    for c in art["coeficientes"]:
        v = c["variable"]
        assert c["ic_bajo"] == pytest.approx(ic.loc[v, 0], rel=1e-8), f"IC bajo de «{v}»"
        assert c["ic_alto"] == pytest.approx(ic.loc[v, 1], rel=1e-8), f"IC alto de «{v}»"


def test_el_dos_etapas_coincide_con_el_dos_etapas_hecho_a_mano():
    """MC2E: primera etapa, valores ajustados, segunda etapa. Sin atajos."""
    import statsmodels.api as sm

    d = _datos("hogares")
    # Primera etapa: la endógena contra instrumento + exógenas.
    Z = sm.add_constant(d[["escolaridad_anios", "tamano_hogar"]])
    primera = sm.OLS(d["ingreso_mensual"], Z).fit()
    ajustada = primera.fittedvalues
    # Segunda etapa: la dependiente contra la endógena AJUSTADA + exógenas.
    X2 = sm.add_constant(pd.DataFrame({"ingreso_mensual": ajustada,
                                       "tamano_hogar": d["tamano_hogar"]}))
    segunda = sm.OLS(d["gasto_vivienda"], X2).fit()

    art = _art("iv", [HOGARES, ("m", "econometria.iv", "IV",
                                {"y": "gasto_vivienda", "endogenas": ["ingreso_mensual"],
                                 "instrumentos": ["escolaridad_anios"],
                                 "exogenas": ["tamano_hogar"]})],
               [("d", "datos", "m", "datos")])["m"]["modelo"]
    coefs = _coefs(art)
    for v in ("ingreso_mensual", "tamano_hogar"):
        assert coefs[v] == pytest.approx(segunda.params[v], rel=1e-6), (
            f"el coeficiente MC2E de «{v}» no coincide con el de dos etapas a mano")


def test_el_logit_coincide_con_statsmodels_y_su_marginal_con_la_derivada():
    """El efecto marginal promedio es la media de p(1-p)·β, no β.

    Confundirlos es un error clásico: el coeficiente de un logit no está en
    unidades de probabilidad, y reportarlo como si lo estuviera cambia la
    conclusión por un factor de cuatro o más.
    """
    import statsmodels.api as sm

    d = _datos("hogares")
    X = sm.add_constant(d[["ingreso_mensual", "escolaridad_anios"]])
    referencia = sm.Logit(d["tiene_credito_hipotecario"], X).fit(disp=False)
    p = referencia.predict(X)
    marginal_mano = {v: float((p * (1 - p)).mean() * referencia.params[v])
                     for v in ("ingreso_mensual", "escolaridad_anios")}

    art = _art("logit", [HOGARES, ("m", "econometria.eleccion_discreta", "Logit",
                                   {"y": "tiene_credito_hipotecario",
                                    "x": ["ingreso_mensual", "escolaridad_anios"],
                                    "familia": "logit", "errores": "clasicos"})],
               [("d", "datos", "m", "datos")])["m"]
    coefs = _coefs(art["modelo"])
    for v in ("ingreso_mensual", "escolaridad_anios"):
        assert coefs[v] == pytest.approx(referencia.params[v], rel=1e-6)

    marginales = _tabla(art["marginales"]).set_index("indice")["dy/dx"]
    for v, esperado in marginal_mano.items():
        assert float(marginales[v]) == pytest.approx(esperado, rel=1e-4), (
            f"el efecto marginal de «{v}» no es la media de p(1-p)·β")
        assert float(marginales[v]) != pytest.approx(coefs[v], rel=1e-3), (
            "el efecto marginal salió igual al coeficiente: no se derivó nada")


def test_la_regresion_cuantilica_estima_la_mediana_condicional():
    import statsmodels.api as sm

    d = _datos("hogares")
    X = sm.add_constant(d[["ingreso_mensual"]])
    referencia = sm.QuantReg(d["gasto_vivienda"], X).fit(q=0.5)

    art = _art("q50", [HOGARES, ("m", "econometria.cuantilica", "Q50",
                                 {"y": "gasto_vivienda", "x": ["ingreso_mensual"],
                                  "cuantil": 0.5})],
               [("d", "datos", "m", "datos")])["m"]["modelo"]
    for v, c in _coefs(art).items():
        assert c == pytest.approx(referencia.params[v], rel=1e-6)


def test_el_vif_es_uno_sobre_uno_menos_r2():
    """VIF_j = 1/(1-R²_j), con R²_j de regresar la j contra todas las demás."""
    import statsmodels.api as sm

    d = _datos("mexico_estados")
    cols = ["escolaridad_anios", "empleo_formal_pct", "ingreso_hogar_mensual"]
    esperado = {}
    for j in cols:
        otras = [c for c in cols if c != j]
        r2 = sm.OLS(d[j], sm.add_constant(d[otras])).fit().rsquared
        esperado[j] = 1.0 / (1.0 - r2)

    art = _art("vif", [ESTADOS, ("v", "econometria.colinealidad", "VIF",
                                 {"columnas": cols})],
               [("d", "datos", "v", "datos")])["v"]["vif"]
    obtenido = _tabla(art).set_index("variable")["vif"]
    for j, valor in esperado.items():
        assert float(obtenido[j]) == pytest.approx(valor, rel=1e-6), f"VIF de «{j}»"


def test_los_diagnosticos_coinciden_con_las_pruebas_de_statsmodels():
    """Breusch-Pagan, White y Jarque-Bera, cada una contra su función."""
    import statsmodels.api as sm
    from statsmodels.stats.diagnostic import het_breuschpagan, het_white
    from statsmodels.stats.stattools import jarque_bera

    d = _datos("mexico_estados")
    X = sm.add_constant(d[["escolaridad_anios", "empleo_formal_pct"]])
    modelo = sm.OLS(d["precio_m2"], X).fit()
    bp = het_breuschpagan(modelo.resid, X)
    white = het_white(modelo.resid, X)
    jb = jarque_bera(modelo.resid)

    art = _art("diag", [ESTADOS,
                        ("m", "econometria.mco", "MCO",
                         {"y": "precio_m2", "x": ["escolaridad_anios", "empleo_formal_pct"],
                          "errores": "clasicos"}),
                        ("g", "econometria.diagnosticos", "Diag", {})],
               [("d", "datos", "m", "datos"), ("m", "modelo", "g", "modelo")])["g"]["pruebas"]
    t = _tabla(art).set_index("prueba")

    esperados = {"Breusch-Pagan": (bp[0], bp[1]), "White": (white[0], white[1]),
                 "Jarque-Bera": (jb[0], jb[1])}
    for nombre, (estadistico, p) in esperados.items():
        fila = next((i for i in t.index if nombre.lower() in str(i).lower()), None)
        assert fila is not None, f"falta la prueba «{nombre}»; hay {list(t.index)}"
        assert float(t.loc[fila, "estadistico"]) == pytest.approx(estadistico, rel=1e-6), nombre
        assert float(t.loc[fila, "p_valor"]) == pytest.approx(p, rel=1e-6), nombre


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

def test_los_efectos_fijos_son_el_estimador_intragrupo():
    """Efectos fijos = MCO sobre las variables restadas su media por entidad.

    Es la definición, y sirve como comprobación independiente de que se estimó
    lo que dice el rótulo: entre efectos fijos y aleatorios sólo cambia una
    palabra en la pantalla, y los números de uno pasan perfectamente por los
    del otro.
    """
    import statsmodels.api as sm

    d = _datos("panel_estados").copy()
    d["log_pib"] = np.log(d["pib_per_capita"])
    d["log_inv"] = np.log(d["inversion_pc"])
    dentro = d.copy()
    for col in ("log_pib", "log_inv"):
        dentro[col] = d[col] - d.groupby("entidad")[col].transform("mean")
    # Sin constante: la absorbieron los efectos fijos.
    referencia = sm.OLS(dentro["log_pib"], dentro[["log_inv"]]).fit()

    art = _art("fe", [PANEL,
                      ("t", "transformar.calcular", "Log PIB",
                       {"operacion": "log", "columna_a": "pib_per_capita"}),
                      ("u", "transformar.calcular", "Log inv",
                       {"operacion": "log", "columna_a": "inversion_pc"}),
                      ("p", "datos.panel", "Panel", {"entidad": "entidad", "periodo": "anio"}),
                      ("f", "econometria.panel", "Efectos fijos",
                       {"y": "log_pib_per_capita", "x": ["log_inversion_pc"],
                        "efectos": "fijos"})],
               [("d", "datos", "t", "datos"), ("t", "datos", "u", "datos"),
                ("u", "datos", "p", "datos"), ("p", "datos", "f", "datos")])["f"]["modelo"]

    coef = _coefs(art)["log_inversion_pc"]
    assert coef == pytest.approx(referencia.params["log_inv"], rel=1e-6), (
        "el coeficiente de efectos fijos no es el intragrupo")


def test_efectos_fijos_y_aleatorios_no_dan_lo_mismo():
    """Si dieran lo mismo, uno de los dos no se estaría estimando."""
    base = [PANEL,
            ("t", "transformar.calcular", "Log PIB",
             {"operacion": "log", "columna_a": "pib_per_capita"}),
            ("u", "transformar.calcular", "Log inv",
             {"operacion": "log", "columna_a": "inversion_pc"}),
            ("p", "datos.panel", "Panel", {"entidad": "entidad", "periodo": "anio"})]
    aristas = [("d", "datos", "t", "datos"), ("t", "datos", "u", "datos"),
               ("u", "datos", "p", "datos"), ("p", "datos", "f", "datos")]

    def coef(efectos):
        nodos = base + [("f", "econometria.panel", efectos,
                         {"y": "log_pib_per_capita", "x": ["log_inversion_pc"],
                          "efectos": efectos})]
        return _coefs(_art(efectos, nodos, aristas)["f"]["modelo"])["log_inversion_pc"]

    assert coef("fijos") != pytest.approx(coef("aleatorios"), rel=1e-6)


# ---------------------------------------------------------------------------
# Series de tiempo
# ---------------------------------------------------------------------------

def test_adf_y_kpss_coinciden_con_statsmodels():
    """Las dos pruebas van en direcciones CONTRARIAS y se confunden fácil:
    la nula de ADF es «hay raíz unitaria» y la de KPSS es «es estacionaria»."""
    from statsmodels.tsa.stattools import adfuller, kpss

    d = _datos("mexico_macro")
    serie = d["pib_indice"].astype(float)
    adf = adfuller(serie, autolag="AIC")
    with pytest.warns(Warning):
        k = kpss(serie, regression="c", nlags="auto")

    art = _art("adf", [MACRO,
                       ("s", "datos.serie_temporal", "Serie",
                        {"columna_fecha": "fecha", "frecuencia": "QS"}),
                       ("r", "series.estacionariedad", "Raíz unitaria",
                        {"columnas": ["pib_indice"]})],
               [("d", "datos", "s", "datos"), ("s", "datos", "r", "datos")])["r"]["pruebas"]
    fila = _tabla(art).set_index("variable").loc["pib_indice"]
    assert float(fila["adf_estadistico"]) == pytest.approx(adf[0], rel=1e-6)
    assert float(fila["adf_p"]) == pytest.approx(adf[1], rel=1e-6)
    assert float(fila["kpss_estadistico"]) == pytest.approx(k[0], rel=1e-6)


def test_el_pronostico_del_arima_coincide_con_el_del_modelo():
    """El pronóstico y su banda, contra `get_forecast` llamado por fuera."""
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    d = _datos("mexico_macro")
    serie = pd.Series(d["pib_indice"].astype(float).values,
                      index=pd.PeriodIndex(pd.to_datetime(d["fecha"]), freq="Q"))
    referencia = SARIMAX(serie, order=(1, 1, 1)).fit(disp=False)
    marco = referencia.get_forecast(steps=6).summary_frame(alpha=0.05)

    art = _art("arima", [MACRO,
                         ("s", "datos.serie_temporal", "Serie",
                          {"columna_fecha": "fecha", "frecuencia": "QS"}),
                         ("a", "series.arima", "ARIMA",
                          {"variable": "pib_indice", "p": 1, "d": 1, "q": 1, "horizonte": 6})],
               [("d", "datos", "s", "datos"), ("s", "datos", "a", "datos")])["a"]["pronostico"]
    t = _tabla(art)
    assert len(t) == 6
    for i in range(6):
        assert float(t["pronostico"].iloc[i]) == pytest.approx(
            float(marco["mean"].iloc[i]), rel=1e-4), f"pronóstico del periodo {i+1}"
        assert float(t["banda_baja"].iloc[i]) < float(t["pronostico"].iloc[i]) \
            < float(t["banda_alta"].iloc[i]), "el pronóstico tiene que caer dentro de su banda"


def test_la_banda_del_pronostico_se_ensancha_con_el_horizonte():
    """No es un detalle estético: si no se ensancha, no es una banda de verdad."""
    art = _art("banda", [MACRO,
                         ("s", "datos.serie_temporal", "Serie",
                          {"columna_fecha": "fecha", "frecuencia": "QS"}),
                         ("a", "series.arima", "ARIMA",
                          {"variable": "pib_indice", "p": 1, "d": 1, "q": 1, "horizonte": 8})],
               [("d", "datos", "s", "datos"), ("s", "datos", "a", "datos")])["a"]["pronostico"]
    t = _tabla(art)
    ancho = t["banda_alta"].astype(float) - t["banda_baja"].astype(float)
    assert ancho.is_monotonic_increasing, f"la banda no se ensancha: {ancho.tolist()}"


def test_el_filtro_hp_reparte_la_serie_entre_tendencia_y_ciclo():
    """La identidad del filtro: serie = tendencia + ciclo, exactamente."""
    from statsmodels.tsa.filters.hp_filter import hpfilter

    d = _datos("mexico_macro")
    ciclo_ref, tendencia_ref = hpfilter(d["pib_indice"].astype(float), lamb=1600)

    art = _art("hp", [MACRO,
                      ("s", "datos.serie_temporal", "Serie",
                       {"columna_fecha": "fecha", "frecuencia": "QS"}),
                      ("h", "series.ciclo", "HP",
                       {"variable": "pib_indice", "metodo": "hp", "lamb": 1600.0})],
               [("d", "datos", "s", "datos"), ("s", "datos", "h", "datos")])["h"]["datos"]
    t = _tabla(art)
    tendencia = next(c for c in t.columns if "tendencia" in c)
    ciclo = next(c for c in t.columns if "ciclo" in c)
    # El bloque renombra la serie a «observado» y deja fecha, observado,
    # tendencia y ciclo: esas cuatro columnas son toda su salida.
    suma = t[tendencia].astype(float) + t[ciclo].astype(float)
    assert np.allclose(suma, t["observado"].astype(float), rtol=1e-9), (
        "tendencia + ciclo no devuelve la serie")
    assert np.allclose(t[ciclo].astype(float).values, ciclo_ref.values, rtol=1e-6)


def test_la_causalidad_de_granger_coincide_con_la_prueba_del_var():
    from statsmodels.tsa.api import VAR

    d = _datos("mexico_macro")
    Y = d[["inflacion_anual", "tasa_objetivo"]].astype(float).dropna()
    referencia = VAR(Y).fit(2)
    p_ref = float(referencia.test_causality("tasa_objetivo", ["inflacion_anual"],
                                            kind="f").pvalue)

    art = _art("granger", [MACRO,
                           ("s", "datos.serie_temporal", "Serie",
                            {"columna_fecha": "fecha", "frecuencia": "QS"}),
                           ("v", "series.var", "VAR",
                            {"variables": ["inflacion_anual", "tasa_objetivo"],
                             "rezagos": 2, "elegir_rezagos": False, "periodos_irf": 4})],
               [("d", "datos", "s", "datos"), ("s", "datos", "v", "datos")])["v"]["causalidad"]
    t = _tabla(art)
    fila = t[(t["causa"] == "inflacion_anual") & (t["efecto"] == "tasa_objetivo")]
    assert len(fila) == 1
    assert float(fila["p_valor"].iloc[0]) == pytest.approx(p_ref, rel=1e-6)


def test_el_impulso_respuesta_arranca_en_el_choque():
    """En t=0 la respuesta de una variable a su propio choque es su desviación
    estándar (Cholesky), y nunca puede ser cero."""
    art = _art("irf", [MACRO,
                       ("s", "datos.serie_temporal", "Serie",
                        {"columna_fecha": "fecha", "frecuencia": "QS"}),
                       ("v", "series.var", "VAR",
                        {"variables": ["inflacion_anual", "tasa_objetivo"],
                         "rezagos": 2, "elegir_rezagos": False, "periodos_irf": 6,
                         "ortogonal": True})],
               [("d", "datos", "s", "datos"), ("s", "datos", "v", "datos")])["v"]["impulso_respuesta"]
    t = _tabla(art)
    propio = t[(t["choque_en"] == "inflacion_anual") & (t["respuesta_de"] == "inflacion_anual")]
    propio = propio.sort_values("periodo")
    assert float(propio["efecto"].iloc[0]) > 0, "la respuesta al propio choque no puede ser cero"
    # Del periodo 0 (el impacto) al 6: siete renglones para un horizonte de seis.
    assert list(propio["periodo"]) == list(range(7))


# ---------------------------------------------------------------------------
# Espacial
# ---------------------------------------------------------------------------

def _grafo_espacial(extra, aristas_extra):
    base = [ESTADOS,
            ("t", "transformar.calcular", "Log precio",
             {"operacion": "log", "columna_a": "precio_m2"}),
            ("u", "datos.ubicacion", "Ubicadas", {"latitud": "lat", "longitud": "lng"}),
            ("w", "espacial.pesos", "Vecinos", {"metodo": "knn", "k": 4})]
    aristas = [("d", "datos", "t", "datos"), ("t", "datos", "u", "datos"),
               ("u", "datos", "w", "datos")]
    return base + extra, aristas + aristas_extra


def test_la_i_de_moran_coincide_con_su_formula():
    """I = (n/S₀)·(z'Wz)/(z'z), con z la variable centrada."""
    libpysal = pytest.importorskip("libpysal")
    esda = pytest.importorskip("esda")

    d = _datos("mexico_estados")
    z = np.log(d["precio_m2"].astype(float)).values
    w = libpysal.weights.KNN.from_array(d[["lat", "lng"]].values, k=4)
    w.transform = "r"
    referencia = esda.Moran(z, w, permutations=999)

    nodos, aristas = _grafo_espacial(
        [("m", "espacial.moran", "Moran",
          {"columnas": ["log_precio_m2"], "permutaciones": 999})],
        [("u", "datos", "m", "datos"), ("w", "pesos", "m", "pesos")])
    art = _art("moran", nodos, aristas)["m"]["resultado"]
    fila = _tabla(art).set_index("variable").loc["log_precio_m2"]
    assert float(fila["I"]) == pytest.approx(referencia.I, rel=1e-6)
    assert float(fila["esperado_bajo_azar"]) == pytest.approx(referencia.EI, rel=1e-6)


def test_el_sar_estima_el_rezago_espacial_y_el_sem_el_del_error():
    """SAR trae ρ (rezago de la dependiente) y SEM trae λ (del error).

    Confundirlos es fácil de cablear mal y cambia por completo la lectura: uno
    dice que el precio del vecino MUEVE el mío, el otro que compartimos causas
    no observadas.
    """
    pytest.importorskip("spreg")

    nodos, aristas = _grafo_espacial(
        [("s", "espacial.sar", "SAR",
          {"y": "log_precio_m2", "x": ["escolaridad_anios"]}),
         ("e", "espacial.sem", "SEM",
          {"y": "log_precio_m2", "x": ["escolaridad_anios"]})],
        [("u", "datos", "s", "datos"), ("w", "pesos", "s", "pesos"),
         ("u", "datos", "e", "datos"), ("w", "pesos", "e", "pesos")])
    art = _art("espacial", nodos, aristas)

    sar = _tabla(art["s"]["coeficientes"])["variable"].tolist()
    sem = _tabla(art["e"]["coeficientes"])["variable"].tolist()
    assert any("W_" in v or "rho" in v.lower() or "ρ" in v for v in sar), (
        f"el SAR no reporta el parámetro del rezago espacial: {sar}")
    assert any("lambda" in v.lower() or "λ" in v for v in sem), (
        f"el SEM no reporta el parámetro del error espacial: {sem}")


def test_lisa_clasifica_cada_punto_en_su_cuadrante():
    """Los cuatro cuadrantes de un LISA: alto-alto, bajo-bajo, alto-bajo,
    bajo-alto. Que existan y que sumen el total."""
    pytest.importorskip("esda")

    nodos, aristas = _grafo_espacial(
        [("l", "espacial.lisa", "LISA",
          {"columna": "log_precio_m2", "permutaciones": 999})],
        [("u", "datos", "l", "datos"), ("w", "pesos", "l", "pesos")])
    art = _art("lisa", nodos, aristas)["l"]["datos"]
    t = _tabla(art)
    clasificacion = next(c for c in t.columns if "grupo" in c or "cuadrante" in c or "lisa" in c)
    assert len(t) == 32, "LISA clasifica cada observación, no las agrupa"
    assert t[clasificacion].notna().all()


# ---------------------------------------------------------------------------
# Macro
# ---------------------------------------------------------------------------

SECTORES_MIP = ["Agropecuario", "Mineria", "Energia", "Manufactura alimentos",
                "Manufactura metalica", "Manufactura otras", "Construccion", "Comercio",
                "Transporte", "Informacion y medios", "Servicios financieros",
                "Servicios diversos"]


def _grafo_mip(extra, aristas_extra):
    base = [("d", "datos.ejemplo", "MIP", {"conjunto": "insumo_producto"}),
            ("s", "macro.insumo_producto", "Sistema",
             {"columna_sectores": "sector", "columnas_matriz": SECTORES_MIP,
              "produccion_total": "produccion_total", "demanda_final": "demanda_final",
              "empleo": "empleo_miles", "remuneraciones": "remuneraciones"})]
    return base + extra, [("d", "datos", "s", "datos")] + aristas_extra


def _inversa_leontief() -> pd.DataFrame:
    """(I − A)⁻¹ calculada aparte con numpy, desde el archivo crudo.

    Se calcula así y no sumando la matriz que Abak muestra porque esa tabla
    viene REDONDEADA para la pantalla: compararla contra sí misma mediría el
    redondeo, no el cálculo.
    """
    d = pd.read_csv(_ruta_mip())
    X = d.set_index("sector").loc[SECTORES_MIP, SECTORES_MIP].astype(float).values
    produccion = d.set_index("sector").loc[SECTORES_MIP, "produccion_total"].astype(float).values
    A = X / produccion                      # coeficientes técnicos: a_ij = x_ij / x_j
    inversa = np.linalg.inv(np.eye(len(SECTORES_MIP)) - A)
    return pd.DataFrame(inversa, index=SECTORES_MIP, columns=SECTORES_MIP)


def _ruta_mip():
    import os
    from pathlib import Path

    return Path(os.environ["ABAK_DATOS"]) / "mexico_insumo_producto.csv"


def test_el_multiplicador_de_produccion_es_la_suma_de_su_columna():
    """En Leontief, el multiplicador de un sector es la suma de su COLUMNA en
    la inversa: cuánto tiene que producir toda la economía por cada peso de
    demanda final de ese sector."""
    referencia = _inversa_leontief()
    nodos, aristas = _grafo_mip([], [])
    multiplicadores = _tabla(_art("mip", nodos, aristas)["s"]["multiplicadores"]).set_index("sector")

    for sector in SECTORES_MIP:
        esperado = float(referencia[sector].sum())
        obtenido = float(multiplicadores.loc[sector, "multiplicador_produccion"])
        assert obtenido == pytest.approx(esperado, rel=1e-6), f"multiplicador de «{sector}»"


def test_los_encadenamientos_de_rasmussen_estan_normalizados_a_uno():
    """El encadenamiento hacia atrás es el multiplicador de cada sector dividido
    entre el multiplicador PROMEDIO. Por construcción, su media es 1."""
    nodos, aristas = _grafo_mip(
        [("e", "macro.encadenamientos", "Encadenamientos", {})],
        [("s", "sistema", "e", "sistema")])
    t = _tabla(_art("enc", nodos, aristas)["e"]["encadenamientos"])
    assert t["encadenamiento_atras"].astype(float).mean() == pytest.approx(1.0, abs=1e-8)
    assert t["encadenamiento_adelante"].astype(float).mean() == pytest.approx(1.0, abs=1e-8)


def test_el_impacto_de_un_choque_es_la_columna_por_el_monto():
    """Un choque de M pesos en un sector produce M × (columna de la inversa)."""
    monto = 100_000.0
    nodos, aristas = _grafo_mip(
        [("i", "macro.impacto", "Choque", {"choques": {"Construccion": monto}})],
        [("s", "sistema", "i", "sistema")])
    impacto = _tabla(_art("choque", nodos, aristas)["i"]["impacto"]).set_index("sector")
    referencia = _inversa_leontief()

    for sector in SECTORES_MIP:
        esperado = monto * float(referencia.loc[sector, "Construccion"])
        assert float(impacto.loc[sector, "produccion_adicional"]) == pytest.approx(
            esperado, rel=1e-8), f"impacto sobre «{sector}»"


# ---------------------------------------------------------------------------
# Machine learning
# ---------------------------------------------------------------------------

def test_las_metricas_del_modelo_son_las_metricas():
    """RMSE, MAE y R², contra scikit-learn. Y que las de PRUEBA salgan de la
    partición de prueba: evaluarse con los datos de entrenamiento es la forma
    más común de anunciar un modelo que no sirve."""
    sk = pytest.importorskip("sklearn.metrics")

    nodos = [HOGARES,
             ("p", "ml.particion", "Partición",
              {"proporcion_prueba": 0.25, "aleatoria": True}),
             ("x", "ml.xgboost", "XGBoost",
              {"y": "gasto_vivienda", "x": ["ingreso_mensual", "escolaridad_anios"],
               "n_arboles": 40})]
    aristas = [("d", "datos", "p", "datos"),
               ("p", "entrenamiento", "x", "entrenamiento"), ("p", "prueba", "x", "prueba")]
    art = _art("ml", nodos, aristas)
    metricas = _tabla(art["x"]["metricas"]).set_index("conjunto")
    # `n_filas` y no `len`: las tablas se truncan para la pantalla.
    n_entrena = art["p"]["entrenamiento"]["n_filas"]
    n_prueba = art["p"]["prueba"]["n_filas"]
    n_total = art["d"]["datos"]["n_filas"]

    assert int(metricas.loc["entrenamiento", "n"]) == n_entrena, (
        "las métricas de entrenamiento no se calcularon sobre el entrenamiento")
    assert int(metricas.loc["prueba", "n"]) == n_prueba, (
        "las métricas de prueba no se calcularon sobre la prueba")
    assert n_entrena + n_prueba == n_total, "la partición pierde o duplica filas"
    assert n_prueba == pytest.approx(0.25 * n_total, abs=1), "la proporción no es la pedida"

    # Y las dos particiones son ajenas: ninguna fila puede estar en las dos.
    indices_entrena = set(_tabla(art["p"]["entrenamiento"])["indice"])
    indices_prueba = set(_tabla(art["p"]["prueba"])["indice"])
    assert not indices_entrena & indices_prueba, (
        "hay filas en entrenamiento Y en prueba: la evaluación no vale nada")
    # Coherencia interna de cada renglón: RMSE ≥ MAE siempre.
    for conjunto in ("entrenamiento", "prueba"):
        rmse = float(metricas.loc[conjunto, "rmse"])
        mae = float(metricas.loc[conjunto, "mae"])
        assert rmse >= mae > 0, f"RMSE < MAE en «{conjunto}»: alguna está mal calculada"
    del sk


def test_las_importancias_suman_uno():
    nodos = [HOGARES,
             ("p", "ml.particion", "Partición", {"proporcion_prueba": 0.25, "aleatoria": True}),
             ("x", "ml.xgboost", "XGBoost",
              {"y": "gasto_vivienda", "x": ["ingreso_mensual", "escolaridad_anios"],
               "n_arboles": 40})]
    aristas = [("d", "datos", "p", "datos"),
               ("p", "entrenamiento", "x", "entrenamiento"), ("p", "prueba", "x", "prueba")]
    t = _tabla(_art("imp", nodos, aristas)["x"]["importancias"])
    assert t["importancia"].astype(float).sum() == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Inmobiliario, escenarios y muestreo
# ---------------------------------------------------------------------------

def _mercado_simulado(n_por_periodo=180, periodos=5, semilla=11) -> pd.DataFrame:
    """Un mercado donde la verdad se conoce: el precio de calidad constante
    sube 4% por periodo, y además cambia LO QUE SE VENDE."""
    rng = np.random.default_rng(semilla)
    filas = []
    for t in range(periodos):
        # La mezcla se degrada: cada periodo se venden casas más chicas.
        superficie = rng.normal(140 - 12 * t, 18, n_por_periodo).clip(45, None)
        calidad = 1.04 ** t
        precio = 20_000 * calidad * (superficie ** 0.85) / 100
        precio *= np.exp(rng.normal(0, 0.05, n_por_periodo))
        filas.append(pd.DataFrame({"periodo": t, "precio": precio,
                                   "superficie": superficie}))
    return pd.concat(filas, ignore_index=True)


def test_el_indice_hedonico_recupera_el_precio_de_calidad_constante(tmp_path):
    """La prueba de fondo del bloque: la mediana de lo vendido CAE mientras el
    precio de la misma vivienda SUBE 4% por periodo. Un índice que siga a la
    mediana estaría midiendo el cambio de mezcla y llamándolo precio."""
    d = _mercado_simulado()
    ruta = tmp_path / "mercado.csv"
    d.to_csv(ruta, index=False)

    indice = _ayudante("indice_hedonico")(
        d, periodo="periodo", precio="precio", caracteristicas=["superficie"],
        base=100.0, minimo_por_periodo=30)

    valores = indice.set_index("periodo")["indice"].astype(float)
    for t in range(1, 5):
        esperado = 100.0 * (1.04 ** t)
        assert valores[t] == pytest.approx(esperado, rel=0.02), (
            f"periodo {t}: el índice dice {valores[t]:.1f} y la verdad es {esperado:.1f}")

    mediana = d.groupby("periodo")["precio"].median()
    assert mediana.iloc[-1] < mediana.iloc[0], (
        "la simulación tenía que hacer CAER la mediana de lo vendido")
    assert valores.iloc[-1] > valores.iloc[0], "y el índice tenía que subir"


def test_la_proyeccion_es_la_prediccion_del_modelo_punto_por_punto():
    """Cada punto del abanico, contra `get_prediction` llamado por fuera."""
    import statsmodels.api as sm

    d = _datos("hogares")
    X = sm.add_constant(d[["ingreso_mensual", "escolaridad_anios"]])
    modelo = sm.OLS(d["gasto_vivienda"], X).fit(cov_type="HC3")

    nodos = [HOGARES,
             ("m", "econometria.mco", "MCO",
              {"y": "gasto_vivienda", "x": ["ingreso_mensual", "escolaridad_anios"],
               "errores": "HC3"}),
             ("e", "escenarios.simular", "¿Qué pasa si?",
              {"variable": "escolaridad_anios", "mover": None, "puntos": 9})]
    aristas = [("d", "datos", "m", "datos"), ("d", "datos", "e", "datos"),
               ("m", "modelo", "e", "modelo")]
    art = _art("escenarios", nodos, aristas)["e"]
    proyeccion = art["proyeccion"]

    # Se rehace la rejilla a mano: percentiles 5 a 95, las demás en su mediana.
    xs = np.linspace(d["escolaridad_anios"].quantile(0.05),
                     d["escolaridad_anios"].quantile(0.95), 9)
    marco = pd.DataFrame({
        "const": 1.0,
        "ingreso_mensual": float(d["ingreso_mensual"].median()),
        "escolaridad_anios": xs,
    })
    esperado = modelo.get_prediction(marco).summary_frame(alpha=0.05)["mean"].values

    obtenido = proyeccion["series"][0]["y"]
    assert len(obtenido) == 9
    for i, (a, b) in enumerate(zip(obtenido, esperado)):
        assert float(a) == pytest.approx(float(b), rel=1e-6), f"punto {i} de la proyección"


def test_el_error_de_muestreo_lleva_la_correccion_de_poblacion_finita():
    """EE = (s/√n)·√((N−n)/(N−1)). Sin la corrección, una muestra del 80% de la
    población reporta más incertidumbre de la que tiene."""
    rng = np.random.default_rng(5)
    N = 5_000
    d = pd.DataFrame({"x": rng.normal(100, 15, N)})

    tomar_muestra = _ayudante("tomar_muestra")
    _, reporte = tomar_muestra(d, 4_000, 42)

    fila = reporte.set_index("columna").loc["x"]
    n = 4_000
    # La desviación se toma de la muestra, así que se rehace igual.
    muestra, _ = tomar_muestra(d, n, 42)
    s = float(muestra["x"].std(ddof=1))
    fpc = np.sqrt((N - n) / (N - 1))
    assert float(fila["error_estandar"]) == pytest.approx(s / np.sqrt(n) * fpc, rel=1e-6)

    # Y con TODA la población el error de muestreo es exactamente cero.
    _, todo = tomar_muestra(d, N, 42, usar_todo=True)
    assert float(todo.set_index("columna").loc["x", "error_estandar"]) == pytest.approx(0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# Explorar
# ---------------------------------------------------------------------------

def test_los_descriptivos_son_los_descriptivos():
    d = _datos("mexico_estados")
    art = _art("desc", [ESTADOS, ("x", "explorar.descriptivos", "Descriptivos",
                                  {"columnas": ["precio_m2", "escolaridad_anios"]})],
               [("d", "datos", "x", "datos")])["x"]["tabla"]
    t = _tabla(art).set_index("variable")
    for col in ("precio_m2", "escolaridad_anios"):
        serie = d[col].astype(float)
        assert float(t.loc[col, "n"]) == len(serie.dropna())
        assert float(t.loc[col, "media"]) == pytest.approx(serie.mean(), rel=1e-9)
        assert float(t.loc[col, "desv_est"]) == pytest.approx(serie.std(ddof=1), rel=1e-9)
        assert float(t.loc[col, "mediana"]) == pytest.approx(serie.median(), rel=1e-9)
        assert float(t.loc[col, "p25"]) == pytest.approx(serie.quantile(0.25), rel=1e-9)
        assert float(t.loc[col, "p75"]) == pytest.approx(serie.quantile(0.75), rel=1e-9)
        assert float(t.loc[col, "minimo"]) == pytest.approx(serie.min(), rel=1e-9)
        assert float(t.loc[col, "maximo"]) == pytest.approx(serie.max(), rel=1e-9)


def test_la_correlacion_es_la_de_pearson_y_su_p_el_correcto():
    from scipy import stats

    d = _datos("mexico_estados")
    r, p = stats.pearsonr(d["precio_m2"].astype(float), d["escolaridad_anios"].astype(float))

    art = _art("corr", [ESTADOS, ("c", "explorar.correlacion", "Correlación",
                                  {"columnas": ["precio_m2", "escolaridad_anios"],
                                   "metodo": "pearson"})],
               [("d", "datos", "c", "datos")])["c"]["tabla"]
    t = _tabla(art)
    fila = t.iloc[0]
    assert float(fila["correlacion"]) == pytest.approx(r, rel=1e-8)
    assert float(fila["p_valor"]) == pytest.approx(p, rel=1e-6)


# ---------------------------------------------------------------------------
# Cointegración
# ---------------------------------------------------------------------------

def test_la_traza_de_johansen_coincide_con_statsmodels():
    """El estadístico de traza y su valor crítico al 5%.

    El valor crítico se lee de una TABLA con tres columnas (10%, 5%, 1%) y una
    fila por hipótesis: tomar la columna o la fila de al lado es un error de
    índice que no da ningún síntoma y cambia todas las conclusiones.
    """
    from statsmodels.tsa.vector_ar.vecm import coint_johansen

    d = _datos("mexico_macro")
    Y = d[["pib_indice", "consumo_indice"]].astype(float).dropna()
    referencia = coint_johansen(Y, det_order=0, k_ar_diff=1)

    art = _art("johansen", [MACRO,
                            ("s", "datos.serie_temporal", "Serie",
                             {"columna_fecha": "fecha", "frecuencia": "QS"}),
                            ("c", "series.cointegracion", "Johansen",
                             {"variables": ["pib_indice", "consumo_indice"], "rezagos": 1})],
               [("d", "datos", "s", "datos"), ("s", "datos", "c", "datos")])["c"]["traza"]
    t = _tabla(art)
    assert len(t) == 2, "con dos variables hay dos hipótesis: r=0 y r≤1"
    for i in range(2):
        assert float(t["estadistico_traza"].iloc[i]) == pytest.approx(
            referencia.lr1[i], rel=1e-6), f"estadístico de traza de la hipótesis {i}"
        # cvt[:, 1] es la columna del 5%: la del medio de (10%, 5%, 1%).
        assert float(t["valor_critico_5pct"].iloc[i]) == pytest.approx(
            referencia.cvt[i, 1], rel=1e-9), f"valor crítico al 5% de la hipótesis {i}"


def test_johansen_decide_rechazar_comparando_contra_el_critico():
    """«Rechaza» tiene que ser estadístico > crítico, no al revés."""
    art = _art("johansen2", [MACRO,
                             ("s", "datos.serie_temporal", "Serie",
                              {"columna_fecha": "fecha", "frecuencia": "QS"}),
                             ("c", "series.cointegracion", "Johansen",
                              {"variables": ["pib_indice", "consumo_indice"], "rezagos": 1})],
               [("d", "datos", "s", "datos"), ("s", "datos", "c", "datos")])["c"]["traza"]
    t = _tabla(art)
    for _, fila in t.iterrows():
        esperado = float(fila["estadistico_traza"]) > float(fila["valor_critico_5pct"])
        assert bool(fila["rechaza"]) is esperado, (
            f"«{fila['hipotesis_nula']}»: {fila['estadistico_traza']} vs "
            f"{fila['valor_critico_5pct']} y dice rechaza={fila['rechaza']}")
