"""
Pruebas de la Fase 3.

Congelan las tres cosas que hacen que esta fase diga la verdad: que el índice
temporal se lea sin inventar, que la prueba de contagio sea realmente hacia
adelante —sin mirar el futuro—, y que el multiplicador espacial reporte la
cantidad que varía y no la que es constante por construcción.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from atlas.campo import multiplicador, superficie
from atlas.config import cargar
from atlas.features import pesos
from atlas.geo import puntos
from atlas.temporal import difusion, indice

CFG = cargar()


# -------------------------------------------------------------- índice SHF
def test_el_panel_shf_se_lee_completo_y_ordenado():
    p = indice.cargar_panel(CFG)
    assert p.nivel.shape[0] >= 20, "la serie SHF debería traer dos décadas"
    assert p.nivel.shape[1] >= 30, "deberían ser las 32 zonas"
    assert list(p.nivel.index) == sorted(p.nivel.index), "los años deben ir en orden"
    assert "Ciudad de México" in p.nivel.columns
    assert p.coords.index.equals(p.nivel.columns), \
        "cada zona del panel necesita su coordenada para el W de la difusión"
    assert not p.real, "sin INPC el panel es nominal y debe declararlo"


def test_el_acumulado_sale_del_indice_y_no_de_componer_la_media():
    """
    Componer la media aritmética de las tasas anuales da un número distinto
    —y siempre optimista— cuando la serie tiene años malos, porque la media
    aritmética de tasas no es la tasa media geométrica.
    """
    p = indice.cargar_panel(CFG)
    a0, a1 = p.anios[0], p.anios[-1]
    real = indice.acumulado(p, "Ciudad de México", a0, a1)
    directo = p.nivel["Ciudad de México"].loc[a1] / p.nivel["Ciudad de México"].loc[a0]
    assert abs(real - directo) < 1e-12

    tasas = p.crecimiento["Ciudad de México"].dropna()
    ingenuo = float(np.exp(tasas.mean() * len(tasas)))
    compuesto_mal = float((1 + np.expm1(tasas).mean()) ** len(tasas))
    assert abs(real - ingenuo) < 1e-6, "log-diferencias sí se suman"
    assert compuesto_mal > real, "componer la media aritmética infla el resultado"


# ------------------------------------------------------------------ difusión
def test_la_validacion_de_contagio_es_hacia_adelante():
    """
    La prueba que importa: cada predicción se hace con años ANTERIORES. Si se
    permitiera mirar hacia adelante, cualquier modelo de series saldría genial
    y el resultado no diría nada. Se verifica que el número de predicciones
    corresponde a los años posteriores al mínimo de ajuste.
    """
    p = indice.cargar_panel(CFG)
    w = difusion.pesos_zonas(p.coords, k=4, cfg=CFG)
    c = difusion.contagio(p, w, minimo_anios=6)

    n_anios = len(c.detalle)
    assert n_anios > 5, "deberían quedar varios años para validar"
    assert c.n_predicciones == n_anios * p.nivel.shape[1]
    assert set(c.detalle["anio"]) <= set(p.anios[6:]), \
        "no se puede predecir un año usado para ajustar"
    # Los tres errores se miden sobre exactamente las mismas observaciones.
    assert (c.detalle[["err_ingenuo", "err_momentum", "err_espacial"]] > 0).all().all()


def test_el_veredicto_de_contagio_depende_del_error_no_de_la_correlacion():
    """
    `aporta` sólo puede ser cierto si el término espacial BAJA el error fuera de
    muestra. Un I de Moran alto no basta: dos vecinos pueden crecer igual por un
    choque común sin que uno empuje al otro.
    """
    c = difusion.Contagio(n_predicciones=100, mae_ingenuo=0.03, mae_momentum=0.02,
                          mae_con_vecinos=0.025, mejora_pct=25.0, coef_espacial=0.5)
    assert not c.aporta, "si el error sube, el vecindario no aporta"
    c2 = difusion.Contagio(n_predicciones=100, mae_ingenuo=0.03, mae_momentum=0.02,
                           mae_con_vecinos=0.018, mejora_pct=-10.0, coef_espacial=0.5)
    assert c2.aporta


# ------------------------------------------------------------- multiplicador
def _rejilla(n=12, paso=0.01):
    zocalo = (19.4326, -99.1332)
    return puntos(pd.DataFrame([
        {"lat": zocalo[0] + i * paso, "lng": zocalo[1] + j * paso}
        for i in range(n) for j in range(n)
    ]), cfg=CFG)


def test_la_suma_de_fila_es_constante_y_por_eso_no_se_reporta_como_hallazgo():
    """
    El bug que congela: la primera versión reportaba la suma de FILA como
    'derrame'. Con W estandarizado por filas esa suma vale 1/(1−ρ) para TODAS
    las unidades: es una identidad algebraica, y el mapa salía plano por
    construcción (0.275 idéntico en las 12,259 celdas). Lo que varía es la
    columna: cuánto mueve al sistema un cambio originado en esa unidad.
    """
    g = _rejilla()
    w = pesos.knn(g, 6, CFG)
    rho = 0.3
    m = multiplicador.calcular(w, rho)

    # La identidad: filas constantes.
    M = np.linalg.inv(np.eye(w.n) - rho * w.full()[0])
    assert np.allclose(M.sum(axis=1), 1 / (1 - rho)), "las filas son constantes"
    # Y la columna sí varía: es lo que se reporta.
    assert m.influencia.std() > 1e-6, "la influencia tiene que variar entre celdas"
    assert np.allclose(m.influencia, M.sum(axis=0))
    assert np.allclose(m.propio, np.diag(M))


def test_la_serie_de_neumann_coincide_con_la_inversa_exacta():
    """El camino barato para muchas celdas debe dar lo mismo que invertir."""
    g = _rejilla(n=10)
    w = pesos.knn(g, 5, CFG)
    exacto = multiplicador.calcular(w, 0.35, exacto_hasta=10_000)
    serie = multiplicador.calcular(w, 0.35, exacto_hasta=1)
    assert np.allclose(exacto.influencia, serie.influencia, rtol=1e-6)
    assert np.allclose(exacto.propio, serie.propio, rtol=1e-6, atol=1e-8)


def test_un_rho_fuera_de_rango_se_rechaza():
    """Con |ρ| ≥ 1 la serie no converge: el multiplicador no existe."""
    g = _rejilla(n=6)
    w = pesos.knn(g, 4, CFG)
    with pytest.raises(ValueError, match="no converge"):
        multiplicador.calcular(w, 1.2)


# --------------------------------------------------------------- superficie
def test_la_superficie_recupera_un_gradiente_conocido():
    """
    Con un plano inclinado sintético, el gradiente estimado debe apuntar hacia
    donde sube y con la magnitud correcta. Si esto falla, las 'flechas' del mapa
    apuntan a cualquier lado.
    """
    rng = np.random.default_rng(CFG.semilla)
    xy = rng.uniform(-8000, 8000, size=(600, 2))
    pendiente = 0.00008                      # 8% por km hacia el este
    y = pendiente * xy[:, 0] + rng.normal(0, 0.02, len(xy))

    gp, centro, media = superficie.ajustar(xy, y, CFG)
    s = superficie.evaluar(gp, centro, media, np.zeros((1, 2)))
    assert abs(s.grad_x[0] - pendiente) / pendiente < 0.25
    assert abs(s.grad_y[0]) < abs(s.grad_x[0]) / 3, "no debe inventar pendiente norte-sur"
    assert 7.0 < s.pendiente_pct_km[0] < 9.5


def test_la_incertidumbre_crece_donde_no_hay_datos():
    """
    Es la virtud del proceso gaussiano sobre un mapa de puntos: en la zona sin
    comparables la sigma se dispara, y eso es una respuesta, no un hueco.
    """
    rng = np.random.default_rng(CFG.semilla)
    xy = rng.uniform(-3000, 3000, size=(400, 2))     # todos en el centro
    # Con señal espacial de verdad, no ruido puro: si se le pasa ruido, el GP
    # aprende que no hay estructura, colapsa la varianza de señal y su sigma no
    # crece al alejarse. Eso es correcto —sin señal, extrapolar una constante no
    # añade incertidumbre— pero no prueba nada sobre el caso que importa.
    y = 0.00005 * xy[:, 0] + 0.00003 * xy[:, 1] + rng.normal(0, 0.05, len(xy))
    gp, centro, media = superficie.ajustar(xy, y, CFG)

    dentro = superficie.evaluar(gp, centro, media, np.array([[0.0, 0.0]]))
    fuera = superficie.evaluar(gp, centro, media, np.array([[25000.0, 25000.0]]))
    assert fuera.sigma[0] > dentro.sigma[0] * 1.5, (
        f"sigma dentro {dentro.sigma[0]:.4f}, fuera {fuera.sigma[0]:.4f}: "
        "la incertidumbre tiene que crecer donde no hay comparables"
    )


def test_la_sigma_del_nivel_se_separa_del_ruido_de_anuncio():
    """
    El bug que congela: `GaussianProcessRegressor.predict(return_std=True)`
    devuelve la desviación de la predicción de UN ANUNCIO, con el ruido del
    WhiteKernel incluido. Reportarla como incertidumbre del mapa hace parecer
    que no se sabe nada: sobre los datos reales daba ±53% cuando la del nivel
    era ±19%. Son preguntas distintas —cuánto puede valer este anuncio, contra
    cuánto vale el m² típico de la zona— y sólo la segunda sirve para un mapa.
    """
    rng = np.random.default_rng(CFG.semilla)
    xy = rng.uniform(-6000, 6000, size=(500, 2))
    y = 0.00006 * xy[:, 0] + rng.normal(0, 0.3, len(xy))   # mucho ruido de anuncio
    gp, centro, media = superficie.ajustar(xy, y, CFG)
    s = superficie.evaluar(gp, centro, media, xy[:50])

    assert (s.sigma_nivel <= s.sigma + 1e-9).all(), "el nivel no puede saber menos que el total"
    assert np.median(s.sigma_nivel) < np.median(s.sigma) / 2, (
        "con ruido de anuncio grande, la incertidumbre del nivel tiene que ser "
        "mucho menor que la total"
    )
    assert np.allclose(s.sigma ** 2 - s.sigma_nivel ** 2, s.ruido, atol=1e-6), \
        "la diferencia en varianza es exactamente el ruido de anuncio"


def test_la_frontera_no_se_busca_sobre_una_superficie_suavizada():
    """
    El bug que congela: la frontera se calculaba sobre la superficie del proceso
    gaussiano y devolvía CERO celdas en toda la CDMX. Parecía decir "no hay
    oportunidad" y en realidad era imposible por construcción: con una escala
    característica de kilómetros, dos puntos vecinos a 174 m tienen valores casi
    idénticos, así que una superficie suave no puede contener un hoyo local.
    Suavizar borra exactamente lo que la función busca.
    """
    g = _rejilla(n=14, paso=0.008)
    w = pesos.knn(g, 8, CFG)
    m = g.to_crs(CFG.crs_metrico)
    base = 1e-5 * m.geometry.x.to_numpy()

    suave = base                                    # sin anomalías locales
    con_hoyo = base.copy()
    rng = np.random.default_rng(CFG.semilla)
    hoyos = rng.choice(len(con_hoyo), 15, replace=False)
    con_hoyo[hoyos] -= 1.2                          # puntos baratos entre caros

    n_suave = int(superficie.frontera(suave, w)["es_frontera"].sum())
    n_hoyo = int(superficie.frontera(con_hoyo, w)["es_frontera"].sum())
    assert n_suave == 0, "una superficie perfectamente suave no tiene frontera, y está bien"
    assert n_hoyo > 0, "con hoyos locales reales, la frontera tiene que encontrarlos"
