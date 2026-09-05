"""Los nodos, ejecutados de verdad. Un `emit()` que no corre no sirve de nada."""

import pytest

from abaco_core import compilar, ejecutar

from .conftest import grafo

pytest.importorskip("statsmodels")

SECTORES = ["Agropecuario", "Mineria", "Energia", "Manufactura alimentos",
            "Manufactura metalica", "Manufactura otras", "Construccion", "Comercio",
            "Transporte", "Informacion y medios", "Servicios financieros", "Servicios diversos"]

FLUJOS = {
    "series": (
        [("d", "datos.ejemplo", "Macro", {"conjunto": "mexico_macro"}),
         ("s", "datos.serie_temporal", "Serie", {"columna_fecha": "fecha", "frecuencia": "QS"}),
         ("r", "series.estacionariedad", "ADF", {"columnas": ["pib_indice", "inflacion_anual"]}),
         ("a", "series.arima", "ARIMA", {"variable": "pib_indice", "p": 1, "d": 1, "q": 1, "horizonte": 6}),
         ("v", "series.var", "VAR", {"variables": ["inflacion_anual", "tasa_objetivo"],
                                     "rezagos": 2, "periodos_irf": 6}),
         ("c", "series.cointegracion", "Johansen",
          {"variables": ["pib_indice", "consumo_indice"], "rezagos": 1})],
        [("d", "datos", "s", "datos"), ("s", "datos", "r", "datos"),
         ("s", "datos", "a", "datos"), ("s", "datos", "v", "datos"), ("s", "datos", "c", "datos")],
    ),
    "espacial": (
        [("d", "datos.ejemplo", "Entidades", {"conjunto": "mexico_estados"}),
         ("t", "transformar.calcular", "Log precio", {"operacion": "log", "columna_a": "precio_m2"}),
         ("u", "datos.ubicacion", "Ubicadas", {"latitud": "lat", "longitud": "lng"}),
         ("w", "espacial.pesos", "Vecinos", {"metodo": "knn", "k": 4}),
         ("m", "espacial.moran", "Moran", {"columnas": ["log_precio_m2"], "permutaciones": 199}),
         ("l", "espacial.diagnostico", "LM", {"y": "log_precio_m2", "x": ["escolaridad_anios"]}),
         ("s", "espacial.sar", "SAR", {"y": "log_precio_m2", "x": ["escolaridad_anios"]}),
         ("i", "espacial.lisa", "LISA", {"columna": "log_precio_m2", "permutaciones": 199})],
        [("d", "datos", "t", "datos"), ("t", "datos", "u", "datos"), ("u", "datos", "w", "datos"),
         ("u", "datos", "m", "datos"), ("w", "pesos", "m", "pesos"),
         ("u", "datos", "l", "datos"), ("w", "pesos", "l", "pesos"),
         ("u", "datos", "s", "datos"), ("w", "pesos", "s", "pesos"),
         ("u", "datos", "i", "datos"), ("w", "pesos", "i", "pesos")],
    ),
    "insumo_producto": (
        [("d", "datos.ejemplo", "MIP", {"conjunto": "insumo_producto"}),
         ("s", "macro.insumo_producto", "Sistema",
          {"columna_sectores": "sector", "columnas_matriz": SECTORES,
           "produccion_total": "produccion_total", "demanda_final": "demanda_final",
           "empleo": "empleo_miles", "remuneraciones": "remuneraciones"}),
         ("e", "macro.encadenamientos", "Encadenamientos", {}),
         ("i", "macro.impacto", "Choque", {"choques": {"Construccion": 100000.0}}),
         ("k", "macro.multiplicador_keynesiano", "Keynesiano", {"propension_consumo": 0.65})],
        [("d", "datos", "s", "datos"), ("s", "sistema", "e", "sistema"), ("s", "sistema", "i", "sistema")],
    ),
    "panel": (
        [("d", "datos.ejemplo", "Panel", {"conjunto": "panel_estados"}),
         ("t", "transformar.calcular", "Log PIB", {"operacion": "log", "columna_a": "pib_per_capita"}),
         ("u", "transformar.calcular", "Log inv", {"operacion": "log", "columna_a": "inversion_pc"}),
         ("p", "datos.panel", "Panel def", {"entidad": "entidad", "periodo": "anio"}),
         ("f", "econometria.panel", "Efectos fijos",
          {"y": "log_pib_per_capita", "x": ["log_inversion_pc"], "efectos": "fijos"})],
        [("d", "datos", "t", "datos"), ("t", "datos", "u", "datos"),
         ("u", "datos", "p", "datos"), ("p", "datos", "f", "datos")],
    ),
    "ml": (
        [("d", "datos.ejemplo", "Hogares", {"conjunto": "hogares"}),
         ("p", "ml.particion", "Particion", {"proporcion_prueba": 0.25, "aleatoria": True}),
         ("x", "ml.xgboost", "XGBoost",
          {"y": "gasto_vivienda", "x": ["ingreso_mensual", "edad_jefe", "tamano_hogar"],
           "n_arboles": 40, "profundidad": 3})],
        [("d", "datos", "p", "datos"), ("p", "entrenamiento", "x", "entrenamiento"),
         ("p", "prueba", "x", "prueba")],
    ),
    "graficos": (
        [("d", "datos.ejemplo", "Entidades", {"conjunto": "mexico_estados"}),
         ("l", "graficos.lienzo", "Lienzo",
          {"x": "escolaridad_anios", "y": "precio_m2", "color": "ciclo"}),
         ("p", "graficos.puntos", "+ Puntos", {}),
         ("t", "graficos.tendencia", "+ Tendencia", {}),
         ("m", "graficos.tema", "Tema", {"titulo": "Prueba", "modo": "oscuro"}),
         ("g", "graficos.dibujar", "Dibujar", {})],
        [("d", "datos", "l", "datos"), ("l", "grafico", "p", "grafico"),
         ("p", "grafico", "t", "grafico"), ("t", "grafico", "m", "grafico"),
         ("m", "grafico", "g", "grafico")],
    ),
    "explorar": (
        [("d", "datos.ejemplo", "Entidades", {"conjunto": "mexico_estados"}),
         ("t", "transformar.calcular", "Log precio", {"operacion": "log", "columna_a": "precio_m2"}),
         ("e", "explorar.descriptivos", "Descriptivos", {"columnas": ["precio_m2", "plusvalia_pct"]}),
         ("c", "explorar.correlacion", "Correlaciones",
          {"columnas": ["log_precio_m2", "escolaridad_anios", "empleo_formal_pct"]}),
         ("g", "explorar.comparar_grupos", "Por ciclo", {"variable": "precio_m2", "grupo": "ciclo"}),
         ("m1", "econometria.mco", "Modelo 1", {"y": "log_precio_m2", "x": ["escolaridad_anios"]}),
         ("m2", "econometria.mco", "Modelo 2",
          {"y": "log_precio_m2", "x": ["escolaridad_anios", "empleo_formal_pct"]}),
         ("tb", "salida.tabla_publicacion", "Tabla", {"nombres": ["Base", "Ampliado"]}),
         ("dg", "econometria.diagnosticos", "Supuestos", {})],
        [("d", "datos", "t", "datos"), ("t", "datos", "e", "datos"), ("t", "datos", "c", "datos"),
         ("t", "datos", "g", "datos"), ("t", "datos", "m1", "datos"), ("t", "datos", "m2", "datos"),
         ("m1", "modelo", "tb", "modelos"), ("m2", "modelo", "tb", "modelos"),
         ("m2", "modelo", "dg", "modelo")],
    ),
}


@pytest.mark.parametrize("nombre", list(FLUJOS))
def test_el_flujo_corre_completo(nombre):
    nodos, aristas = FLUJOS[nombre]
    programa = compilar(grafo(nombre, nodos, aristas))
    assert not programa.hay_errores, [
        d.mensaje for d in programa.diagnosticos if d.severidad == "error"]

    resultado = ejecutar(programa)
    fallidos = [(n.nodo_id, n.error.excepcion) for n in resultado.nodos if n.error]
    assert not fallidos, fallidos
    assert resultado.ok


def test_el_cache_evita_recalcular():
    from abaco_core.runtime.cache import CacheMemoria
    from abaco_core.runtime.ejecutor import Ejecutor

    nodos, aristas = FLUJOS["explorar"]
    programa = compilar(grafo("cache", nodos, aristas))
    cache = CacheMemoria()

    primera = Ejecutor(cache=cache).ejecutar(programa)
    assert primera.ok
    assert all(n.estado == "listo" for n in primera.nodos)

    segunda = Ejecutor(cache=cache).ejecutar(programa)
    assert segunda.ok
    assert all(n.estado == "cacheado" for n in segunda.nodos), (
        "la segunda corrida del mismo grafo no debería recalcular nada"
    )


def test_un_nodo_que_falla_no_arrastra_a_sus_hermanos():
    """Si un bloque truena, los que no dependen de él siguen corriendo.

    El fallo se provoca con un sector que no está en la matriz: es un error del
    usuario que sólo se puede detectar al ejecutar, porque los nombres de los
    sectores viven en los DATOS, no en el esquema.
    """
    g = grafo("fallo parcial", [
        ("d", "datos.ejemplo", "MIP", {"conjunto": "insumo_producto"}),
        ("s", "macro.insumo_producto", "Sistema",
         {"columna_sectores": "sector", "columnas_matriz": SECTORES,
          "produccion_total": "produccion_total", "demanda_final": "demanda_final"}),
        ("bien", "macro.encadenamientos", "Encadenamientos", {}),
        ("mal", "macro.impacto", "Choque a un sector que no existe",
         {"choques": {"Turismo espacial": 100000.0}}),
    ], [("d", "datos", "s", "datos"), ("s", "sistema", "bien", "sistema"),
        ("s", "sistema", "mal", "sistema")])

    programa = compilar(g)
    assert not programa.hay_errores, "el problema no se ve al compilar: sólo al ejecutar"

    resultado = ejecutar(programa)
    por_nodo = resultado.por_nodo()
    assert por_nodo["mal"].estado == "error"
    assert por_nodo["bien"].estado in ("listo", "cacheado"), (
        "un hermano que no depende del que falló tiene que correr igual"
    )
    assert not resultado.ok
    # El error se traduce para el usuario, y el traceback completo queda para
    # quien tenga que depurar.
    assert por_nodo["mal"].error is not None
    assert por_nodo["mal"].error.traceback
    assert "Turismo espacial" in por_nodo["mal"].error.excepcion


def test_los_nodos_que_dependen_de_uno_que_fallo_se_omiten():
    """Intentar un nodo cuya entrada nunca se produjo sólo genera un segundo
    error que no dice nada. Se marcan como omitidos."""
    g = grafo("cascada", [
        ("d", "datos.ejemplo", "MIP", {"conjunto": "insumo_producto"}),
        ("s", "macro.insumo_producto", "Sistema",
         {"columna_sectores": "sector", "columnas_matriz": SECTORES,
          "produccion_total": "produccion_total"}),
        ("mal", "macro.impacto", "Choque imposible", {"choques": {"Turismo espacial": 1000.0}}),
        ("l", "graficos.lienzo", "Lienzo",
         {"x": "sector", "y": "produccion_adicional"}),
        ("p", "graficos.barras", "+ Barras", {}),
        ("g", "graficos.dibujar", "Dibujar", {}),
    ], [("d", "datos", "s", "datos"), ("s", "sistema", "mal", "sistema"),
        ("mal", "impacto", "l", "datos"), ("l", "grafico", "p", "grafico"),
        ("p", "grafico", "g", "grafico")])

    programa = compilar(g)
    assert not programa.hay_errores
    resultado = ejecutar(programa)
    por_nodo = resultado.por_nodo()
    assert por_nodo["mal"].estado == "error"
    for aguas_abajo in ("l", "p", "g"):
        assert por_nodo[aguas_abajo].estado == "omitido", (
            f"«{aguas_abajo}» depende del que falló y no debió intentarse"
        )
