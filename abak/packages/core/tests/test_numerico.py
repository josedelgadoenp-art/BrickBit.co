"""Precisión: los números contra valores que se pueden verificar a mano.

Que un análisis corra no dice nada de que esté bien. Estas pruebas comparan lo
que produce Abak contra resultados conocidos de antemano: fórmulas cerradas,
casos construidos con la respuesta puesta, y sistemas chicos que se resuelven
con lápiz.

Es la diferencia entre «no truena» y «da el número correcto».
"""

import numpy as np
import pandas as pd
import pytest

from abak_core import AristaSpec, GrafoSpec, NodoSpec, compilar, ejecutar
from abak_core.codegen.contexto import resolver_ayudantes


def _ayudante(nombre: str):
    """Ejecuta un ayudante aislado, igual que lo haría el script exportado."""
    espacio: dict = {}
    for ayudante in resolver_ayudantes([nombre]):
        for modulo, alias in ayudante.imports:
            espacio[alias or modulo.split(".")[0]] = __import__(modulo, fromlist=["_"])
        exec(ayudante.fuente, espacio)
    return espacio[nombre]


# --- MCO contra la solución analítica ---------------------------------------

def test_mco_recupera_exactamente_una_relacion_sin_ruido():
    """Con y = 3 + 2x exacta, los coeficientes tienen que ser 3 y 2.

    No «cerca de»: exactos hasta la precisión de la máquina. Una desviación
    aquí sería un problema en la construcción del diseño, no en los datos.
    """
    import statsmodels.api as sm

    x = np.arange(1, 501, dtype=float)
    ajuste = sm.OLS(3.0 + 2.0 * x, sm.add_constant(x)).fit()
    assert ajuste.params[0] == pytest.approx(3.0, abs=1e-9)
    assert ajuste.params[1] == pytest.approx(2.0, abs=1e-12)


def test_mco_coincide_con_la_formula_matricial():
    """β = (X'X)⁻¹X'y, calculado aparte con numpy."""
    import statsmodels.api as sm

    rng = np.random.default_rng(42)
    n = 400
    crudo = rng.normal(size=(n, 3))
    y = 1.5 + crudo @ np.array([0.8, -1.2, 0.35]) + rng.normal(0, 0.4, n)
    X = np.column_stack([np.ones(n), crudo])
    np.testing.assert_allclose(sm.OLS(y, X).fit().params,
                               np.linalg.solve(X.T @ X, X.T @ y), rtol=0, atol=1e-10)


def test_los_errores_robustos_no_mueven_los_coeficientes():
    """HC0, HC1 y HC3 estiman lo mismo; cambia sólo la inferencia.

    Si un cambio de tipo de error moviera un coeficiente, sería un fallo grave
    y muy difícil de notar mirando una tabla.
    """
    import statsmodels.api as sm

    rng = np.random.default_rng(7)
    n = 300
    x = rng.normal(size=n)
    y = 2 + 0.5 * x + rng.normal(0, np.exp(x / 2))   # heterocedasticidad a propósito
    X = sm.add_constant(x)
    base = sm.OLS(y, X).fit()
    for tipo in ("HC0", "HC1", "HC3"):
        robusto = sm.OLS(y, X).fit(cov_type=tipo)
        np.testing.assert_allclose(robusto.params, base.params, rtol=0, atol=1e-14)
        assert not np.allclose(robusto.bse, base.bse), f"{tipo} debería cambiar los errores"


# --- Leontief: un sistema que se resuelve con lápiz -------------------------

def test_leontief_contra_la_inversa_calculada_a_mano():
    """Con A = [[0.2, 0.3], [0.4, 0.1]]:

        I - A   = [[0.8, -0.3], [-0.4, 0.9]]
        det     = 0.72 - 0.12 = 0.60
        (I-A)⁻¹ = (1/0.60)·[[0.9, 0.3], [0.4, 0.8]] = [[1.5, 0.5], [2/3, 4/3]]
    """
    resolver = _ayudante("resolver_leontief")
    # OJO con la orientación, que es donde se cometen los errores:
    # A[i][j] es lo que el sector j COMPRA al sector i por cada unidad que
    # produce, así que Z[i][j] = A[i][j] · x[j] y la columna j se divide entre
    # la producción de j. En el DataFrame, la columna llamada "A" es j = A, y
    # sus renglones son los proveedores i.
    #   columna A = [A[0][0]·100, A[1][0]·100] = [0.2·100, 0.4·100] = [20, 40]
    #   columna B = [A[0][1]·200, A[1][1]·200] = [0.3·200, 0.1·200] = [60, 20]
    datos = pd.DataFrame({
        "sector": ["A", "B"],
        "A": [0.2 * 100, 0.4 * 100],
        "B": [0.3 * 200, 0.1 * 200],
        "produccion_total": [100.0, 200.0],
    })
    sistema = resolver(datos, "sector", ["A", "B"], "produccion_total")
    np.testing.assert_allclose(sistema["A"].to_numpy(),
                               np.array([[0.2, 0.3], [0.4, 0.1]]), rtol=0, atol=1e-12)
    esperado = np.array([[1.5, 0.5], [2 / 3, 4 / 3]])
    np.testing.assert_allclose(sistema["L"].to_numpy(), esperado, rtol=0, atol=1e-12)
    np.testing.assert_allclose(
        sistema["multiplicadores"]["multiplicador_produccion"].to_numpy(),
        esperado.sum(axis=0), rtol=0, atol=1e-12)


def test_leontief_satisface_su_propia_identidad():
    """x = (I-A)⁻¹f tiene que devolver la producción observada.

    Cierra el círculo: si la inversa estuviera mal, este residuo no daría cero.
    """
    resolver = _ayudante("resolver_leontief")
    rng = np.random.default_rng(3)
    k = 8
    sectores = [f"S{i}" for i in range(k)]
    A = rng.uniform(0.01, 0.08, (k, k))
    x = rng.uniform(500, 5000, k)
    Z = A * x
    demanda = x - Z.sum(axis=1)

    datos = pd.DataFrame(Z, columns=sectores)
    datos.insert(0, "sector", sectores)
    datos["produccion_total"] = x
    datos["demanda_final"] = demanda

    sistema = resolver(datos, "sector", sectores, "produccion_total", demanda_col="demanda_final")
    np.testing.assert_allclose(sistema["L"].to_numpy() @ demanda, x, rtol=1e-10, atol=1e-8)


def test_impacto_de_demanda_es_la_columna_de_la_inversa():
    resolver = _ayudante("resolver_leontief")
    impacto = _ayudante("impacto_demanda")
    datos = pd.DataFrame({
        "sector": ["A", "B"], "A": [20.0, 60.0], "B": [40.0, 20.0],
        "produccion_total": [100.0, 200.0],
    })
    sistema = resolver(datos, "sector", ["A", "B"], "produccion_total")
    tabla = impacto(sistema, {"A": 10.0})
    esperado = sistema["L"].to_numpy()[:, 0] * 10.0
    np.testing.assert_allclose(tabla["produccion_adicional"].to_numpy(), esperado,
                               rtol=0, atol=1e-12)
    assert tabla["efecto_indirecto"].iloc[0] == pytest.approx(esperado[0] - 10.0, abs=1e-12)


def test_un_sector_inexistente_se_rechaza():
    resolver = _ayudante("resolver_leontief")
    impacto = _ayudante("impacto_demanda")
    datos = pd.DataFrame({"sector": ["A", "B"], "A": [20.0, 60.0], "B": [40.0, 20.0],
                          "produccion_total": [100.0, 200.0]})
    with pytest.raises(ValueError, match="no esta en la matriz"):
        impacto(resolver(datos, "sector", ["A", "B"], "produccion_total"), {"Z": 1.0})


# --- Multiplicador keynesiano ----------------------------------------------

@pytest.mark.parametrize("c,t,m", [(0.8, 0.0, 0.0), (0.65, 0.16, 0.30), (0.9, 0.25, 0.4)])
def test_multiplicador_keynesiano(c, t, m):
    """k = 1 / (1 - c(1-t) + m), contra la aritmética directa."""
    calcular = _ayudante("multiplicador_keynesiano")
    fila = calcular(c, t, m, 1000.0).iloc[0]
    esperado = 1.0 / (1 - c * (1 - t) + m)
    assert fila["multiplicador"] == pytest.approx(esperado, rel=1e-12)
    assert fila["efecto_total_sobre_pib"] == pytest.approx(1000.0 * esperado, rel=1e-12)


def test_sin_filtraciones_se_niega_a_dar_infinito():
    calcular = _ayudante("multiplicador_keynesiano")
    with pytest.raises(ValueError, match="infinito"):
        calcular(1.0, 0.0, 0.0)


# --- Moran contra patrones construidos --------------------------------------

def test_moran_detecta_el_patron_que_se_le_puso():
    """Tablero de ajedrez -> Moran negativo. Dos bloques -> positivo."""
    esda = pytest.importorskip("esda")
    libpysal = pytest.importorskip("libpysal")

    lado = 10
    w = libpysal.weights.lat2W(lado, lado, rook=True)
    w.transform = "r"
    tablero = np.array([[(i + j) % 2 for j in range(lado)] for i in range(lado)],
                       dtype=float).ravel()
    bloques = np.array([[1.0 if i < lado / 2 else 0.0 for _ in range(lado)]
                        for i in range(lado)]).ravel()

    m_tablero = esda.moran.Moran(tablero, w, permutations=999)
    m_bloques = esda.moran.Moran(bloques, w, permutations=999)
    assert m_tablero.I < -0.5, "un tablero de ajedrez es autocorrelación negativa fuerte"
    assert m_bloques.I > 0.5, "dos bloques contiguos son autocorrelación positiva fuerte"
    assert m_tablero.p_sim < 0.05 and m_bloques.p_sim < 0.05


# --- Aritmética de las transformaciones -------------------------------------

def test_deflactar_es_una_division_exacta():
    """real = nominal / índice × base."""
    nominal = np.array([100.0, 210.0, 330.0])
    inpc = np.array([100.0, 105.0, 110.0])
    np.testing.assert_allclose(nominal / inpc * 100.0, [100.0, 200.0, 300.0],
                               rtol=0, atol=1e-12)


def test_crecimiento_porcentual_y_log_diferencia_casi_coinciden():
    """Para cambios chicos, 100·Δln(x) ≈ cambio porcentual. Se verifica que las
    dos fórmulas se implementaron bien comparándolas entre sí."""
    g = GrafoSpec(titulo="crecimiento", nodos=[
        NodoSpec(id="d", op="datos.ejemplo", etiqueta="Macro", params={"conjunto": "mexico_macro"}),
        NodoSpec(id="s", op="datos.serie_temporal", etiqueta="Serie",
                 params={"columna_fecha": "fecha", "frecuencia": "QS"}, posicion={"x": 0, "y": 1}),
        NodoSpec(id="g", op="transformar.crecimiento", etiqueta="Porcentual",
                 params={"columnas": ["pib_indice"], "tipo": "porcentaje"},
                 posicion={"x": 0, "y": 2}),
        NodoSpec(id="l", op="transformar.crecimiento", etiqueta="Log dif",
                 params={"columnas": ["pib_indice"], "tipo": "log_diferencia"},
                 posicion={"x": 0, "y": 3}),
        NodoSpec(id="e", op="explorar.descriptivos", etiqueta="Fin",
                 params={"columnas": ["g_pib_indice", "dln_pib_indice"]},
                 posicion={"x": 0, "y": 4}),
    ], aristas=[
        AristaSpec(origen="d", puerto_origen="datos", destino="s", puerto_destino="datos"),
        AristaSpec(origen="s", puerto_origen="datos", destino="g", puerto_destino="datos"),
        AristaSpec(origen="g", puerto_origen="datos", destino="l", puerto_destino="datos"),
        AristaSpec(origen="l", puerto_origen="datos", destino="e", puerto_destino="datos"),
    ])
    programa = compilar(g)
    assert not programa.hay_errores, [d.mensaje for d in programa.diagnosticos]
    resultado = ejecutar(programa)
    assert resultado.ok, [n.error.excepcion for n in resultado.nodos if n.error]

    tabla = resultado.por_nodo()["e"].artefactos["tabla"]
    columnas = [c["nombre"] for c in tabla["columnas"]]
    filas = {f[columnas.index("variable")]: f for f in tabla["filas"]}
    media_g = filas["g_pib_indice"][columnas.index("media")]
    media_l = filas["dln_pib_indice"][columnas.index("media")]
    assert abs(media_g - media_l) < 0.5


# --- Determinismo -----------------------------------------------------------

def test_dos_corridas_dan_exactamente_lo_mismo():
    """Con la misma semilla y los mismos datos, hasta el último dígito."""
    from abak_core.runtime.cache import SinCache
    from abak_core.runtime.ejecutor import Ejecutor

    g = GrafoSpec(titulo="determinismo", semilla=99, nodos=[
        NodoSpec(id="d", op="datos.ejemplo", etiqueta="Hogares", params={"conjunto": "hogares"}),
        NodoSpec(id="p", op="ml.particion", etiqueta="Partición",
                 params={"proporcion_prueba": 0.3, "aleatoria": True}, posicion={"x": 0, "y": 1}),
        NodoSpec(id="x", op="ml.xgboost", etiqueta="XGBoost",
                 params={"y": "gasto_vivienda", "x": ["ingreso_mensual", "edad_jefe"],
                         "n_arboles": 30, "profundidad": 3}, posicion={"x": 0, "y": 2}),
    ], aristas=[
        AristaSpec(origen="d", puerto_origen="datos", destino="p", puerto_destino="datos"),
        AristaSpec(origen="p", puerto_origen="entrenamiento", destino="x",
                   puerto_destino="entrenamiento"),
        AristaSpec(origen="p", puerto_origen="prueba", destino="x", puerto_destino="prueba"),
    ])

    def metricas():
        resultado = Ejecutor(cache=SinCache()).ejecutar(compilar(g))
        assert resultado.ok, [n.error.excepcion for n in resultado.nodos if n.error]
        return {tuple(f) for f in resultado.por_nodo()["x"].artefactos["metricas"]["filas"]}

    assert metricas() == metricas(), "dos corridas con la misma semilla difieren"


def test_limpiar_no_borra_las_magnitudes_pequenas():
    """Un p-valor diminuto NO puede salir como cero.

    Con `round(v, 10)` cualquier cosa por debajo de 5e-11 se volvía 0.0 exacto y
    la pantalla decía «Prob(F): 0». Ninguna probabilidad es cero: eso es afirmar
    algo que los datos no dicen.
    """
    from abak_core.runtime.artefactos import _limpio

    for v in (1e-20, 3.2e-14, 5e-300, -1e-18):
        assert _limpio(v) == pytest.approx(v, rel=1e-9), f"se borró {v}"
        assert _limpio(v) != 0.0

    # Y sigue quitando el ruido del flotante, que era para lo que estaba.
    assert _limpio(0.1 + 0.2) == 0.3
    assert _limpio(2.6749999999999998) == 2.675

    # Sale float de Python, no np.float64: lo que va a JSON no lleva numpy.
    import numpy as np
    assert type(_limpio(np.float64(1e-20))) is float
    assert _limpio(float("nan")) is None
    assert _limpio(float("inf")) is None


def test_los_p_valores_llegan_a_la_interfaz_sin_aplastarse():
    """El artefacto de un modelo conserva el p-valor por chico que sea."""
    import numpy as np
    import pandas as pd
    import statsmodels.api as sm

    from abak_core.runtime.artefactos import modelo_a_json

    # Una relación clara pero no absurda: Prob(F) ~ 4e-14. Tiene que caer por
    # debajo de 5e-11 (lo que el `round(v, 10)` de antes borraba) y por encima
    # del mínimo representable, o el aplastamiento vendría de statsmodels y no
    # de nosotros: con una relación mucho más fuerte, scipy devuelve 0.0 real
    # porque el p-valor verdadero no cabe en un flotante de doble precisión.
    rng = np.random.default_rng(0)
    x = rng.normal(size=300)
    y = 0.4 * x + rng.normal(size=300)
    res = sm.OLS(y, sm.add_constant(pd.DataFrame({"x": x}))).fit()
    assert 0.0 < res.f_pvalue < 1e-11, "el caso de prueba ya no ejercita el aplastamiento"

    art = modelo_a_json(res)
    prob = art["diagnosticos"]["Prob(F)"]
    assert prob is not None and prob > 0.0, "Prob(F) se aplastó a cero"
    assert prob == pytest.approx(res.f_pvalue, rel=1e-9)


def test_la_salida_de_un_mco_trae_lo_mismo_que_eviews():
    """Los 14 estadísticos que EViews imprime en un MCO, con sus mismos valores.

    Quien llega de EViews compara renglón por renglón. Si falta la mitad del
    bloque de abajo, la conclusión es que la herramienta es de juguete, aunque
    los coeficientes estén bien.
    """
    import numpy as np
    import pandas as pd
    import statsmodels.api as sm
    from statsmodels.stats.stattools import durbin_watson

    from abak_core.registry import glosario
    from abak_core.runtime.artefactos import modelo_a_json

    rng = np.random.default_rng(0)
    X = pd.DataFrame({f"X{i}": rng.normal(size=40) for i in range(1, 5)})
    y = X @ [0.17, -1.56, 1.57, 1.63] + rng.normal(scale=24, size=40)
    res = sm.OLS(y, sm.add_constant(X)).fit()
    d = modelo_a_json(res)["diagnosticos"]

    esperado = {
        "R²": res.rsquared, "R² ajustada": res.rsquared_adj,
        "Log-verosimilitud": res.llf, "AIC": res.aic, "BIC": res.bic,
        "F": res.fvalue, "Prob(F)": res.f_pvalue, "Observaciones": res.nobs,
        "E.E. de la regresión": np.sqrt(res.mse_resid),
        "Suma de residuos²": res.ssr,
        "Media de la dependiente": np.mean(res.model.endog),
        "D.E. de la dependiente": np.std(res.model.endog, ddof=1),
        "Durbin-Watson": durbin_watson(np.asarray(res.resid)),
    }
    for k, v in esperado.items():
        assert k in d, f"falta {k}, que EViews sí imprime"
        assert d[k] == pytest.approx(float(v), rel=1e-9), k

    # Hannan-Quinn: -2·log L + 2·k·ln(ln n), con k contando la constante.
    hq = -2 * res.llf + 2 * (res.df_model + 1) * np.log(np.log(res.nobs))
    assert d["Hannan-Quinn"] == pytest.approx(hq, rel=1e-9)

    # Y ninguno se queda sin explicación en pantalla.
    sin_ficha = [k for k in d if glosario.buscar(k) is None]
    assert not sin_ficha, f"indicadores sin ficha: {sin_ficha}"
