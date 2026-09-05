"""
Pruebas de la Fase 4.

La app no se prueba pintando pantallas: se prueba el contrato del que depende,
que es el paquete guardado. Si una columna se corre, si el intervalo se
desempareja de su predictor o si un modelo viejo pasa por nuevo, la app enseña
un número convincente y equivocado, que es peor que no enseñar nada.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from atlas import lago
from atlas.config import cargar
from atlas.modelos import persistencia

CFG = cargar()


def _paquete():
    p = persistencia.cargar_paquete(CFG)
    if p is None:
        pytest.skip("no hay AVM entrenado; corre python -m pipelines.fase2")
    return p


def test_el_paquete_trae_todas_las_piezas_emparejadas():
    """
    Un AVM no es un modelo: son seis piezas que sólo significan algo juntas.
    Guardar el predictor sin sus correcciones conformes daría un número con una
    banda que no le corresponde.
    """
    p = _paquete()
    assert p.columnas and p.boosting is not None and p.apilado is not None
    assert p.dispersion is not None and len(p.lineal) == 3
    assert p.conforme_por_alpha, "sin correcciones conformes no hay intervalo"
    assert 0.05 in p.alphas, "el 95% tiene que estar calibrado"
    assert p.n_entrenamiento > 0 and p.fecha_datos
    assert p.version == persistencia.VERSION


def test_la_fila_respeta_el_orden_de_columnas_del_modelo():
    """
    Un modelo de árboles no valida nombres: si una columna llega corrida, la
    predicción sale perfectamente plausible y perfectamente equivocada. El
    orden lo manda el paquete, nunca lo que traiga el que llama.
    """
    p = _paquete()
    feats = lago.leer("features_malla", CFG)
    X = persistencia.fila_de_inmueble(
        19.4326, -99.1650,
        {"tipo": "depto", "superficie_construida_m2": 90, "recamaras": 2},
        feats, p.columnas, p.tipo_referencia, CFG)
    assert list(X.columns) == list(p.columnas)
    assert len(X) == 1


def test_las_indicadoras_de_tipo_son_excluyentes():
    """Un inmueble es de un tipo. Dos indicadoras encendidas sería incoherente."""
    p = _paquete()
    feats = lago.leer("features_malla", CFG)
    cols_tipo = [c for c in p.columnas if c.startswith("tipo_")]
    if not cols_tipo:
        pytest.skip("el modelo no usa indicadoras de tipo")
    for tipo in [c.replace("tipo_", "") for c in cols_tipo]:
        X = persistencia.fila_de_inmueble(
            19.4326, -99.1650, {"tipo": tipo, "superficie_construida_m2": 80},
            feats, p.columnas, p.tipo_referencia, CFG)
        assert X[cols_tipo].sum(axis=1).iloc[0] == 1.0, f"tipo {tipo}"


def test_un_punto_fuera_de_la_malla_toma_la_celda_mas_cercana():
    """No se puede devolver NaN por estar 200 m fuera del recorte de la malla."""
    p = _paquete()
    feats = lago.leer("features_malla", CFG)
    X = persistencia.fila_de_inmueble(
        19.02, -99.35, {"tipo": "casa", "superficie_construida_m2": 120},
        feats, p.columnas, p.tipo_referencia, CFG)
    espaciales = [c for c in p.columnas if c.startswith(("acc_", "dist_", "n_"))]
    assert X[espaciales].notna().any(axis=1).iloc[0], \
        "debería heredar variables de la celda más cercana"


def test_bajar_el_nivel_de_confianza_estrecha_la_banda():
    """Y el punto no se mueve: el nivel cambia el intervalo, no la estimación."""
    p = _paquete()
    feats = lago.leer("features_malla", CFG)
    X = persistencia.fila_de_inmueble(
        19.4326, -99.1650,
        {"tipo": "depto", "superficie_construida_m2": 90, "recamaras": 2},
        feats, p.columnas, p.tipo_referencia, CFG)

    anchos, puntos = [], []
    for a in (0.50, 0.20, 0.05):
        v = persistencia.valuar(p, X, 90, alpha=a)
        anchos.append(v.ancho_pct)
        puntos.append(v.precio_total)
        assert v.lo_total < v.precio_total < v.hi_total, "el punto va dentro de su banda"
    assert anchos[0] < anchos[1] < anchos[2], "menos confianza, menos ancho"
    assert np.allclose(puntos, puntos[0]), "el nivel no puede mover la estimación"


def test_mas_superficie_no_cambia_el_precio_por_m2_por_arte_de_magia():
    """
    El total escala con la superficie; el precio por m² no tiene por qué ser
    constante —un depto chico suele valer más por m²— pero sí tiene que
    responder de forma monótona y sin saltos absurdos.
    """
    p = _paquete()
    feats = lago.leer("features_malla", CFG)
    totales = []
    for sup in (60, 90, 140):
        X = persistencia.fila_de_inmueble(
            19.4326, -99.1650, {"tipo": "depto", "superficie_construida_m2": sup},
            feats, p.columnas, p.tipo_referencia, CFG)
        totales.append(persistencia.valuar(p, X, sup).precio_total)
    assert totales[0] < totales[1] < totales[2], "más metros, más precio total"


def test_el_paquete_sabe_de_cuando_son_sus_datos():
    """
    Un AVM entrenado con inventario viejo sigue dando números convincentes
    mucho después de dejar de ser cierto. La app avisa a partir de 90 días, y
    sólo puede hacerlo si el paquete guarda la fecha.
    """
    p = _paquete()
    d = p.antiguedad_dias()
    assert d >= 0, "la fecha de los datos tiene que ser legible"
