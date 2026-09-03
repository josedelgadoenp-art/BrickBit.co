"""
Pruebas de la Fase 0.

No comprueban que el código corra —eso lo dice el pipeline— sino que las
decisiones que importan sigan siendo ciertas: que no se midan distancias en
grados, que un municipio homónimo no se cuele, que el dedup conserve el
registro vigente, y que dos corridas den lo mismo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from atlas import lago
from atlas.config import cargar, fijar_semilla
from atlas.esquema import ESQUEMA, deduplicar, geohash, id_estable, normalizar
from atlas.geo import (a_geografico, a_metrico, conteo_en_radios,
                       distancia_al_mas_cercano, es_metrico, exigir_metrico,
                       haversine_m, puntos)

CFG = cargar()

# Dos puntos reales de la CDMX: Zócalo y Ángel de la Independencia.
ZOCALO = (19.4326, -99.1332)
ANGEL = (19.4270, -99.1677)


def _df(filas):
    return pd.DataFrame(filas)


# ------------------------------------------------------------------- config
def test_config_carga_y_es_unica():
    a = cargar()
    b = cargar()
    assert a is b, "cargar() debe cachear: una sola verdad por proceso"
    assert a.crs_metrico == "EPSG:6372"
    assert len(a.alcaldias) == 16, "la CDMX tiene 16 alcaldías"


def test_semilla_es_determinista():
    import random
    fijar_semilla(CFG)
    x = [random.random() for _ in range(5)]
    fijar_semilla(CFG)
    y = [random.random() for _ in range(5)]
    assert x == y, "sin determinismo, 'reproducible' es mentira"


def test_caja_rechaza_lo_de_fuera():
    caja = CFG.caja
    assert caja.contiene(*ZOCALO)
    assert not caja.contiene(21.1619, -86.8515)   # Cancún
    assert not caja.contiene(float("nan"), -99.1)  # NaN no debe pasar


# ---------------------------------------------------------------------- geo
def test_metrico_mide_en_metros_y_geografico_no():
    """
    El error que este módulo existe para impedir: la distancia Zócalo–Ángel es
    de ~3.6 km. En grados da ~0.038, que es el número que se colaría si alguien
    midiera sin proyectar.
    """
    g = puntos(_df([{"lat": ZOCALO[0], "lng": ZOCALO[1]},
                    {"lat": ANGEL[0], "lng": ANGEL[1]}]), cfg=CFG)
    en_grados = g.geometry.iloc[0].distance(g.geometry.iloc[1])
    m = a_metrico(g, CFG)
    en_metros = m.geometry.iloc[0].distance(m.geometry.iloc[1])

    real = haversine_m(*ZOCALO, *ANGEL)
    assert 3000 < real < 4500, f"referencia haversine fuera de rango: {real}"
    # La proyección debe coincidir con haversine dentro del 1%.
    assert abs(en_metros - real) / real < 0.01
    # Y el número en grados no debe parecerse ni de lejos: ese es el riesgo.
    assert en_grados < 1


def test_exigir_metrico_falla_ruidosamente():
    g = puntos(_df([{"lat": ZOCALO[0], "lng": ZOCALO[1]}]), cfg=CFG)
    with pytest.raises(ValueError, match="grados"):
        exigir_metrico(g, CFG)
    exigir_metrico(a_metrico(g, CFG), CFG)   # no debe lanzar


def test_reproyeccion_ida_y_vuelta_conserva_el_punto():
    g = puntos(_df([{"lat": ZOCALO[0], "lng": ZOCALO[1]}]), cfg=CFG)
    v = a_geografico(a_metrico(g, CFG), CFG)
    assert abs(v.geometry.iloc[0].y - ZOCALO[0]) < 1e-6
    assert abs(v.geometry.iloc[0].x - ZOCALO[1]) < 1e-6


def test_puntos_descarta_fuera_de_caja_y_basura():
    g = puntos(_df([
        {"lat": ZOCALO[0], "lng": ZOCALO[1]},     # dentro
        {"lat": 21.1619, "lng": -86.8515},        # Cancún
        {"lat": None, "lng": -99.1},              # sin lat
        {"lat": "abc", "lng": "def"},             # ilegible
    ]), cfg=CFG)
    assert len(g) == 1


def test_distancia_al_mas_cercano_sin_destinos_da_nan_no_cero():
    """'No hay ninguno' y 'hay uno pegado' no pueden ser el mismo número."""
    o = puntos(_df([{"lat": ZOCALO[0], "lng": ZOCALO[1]}]), cfg=CFG)
    vacio = o.iloc[0:0]
    d = distancia_al_mas_cercano(o, vacio, CFG)
    assert len(d) == 1 and np.isnan(d[0])


def test_distancia_al_mas_cercano_coincide_con_haversine():
    o = puntos(_df([{"lat": ZOCALO[0], "lng": ZOCALO[1]}]), cfg=CFG)
    d = puntos(_df([{"lat": ANGEL[0], "lng": ANGEL[1]}]), cfg=CFG)
    got = distancia_al_mas_cercano(o, d, CFG)[0]
    esperado = haversine_m(*ZOCALO, *ANGEL)
    assert abs(got - esperado) / esperado < 0.01


def test_conteo_en_radios_respeta_el_radio():
    o = puntos(_df([{"lat": ZOCALO[0], "lng": ZOCALO[1]}]), cfg=CFG)
    # ~111 m al norte y ~1.1 km al norte
    d = puntos(_df([
        {"lat": ZOCALO[0] + 0.001, "lng": ZOCALO[1]},
        {"lat": ZOCALO[0] + 0.010, "lng": ZOCALO[1]},
    ]), cfg=CFG)
    c = conteo_en_radios(o, d, [300, 1000, 2000], CFG)
    assert c["n_300m"].iloc[0] == 1
    assert c["n_2000m"].iloc[0] == 2


# ------------------------------------------------------------------ esquema
def test_normalizar_completa_el_esquema_y_cuenta_descartes():
    limpio, rep = normalizar(_df([
        # válido
        {"lat": ZOCALO[0], "lng": ZOCALO[1], "precio_asking": 4_000_000,
         "superficie_construida_m2": 80, "tipo": "Departamento", "operacion": "Venta",
         "source": "prueba", "fecha_captura": "2026-01-01"},
        # fuera de la CDMX
        {"lat": 21.16, "lng": -86.85, "precio_asking": 1_000_000,
         "superficie_construida_m2": 60, "source": "prueba"},
        # sin precio
        {"lat": ZOCALO[0], "lng": ZOCALO[1], "precio_asking": None,
         "superficie_construida_m2": 60, "source": "prueba"},
        # precio/m² absurdo en venta
        {"lat": ZOCALO[0], "lng": ZOCALO[1], "precio_asking": 5000,
         "superficie_construida_m2": 100, "operacion": "venta", "source": "prueba"},
    ]), CFG)
    assert list(limpio.columns) == list(ESQUEMA), "el esquema debe salir completo y en orden"
    assert rep.fuera_de_caja == 1
    assert rep.sin_precio == 1
    assert rep.precio_m2_absurdo == 1
    assert rep.aceptados == 1
    assert limpio["tipo"].iloc[0] == "depto"
    assert limpio["operacion"].iloc[0] == "venta"
    assert abs(limpio["precio_m2_asking"].iloc[0] - 50_000) < 1


def test_renta_no_se_filtra_con_el_umbral_de_venta():
    """Una renta de $250/m² al mes es normal; el piso es para venta."""
    limpio, rep = normalizar(_df([
        {"lat": ZOCALO[0], "lng": ZOCALO[1], "precio_asking": 20_000,
         "superficie_construida_m2": 80, "operacion": "renta", "source": "p"},
    ]), CFG)
    assert rep.aceptados == 1 and rep.precio_m2_absurdo == 0


def test_id_estable_no_depende_de_la_fecha():
    a = id_estable("c21", 19.4326, -99.1332, 4_000_000, 80)
    b = id_estable("c21", 19.4326, -99.1332, 4_000_000, 80)
    assert a == b and len(a) == 16


def test_geohash_agrupa_lo_cercano_y_separa_lo_lejano():
    cerca = geohash(ZOCALO[0], ZOCALO[1], 8)
    igual = geohash(ZOCALO[0] + 1e-5, ZOCALO[1], 8)   # ~1 m
    lejos = geohash(ANGEL[0], ANGEL[1], 8)            # ~3.6 km
    assert cerca == igual
    assert cerca != lejos


def test_dedup_conserva_el_registro_mas_reciente():
    base = {"lat": ZOCALO[0], "lng": ZOCALO[1], "superficie_construida_m2": 80,
            "tipo": "depto", "operacion": "venta", "source": "p"}
    limpio, _ = normalizar(_df([
        {**base, "precio_asking": 4_000_000, "fecha_captura": "2026-01-01"},
        {**base, "precio_asking": 4_000_000, "fecha_captura": "2026-06-01"},  # republicado
        {**base, "precio_asking": 9_000_000, "fecha_captura": "2026-03-01"},  # otro inmueble
    ]), CFG)
    dd, n = deduplicar(limpio, CFG)
    assert n == 1, "el republicado debía colapsarse"
    assert len(dd) == 2
    vigente = dd.loc[dd["precio_asking"] == 4_000_000, "fecha_captura"].iloc[0]
    assert vigente == pd.Timestamp("2026-06-01"), "debe quedar el precio vigente"


def test_dedup_sobre_vacio_no_revienta():
    vacio, _ = normalizar(pd.DataFrame(), CFG)
    dd, n = deduplicar(vacio, CFG)
    assert len(dd) == 0 and n == 0


# ------------------------------------------------------------------- DENUE
def test_denue_rechaza_municipios_homonimos():
    """
    El bug que esta prueba congela: `establecimientos_benito_juarez.csv.gz` es
    Benito Juárez de QUINTANA ROO (Cancún). Emparejar por nombre lo metía en el
    Atlas de la CDMX. La selección tiene que ser geográfica.
    """
    from atlas.ingesta import denue

    archivos = denue.archivos_disponibles(CFG)
    if "benito_juarez" not in archivos:
        pytest.skip("no hay datos de Benito Juárez en este entorno")
    elegido = archivos["benito_juarez"].name
    assert elegido == "establecimientos_benito_juarez_cdmx.csv.gz", (
        f"se eligió {elegido}: revisa la verificación geográfica"
    )


def test_denue_es_determinista():
    from atlas.ingesta import denue

    a = {k: str(v) for k, v in denue.archivos_disponibles(CFG).items()}
    denue._verificados.cache_clear()
    b = {k: str(v) for k, v in denue.archivos_disponibles(CFG).items()}
    assert a == b


# --------------------------------------------------------------------- lago
def test_lago_guarda_y_lee_con_geometria_y_procedencia(tmp_path, monkeypatch):
    g = puntos(_df([{"lat": ZOCALO[0], "lng": ZOCALO[1], "n": 1}]), cfg=CFG)
    monkeypatch.setattr(type(CFG), "lago", property(lambda self: tmp_path))
    lago.guardar("prueba", g, fuente="test", nota="ida y vuelta", cfg=CFG)
    v = lago.leer("prueba", cfg=CFG)
    assert len(v) == 1
    assert v.crs is not None and es_metrico(a_metrico(v, CFG), CFG)
    man = lago.manifiesto(CFG)["prueba"]
    assert man["filas"] == 1 and man["fuente"] == "test"


def test_lago_falla_claro_si_no_existe_la_capa(tmp_path, monkeypatch):
    monkeypatch.setattr(type(CFG), "lago", property(lambda self: tmp_path))
    with pytest.raises(FileNotFoundError, match="Fase 0"):
        lago.leer("no_existe", cfg=CFG)
