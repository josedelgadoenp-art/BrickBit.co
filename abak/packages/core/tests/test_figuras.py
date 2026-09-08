"""Las figuras automaticas existen de verdad.

`figura_opcional` se traga cualquier excepcion a proposito: una grafica es
presentacion y no puede costar el resultado del modelo. El precio de esa
decision es que un constructor roto no rompe ninguna prueba — desaparece en
silencio y el usuario simplemente deja de ver graficas.

Esta prueba paga ese precio: por cada familia dice QUE figura tiene que salir,
y falla si no sale. Es el unico lugar del repositorio donde la ausencia de una
grafica es un error.
"""

import pytest

from abak_core import compilar, ejecutar

from .conftest import grafo
from .test_nodos import FLUJOS

pytest.importorskip("statsmodels")
pytest.importorskip("plotly")


def _artefactos(nombre):
    """{id del nodo: sus artefactos}. `resultado.nodos` es una LISTA, no un dict."""
    nodos, aristas = FLUJOS[nombre]
    resultado = ejecutar(compilar(grafo(nombre, nodos, aristas)))
    return {r.nodo_id: (r.artefactos or {}) for r in resultado.nodos}, resultado


# (flujo, nodo, clave del artefacto esperado)
ESPERADAS = [
    ("series", "a", "figura_pronostico"),          # ARIMA: el abanico
    ("series", "v", "figura_impulso_respuesta"),   # VAR: la rejilla
    ("espacial", "s", "figura_coeficientes"),      # SAR
    ("panel", "f", "figura_coeficientes"),         # efectos fijos
    ("insumo_producto", "s", "figura_multiplicadores"),
    ("explorar", None, "figura_cajas"),            # descriptivos
]


@pytest.mark.parametrize("flujo,nodo,clave", ESPERADAS)
def test_la_figura_automatica_sale(flujo, nodo, clave):
    arts, resultado = _artefactos(flujo)
    if nodo is None:
        encontrada = any(clave in a for a in arts.values())
        assert encontrada, (f"ningun nodo de «{flujo}» produjo «{clave}». "
                            f"Bitacora: {resultado.bitacora[-3:]}")
        return
    assert clave in arts.get(nodo, {}), (
        f"«{flujo}/{nodo}» no produjo «{clave}»; trae {sorted(arts.get(nodo, {}))}. "
        f"Bitacora: {resultado.bitacora[-3:]}")


@pytest.mark.parametrize("flujo,nodo,clave", ESPERADAS)
def test_la_figura_es_una_figura_de_plotly(flujo, nodo, clave):
    arts, _ = _artefactos(flujo)
    candidatas = [a[clave] for a in arts.values() if clave in a]
    assert candidatas
    fig = candidatas[0]
    assert fig["tipo"] == "figura"
    assert fig["figura"].get("data"), "la figura salio sin trazos"


def test_la_regresion_trae_coeficientes_y_ajuste():
    """MCO es el nodo mas usado: sus dos figuras no pueden faltar."""
    nodos = [("d", "datos.ejemplo", "Entidades", {"conjunto": "mexico_estados"}),
             ("m", "econometria.mco", "MCO",
              {"y": "precio_m2", "x": ["escolaridad_anios", "empleo_formal_pct"], "errores": "HC3"})]
    aristas = [("d", "datos", "m", "datos")]
    r = ejecutar(compilar(grafo("figuras de MCO", nodos, aristas)))
    arts = {n.nodo_id: (n.artefactos or {}) for n in r.nodos}["m"]
    assert "figura_coeficientes" in arts, sorted(arts)
    assert "figura_ajuste" in arts, sorted(arts)


def test_el_ambar_no_se_usa_como_color_decorativo():
    """#F5C277 marca lo estimado. Si aparece en una figura, es por eso.

    Se revisa donde mas facil seria colarse: el bosque de coeficientes, que no
    dibuja ninguna serie estimada y por lo tanto no puede traer ambar.
    """
    import json

    nodos = [("d", "datos.ejemplo", "Entidades", {"conjunto": "mexico_estados"}),
             ("m", "econometria.mco", "MCO",
              {"y": "precio_m2", "x": ["escolaridad_anios"], "errores": "HC3"})]
    r = ejecutar(compilar(grafo("ámbar", nodos, [("d", "datos", "m", "datos")])))
    arts = {n.nodo_id: (n.artefactos or {}) for n in r.nodos}["m"]
    texto = json.dumps(arts["figura_coeficientes"])
    assert "F5C277" not in texto.upper(), "el ámbar se coló como color decorativo"


# ---------------------------------------------------------------------------
# Proyecciones interactivas
# ---------------------------------------------------------------------------

def _proyeccion():
    nodos = [("d", "datos.ejemplo", "Entidades", {"conjunto": "mexico_estados"}),
             ("m", "econometria.mco", "MCO",
              {"y": "precio_m2", "x": ["ingreso_hogar_mensual", "escolaridad_anios"],
               "errores": "HC3"}),
             ("s", "escenarios.simular", "¿Qué pasa si?",
              {"variable": "escolaridad_anios", "mover": "ingreso_hogar_mensual",
               "puntos": 21, "puntos_mover": 5})]
    aristas = [("d", "datos", "m", "datos"), ("d", "datos", "s", "datos"),
               ("m", "modelo", "s", "modelo")]
    r = ejecutar(compilar(grafo("escenarios", nodos, aristas)))
    return {n.nodo_id: (n.artefactos or {}) for n in r.nodos}, r


def test_la_proyeccion_trae_una_curva_por_escenario():
    arts, r = _proyeccion()
    p = arts["s"].get("proyeccion")
    assert p is not None, f"no salió la proyección; hay {sorted(arts['s'])}. {r.bitacora[-2:]}"
    assert len(p["series"]) == 5, "un escenario por cada valor del control"
    assert len(p["x"]["valores"]) == 21
    assert all(len(s["y"]) == 21 for s in p["series"])
    assert p["control"]["nombre"] == "ingreso_hogar_mensual"
    assert p["respuesta"] == "precio_m2"


def test_el_control_de_verdad_mueve_la_proyeccion():
    """Si todas las curvas fueran iguales, el deslizador seria un adorno."""
    arts, _ = _proyeccion()
    p = arts["s"]["proyeccion"]
    medio = len(p["x"]["valores"]) // 2
    bajo = p["series"][0]["y"][medio]
    alto = p["series"][-1]["y"][medio]
    assert abs(alto - bajo) > 1e-6, "mover el control no cambia nada"


def test_todo_lo_de_la_proyeccion_esta_en_la_tabla():
    """El deslizador escoge; no calcula. Cada punto tiene que estar en la tabla.

    Es la propiedad que hace auditable a la proyeccion: lo que se ve en pantalla
    es lo mismo que se exporta y lo mismo que va al PDF.
    """
    arts, _ = _proyeccion()
    p = arts["s"]["proyeccion"]
    tabla = arts["s"]["escenarios"]
    columnas = [c["nombre"] for c in tabla["columnas"]]
    i_pred = columnas.index("prediccion")
    en_tabla = {round(float(f[i_pred]), 6) for f in tabla["filas"] if f[i_pred] is not None}
    for serie in p["series"]:
        for y in serie["y"]:
            assert round(float(y), 6) in en_tabla, "hay un punto dibujado que no está en la tabla"


def test_la_proyeccion_no_extrapola_fuera_de_lo_observado():
    """El recorrido va del percentil 5 al 95, no del minimo al maximo."""
    import pandas as pd

    arts, _ = _proyeccion()
    p = arts["s"]["proyeccion"]
    datos = arts["d"]["datos"]
    columnas = [c["nombre"] for c in datos["columnas"]]
    i = columnas.index("escolaridad_anios")
    observado = pd.Series([f[i] for f in datos["filas"]], dtype="float64")
    assert p["x"]["valores"][0] >= float(observado.min())
    assert p["x"]["valores"][-1] <= float(observado.max())
