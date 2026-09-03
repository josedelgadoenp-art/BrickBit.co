"""
Pruebas de la Fase 1.

Congelan las decisiones que costaron encontrar: que las familias DENUE existan
de verdad en la fuente, que el vecindario H3 no tenga sesgo direccional, que
los bloques de validación mantengan juntos a los vecinos, y que el motor
vectorizado dé lo mismo que la fórmula a mano.
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest

from atlas.config import cargar
from atlas.features import amenidades, malla, pesos
from atlas.geo import (accesibilidad_gravitacional, conteo_en_radios,
                       distancia_al_mas_cercano, haversine_m, puntos)

CFG = cargar()
ZOCALO = (19.4326, -99.1332)


def _pts(coords):
    return puntos(pd.DataFrame([{"lat": la, "lng": lo} for la, lo in coords]), cfg=CFG)


# --------------------------------------------------------------------- malla
def test_malla_cubre_la_ciudad_y_es_estable():
    g = malla.malla(resolucion=7, cfg=CFG)   # res gruesa: rápida para la prueba
    assert len(g) > 50, "la CDMX no cabe en tan pocas celdas"
    assert g["h3"].is_unique
    assert list(g["h3"]) == sorted(g["h3"]), "el orden debe ser estable"
    caja = CFG.caja
    assert g["lat"].between(caja.lat_min, caja.lat_max).all()
    assert g["lng"].between(caja.lng_min, caja.lng_max).all()


def test_malla_es_determinista():
    a = malla.malla(resolucion=7, cfg=CFG)
    b = malla.malla(resolucion=7, cfg=CFG)
    assert list(a["h3"]) == list(b["h3"])


def test_bloques_mantienen_juntos_a_los_vecinos():
    """
    El punto de los bloques: dos celdas contiguas deben caer en el MISMO
    pliegue de validación. Si cayeran en pliegues distintos, un comparable
    vecino estaría a la vez en entrenamiento y en prueba, que es la fuga que
    infla artificialmente el desempeño.
    """
    g = malla.malla(resolucion=7, cfg=CFG)
    b = malla.bloques(g, CFG)
    assert b.nunique() < len(g), "los bloques deben agrupar, no ser uno por celda"
    assert b.notna().all()


def test_centros_son_puntos_dentro_de_su_celda():
    g = malla.malla(resolucion=7, cfg=CFG).head(20)
    c = malla.centros(g, CFG)
    assert (c.geometry.geom_type == "Point").all()
    for i in range(len(g)):
        assert g.geometry.iloc[i].contains(c.geometry.iloc[i]), \
            "el centro debe caer dentro de su propia celda"


# ---------------------------------------------------------- motor vectorizado
def test_distancia_vectorizada_coincide_con_haversine():
    """El árbol KD es una optimización, no una aproximación: debe dar lo mismo."""
    o = _pts([ZOCALO])
    d = _pts([(19.4270, -99.1677), (19.5000, -99.2000)])
    got = distancia_al_mas_cercano(o, d, CFG)[0]
    esperado = min(haversine_m(*ZOCALO, 19.4270, -99.1677),
                   haversine_m(*ZOCALO, 19.5000, -99.2000))
    assert abs(got - esperado) / esperado < 0.01


def test_conteo_es_por_fila_no_agregado():
    """Cada origen tiene su propio conteo; un agregado global sería inservible."""
    o = _pts([ZOCALO, (19.5000, -99.2000)])
    d = _pts([(ZOCALO[0] + 0.001, ZOCALO[1]),      # ~111 m del Zócalo
              (ZOCALO[0] + 0.002, ZOCALO[1])])     # ~222 m del Zócalo
    c = conteo_en_radios(o, d, [300], CFG)
    assert len(c) == 2
    assert c["n_300m"].iloc[0] == 2, "los dos están cerca del Zócalo"
    assert c["n_300m"].iloc[1] == 0, "ninguno está cerca del segundo punto"


def test_accesibilidad_decae_con_la_distancia():
    cerca = accesibilidad_gravitacional(
        _pts([ZOCALO]), _pts([(ZOCALO[0] + 0.002, ZOCALO[1])]), beta=1.5, cfg=CFG)[0]
    lejos = accesibilidad_gravitacional(
        _pts([ZOCALO]), _pts([(ZOCALO[0] + 0.020, ZOCALO[1])]), beta=1.5, cfg=CFG)[0]
    assert cerca > lejos > 0


def test_accesibilidad_pondera_por_atractivo():
    o, d = _pts([ZOCALO]), _pts([(ZOCALO[0] + 0.002, ZOCALO[1])])
    poco = accesibilidad_gravitacional(o, d, atractivo=np.array([1.0]), cfg=CFG)[0]
    mucho = accesibilidad_gravitacional(o, d, atractivo=np.array([100.0]), cfg=CFG)[0]
    assert abs(mucho - 100 * poco) / mucho < 1e-9


def test_sin_destinos_distancia_es_nan_y_conteo_cero():
    o = _pts([ZOCALO])
    vacio = o.iloc[0:0]
    assert np.isnan(distancia_al_mas_cercano(o, vacio, CFG)[0])
    assert conteo_en_radios(o, vacio, [300], CFG)["n_300m"].iloc[0] == 0
    assert accesibilidad_gravitacional(o, vacio, cfg=CFG)[0] == 0


# ------------------------------------------------------------------- pesos W
def _rejilla(n=6, paso=0.004):
    """Rejilla regular alrededor del Zócalo, para probar W sin depender del lago."""
    return _pts([(ZOCALO[0] + i * paso, ZOCALO[1] + j * paso)
                 for i in range(n) for j in range(n)])


def test_w_esta_estandarizado_por_filas():
    """Con filas estandarizadas, W·y es el PROMEDIO de los vecinos."""
    g = _rejilla()
    w = pesos.knn(g, 4, CFG)
    filas = np.asarray(w.sparse.sum(axis=1)).ravel()
    assert np.allclose(filas, 1.0)


def test_rezago_de_una_constante_es_la_constante():
    """Si todos los vecinos valen 7, el promedio del vecindario es 7."""
    g = _rejilla()
    w = pesos.knn(g, 4, CFG)
    r = pesos.rezago(w, np.full(len(g), 7.0))
    assert np.allclose(r, 7.0)


def test_moran_detecta_estructura_y_la_distingue_del_ruido():
    g = _rejilla(n=8)
    m = g.to_crs(CFG.crs_metrico)
    gradiente = m.geometry.x.to_numpy()          # variable perfectamente espacial
    rng = np.random.default_rng(CFG.semilla)
    ruido = rng.normal(size=len(g))              # sin estructura

    w = pesos.knn(g, 4, CFG)
    I_grad, p_grad = pesos.moran(w, gradiente, permutaciones=199)
    I_ruido, _ = pesos.moran(w, ruido, permutaciones=199)
    assert I_grad > 0.5 and p_grad < 0.05, "un gradiente debe dar Moran alto"
    assert abs(I_ruido) < 0.3, "el ruido no debe parecer estructura"


def test_rezago_tolera_nulos_sin_perder_la_fila():
    g = _rejilla()
    y = np.full(len(g), 5.0)
    y[3] = np.nan
    r = pesos.rezago(pesos.knn(g, 4, CFG), y)
    assert len(r) == len(g) and np.isfinite(r).all()


def test_elegir_devuelve_el_de_mayor_moran():
    g = _rejilla(n=7)
    m = g.to_crs(CFG.crs_metrico)
    w, el = pesos.elegir(g, m.geometry.x.to_numpy(), CFG, permutaciones=99)
    validos = el.candidatos.dropna(subset=["I"])
    assert el.moran_I >= validos["I"].max() - 1e-9
    assert el.tipo in ("knn", "banda")


def test_lisa_marca_los_cuadrantes():
    g = _rejilla(n=8)
    m = g.to_crs(CFG.crs_metrico)
    w = pesos.knn(g, 4, CFG)
    cl = pesos.lisa(w, m.geometry.x.to_numpy(), permutaciones=199)
    assert set(cl.columns) == {"lisa_I", "lisa_p", "lisa_cuadrante", "lisa_sig"}
    assert cl["lisa_cuadrante"].isin(["AA", "BB", "BA", "AB", "?"]).all()
    assert cl["lisa_sig"].any(), "un gradiente debe producir clústeres significativos"


# ------------------------------------------------------------- familias DENUE
def test_las_familias_denue_existen_en_la_fuente():
    """
    El bug que esta prueba congela: las familias eran salud/educación/ocio, que
    el DENUE agregado del repo NO distingue —sólo tiene Servicios, Comercio,
    Alimentos e Industria—. Producían columnas enteras de NaN y una falsa
    sensación de cobertura.
    """
    from atlas import lago
    from atlas.ingesta import denue

    if not lago.existe("denue", CFG):
        pytest.skip("el lago no tiene la capa denue; corre la Fase 0")
    d = lago.leer("denue", CFG)
    presentes = set(d["familia"].unique()) - {"otro"}
    declaradas = set(amenidades.FAMILIAS_DENUE)
    assert declaradas <= presentes | {"otro"}, (
        f"se declaran familias que la fuente no produce: {declaradas - presentes}"
    )
    for fam in amenidades.FAMILIAS_DENUE:
        assert (d["familia"] == fam).any(), f"la familia '{fam}' quedó vacía"


def test_desde_denue_no_deja_columnas_todas_nulas():
    from atlas import lago

    if not lago.existe("denue", CFG):
        pytest.skip("el lago no tiene la capa denue; corre la Fase 0")
    d = lago.leer("denue", CFG).sample(4000, random_state=CFG.semilla)
    o = _rejilla(n=5)
    f = amenidades.desde_denue(o, d, CFG)
    todas_nulas = [c for c in f.columns if f[c].isna().all()]
    assert not todas_nulas, f"columnas sin ningún valor: {todas_nulas}"


def test_desde_osm_declara_ausencia_con_la_misma_forma():
    """
    Sin OSM las columnas deben EXISTIR con ausencia declarada, no faltar: un
    modelo entrenado con OSM reventaría al recibir una matriz sin esas columnas.
    """
    o = _rejilla(n=4)
    sin = amenidades.desde_osm(o, None, CFG)
    fingido = gpd.GeoDataFrame(
        {"categoria": ["parques"], "osm_id": ["x"], "nombre": ["y"]},
        geometry=_pts([(ZOCALO[0] + 0.001, ZOCALO[1])]).geometry.to_numpy(),
        crs=CFG.crs_geografico,
    )
    con = amenidades.desde_osm(o, fingido, CFG)
    assert list(sin.columns) == list(con.columns)
    assert sin["dist_parques_m"].isna().all()
    assert (sin["n_parques_300m"] == 0).all()
