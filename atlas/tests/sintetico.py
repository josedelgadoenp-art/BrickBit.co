"""
Generador de listados SINTÉTICOS. **Sólo para pruebas.**

⚠ NADA DE LO QUE SALE DE AQUÍ PUEDE ENTRAR AL LAGO NI A UN INFORME. Es un
banco de pruebas: sirve para verificar que el pipeline de la Fase 2 corre, que
la partición no filtra, que el intervalo cubre lo que promete y que los números
salen donde deben. Un resultado calculado sobre estos datos no dice nada sobre
el mercado de la CDMX, y presentarlo como si lo dijera sería exactamente lo que
el principio de honestidad del proyecto prohíbe.

Vive en `tests/` y no en `atlas/` a propósito: así ningún camino de producción
puede importarlo por accidente.

El generador imita la estructura que el modelo tiene que encontrar —precio que
depende de la ubicación de forma suave, tamaño con rendimientos decrecientes,
ruido heterocedástico y agrupamiento espacial— para que una prueba de cobertura
sea informativa. No imita los niveles del mercado real y no lo pretende.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def listados(n: int = 2100, semilla: int = 20260828) -> pd.DataFrame:
    """Listados sintéticos con estructura espacial, en el esquema canónico."""
    rng = np.random.default_rng(semilla)

    # Cúmulos: el inventario real se agrupa, no se esparce uniforme. Importa
    # porque la partición por bloques sólo se pone a prueba si hay cúmulos.
    n_cumulos = 40
    cl_lat = rng.uniform(19.30, 19.55, n_cumulos)
    cl_lng = rng.uniform(-99.25, -99.05, n_cumulos)
    cual = rng.integers(0, n_cumulos, n)
    lat = cl_lat[cual] + rng.normal(0, 0.006, n)
    lng = cl_lng[cual] + rng.normal(0, 0.006, n)

    tipo = rng.choice(["depto", "casa", "terreno"], n, p=[0.62, 0.33, 0.05])
    sup = np.where(tipo == "casa", rng.lognormal(5.0, 0.45, n), rng.lognormal(4.4, 0.40, n))
    sup = np.clip(sup, 25, 900)
    rec = np.clip(np.round(1 + sup / 60 + rng.normal(0, 0.7, n)), 1, 6)
    ban = np.clip(np.round(rec * 0.8 + rng.normal(0, 0.5, n)), 1, 5)
    est = np.clip(np.round(rec * 0.6 + rng.normal(0, 0.6, n)), 0, 4)
    ant = np.clip(rng.gamma(2.0, 8.0, n), 0, 70)

    # Un "centro de valor" y decaimiento suave: es la estructura espacial que el
    # modelo tiene que recuperar y sobre la que se mide la I de Moran.
    dist = np.hypot((lat - 19.43) * 111.0, (lng + 99.17) * 105.0)
    ln_p = (
        10.05
        - 0.055 * dist
        - 0.13 * np.log(sup)
        - 0.004 * ant
        + 0.06 * (tipo == "depto")
        - 0.35 * (tipo == "terreno")
        + rng.normal(0, 0.18 + 0.010 * dist, n)   # ruido que crece con la lejanía
    )
    precio_m2 = np.exp(ln_p)
    operacion = rng.choice(["venta", "renta"], n, p=[0.8, 0.2])
    precio = np.where(operacion == "venta", precio_m2 * sup, precio_m2 * sup / 200.0)

    faltante = rng.random(n) < 0.35     # los anuncios reales vienen incompletos
    return pd.DataFrame({
        "id": [f"sint{i:06d}" for i in range(n)],
        "source": "SINTETICO-PRUEBAS",
        "fecha_captura": pd.Timestamp("2026-09-01"),
        "lat": lat, "lng": lng,
        "precio_asking": precio,
        "moneda": "MXN",
        "precio_m2_asking": np.where(operacion == "venta", precio_m2, precio_m2 / 200.0),
        "tipo": tipo, "operacion": operacion,
        "superficie_construida_m2": sup,
        "superficie_terreno_m2": np.where(tipo == "casa", sup * 1.3, np.nan),
        "recamaras": rec, "banos": ban,
        "medios_banos": np.where(rng.random(n) < 0.4, 1.0, 0.0),
        "estacionamientos": est,
        "antiguedad_anios": np.where(faltante, np.nan, ant),
        "niveles": np.where(faltante, np.nan, np.clip(np.round(rng.normal(2, 1, n)), 1, 20)),
        "amenidades": [None] * n,
        "alcaldia": pd.NA, "colonia": pd.NA, "cp": pd.NA, "ageb": pd.NA,
        "uso_suelo_seduvi": pd.NA, "niveles_permitidos": np.nan,
    })
