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


# ─────────────────────────── comparables: la señal que faltaba ───────────────
def test_los_comparables_no_se_miran_a_si_mismos():
    """
    La fuga obvia: si los comparables de un inmueble incluyen su propio anuncio,
    el modelo aprende a copiar la respuesta. Se evita excluyendo su bloque.
    """
    from atlas.modelos import comparables

    rng = np.random.default_rng(0)
    xy = rng.uniform(0, 10_000, size=(200, 2))
    y = rng.normal(10, 1, 200)
    bloque = np.array([f"b{i % 10}" for i in range(200)], dtype=object)

    c = comparables.variables(xy, xy, y, bloque_objetivo=bloque, bloque_fuente=bloque)
    # Si se mirara a sí mismo, con k=5 el propio valor entraría en la mediana y
    # la correlación con y sería altísima. Al excluir el bloque, no.
    corr = float(np.corrcoef(c["comp5_ln_precio_m2"].fillna(y.mean()), y)[0, 1])
    assert abs(corr) < 0.5, f"correlación {corr:.2f}: parece estar viéndose a sí mismo"


def test_los_comparables_recuperan_una_estructura_espacial_real():
    """Con precio que depende de la posición, el comparable tiene que reflejarlo."""
    from atlas.modelos import comparables

    rng = np.random.default_rng(1)
    xy = rng.uniform(0, 20_000, size=(400, 2))
    y = 1e-4 * xy[:, 0] + rng.normal(0, 0.05, 400)     # caro al este
    # Bloques por franjas verticales: los comparables vienen de otras franjas.
    bloque = np.array([f"f{int(x // 4000)}" for x in xy[:, 0]], dtype=object)

    c = comparables.variables(xy, xy, y, bloque_objetivo=bloque, bloque_fuente=bloque)
    ok = c["comp15_ln_precio_m2"].notna()
    corr = float(np.corrcoef(c.loc[ok, "comp15_ln_precio_m2"], y[ok.to_numpy()])[0, 1])
    assert corr > 0.5, "el comparable debe captar que al este es más caro"


def test_sin_fuentes_las_columnas_existen_con_ausencia_declarada():
    """
    Un modelo entrenado con comparables revienta si le llega una matriz sin esas
    columnas. Deben existir siempre, en NaN cuando no hay con qué llenarlas.
    """
    from atlas.modelos import comparables

    vacio = np.zeros((0, 2))
    c = comparables.variables(np.array([[0.0, 0.0]]), vacio, np.array([]))
    assert len(c) == 1
    assert any(col.endswith("ln_precio_m2") for col in c.columns)
    assert c.filter(like="ln_precio_m2").isna().all().all()


def test_los_hiperparametros_se_eligen_por_bloque_y_no_al_azar():
    """
    Ajustarlos al azar sería peor que no ajustarlos: con vecinos a los dos lados
    la validación premia al que mejor memoriza la cuadra, que es justo el que
    peor generaliza a un barrio nuevo.
    """
    from atlas.modelos import arboles

    rng = np.random.default_rng(2)
    n = 600
    X = pd.DataFrame(rng.normal(size=(n, 6)), columns=[f"v{i}" for i in range(6)])
    y = pd.Series(X["v0"] * 2 + rng.normal(0, 0.4, n))
    bloque = pd.Series([f"b{i % 12}" for i in range(n)])

    mejores, tabla = arboles.elegir_hiperparametros(X, y, bloque, semilla=0)
    assert mejores["early_stopping"] is False, "el paro temprano parte al azar"
    assert len(tabla) == len(arboles.REJILLA)
    assert tabla["mediana_abs_log"].is_monotonic_increasing, "la tabla va de mejor a peor"
    assert mejores["max_leaf_nodes"] in {c["max_leaf_nodes"] for c in arboles.REJILLA}
