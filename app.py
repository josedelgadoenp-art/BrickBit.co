# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
 BrickBit · MOTOR DE MORFOGÉNESIS URBANA — MÉXICO A RESOLUCIÓN MUNICIPAL 🇲🇽
═══════════════════════════════════════════════════════════════════════════════
 La República como ORGANISMO VIVO, en tres escalas de un mismo tejido:

 🏛 REPÚBLICA · MUNICIPIOS — las 2,436 células administrativas reales del
    país, con la delimitación estatal superpuesta (estilo Google Maps).
    El contagio de plusvalía viaja municipio a municipio por su matriz de
    contigüidad real (15 mil fronteras compartidas).

 🇲🇽 REPÚBLICA · ESTADOS — los 32 órganos del organismo y el capital
    circulando entre las 32 zonas metropolitanas dominantes.

 🧫 MICROTEJIDO — zoom celular a Azcapotzalco/Vallejo (CDMX): cada manzana
    es una célula que muta al ritmo de sus vecinas.

 Analítica integrada: Índice de Moran (cohesión espacial), ranking de
 mutación, trayectorias proyectadas, diagrama de fases del mercado y
 megaproyectos detonantes (Tren Maya, nearshoring, Interoceánico…).

 Identidad visual: paleta, tipografía (Fraunces · Hanken Grotesk · Space
 Mono) y logo oficiales de https://brickbit.co

 Ejecución:
     pip install -r requirements.txt
     streamlit run app.py

 Datos: precios/plusvalía/yield del dataset BrickBit (zonas.js) + población
 y PIB per cápita aproximados; el detalle municipal se sintetiza por
 proximidad a las ZM. Proyecciones 100% simuladas (demo visual).
═══════════════════════════════════════════════════════════════════════════════
"""

import base64
import json
import math
import os
import re
import time
import unicodedata
import urllib.request
from urllib.parse import quote

import numpy as np
import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st
from fpdf import FPDF
from shapely.geometry import box

# ══════════════════════════════════════════════════════════════════════════════
# 1 · IDENTIDAD BRICKBIT + CONFIGURACIÓN GLOBAL
# ══════════════════════════════════════════════════════════════════════════════

# ── Design tokens oficiales de brickbit.co ────────────────────────────────────
TIERRA = "#100c0a"          # --bg          fondo tierra oscura
SUPERFICIE = "#1d1713"      # --surface     tarjetas / paneles
CREMA = "#f5ede3"           # --cream       texto principal
TEXTO_SUAVE = "#a89a8c"     # --muted-txt   texto secundario
ARCILLA_PROF = "#0c4a30"    # --clay-deep
ARCILLA = "#24664a"         # --clay        bosque mate
ARCILLA_SUAVE = "#6fa287"   # --clay-soft   salvia mate
LIMA = "#b7c489"            # --lime        oliva mate (acento)
LIMA_PROF = "#9aac6b"       # --lime-deep   oliva profundo mate

FUENTES_URL = ("https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400..700"
               "&family=Hanken+Grotesk:wght@400;500;600;700&family=Space+Mono:wght@400;700"
               "&display=swap")

SEMILLA = 42
AÑOS = 10                          # horizonte de simulación
CRECIMIENTO_BASE = 0.018           # inflación inmobiliaria de fondo (micro)

_DIR = os.path.dirname(os.path.abspath(__file__))
RUTA_ESTADOS = os.path.join(_DIR, "data", "mexico_estados.json")
RUTA_MUNICIPIOS = os.path.join(_DIR, "data", "mexico_municipios.json")
RUTA_LOGO = os.path.join(_DIR, "assets", "brickbit_logo.png")
URL_ESTADOS = ("https://raw.githubusercontent.com/angelnmara/geojson/"
               "master/mexicoHigh.json")
URL_MUNICIPIOS = ("https://raw.githubusercontent.com/strotgen/mexico-leaflet/"
                  "master/municipalities.geojson")

# Basemap FIJO: Tierra BrickBit (Carto dark-matter, sin token) — el único
# estilo de la app; casa con la paleta mate (tierra #100c0a / crema #f5ede3).
ESTILO_MAPA = ("https://basemaps.cartocdn.com/gl/"
               "dark-matter-nolabels-gl-style/style.json")

# Las cinco escalas del organismo: clave interna → etiqueta del selector.
# La LÓGICA compara siempre la clave (esc == "micro"…), nunca la etiqueta.
ESCALAS = {
    "muni": "República · municipios",
    "edos": "República · estados",
    "cp": "CDMX · códigos postales",
    "calle": "Calle · establecimiento",
    "micro": "Microtejido (CDMX)",
}
ESCALA_POR_LABEL = {v: k for k, v in ESCALAS.items()}

# Rampa "vegetal" BrickBit: arcilla profunda → arcilla → arcilla suave → lima → crema
_STOPS_T = np.array([0.00, 0.30, 0.55, 0.80, 1.00])
_STOPS_R = np.array([12.0, 36.0, 111.0, 183.0, 245.0])
_STOPS_G = np.array([74.0, 102.0, 162.0, 196.0, 237.0])
_STOPS_B = np.array([48.0, 74.0, 135.0, 137.0, 227.0])

# Colorway Plotly de marca
NEON = [LIMA, ARCILLA_SUAVE, CREMA, LIMA_PROF, ARCILLA,
        "#55997e", "#c07a66", "#cf928b"]
ESCALA_PLOTLY = [[0.0, ARCILLA_PROF], [0.30, ARCILLA],
                 [0.55, ARCILLA_SUAVE], [0.80, LIMA], [1.0, CREMA]]

# Colores RGBA de capas (sistema circulatorio en verdes/lima de marca)
RGB_ARCILLA_SUAVE = [111, 162, 135]
RGB_LIMA = [183, 196, 137]
RGB_CREMA = [245, 237, 227]

# Claves INEGI de entidad federativa (state_code del GeoJSON municipal)
CODIGO_ESTADO = {
    1: "Aguascalientes", 2: "Baja California", 3: "Baja California Sur",
    4: "Campeche", 5: "Coahuila", 6: "Colima", 7: "Chiapas", 8: "Chihuahua",
    9: "Ciudad de México", 10: "Durango", 11: "Guanajuato", 12: "Guerrero",
    13: "Hidalgo", 14: "Jalisco", 15: "México", 16: "Michoacán", 17: "Morelos",
    18: "Nayarit", 19: "Nuevo León", 20: "Oaxaca", 21: "Puebla",
    22: "Querétaro", 23: "Quintana Roo", 24: "San Luis Potosí", 25: "Sinaloa",
    26: "Sonora", 27: "Tabasco", 28: "Tamaulipas", 29: "Tlaxcala",
    30: "Veracruz", 31: "Yucatán", 32: "Zacatecas",
}


def paleta_marca(t: np.ndarray) -> np.ndarray:
    """Mapea valores normalizados [0,1] a la rampa vegetal BrickBit (RGB)."""
    t = np.clip(t, 0, 1)
    return np.stack([np.interp(t, _STOPS_T, _STOPS_R),
                     np.interp(t, _STOPS_T, _STOPS_G),
                     np.interp(t, _STOPS_T, _STOPS_B)], axis=1)


def norm01(x: np.ndarray) -> np.ndarray:
    """Normaliza un vector a [0,1] (robusto ante rango cero)."""
    x = np.asarray(x, dtype=float)
    return (x - x.min()) / (np.ptp(x) + 1e-9)


def estado_en(valores: np.ndarray, año: float) -> tuple[np.ndarray, np.ndarray]:
    """
    Interpola linealmente entre años enteros para que el slider se sienta
    continuo (el organismo "respira" en vez de saltar). Devuelve el valor en
    el instante `año` y la tasa de crecimiento anual instantánea por unidad.
    """
    n = valores.shape[0] - 1
    t0 = int(np.clip(math.floor(año), 0, n))
    t1 = int(np.clip(t0 + 1, 0, n))
    f = np.clip(año - t0, 0, 1)
    v_t = valores[t0] * (1 - f) + valores[t1] * f
    tasa = (valores[t1] - valores[t0]) / valores[t0] if t1 > t0 \
        else (valores[t0] - valores[t0 - 1]) / valores[t0 - 1]
    return v_t, tasa


RETRO = 5   # años de retro-simulación del time-lapse bidireccional


def extender_pasado(valores: np.ndarray, años: int = RETRO) -> np.ndarray:
    """
    Time-lapse bidireccional: antepone una RETRO-SIMULACIÓN (claramente
    etiquetada) integrando el crecimiento del primer año hacia atrás, para
    ver de dónde VIENE la ola además de a dónde va. Con datos históricos
    reales (DENUE/SHF vía scripts de ingesta) este tramo se vuelve real.
    """
    r = (valores[1] / valores[0] - 1) * 0.8
    filas = [valores[0] / (1 + r) ** k for k in range(años, 0, -1)]
    return np.vstack(filas + [valores])


def moran_local(v: np.ndarray, pares: tuple) -> tuple[np.ndarray, np.ndarray]:
    """
    Moran LOCAL (LISA): z-score de cada célula y el promedio de sus vecinas
    (lag espacial). El cuadrante Low-High (célula barata rodeada de caras)
    es el FRENTE DE ONDA de la gentrificación: ahí rompe la siguiente ola.
    """
    pi, pj, g = pares
    z = (v - v.mean()) / (v.std() + 1e-9)
    lag = np.bincount(pi, weights=z[pj], minlength=v.size) / g
    return z, lag


def frente_de_onda(v: np.ndarray, pares: tuple) -> np.ndarray:
    """Máscara Low-High del LISA: la frontera donde la ola va a romper."""
    z, lag = moran_local(v, pares)
    return (z < -0.05) & (lag > 0.15)


RUTA_PRECIOS = os.path.join(_DIR, "data", "precios_zonas.csv")


@st.cache_data(max_entries=1)
def precios_reales() -> pd.DataFrame | None:
    """
    Anclajes de precio REALES muestreados de portales inmobiliarios
    (scripts/ingerir_precios.py). None si aún no se han ingerido.
    """
    if not os.path.exists(RUTA_PRECIOS):
        return None
    df = pd.read_csv(RUTA_PRECIOS)
    # mediana entre portales por zona (más robusta que un portal único)
    agg = df.groupby(["zona", "lat", "lng"], as_index=False) \
        .agg(precio_m2=("precio_m2_mediano", "median"),
             n_muestras=("n_muestras", "sum"))
    # control de calidad: un ancla necesita ≥8 muestras para usarse
    agg = agg[agg["n_muestras"] >= 8]
    return agg if not agg.empty else None


def calibrar_con_precios(lng: np.ndarray, lat: np.ndarray,
                         precio_sint: np.ndarray
                         ) -> tuple[np.ndarray, int]:
    """
    Calibra el precio sintético contra los anclajes reales: ajusta el nivel
    global (mediana de ratios reales/sintéticos en las zonas ancla) y aplica
    una corrección local que decae con la distancia a cada ancla. Devuelve
    (precio calibrado, n_zonas ancla usadas). Sin anclas, devuelve intacto.
    """
    anc = precios_reales()
    if anc is None or anc.empty:
        return precio_sint, 0
    ax, ay = anc["lng"].to_numpy(), anc["lat"].to_numpy()
    ap_ = anc["precio_m2"].to_numpy(dtype=float)
    # ratio real/sintético en la celda más cercana a cada ancla
    ratios = []
    for x, y, pr in zip(ax, ay, ap_):
        d = np.hypot(lng - x, lat - y)
        j = int(np.argmin(d))
        if d[j] < 0.03 and precio_sint[j] > 0:      # ancla dentro de ~3 km
            ratios.append(pr / precio_sint[j])
    if not ratios:
        return precio_sint, 0
    factor = float(np.median(ratios))
    p = precio_sint * factor
    # corrección local suave hacia cada ancla (kernel gaussiano ~1.2 km)
    for x, y, pr in zip(ax, ay, ap_):
        w = np.exp(-((lng - x) ** 2 + (lat - y) ** 2) / (2 * 0.011 ** 2))
        p = p * (1 - 0.6 * w) + pr * 0.6 * w
    return p.round(0), len(ratios)


def score_brickbit(v_t: np.ndarray, v0: np.ndarray, potencial: np.ndarray,
                   tasa: np.ndarray) -> np.ndarray:
    """
    Score BrickBit 0–10 por célula: plusvalía proyectada (40%) + potencial
    morfogenético (25%) + velocidad de contagio (20%) + accesibilidad de
    entrada (15%). Cada punto es auditable en 'Origen del crecimiento'.
    """
    acum = v_t / v0 - 1
    s = (0.40 * norm01(acum) + 0.25 * np.asarray(potencial, dtype=float)
         + 0.20 * norm01(tasa) + 0.15 * (1 - norm01(v_t)))
    return np.round(10 * np.clip(s, 0, 1), 1)


def clasificar_bio(tasa: np.ndarray) -> np.ndarray:
    """Etiqueta biológica por percentil de contagio."""
    p85, p55 = np.quantile(tasa, 0.85), np.quantile(tasa, 0.55)
    return np.where(tasa >= p85, "🧬 Mutación activa",
                    np.where(tasa >= p55, "🌱 Expansión", "💤 Latente"))


# ══════════════════════════════════════════════════════════════════════════════
# 2 · DATASET NACIONAL — 32 ZONAS METROPOLITANAS · 32 ESTADOS
#     precio_m2 / plusvalía / yield: dataset BrickBit "Valor Futuro" (zonas.js)
# ══════════════════════════════════════════════════════════════════════════════

CIUDADES = [
    # ciudad, estado, lat, lng, precio_m2, plusvalía %, yield %, pob ZM (M)
    ("Ciudad de México", "Ciudad de México", 19.432, -99.133, 40500, 5.1, 4.5, 21.8),
    ("Guadalajara", "Jalisco", 20.667, -103.347, 13400, 12.5, 6.2, 5.3),
    ("Monterrey", "Nuevo León", 25.686, -100.316, 12700, 9.3, 6.8, 5.3),
    ("Cancún", "Quintana Roo", 21.161, -86.851, 17400, 13.4, 7.8, 0.93),
    ("Mérida", "Yucatán", 20.967, -89.623, 19200, 10.7, 7.1, 1.2),
    ("Querétaro", "Querétaro", 20.588, -100.389, 20000, 6.6, 6.5, 1.5),
    ("Tijuana", "Baja California", 32.514, -117.038, 17600, 11.0, 5.8, 2.2),
    ("Puebla", "Puebla", 19.041, -98.206, 17200, 9.2, 5.9, 3.2),
    ("León", "Guanajuato", 21.122, -101.682, 12500, 8.2, 6.4, 1.9),
    ("San Luis Potosí", "San Luis Potosí", 22.150, -100.976, 13900, 7.5, 6.9, 1.2),
    ("Aguascalientes", "Aguascalientes", 21.882, -102.291, 11500, 11.7, 6.7, 1.1),
    ("La Paz", "Baja California Sur", 24.142, -110.311, 25600, 11.1, 7.4, 0.30),
    ("Saltillo", "Coahuila", 25.423, -101.005, 10500, 8.4, 5.4, 1.0),
    ("Chihuahua", "Chihuahua", 28.632, -106.069, 14500, 10.2, 5.6, 1.0),
    ("Culiacán", "Sinaloa", 24.809, -107.394, 14200, 10.7, 6.6, 1.0),
    ("Hermosillo", "Sonora", 29.073, -110.956, 12500, 9.8, 5.7, 0.95),
    ("Durango", "Durango", 24.028, -104.668, 8300, 4.9, 7.0, 0.70),
    ("Tepic", "Nayarit", 21.504, -104.894, 16300, 11.8, 6.3, 0.50),
    ("Colima", "Colima", 19.243, -103.725, 11500, 8.4, 6.0, 0.38),
    ("Toluca", "México", 19.283, -99.656, 15200, 5.2, 5.2, 2.4),
    ("Morelia", "Michoacán", 19.706, -101.195, 11600, 10.9, 5.5, 0.90),
    ("Cuernavaca", "Morelos", 18.924, -99.221, 20100, 9.1, 5.3, 1.0),
    ("Pachuca", "Hidalgo", 20.101, -98.759, 13900, 9.6, 5.5, 0.60),
    ("Oaxaca", "Oaxaca", 17.073, -96.726, 17600, 7.1, 5.3, 0.70),
    ("Tuxtla Gutiérrez", "Chiapas", 16.753, -93.116, 15800, 8.4, 4.6, 0.85),
    ("Villahermosa", "Tabasco", 17.989, -92.928, 13200, 5.9, 4.8, 0.85),
    ("Campeche", "Campeche", 19.845, -90.523, 17200, 7.5, 5.4, 0.30),
    ("Veracruz", "Veracruz", 19.173, -96.134, 13100, 7.1, 5.1, 0.94),
    ("Zacatecas", "Zacatecas", 22.770, -102.583, 9000, 5.8, 5.6, 0.40),
    ("Tlaxcala", "Tlaxcala", 19.318, -98.237, 9300, 5.0, 5.2, 0.55),
    ("Reynosa", "Tamaulipas", 26.051, -98.288, 9600, 11.3, 6.1, 0.90),
    ("Chilpancingo", "Guerrero", 17.551, -99.505, 15100, 8.1, 4.4, 0.30),
]

POB_ESTADO = {  # millones de habitantes (censo 2020, aprox)
    "Aguascalientes": 1.43, "Baja California": 3.77, "Baja California Sur": 0.80,
    "Campeche": 0.93, "Coahuila": 3.15, "Colima": 0.73, "Chiapas": 5.54,
    "Chihuahua": 3.74, "Ciudad de México": 9.21, "Durango": 1.83,
    "Guanajuato": 6.17, "Guerrero": 3.54, "Hidalgo": 3.08, "Jalisco": 8.35,
    "México": 16.99, "Michoacán": 4.75, "Morelos": 1.97, "Nayarit": 1.24,
    "Nuevo León": 5.78, "Oaxaca": 4.13, "Puebla": 6.58, "Querétaro": 2.37,
    "Quintana Roo": 1.86, "San Luis Potosí": 2.82, "Sinaloa": 3.03,
    "Sonora": 2.94, "Tabasco": 2.40, "Tamaulipas": 3.53, "Tlaxcala": 1.34,
    "Veracruz": 8.06, "Yucatán": 2.32, "Zacatecas": 1.62,
}

PIB_PC = {  # PIB per cápita estatal aprox, miles de MXN/año
    "Aguascalientes": 220, "Baja California": 230, "Baja California Sur": 260,
    "Campeche": 300, "Coahuila": 280, "Colima": 170, "Chiapas": 60,
    "Chihuahua": 240, "Ciudad de México": 430, "Durango": 150,
    "Guanajuato": 175, "Guerrero": 75, "Hidalgo": 125, "Jalisco": 200,
    "México": 110, "Michoacán": 105, "Morelos": 115, "Nayarit": 115,
    "Nuevo León": 375, "Oaxaca": 80, "Puebla": 110, "Querétaro": 275,
    "Quintana Roo": 220, "San Luis Potosí": 200, "Sinaloa": 155,
    "Sonora": 265, "Tabasco": 270, "Tamaulipas": 215, "Tlaxcala": 85,
    "Veracruz": 115, "Yucatán": 160, "Zacatecas": 130,
}

MEGAPROYECTOS = {
    "— Sin megaproyecto —": None,
    "Tren Maya + Riviera (sureste)": dict(
        estados=["Yucatán", "Quintana Roo", "Campeche", "Tabasco", "Chiapas"],
        año=1, fuerza=0.50),
    "Nearshoring · corredor norte": dict(
        estados=["Nuevo León", "Coahuila", "Chihuahua", "Tamaulipas",
                 "Baja California", "Sonora"], año=2, fuerza=0.45),
    "Corredor Interoceánico (Istmo)": dict(
        estados=["Oaxaca", "Veracruz", "Tabasco"], año=2, fuerza=0.55),
    "Polo aeroespacial del Bajío": dict(
        estados=["Querétaro", "Guanajuato", "Aguascalientes",
                 "San Luis Potosí", "Jalisco"], año=3, fuerza=0.40),
}


# ══════════════════════════════════════════════════════════════════════════════
# 3 · GEOMETRÍA — ESTADOS Y MUNICIPIOS CON CONTIGÜIDAD REAL
# ══════════════════════════════════════════════════════════════════════════════

def _cargar_geojson(ruta: str, url: str) -> dict:
    """GeoJSON local con fallback a descarga (se persiste para la siguiente corrida)."""
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    with urllib.request.urlopen(url, timeout=120) as r:
        geo = json.load(r)
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(geo, f)
    except OSError:
        pass
    return geo


@st.cache_data(show_spinner="🗺 Cargando delimitación estatal…", max_entries=1)
def cargar_estados() -> gpd.GeoDataFrame:
    """Los 32 polígonos estatales → GeoDataFrame(estado, geometry)."""
    geo = _cargar_geojson(RUTA_ESTADOS, URL_ESTADOS)
    gdf = gpd.GeoDataFrame.from_features(geo["features"], crs="EPSG:4326")
    gdf = gdf.rename(columns={"name": "estado"})[["estado", "geometry"]]
    return gdf.sort_values("estado").reset_index(drop=True)


@st.cache_data(show_spinner="🏛 Cargando los 2,436 municipios…", max_entries=1)
def cargar_municipios() -> gpd.GeoDataFrame:
    """
    Las 2,436 células administrativas reales del país (GeoJSON simplificado a
    ~800 m). Columnas: municipio, estado, lng, lat (centroide), geometry.
    """
    geo = _cargar_geojson(RUTA_MUNICIPIOS, URL_MUNICIPIOS)
    gdf = gpd.GeoDataFrame.from_features(geo["features"], crs="EPSG:4326")
    gdf["geometry"] = gdf.geometry.simplify(0.008, preserve_topology=True)
    gdf["municipio"] = gdf["mun_name"]
    gdf["estado"] = gdf["state_code"].map(CODIGO_ESTADO)
    # CVEGEO INEGI (entidad 2 díg + municipio 3 díg) para cruzar con el DENUE
    gdf["cvegeo"] = (gdf["state_code"].astype(int).astype(str).str.zfill(2)
                     + gdf["mun_code"].astype(int).astype(str).str.zfill(3))
    cen = gdf.geometry.representative_point()
    gdf["lng"], gdf["lat"] = cen.x, cen.y
    return gdf[["municipio", "estado", "cvegeo", "lng", "lat", "geometry"]] \
        .reset_index(drop=True)


def _vecindad(geoms: list, tolerancia: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pares (i, j) de geometrías que se tocan (matriz W del SAR, vía STRtree)."""
    gdf = gpd.GeoDataFrame(geometry=list(geoms), crs="EPSG:4326")
    buf = gdf.copy()
    buf["geometry"] = buf.geometry.buffer(tolerancia)
    join = gpd.sjoin(buf, gdf, predicate="intersects")
    pi = join.index.to_numpy()
    pj = join["index_right"].to_numpy()
    mask = pi != pj
    pi, pj = pi[mask], pj[mask]
    grados = np.bincount(pi, minlength=len(gdf)).astype(float)
    grados[grados == 0] = 1.0
    return pi, pj, grados


@st.cache_data(show_spinner="🧠 Tejiendo contigüidad estatal…", max_entries=1)
def vecindad_estados() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return _vecindad(cargar_estados().geometry.tolist(), 0.03)


@st.cache_data(show_spinner="🧠 Tejiendo las ~15,000 fronteras municipales…", max_entries=1)
def vecindad_municipios() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return _vecindad(cargar_municipios().geometry.tolist(), 0.015)


@st.cache_data(max_entries=1)
def contornos_estatales() -> pd.DataFrame:
    """MultiPolygons estatales explotados a anillos exteriores para PyDeck."""
    filas = []
    for idx, fila in cargar_estados().iterrows():
        geoms = fila.geometry.geoms if fila.geometry.geom_type == "MultiPolygon" \
            else [fila.geometry]
        for g in geoms:
            filas.append({"idx_estado": idx,
                          "contorno": [list(map(list, g.exterior.coords))]})
    return pd.DataFrame(filas)


@st.cache_data(max_entries=1)
def contornos_municipales() -> pd.DataFrame:
    """Anillos municipales (coordenadas a 4 decimales ≈ 11 m para aligerar)."""
    filas = []
    for idx, geom in enumerate(cargar_municipios().geometry):
        geoms = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
        for g in geoms:
            filas.append({"idx_mun": idx,
                          "contorno": [[[round(x, 4), round(y, 4)]
                                        for x, y in g.exterior.coords]]})
    return pd.DataFrame(filas)


# ══════════════════════════════════════════════════════════════════════════════
# 4 · EXPEDIENTES — ATRIBUTOS ESTATALES Y MUNICIPALES
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(max_entries=1)
def datos_estatales() -> pd.DataFrame:
    """Expediente de cada estado alineado al GeoDataFrame estatal."""
    gdf = cargar_estados()
    df_c = pd.DataFrame(CIUDADES, columns=[
        "ciudad", "estado", "lat", "lng", "precio_m2",
        "plusvalia", "yld", "pob_zm"])
    ref = df_c.drop_duplicates("estado").set_index("estado")
    df = pd.DataFrame({"estado": gdf["estado"]})
    for col in ["ciudad", "lat", "lng", "precio_m2", "plusvalia", "yld"]:
        df[col] = df["estado"].map(ref[col])
    df["poblacion"] = df["estado"].map(POB_ESTADO)
    df["pib_pc"] = df["estado"].map(PIB_PC)
    df["masa_economica"] = df["poblacion"] * df["pib_pc"]
    df["potencial"] = np.clip(
        0.55 * norm01(df["plusvalia"]) + 0.25 * norm01(df["yld"])
        + 0.20 * (1 - norm01(df["precio_m2"])), 0, 1).round(3)
    return df


@st.cache_data(show_spinner="🧫 Sintetizando el expediente municipal…", max_entries=1)
def datos_municipales() -> pd.DataFrame:
    """
    Expediente de los 2,436 municipios. Sin microdatos públicos por municipio,
    el precio se sintetiza con un gradiente de accesibilidad realista:

        precio = precio_estatal · (0.42 + 0.78·e^-(d/0.30)²) · ruido

    donde d es la distancia a la ZM más cercana → los municipios conurbados
    heredan el precio metropolitano y el México profundo queda accesible.
    El potencial pico vive en el ANILLO PERIURBANO (d≈25 km): la frontera de
    expansión donde la mancha urbana muta primero.
    """
    rng = np.random.default_rng(SEMILLA)
    gdf = cargar_municipios()
    df_e = datos_estatales().set_index("estado")

    lng, lat = gdf["lng"].to_numpy(), gdf["lat"].to_numpy()
    c_lng = np.array([c[3] for c in CIUDADES])
    c_lat = np.array([c[2] for c in CIUDADES])
    # distancia (en grados ≈ 105 km/grado) a la ZM más cercana
    d = np.sqrt((lng[:, None] - c_lng[None, :]) ** 2
                + (lat[:, None] - c_lat[None, :]) ** 2)
    zm_idx = d.argmin(axis=1)
    d_zm = d.min(axis=1)

    precio_e = gdf["estado"].map(df_e["precio_m2"]).to_numpy(dtype=float)
    plusv_e = gdf["estado"].map(df_e["plusvalia"]).to_numpy(dtype=float)
    pot_e = gdf["estado"].map(df_e["potencial"]).to_numpy(dtype=float)

    gradiente = 0.42 + 0.78 * np.exp(-(d_zm / 0.30) ** 2)
    precio = precio_e * gradiente * rng.lognormal(0.0, 0.08, len(gdf))

    anillo = np.exp(-((d_zm - 0.22) / 0.22) ** 2)   # anillo periurbano
    potencial = np.clip(0.55 * pot_e + 0.50 * anillo
                        + rng.normal(0, 0.06, len(gdf)), 0.02, 1)

    df = pd.DataFrame({
        "municipio": gdf["municipio"], "estado": gdf["estado"],
        "cvegeo": gdf["cvegeo"],
        "lng": lng, "lat": lat,
        "precio_actual": precio.round(0),
        "potencial_crecimiento": potencial.round(3),
        "plusvalia_estatal": plusv_e,
        "zm_cercana": [CIUDADES[i][0] for i in zm_idx],
        "dist_zm_km": (d_zm * 105).round(0),
        "n_estab": 0, "empleo": 0, "resiliencia": 0.0,
        "indicadoras": 0, "vitalidad_real": np.nan,
    })

    # 🏪 Vitalidad económica REAL del DENUE por municipio (si fue ingerida
    # con scripts/ingerir_denue_nacional.py). Ancla precio y potencial en la
    # densidad de negocios/empleo observada, no solo en el gradiente a la ZM.
    ruta = os.path.join(_DIR, "data", "denue_municipal.csv")
    if os.path.exists(ruta):
        den = pd.read_csv(ruta, dtype={"cvegeo": str})
        df = df.merge(den[["cvegeo", "n_estab", "empleo", "resiliencia",
                           "indicadoras"]], on="cvegeo", how="left",
                      suffixes=("", "_r"))
        for c in ["n_estab_r", "empleo_r", "resiliencia_r", "indicadoras_r"]:
            base = c[:-2]
            df[base] = df[c].fillna(df[base])
            df.drop(columns=c, inplace=True)
        # vitalidad real = densidad económica (negocios + empleo) normalizada
        vital = norm01(np.log1p(df["n_estab"].to_numpy())
                       + 0.6 * norm01(np.log1p(df["empleo"].to_numpy())))
        tiene = df["n_estab"].to_numpy() > 0
        df["vitalidad_real"] = np.where(tiene, vital, np.nan)
        # el precio real-informado: mezcla el gradiente con la densidad real
        precio_real = precio_e * (0.35 + 1.3 * vital) \
            * rng.lognormal(0.0, 0.05, len(df))
        df.loc[tiene, "precio_actual"] = precio_real[tiene].round(0)
        # el potencial sube donde hay especies indicadoras recientes reales
        ind = norm01(df["indicadoras"].to_numpy())
        df.loc[tiene, "potencial_crecimiento"] = np.clip(
            0.45 * potencial + 0.30 * anillo + 0.25 * ind, 0.02, 1
        )[tiene].round(3)

        # 🏚 estancamiento: municipios urbanos cuyo tejido NO se renueva
        # (tasa de aperturas recientes por negocio en el percentil más bajo)
        alta = pd.read_csv(ruta, dtype={"cvegeo": str})[
            ["cvegeo", "altas_recientes"]]
        df = df.merge(alta, on="cvegeo", how="left")
        df["altas_recientes"] = df["altas_recientes"].fillna(0)
        renovacion = df["altas_recientes"] / df["n_estab"].clip(lower=1)
        urbano = df["n_estab"] >= 300
        umbral = renovacion[urbano].quantile(0.15) if urbano.any() else 0
        df["tasa_renovacion"] = renovacion.round(4)
        df["estancado"] = urbano & (renovacion <= umbral)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 4.5 · MERCADO VIVO C21 — medianas REALES de lista por zona (worker BrickBit)
#       Capa de VERDAD aterrizada: enriquece tooltips, nunca recolorea el mapa.
# ══════════════════════════════════════════════════════════════════════════════

URL_MERCADO_VIVO = ("https://brickbit-api.jose-delgado-enp.workers.dev"
                    "/api/listados?zona=_metricas")


def slugificar(texto: str) -> str:
    """
    Slug idéntico al del worker BrickBit (c21-subir.mjs):
    NFD → sin diacríticos → lower → no-alfanumérico a '-' → strip '-'.
    """
    t = unicodedata.normalize("NFD", str(texto))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


@st.cache_data(ttl=3600, show_spinner=False)
def cargar_mercado_vivo() -> dict:
    """
    Medianas reales de PRECIOS DE LISTA Century 21 por zona, refrescadas a
    diario por el worker BrickBit → {slug: registro}. Cualquier fallo (sin
    red, timeout, JSON inesperado) devuelve {} en silencio: la app NUNCA
    debe romperse por esta capa.
    """
    try:
        import requests
        r = requests.get(URL_MERCADO_VIVO, timeout=8)
        r.raise_for_status()
        datos = r.json()
        if isinstance(datos, dict):    # tolerar envolturas {"items": [...]}
            datos = (datos.get("items") or datos.get("listados")
                     or datos.get("zonas") or [])
        return {str(d["slug"]): d for d in datos
                if isinstance(d, dict) and d.get("slug")}
    except Exception:                                      # noqa: BLE001
        return {}


def _c21_registro(nombre: str, mercado: dict) -> dict | None:
    """
    Empata un nombre BrickBit contra el inventario C21 por slug. Prueba el
    nombre completo ('municipio-estado', separador '·' o ',') y luego solo
    la primera parte ('municipio' / ciudad ancla).
    """
    if not mercado:
        return None
    candidatos = [slugificar(nombre)]
    candidatos += [slugificar(p) for p in str(nombre).split("·") if p.strip()]
    for s in candidatos:
        if s and s in mercado:
            return mercado[s]
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def c21_lineas_municipales() -> tuple[list[str], int]:
    """
    Línea de tooltip 'Mercado vivo C21' por municipio (o '' si no hay dato)
    + cuántos municipios empatan. Empate por slug de 'Municipio, Estado' y,
    como respaldo, solo 'Municipio' (las 32 ciudades ancla usan la ciudad).
    """
    mercado = cargar_mercado_vivo()
    df = datos_municipales()
    lineas: list[str] = []
    n = 0
    for muni, edo in zip(df["municipio"], df["estado"]):
        reg = None
        if mercado:
            reg = (mercado.get(slugificar(f"{muni}, {edo}"))
                   or mercado.get(slugificar(str(muni))))
        pm2v = (reg or {}).get("pm2v")
        if reg and pm2v:
            nv = reg.get("nV") or 0
            cuenta = f"{int(nv):,} ventas · lista C21" if nv else "lista C21"
            lineas.append(
                f"<br/><span style='color:{ARCILLA_SUAVE}'>Mercado vivo "
                f"C21: <b>${float(pm2v):,.0f}/m²</b> ({cuenta}) · dato "
                "diario</span>")
            n += 1
        else:
            lineas.append("")
    return lineas, n


# ══════════════════════════════════════════════════════════════════════════════
# 4B · HELPERS PDF — ENTREGABLES CON MARCA BRICKBIT (fpdf2)
#      Documento tipo papel: fondo BLANCO, banda superior verde bosque
#      (#24664a) con "BRICKBIT" en crema (el tierra #100c0a no imprime bien),
#      tipografía Helvetica core (latin-1: acentos OK, sin emojis ni
#      em-dashes), zebra suave #f2ede4 en tablas y callout ámbar #F5C277
#      reservado a la honestidad de datos. Pie: "brickbit.co · página N".
# ══════════════════════════════════════════════════════════════════════════════

PDF_BOSQUE = (36, 102, 74)        # #24664a  banda y títulos
PDF_CREMA = (245, 237, 227)       # #f5ede3  texto sobre la banda
PDF_TINTA = (28, 24, 20)          # texto principal sobre blanco
PDF_GRIS = (110, 100, 90)         # texto secundario y pies
PDF_ZEBRA = (242, 237, 228)       # #f2ede4  filas alternas
PDF_AMBAR = (245, 194, 119)       # #F5C277  SOLO honestidad de datos
PDF_AMBAR_FONDO = (250, 243, 229)  # fondo pálido del callout
PDF_SALVIA = (111, 162, 135)      # #6fa287  reglas y acentos suaves


def _l1(texto) -> str:
    """Sanitiza cualquier texto a latin-1 (Helvetica core): á é í ó ú ñ ü ²
    sobreviven; lo que no exista en latin-1 se reemplaza con '?'."""
    return str(texto).encode("latin-1", errors="replace").decode("latin-1")


class PDFBrickBit(FPDF):
    """Documento con marca BrickBit: banda superior bosque en cada página y
    pie con 'brickbit.co · página N · fecha'."""

    def __init__(self, titulo: str = "BrickBit"):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.titulo_doc = _l1(titulo)
        self.set_title(self.titulo_doc)
        self.set_author("BrickBit")
        self.set_margins(16, 24, 16)
        self.set_auto_page_break(auto=True, margin=22)
        # sin compresión de streams: documento inspeccionable y estable
        # (los entregables pesan decenas de KB, no importa el ahorro)
        self.compress = True   # PDFs ligeros: mismo contenido, menos peso

    def header(self):
        self.set_fill_color(*PDF_BOSQUE)
        self.rect(0, 0, self.w, 13, style="F")
        self.set_xy(16, 3.5)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*PDF_CREMA)
        self.cell(60, 6, "BRICKBIT")
        self.set_font("Helvetica", "", 8)
        self.cell(self.w - 32 - 60, 6, self.titulo_doc[:72], align="R")
        self.set_y(20)
        self.set_text_color(*PDF_TINTA)

    def footer(self):
        from datetime import date as _d
        self.set_y(-16)
        self.set_draw_color(*PDF_SALVIA)
        self.set_line_width(0.3)
        self.line(16, self.get_y(), self.w - 16, self.get_y())
        self.set_y(-13)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*PDF_GRIS)
        self.cell(0, 6, _l1(f"brickbit.co · página {self.page_no()} · "
                            f"{_d.today().isoformat()}"), align="C")


def pdf_h1(pdf: PDFBrickBit, texto: str) -> None:
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*PDF_BOSQUE)
    pdf.multi_cell(0, 8, _l1(texto))
    pdf.set_draw_color(*PDF_SALVIA)
    pdf.set_line_width(0.4)
    pdf.line(pdf.l_margin, pdf.get_y() + 1,
             pdf.l_margin + 52, pdf.get_y() + 1)
    pdf.ln(5)
    pdf.set_text_color(*PDF_TINTA)


def pdf_h2(pdf: PDFBrickBit, texto: str) -> None:
    pdf.ln(1.5)
    pdf.set_font("Helvetica", "B", 11.5)
    pdf.set_text_color(*PDF_BOSQUE)
    pdf.multi_cell(0, 6.4, _l1(texto))
    pdf.ln(1)
    pdf.set_text_color(*PDF_TINTA)


def pdf_parrafo(pdf: PDFBrickBit, texto: str, tam: float = 10,
                color: tuple = PDF_TINTA, estilo: str = "") -> None:
    pdf.set_font("Helvetica", estilo, tam)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, 5.3, _l1(texto))
    pdf.ln(1.2)
    pdf.set_text_color(*PDF_TINTA)


def pdf_vineta(pdf: PDFBrickBit, texto: str, tam: float = 10) -> None:
    """Viñeta simple con '·' (latin-1) y sangría francesa."""
    pdf.set_font("Helvetica", "", tam)
    pdf.set_text_color(*PDF_TINTA)
    pdf.set_x(pdf.l_margin + 3)
    pdf.multi_cell(pdf.epw - 3, 5.3, _l1(f"·  {texto}"))
    pdf.ln(0.6)


def pdf_tabla(pdf: PDFBrickBit, df: pd.DataFrame, tam: float = 8.5,
              max_filas: int = 40) -> None:
    """Tabla sencilla de marca: encabezado bosque/crema y zebra #f2ede4.
    Trunca celdas largas para que la fila nunca se desborde."""
    if df is None or len(df) == 0:
        pdf_parrafo(pdf, "(sin datos)", color=PDF_GRIS, estilo="I")
        return
    d = df.head(max_filas).copy()
    cols = [str(c) for c in d.columns]
    celdas = [[_l1(v) for v in map(str, d[c].tolist())] for c in d.columns]
    # anchos proporcionales al contenido (acotados) sobre el ancho útil
    pesos = []
    for j, c in enumerate(cols):
        largo = max([len(c)] + [len(v) for v in celdas[j]])
        pesos.append(min(max(largo, 6), 46))
    epw = pdf.epw
    anchos = [epw * p / sum(pesos) for p in pesos]
    alto = 6.0

    def _fila(valores, fill_rgb, txt_rgb, negrita=False):
        if pdf.get_y() + alto > pdf.page_break_trigger:
            pdf.add_page()
        pdf.set_font("Helvetica", "B" if negrita else "", tam)
        pdf.set_text_color(*txt_rgb)
        if fill_rgb:
            pdf.set_fill_color(*fill_rgb)
        for w, v in zip(anchos, valores):
            tope = max(3, int(w / (0.62 * tam / 3.2)))
            txt = v if len(v) <= tope else v[:tope - 1] + "..."
            pdf.cell(w, alto, txt, border=0, fill=bool(fill_rgb))
        pdf.ln(alto)

    _fila([_l1(c) for c in cols], PDF_BOSQUE, PDF_CREMA, negrita=True)
    for i in range(len(d)):
        _fila([celdas[j][i] for j in range(len(cols))],
              PDF_ZEBRA if i % 2 else None, PDF_TINTA)
    pdf.ln(2)
    pdf.set_text_color(*PDF_TINTA)


def pdf_callout(pdf: PDFBrickBit, texto: str,
                titulo: str = "Honestidad de datos") -> None:
    """Callout ámbar de honestidad: borde izquierdo #F5C277 (el ámbar es
    intocable y SOLO marca estimaciones/alcance) sobre fondo pálido."""
    pdf.ln(2)
    cuerpo = _l1(texto)
    pdf.set_font("Helvetica", "", 9)
    alto_txt = pdf.multi_cell(pdf.epw - 8, 4.8, cuerpo, dry_run=True,
                              output="HEIGHT")
    alto_tot = alto_txt + 12
    if pdf.get_y() + alto_tot > pdf.page_break_trigger:
        pdf.add_page()
    x, y = pdf.l_margin, pdf.get_y()
    pdf.set_fill_color(*PDF_AMBAR_FONDO)
    pdf.rect(x, y, pdf.epw, alto_tot, style="F")
    pdf.set_fill_color(*PDF_AMBAR)
    pdf.rect(x, y, 1.8, alto_tot, style="F")
    pdf.set_xy(x + 5, y + 3)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*PDF_TINTA)
    pdf.cell(0, 5, _l1(titulo))
    pdf.set_xy(x + 5, y + 9)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(pdf.epw - 8, 4.8, cuerpo)
    pdf.set_y(y + alto_tot + 3)
    pdf.set_text_color(*PDF_TINTA)


def pdf_portada(pdf: PDFBrickBit, titulo: str, subtitulo: str = "",
                lineas: tuple = ()) -> None:
    """Portada: título grande bosque + subtítulo + fecha (nueva página)."""
    from datetime import date as _d
    pdf.add_page()
    pdf.set_y(56)
    pdf.set_font("Helvetica", "B", 23)
    pdf.set_text_color(*PDF_BOSQUE)
    pdf.multi_cell(0, 10.5, _l1(titulo))
    if subtitulo:
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 13)
        pdf.set_text_color(*PDF_GRIS)
        pdf.multi_cell(0, 7, _l1(subtitulo))
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*PDF_GRIS)
    pdf.cell(0, 6, _l1(f"BrickBit · Motor de Morfogénesis Urbana · "
                       f"{_d.today().isoformat()}"))
    pdf.ln(10)
    pdf.set_draw_color(*PDF_SALVIA)
    pdf.set_line_width(0.5)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 60, pdf.get_y())
    pdf.ln(8)
    pdf.set_text_color(*PDF_TINTA)
    for linea in lineas:
        pdf_vineta(pdf, linea)


def pdf_bytes(pdf: PDFBrickBit) -> bytes:
    """El documento como bytes listos para st.download_button."""
    return bytes(pdf.output())


# ══════════════════════════════════════════════════════════════════════════════
# 5 · MOTOR SAR (ESTADOS · MUNICIPIOS) + ÍNDICE DE MORAN
# ══════════════════════════════════════════════════════════════════════════════

def _sar(v0: np.ndarray, potencial: np.ndarray, g_propio: np.ndarray,
         pares_i: np.ndarray, pares_j: np.ndarray, grados: np.ndarray,
         rho: float, escala_rho: float, shock_mask: np.ndarray | None,
         shock_año: int, shock_fuerza: float) -> np.ndarray:
    """
    Núcleo del proceso espacial autorregresivo, común a todas las escalas:

        v[t+1] = v[t] · (1 + g_propio + ρ·k · (W·v_norm[t]) · potencial)

    El shock (megaproyecto/catalizador) eleva el potencial en su año de
    arranque y detona la mutación en cadena.
    """
    potencial = potencial.copy()
    valores = np.empty((AÑOS + 1, v0.size))
    valores[0] = v0
    for t in range(AÑOS):
        v = valores[t]
        if shock_mask is not None and t == shock_año:
            potencial = np.clip(potencial + shock_fuerza * shock_mask, 0, 1.35)
        derrame = np.bincount(pares_i, weights=norm01(v)[pares_j],
                              minlength=v.size) / grados
        valores[t + 1] = v * (1.0 + g_propio + rho * escala_rho
                              * derrame * potencial)
    return valores


def _shock_clic(lng: np.ndarray, lat: np.ndarray, clic: tuple | None,
                radio: float) -> np.ndarray | None:
    """
    Detonante point-and-click: el usuario hace clic en cualquier célula del
    mapa y el motor inyecta ahí una célula madre (shock gaussiano en año 1).
    SimCity al revés: pon tu hipótesis y mira la onda expansiva.
    """
    if clic is None:
        return None
    return np.exp(-((lng - clic[0]) ** 2 + (lat - clic[1]) ** 2)
                  / (2 * radio ** 2))


def _args_nacion(rho: float, megaproyecto: str, clic: tuple = None) -> dict:
    """Argumentos del núcleo SAR para la escala estados."""
    df = datos_estatales()
    pi, pj, g = vecindad_estados()
    mega = MEGAPROYECTOS.get(megaproyecto)
    mask = df["estado"].isin(mega["estados"]).to_numpy().astype(float) \
        if mega else None
    m_clic = _shock_clic(df["lng"].to_numpy(), df["lat"].to_numpy(), clic, 1.2)
    if m_clic is not None:
        mask, mega = m_clic, dict(año=1, fuerza=0.6)
    return dict(v0=df["precio_m2"].to_numpy(dtype=float),
                potencial=df["potencial"].to_numpy(dtype=float),
                g_propio=df["plusvalia"].to_numpy(dtype=float) / 100.0 * 0.55,
                pares_i=pi, pares_j=pj, grados=g, rho=rho, escala_rho=0.10,
                shock_mask=mask, shock_año=mega["año"] if mega else 0,
                shock_fuerza=mega["fuerza"] if mega else 0)


@st.cache_data(show_spinner="🧬 Simulando morfogénesis estatal (SAR, max_entries=8)…")
def simular_nacion(rho: float, megaproyecto: str,
                   clic: tuple = None) -> np.ndarray:
    """SAR sobre la contigüidad real de los 32 estados."""
    return _sar(**_args_nacion(rho, megaproyecto, clic))


def _args_municipios(rho: float, megaproyecto: str, clic: tuple = None) -> dict:
    """Argumentos del núcleo SAR para la escala municipios."""
    df = datos_municipales()
    pi, pj, g = vecindad_municipios()
    mega = MEGAPROYECTOS.get(megaproyecto)
    mask = df["estado"].isin(mega["estados"]).to_numpy().astype(float) \
        if mega else None
    m_clic = _shock_clic(df["lng"].to_numpy(), df["lat"].to_numpy(), clic, 0.30)
    if m_clic is not None:
        mask, mega = m_clic, dict(año=1, fuerza=0.65)
    return dict(v0=df["precio_actual"].to_numpy(dtype=float),
                potencial=df["potencial_crecimiento"].to_numpy(dtype=float),
                g_propio=df["plusvalia_estatal"].to_numpy(dtype=float)
                / 100.0 * 0.45,
                pares_i=pi, pares_j=pj, grados=g, rho=rho, escala_rho=0.14,
                shock_mask=mask, shock_año=mega["año"] if mega else 0,
                shock_fuerza=(mega["fuerza"] * 0.9) if mega else 0)


@st.cache_data(show_spinner="🧬 Simulando morfogénesis municipal (2,436 células, max_entries=8)…")
def simular_municipios(rho: float, megaproyecto: str,
                       clic: tuple = None) -> np.ndarray:
    """
    SAR sobre las ~15,000 fronteras municipales reales: la plusvalía se
    contagia municipio a municipio, como células de un mismo tejido.
    """
    return _sar(**_args_municipios(rho, megaproyecto, clic))


def indice_moran(v: np.ndarray, pares: tuple) -> float:
    """
    Índice de Moran I: el electrocardiograma espacial del mercado. Mide si el
    organismo crece cohesionado (I→1, valores altos junto a altos) o
    fragmentado (I≈0).
    """
    pi, pj, _ = pares
    z = v - v.mean()
    return (len(v) / len(pi)) * float((z[pi] * z[pj]).sum()) \
        / float((z ** 2).sum() + 1e-12)


# ══════════════════════════════════════════════════════════════════════════════
# 6 · SISTEMA CIRCULATORIO — CAPITAL ENTRE ZONAS METROPOLITANAS
# ══════════════════════════════════════════════════════════════════════════════

def flujos_nacionales(valores: np.ndarray, año: float,
                      n_fuentes: int = 6, n_destinos: int = 20) -> pd.DataFrame:
    """
    Modelo gravitacional de rotación de capital: las ZM con mayor masa
    económica bombean liquidez hacia los estados de mayor crecimiento
    proyectado. atracción = masa_fuente / distancia^1.2.
    """
    df_e = datos_estatales()
    v_t, tasa = estado_en(valores, año)
    ratio = v_t / valores[0]

    df_c = pd.DataFrame(CIUDADES, columns=[
        "ciudad", "estado", "lat", "lng", "precio_m2",
        "plusvalia", "yld", "pob_zm"])
    idx_e = {e: i for i, e in enumerate(df_e["estado"])}
    ie = df_c["estado"].map(idx_e).to_numpy()
    precio_t = df_c["precio_m2"].to_numpy() * ratio[ie]
    tasa_c = tasa[ie]
    masa = df_c["pob_zm"].to_numpy() * precio_t

    fuentes = np.argsort(masa)[-n_fuentes:]
    destinos = [c for c in np.argsort(tasa_c)[::-1]
                if c not in set(fuentes)][:n_destinos]

    lng, lat = df_c["lng"].to_numpy(), df_c["lat"].to_numpy()
    filas = []
    for k, d in enumerate(destinos):
        dist = np.hypot(lng[fuentes] - lng[d], lat[fuentes] - lat[d])
        f = fuentes[int(np.argmax(masa[fuentes] / (dist + 0.1) ** 1.2))]
        capital = tasa_c[d] * precio_t[d] * df_c["pob_zm"].iloc[d] * 9 / 1000
        filas.append({
            "origen": [float(lng[f]), float(lat[f])],
            "destino": [float(lng[d]), float(lat[d])],
            "ciudad_origen": df_c["ciudad"].iloc[f],
            "ciudad_destino": df_c["ciudad"].iloc[d],
            "intensidad": float(tasa_c[d] / (tasa_c.max() + 1e-9)),
            "capital_mmd": float(capital),          # mil millones MXN/año
            "desfase": (k * 0.11) % 1.0,
        })
    return pd.DataFrame(filas)


def construir_trayectos(flujos: pd.DataFrame) -> list[dict]:
    """Arcos → trayectos curvos con timestamps (los glóbulos del TripsLayer)."""
    trayectos = []
    for _, fl in flujos.iterrows():
        (x0, y0), (x1, y1) = fl["origen"], fl["destino"]
        px, py = -(y1 - y0), (x1 - x0)      # perpendicular → curva suave
        s = np.linspace(0.0, 1.0, 16)
        arco = np.sin(s * math.pi) * 0.16
        camino = [[float(x0 + (x1 - x0) * u + px * a),
                   float(y0 + (y1 - y0) * u + py * a)] for u, a in zip(s, arco)]
        marcas = (fl["desfase"] + s * 0.55).tolist()
        trayectos.append({"camino": camino, "marcas": marcas,
                          "intensidad": float(fl["intensidad"])})
    return trayectos


def torres_metropolitanas(valores: np.ndarray, año: float) -> pd.DataFrame:
    """Las 32 ZM como torres de energía: altura = precio, color = contagio."""
    df_e = datos_estatales()
    v_t, tasa = estado_en(valores, año)
    ratio = v_t / valores[0]

    df_c = pd.DataFrame(CIUDADES, columns=[
        "ciudad", "estado", "lat", "lng", "precio_m2",
        "plusvalia", "yld", "pob_zm"])
    idx_e = {e: i for i, e in enumerate(df_e["estado"])}
    ie = df_c["estado"].map(idx_e).to_numpy()
    precio_t = df_c["precio_m2"].to_numpy() * ratio[ie]
    tasa_c = tasa[ie]

    rgb = paleta_marca(norm01(tasa_c) ** 0.8)
    return pd.DataFrame({
        "pos": [[float(a), float(b)] for a, b in zip(df_c["lng"], df_c["lat"])],
        "nombre": df_c["ciudad"],
        "altura": (precio_t * 5.5).tolist(),
        "color": np.column_stack([rgb, np.full(len(df_c), 215)])
                   .astype(int).tolist(),
        "masa": (df_c["pob_zm"].to_numpy() * precio_t).tolist(),
        "estado_bio": "",
        "precio_txt": [f"${p:,.0f} MXN/m²" for p in precio_t],
        "crec_txt": [f"+{r * 100:.1f}% anual" for r in tasa_c],
        "plusvalia_txt": [f"+{(r - 1) * 100:.0f}% vs hoy" for r in ratio[ie]],
        "extra_txt": [f"ZM {p:.1f}M hab · yield {y:.1f}%"
                      for p, y in zip(df_c["pob_zm"], df_c["yld"])],
    })


# ══════════════════════════════════════════════════════════════════════════════
# 7 · RENDER PYDECK — CAPAS DEL ORGANISMO EN LOS COLORES BRICKBIT
# ══════════════════════════════════════════════════════════════════════════════

def _capas_circulatorias(flujos: pd.DataFrame, fase: float,
                         escala: float = 1.0) -> list[pdk.Layer]:
    """Venas (arcos), glóbulos (trips) y corazones (glow), en verdes/lima."""
    pulso = 0.5 + 0.5 * math.sin(2 * math.pi * fase)
    nodos = pd.DataFrame({"pos": flujos["origen"]
                         .apply(tuple).drop_duplicates().apply(list).tolist()})
    return [
        pdk.Layer(
            "ArcLayer", data=flujos,
            get_source_position="origen", get_target_position="destino",
            get_source_color=RGB_ARCILLA_SUAVE + [int(80 + 120 * pulso)],
            get_target_color=RGB_LIMA + [int(140 + 110 * pulso)],
            get_width=f"1.5 + intensidad * {3.0 + 3.0 * pulso}",
            get_height=0.35, great_circle=False,
        ),
        pdk.Layer(
            "TripsLayer", data=construir_trayectos(flujos),
            get_path="camino", get_timestamps="marcas",
            get_color=[245, 237, 227], width_min_pixels=3,
            trail_length=0.30, current_time=(fase * 2.0) % 2.0, opacity=0.9,
        ),
        pdk.Layer(
            "ScatterplotLayer", data=nodos, get_position="pos",
            get_radius=(26000 + 16000 * pulso) * escala,
            get_fill_color=RGB_LIMA + [int(40 + 55 * pulso)],
            stroked=True,
            get_line_color=RGB_CREMA + [int(110 + 90 * pulso)],
            line_width_min_pixels=2,
        ),
    ]


def _tooltip() -> dict:
    """Tooltip de marca: superficie tierra, borde lima, texto crema."""
    return {
        "html": (
            "<div style='font-family:Space Mono,monospace'>"
            f"<b style='color:{LIMA}'>{{nombre}}</b> {{estado_bio}}<br/>"
            "💰 <b>{precio_txt}</b><br/>"
            f"🧬 Contagio: <b style='color:{ARCILLA_SUAVE}'>{{crec_txt}}</b> · "
            "📈 {plusvalia_txt}<br/>"
            f"<span style='color:{TEXTO_SUAVE}'>{{extra_txt}}</span></div>"
        ),
        "style": {"backgroundColor": SUPERFICIE, "color": CREMA,
                  "border": f"1px solid {LIMA}", "borderRadius": "8px"},
    }


def _vista(lng, lat, zoom, pitch=46, bearing=-8):
    return pdk.ViewState(longitude=lng, latitude=lat, zoom=zoom,
                         pitch=pitch, bearing=bearing)


def _respiracion(t: np.ndarray, fase: float) -> np.ndarray:
    """Latido de opacidad: las zonas calientes respiran más fuerte."""
    return 0.88 + 0.12 * np.sin(2 * math.pi * (fase + t * 2.0))


def capa_frente_onda(contornos: pd.DataFrame, idx_col: str,
                     frente: np.ndarray) -> pdk.Layer:
    """
    🌊 Frente de onda (LISA Low-High): contorno crema brillante sobre las
    células baratas rodeadas de caras — donde la ola va a romper.
    """
    marcadas = contornos[contornos[idx_col].map(
        lambda i: bool(frente[int(i)]))]
    return pdk.Layer(
        "PolygonLayer", data=marcadas, get_polygon="contorno",
        filled=False, stroked=True, get_line_color=RGB_CREMA + [235],
        line_width_min_pixels=2.2, pickable=False,
    )


def preparar_estados_render(valores: np.ndarray, año: float,
                            fase: float) -> pd.DataFrame:
    """Color/latido de cada estado: valor proyectado + plusvalía acumulada."""
    df = datos_estatales()
    v_t, tasa = estado_en(valores, año)
    acum = v_t / valores[0] - 1
    t = 0.45 * norm01(v_t) + 0.55 * norm01(acum)
    rgb = paleta_marca(t ** 0.85)
    alfa = np.clip((80 + 130 * t) * _respiracion(t, fase), 45, 235)
    base = pd.DataFrame({
        "nombre": df["estado"],
        "lng": df["lng"], "lat": df["lat"],
        "color": np.column_stack([rgb, alfa]).astype(int).tolist(),
        "estado_bio": clasificar_bio(tasa),
        "precio_txt": [f"${p:,.0f} MXN/m²" for p in v_t],
        "crec_txt": [f"+{r * 100:.1f}% anual" for r in tasa],
        "plusvalia_txt": [f"+{a * 100:.0f}% vs hoy" for a in acum],
        "extra_txt": [f"👥 {p:.2f}M hab · PIB pc ${g:.0f}k · potencial {q:.2f}"
                      for p, g, q in zip(df["poblacion"], df["pib_pc"],
                                         df["potencial"])],
    })
    return contornos_estatales().join(base, on="idx_estado")


def preparar_municipios_render(valores: np.ndarray, año: float,
                               fase: float) -> pd.DataFrame:
    """Color/latido de las 2,436 células municipales."""
    df = datos_municipales()
    v_t, tasa = estado_en(valores, año)
    acum = v_t / valores[0] - 1
    t = 0.40 * norm01(v_t) + 0.60 * norm01(acum)
    rgb = paleta_marca(t ** 0.9)
    alfa = np.clip((70 + 145 * t) * _respiracion(t, fase), 40, 235)
    base = pd.DataFrame({
        "nombre": df["municipio"] + " · " + df["estado"],
        "lng": df["lng"], "lat": df["lat"],
        "color": np.column_stack([rgb, alfa]).astype(int).tolist(),
        "estado_bio": clasificar_bio(tasa),
        "precio_txt": [f"${p:,.0f} MXN/m²" for p in v_t],
        "crec_txt": [f"+{r * 100:.1f}% anual" for r in tasa],
        "plusvalia_txt": [f"+{a * 100:.0f}% vs hoy" for a in acum],
        "extra_txt": [
            (f"🏪 {int(n):,} negocios · {int(e):,} empleos (DENUE) · "
             f"resiliencia {r:.2f}" if n > 0 else
             f"ZM más cercana: {z} ({d:.0f} km) · potencial {q:.2f}") + c21
            for n, e, r, z, d, q, c21 in zip(
                df["n_estab"], df["empleo"], df["resiliencia"],
                df["zm_cercana"], df["dist_zm_km"],
                df["potencial_crecimiento"],
                c21_lineas_municipales()[0])],
    })
    return contornos_municipales().join(base, on="idx_mun")


def capa_bordes_estatales() -> pdk.Layer:
    """Delimitación estatal superpuesta (estilo Google Maps), en crema."""
    return pdk.Layer(
        "PolygonLayer", data=contornos_estatales(),
        get_polygon="contorno", filled=False, stroked=True,
        get_line_color=RGB_CREMA + [130], line_width_min_pixels=1.6,
        pickable=False,
    )


def construir_deck_nacion(valores: np.ndarray, año: float, fase: float,
                          mostrar_flujos: bool, mostrar_torres: bool,
                          mostrar_etiquetas: bool,
                          flujos: pd.DataFrame) -> pdk.Deck:
    """Escala estados: piel estatal + órganos ZM + sangre de capital."""
    capas = [pdk.Layer(
        "PolygonLayer", id="celulas",
        data=preparar_estados_render(valores, año, fase),
        get_polygon="contorno", get_fill_color="color",
        get_line_color=RGB_ARCILLA_SUAVE + [110], line_width_min_pixels=1,
        stroked=True, pickable=True, auto_highlight=True,
        highlight_color=RGB_CREMA + [90],
    )]
    torres = torres_metropolitanas(valores, año)
    if mostrar_torres:
        capas.append(pdk.Layer(
            "ColumnLayer", data=torres, get_position="pos",
            get_elevation="altura", get_fill_color="color",
            radius=16000, pickable=True, auto_highlight=True,
        ))
    if mostrar_flujos:
        capas += _capas_circulatorias(flujos, fase)
    if mostrar_etiquetas:
        capas.append(pdk.Layer(
            "TextLayer", data=torres.nlargest(14, "masa"),
            get_position="pos", get_text="nombre", get_size=13,
            get_color=RGB_CREMA + [210],
            get_alignment_baseline="'top'", get_pixel_offset=[0, 10],
        ))
    return pdk.Deck(layers=capas,
                    initial_view_state=_vista(-102.4, 23.9, 4.4),
                    map_style=ESTILO_MAPA, tooltip=_tooltip())


def construir_deck_municipios(valores: np.ndarray, año: float, fase: float,
                              mostrar_flujos: bool, mostrar_torres: bool,
                              mostrar_etiquetas: bool,
                              flujos: pd.DataFrame,
                              valores_edo: np.ndarray,
                              mostrar_lisa: bool = False) -> pdk.Deck:
    """
    Escala municipios: 2,436 células reales + delimitación estatal encima
    (como Google Maps) + el mismo sistema circulatorio metropolitano.
    """
    capas = [
        pdk.Layer(
            "PolygonLayer", id="celulas",
            data=preparar_municipios_render(valores, año, fase),
            get_polygon="contorno", get_fill_color="color",
            get_line_color=RGB_LIMA + [22], line_width_min_pixels=0.5,
            stroked=True, pickable=True, auto_highlight=True,
            highlight_color=RGB_CREMA + [110],
        ),
        capa_bordes_estatales(),
    ]
    if mostrar_lisa:
        v_t, _ = estado_en(valores, año)
        capas.append(capa_frente_onda(contornos_municipales(), "idx_mun",
                                      frente_de_onda(v_t, vecindad_municipios())))
    torres = torres_metropolitanas(valores_edo, año)
    if mostrar_torres:
        capas.append(pdk.Layer(
            "ColumnLayer", data=torres, get_position="pos",
            get_elevation="altura", get_fill_color="color",
            radius=12000, pickable=True, auto_highlight=True,
        ))
    if mostrar_flujos:
        capas += _capas_circulatorias(flujos, fase)
    if mostrar_etiquetas:
        capas.append(pdk.Layer(
            "TextLayer", data=torres.nlargest(14, "masa"),
            get_position="pos", get_text="nombre", get_size=13,
            get_color=RGB_CREMA + [210],
            get_alignment_baseline="'top'", get_pixel_offset=[0, 10],
        ))
    return pdk.Deck(layers=capas,
                    initial_view_state=_vista(-102.4, 23.9, 4.6, pitch=42),
                    map_style=ESTILO_MAPA, tooltip=_tooltip())


# ══════════════════════════════════════════════════════════════════════════════
# 8 · ESCALA MICRO — TEJIDO CELULAR AZCAPOTZALCO/VALLEJO (motor original)
# ══════════════════════════════════════════════════════════════════════════════

NX, NY = 26, 26
CENTRO_LNG, CENTRO_LAT = -99.186, 19.482
PASO_LNG, PASO_LAT = 0.00245, 0.00228
FACTOR_MANZANA = 0.80

BARRIOS = [
    "El Rosario", "San Martín Xochinahuac", "Santa Bárbara",
    "Vallejo Industrial", "Clavería", "Ángel Zimbrón",
    "San Álvaro", "Nueva Santa María", "Santo Tomás",
]

CATALIZADORES = {
    "— Sin catalizador —": None,
    "Nueva línea de Metro (norte)": dict(lng=-99.192, lat=19.497, año=2, fuerza=0.85, radio=0.011),
    "Centro comercial (poniente)": dict(lng=-99.203, lat=19.478, año=3, fuerza=0.70, radio=0.009),
    "Parque lineal Vallejo (centro)": dict(lng=-99.184, lat=19.486, año=1, fuerza=0.55, radio=0.013),
    # catalizadores a escala ZMVM (alcance metropolitano del microtejido)
    "AIFA + Tren Suburbano (norte ZMVM)": dict(lng=-99.02, lat=19.69, año=1, fuerza=0.90, radio=0.055),
    "Mexibús Ecatepec (oriente ZMVM)": dict(lng=-99.05, lat=19.60, año=2, fuerza=0.65, radio=0.040),
    "Corredor Interlomas (poniente ZMVM)": dict(lng=-99.28, lat=19.40, año=2, fuerza=0.70, radio=0.035),
}

# ── semillas del tejido ZMVM: (nombre, lng, lat, peso_precio $/m², sigma) ──
_SEMILLAS_ZMVM = [
    ("Polanco · M. Hidalgo",   -99.19, 19.435, 27000, 0.030),
    ("Centro · Cuauhtémoc",    -99.14, 19.432, 17000, 0.028),
    ("Santa Fe · A. Obregón",  -99.26, 19.36,  20000, 0.026),
    ("Coyoacán",               -99.16, 19.35,  13000, 0.028),
    ("GAM · Basílica",         -99.11, 19.49,   6500, 0.026),
    ("Iztapalapa",             -99.06, 19.355,  3800, 0.030),
    ("Naucalpan",              -99.24, 19.475,  8000, 0.026),
    ("Tlalnepantla",           -99.195, 19.54,  6800, 0.026),
    ("Atizapán",               -99.26, 19.56,   6600, 0.024),
    ("Cuautitlán Izcalli",     -99.245, 19.645, 5800, 0.026),
    ("Ecatepec",               -99.06, 19.60,   3600, 0.032),
    ("Nezahualcóyotl",         -99.03, 19.40,   4200, 0.028),
    ("Chimalhuacán",           -98.955, 19.42,  2800, 0.024),
    ("Coacalco",               -99.11, 19.63,   4600, 0.022),
    ("Huixquilucan · Interlomas", -99.29, 19.395, 18000, 0.022),
    ("Tecámac · AIFA",         -98.99, 19.66,   4200, 0.030),
]
# focos de POTENCIAL en la ZMVM: corredores donde el crecimiento despierta
_EMERGENTES_ZMVM = [(-99.00, 19.69, 0.85, 0.045),   # AIFA / Suburbano
                    (-99.06, 19.60, 0.55, 0.035),   # Ecatepec
                    (-99.245, 19.645, 0.55, 0.030), # C. Izcalli
                    (-99.03, 19.40, 0.50, 0.030),   # Neza
                    (-98.955, 19.42, 0.45, 0.026),  # Chimalhuacán
                    (-99.26, 19.36, 0.35, 0.024),   # Santa Fe
                    (-99.11, 19.49, 0.35, 0.024)]   # GAM

# ── Unidades del microtejido: 16 alcaldías CDMX + 10 municipios Edomex ──────
# Tejido SIMULADO calibrado con las semillas reales de _SEMILLAS_ZMVM.
# centro = (lng, lat) geográfico aproximado; medio_* = semiancho del bbox en
# grados (alcaldías chicas ±0.03°, grandes ±0.06°, municipios ±0.05°).
def _u(nombre, zona, lng, lat, m_lng, m_lat):
    return {"nombre": nombre, "zona": zona, "centro": (lng, lat),
            "medio_lng": m_lng, "medio_lat": m_lat}


UNIDADES_MICRO = {
    # CDMX — 16 alcaldías
    "alvaro_obregon": _u("Álvaro Obregón", "CDMX", -99.235, 19.345, 0.045, 0.055),
    "azcapotzalco": _u("Azcapotzalco", "CDMX", CENTRO_LNG, CENTRO_LAT,
                       NX / 2 * PASO_LNG, NY / 2 * PASO_LAT),
    "benito_juarez": _u("Benito Juárez", "CDMX", -99.16, 19.385, 0.030, 0.030),
    "coyoacan": _u("Coyoacán", "CDMX", -99.15, 19.33, 0.040, 0.035),
    "cuajimalpa": _u("Cuajimalpa", "CDMX", -99.30, 19.355, 0.045, 0.045),
    "cuauhtemoc": _u("Cuauhtémoc", "CDMX", -99.145, 19.43, 0.030, 0.030),
    "gustavo_a_madero": _u("Gustavo A. Madero", "CDMX", -99.11, 19.51, 0.060, 0.055),
    "iztacalco": _u("Iztacalco", "CDMX", -99.095, 19.395, 0.030, 0.026),
    "iztapalapa": _u("Iztapalapa", "CDMX", -99.055, 19.345, 0.060, 0.050),
    "magdalena_contreras": _u("M. Contreras", "CDMX", -99.245, 19.29, 0.038, 0.040),
    "miguel_hidalgo": _u("Miguel Hidalgo", "CDMX", -99.20, 19.43, 0.040, 0.035),
    "milpa_alta": _u("Milpa Alta", "CDMX", -99.02, 19.13, 0.060, 0.055),
    "tlahuac": _u("Tláhuac", "CDMX", -99.00, 19.27, 0.050, 0.040),
    "tlalpan": _u("Tlalpan", "CDMX", -99.185, 19.24, 0.060, 0.060),
    "venustiano_carranza": _u("Venustiano Carranza", "CDMX", -99.095, 19.43, 0.032, 0.028),
    "xochimilco": _u("Xochimilco", "CDMX", -99.10, 19.245, 0.050, 0.040),
    # Edomex — 10 municipios metropolitanos clave
    "ecatepec": _u("Ecatepec", "Edomex", -99.06, 19.60, 0.050, 0.050),
    "naucalpan": _u("Naucalpan", "Edomex", -99.24, 19.475, 0.050, 0.045),
    "tlalnepantla": _u("Tlalnepantla", "Edomex", -99.195, 19.54, 0.050, 0.045),
    "nezahualcoyotl": _u("Nezahualcóyotl", "Edomex", -99.03, 19.40, 0.040, 0.038),
    "cuautitlan_izcalli": _u("Cuautitlán Izcalli", "Edomex", -99.245, 19.645, 0.050, 0.048),
    "huixquilucan": _u("Huixquilucan", "Edomex", -99.29, 19.395, 0.050, 0.042),
    "atizapan": _u("Atizapán", "Edomex", -99.26, 19.56, 0.050, 0.040),
    "tecamac": _u("Tecámac", "Edomex", -98.99, 19.66, 0.050, 0.050),
    "chimalhuacan": _u("Chimalhuacán", "Edomex", -98.955, 19.42, 0.040, 0.036),
    "coacalco": _u("Coacalco", "Edomex", -99.11, 19.63, 0.035, 0.030),
}


def _dims_micro(alcance: str) -> tuple[int, int, float, float, float, float]:
    """(NX, NY, centro_lng, centro_lat, paso_lng, paso_lat) por alcance."""
    if alcance == "zmvm":
        # ZMVM: CDMX + municipios clave del Edomex (Ecatepec, Naucalpan,
        # Tlalnepantla, Neza, C. Izcalli, Huixquilucan, Tecámac/AIFA…)
        nx, ny = 48, 48
        lng_min, lng_max = -99.38, -98.92
        lat_min, lat_max = 19.22, 19.74
        return (nx, ny, (lng_min + lng_max) / 2, (lat_min + lat_max) / 2,
                (lng_max - lng_min) / nx, (lat_max - lat_min) / ny)
    u = UNIDADES_MICRO.get(alcance)
    if u is not None:
        # grid FINO estilo Azcapotzalco (26×26) centrado en el bbox de la
        # unidad; el paso escala con su semiancho real
        nx, ny = NX, NY
        return (nx, ny, u["centro"][0], u["centro"][1],
                2 * u["medio_lng"] / nx, 2 * u["medio_lat"] / ny)
    return NX, NY, CENTRO_LNG, CENTRO_LAT, PASO_LNG, PASO_LAT


@st.cache_data(show_spinner="🧫 Cultivando tejido urbano…", max_entries=8)
def generar_tejido_urbano(alcance: str = "azcapotzalco") -> gpd.GeoDataFrame:
    """GeoDataFrame de manzanas simuladas con precio, potencial y flujo.
    alcance='azcapotzalco' (676 manzanas finas, modelo original), 'zmvm'
    (2,304 células metropolitanas) o cualquier clave de UNIDADES_MICRO
    (grid fino 26×26 con el modelo ZMVM + corazón local propio)."""
    rng = np.random.default_rng(SEMILLA)
    nx, ny, c_lng, c_lat, p_lng, p_lat = _dims_micro(alcance)
    ix, iy = np.meshgrid(np.arange(nx), np.arange(ny))
    ix, iy = ix.ravel(), iy.ravel()
    lng0 = c_lng + (ix - nx / 2) * p_lng
    lat0 = c_lat + (iy - ny / 2) * p_lat
    m_lng = p_lng * (1 - FACTOR_MANZANA) / 2
    m_lat = p_lat * (1 - FACTOR_MANZANA) / 2
    geometrias = [box(x + m_lng, y + m_lat,
                      x + p_lng - m_lng, y + p_lat - m_lat)
                  for x, y in zip(lng0, lat0)]
    cx, cy = lng0 + p_lng / 2, lat0 + p_lat / 2

    def nucleo(lng, lat, sigma):
        return np.exp(-((cx - lng) ** 2 + (cy - lat) ** 2) / (2 * sigma ** 2))

    es_unidad = alcance in UNIDADES_MICRO and alcance != "azcapotzalco"
    if alcance == "zmvm" or es_unidad:
        precio = np.full(cx.size, 5200.0)
        for _, sl, st_, peso, sig in _SEMILLAS_ZMVM:
            precio += peso * nucleo(sl, st_, sig)
        potencial = rng.uniform(0.04, 0.18, precio.size)
        for el, et, peso, sig in _EMERGENTES_ZMVM:
            potencial += peso * nucleo(el, et, sig)
        if es_unidad:
            # corazón local SUAVE en el centro de la unidad: mismo modelo
            # ZMVM (semillas reales) pero con núcleo propio para que el
            # tejido de cada alcaldía/municipio tenga vida centrípeta
            u = UNIDADES_MICRO[alcance]
            sig_u = 0.45 * max(u["medio_lng"], u["medio_lat"])
            n_u = nucleo(u["centro"][0], u["centro"][1], sig_u)
            precio += 2500.0 * n_u
            potencial += 0.25 * n_u
        precio *= rng.lognormal(0.0, 0.12, precio.size)
        potencial = np.clip(potencial, 0, 1)
        if es_unidad:
            # dentro de una unidad, cada célula se nombra por su cuadrante
            u = UNIDADES_MICRO[alcance]
            dx = np.where(cx < u["centro"][0], "Pte", "Ote")
            dy = np.where(cy < u["centro"][1], "Sur", "Nte")
            barrios = [f"{u['nombre']} · {a}-{b}" for a, b in zip(dy, dx)]
        else:
            # cada célula toma el nombre de su semilla municipal más cercana
            sx = np.array([s[1] for s in _SEMILLAS_ZMVM])
            sy = np.array([s[2] for s in _SEMILLAS_ZMVM])
            cerca = np.argmin((cx[:, None] - sx) ** 2
                              + (cy[:, None] - sy) ** 2, axis=1)
            barrios = [_SEMILLAS_ZMVM[int(i)][0] for i in cerca]
    else:
        precio = (13500 + 14000 * nucleo(-99.176, 19.470, 0.010)
                  + 9000 * nucleo(-99.170, 19.492, 0.008)
                  + 5500 * nucleo(-99.200, 19.472, 0.007))
        precio *= rng.lognormal(0.0, 0.10, precio.size)
        potencial = np.clip(0.90 * nucleo(-99.186, 19.489, 0.011)
                            + 0.65 * nucleo(-99.199, 19.494, 0.009)
                            + 0.40 * nucleo(-99.174, 19.478, 0.010)
                            + rng.uniform(0.05, 0.22, precio.size), 0, 1)
        qx, qy = np.minimum(ix * 3 // nx, 2), np.minimum(iy * 3 // ny, 2)
        barrios = [BARRIOS[int(b)] for b in (qy * 3 + qx)]

    gdf = gpd.GeoDataFrame({
        "barrio": barrios,
        "precio_actual": precio.round(0),
        "potencial_crecimiento": potencial.round(3),
        "lng": cx, "lat": cy,
    }, geometry=geometrias, crs="EPSG:4326")
    gdf["contorno"] = gdf.geometry.apply(
        lambda g: [list(map(list, g.exterior.coords))])
    return gdf


@st.cache_data(max_entries=8)
def vecindad_reina(alcance: str = "azcapotzalco"
                   ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Contigüidad reina de la retícula micro: la W del SAR celular."""
    gx, gy = _dims_micro(alcance)[:2]
    pares_i, pares_j = [], []
    for y in range(gy):
        for x in range(gx):
            i = y * gx + x
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx_, ny_ = x + dx, y + dy
                    if 0 <= nx_ < gx and 0 <= ny_ < gy:
                        pares_i.append(i)
                        pares_j.append(ny_ * gx + nx_)
    pares_i, pares_j = np.asarray(pares_i), np.asarray(pares_j)
    grados = np.bincount(pares_i, minlength=gx * gy).astype(float)
    return pares_i, pares_j, grados


@st.cache_data(show_spinner="🧬 Simulando morfogénesis celular…", max_entries=16)
def simular_micro(rho: float, catalizador: str,
                  alcance: str = "azcapotzalco") -> np.ndarray:
    """SAR celular con catalizador gaussiano (célula madre puntual)."""
    gdf = generar_tejido_urbano(alcance)
    pi, pj, g = vecindad_reina(alcance)
    cx, cy = gdf["lng"].to_numpy(), gdf["lat"].to_numpy()
    cat = CATALIZADORES.get(catalizador)
    mask = None
    if cat is not None:
        mask = np.exp(-((cx - cat["lng"]) ** 2 + (cy - cat["lat"]) ** 2)
                      / (2 * cat["radio"] ** 2))
    return _sar(gdf["precio_actual"].to_numpy(dtype=float),
                gdf["potencial_crecimiento"].to_numpy(dtype=float),
                np.full(len(gdf), CRECIMIENTO_BASE),
                pi, pj, g, rho, 0.16, mask,
                cat["año"] if cat else 0, cat["fuerza"] if cat else 0)


def flujos_micro(gdf: gpd.GeoDataFrame, valores: np.ndarray,
                 año: float) -> pd.DataFrame:
    """Capital intraurbano: corazones → células emergentes (gravitacional)."""
    precio_t, tasa = estado_en(valores, año)
    cx, cy = gdf["lng"].to_numpy(), gdf["lat"].to_numpy()
    fuentes = np.argsort(precio_t)[-6:]
    destinos = [c for c in np.argsort(tasa)[::-1]
                if c not in set(fuentes)][:22]
    filas = []
    for k, d in enumerate(destinos):
        dist = np.hypot(cx[fuentes] - cx[d], cy[fuentes] - cy[d])
        f = fuentes[int(np.argmax(precio_t[fuentes] / (dist + 1e-4)))]
        filas.append({"origen": [float(cx[f]), float(cy[f])],
                      "destino": [float(cx[d]), float(cy[d])],
                      "intensidad": float(tasa[d] / (tasa.max() + 1e-9)),
                      "desfase": (k * 0.13) % 1.0})
    return pd.DataFrame(filas)


def preparar_celulas(gdf: gpd.GeoDataFrame, valores: np.ndarray, año: float,
                     fase: float, extrusion: bool) -> pd.DataFrame:
    """Color, latido y altura de cada célula del microtejido."""
    precio_t, tasa = estado_en(valores, año)
    base = valores[0]
    t = np.clip((precio_t - base.min())
                / (valores[-1].max() - base.min()), 0, 1)
    rgb = paleta_marca(t ** 0.85)
    alfa = (95 + 150 * t) * (0.75 + 0.5 * norm01(tasa)) * _respiracion(t, fase)
    return pd.DataFrame({
        "contorno": gdf["contorno"].tolist(),
        "color": np.column_stack([rgb, np.clip(alfa, 30, 255)])
                   .astype(int).tolist(),
        "altura": ((t ** 1.5) * 900 * (1.0 if extrusion else 0.0)).tolist(),
        "nombre": gdf["barrio"].tolist(),
        "estado_bio": clasificar_bio(tasa).tolist(),
        "precio_txt": [f"${p:,.0f} MXN/m²" for p in precio_t],
        "crec_txt": [f"+{r * 100:.1f}% anual" for r in tasa],
        "plusvalia_txt": [f"+{(pt / b - 1) * 100:.0f}% vs hoy"
                          for pt, b in zip(precio_t, base)],
        "extra_txt": "",
    })


def construir_deck_micro(gdf: gpd.GeoDataFrame, valores: np.ndarray,
                         año: float, fase: float, mostrar_flujos: bool,
                         extrusion: bool) -> pdk.Deck:
    """El microtejido celular completo (motor original de morfogénesis)."""
    capas = [pdk.Layer(
        "PolygonLayer",
        data=preparar_celulas(gdf, valores, año, fase, extrusion),
        get_polygon="contorno", get_fill_color="color",
        get_elevation="altura", extruded=extrusion,
        get_line_color=RGB_ARCILLA_SUAVE + [40], line_width_min_pixels=1,
        pickable=True, auto_highlight=True,
        highlight_color=RGB_CREMA + [120],
    )]
    if mostrar_flujos:
        capas += _capas_circulatorias(flujos_micro(gdf, valores, año),
                                      fase, escala=0.006)
    # vista adaptada al tamaño del tejido (fino por unidad o ZMVM completa):
    # zoom continuo — a doble de extensión, un nivel menos de zoom
    lng_span = float(gdf["lng"].max() - gdf["lng"].min())
    es_zmvm = lng_span > 0.1
    zoom = float(np.clip(13.1 + math.log2(0.0637 / max(lng_span, 1e-6)),
                         9.6, 13.5))
    vista = _vista(float(gdf["lng"].mean()), float(gdf["lat"].mean()), zoom,
                   pitch=48 if es_zmvm else 52,
                   bearing=-10 if es_zmvm else -16)
    return pdk.Deck(layers=capas, initial_view_state=vista,
                    map_style=ESTILO_MAPA, tooltip=_tooltip())


# ══════════════════════════════════════════════════════════════════════════════
# 8B · ESCALA CÓDIGO POSTAL — 1,182 POLÍGONOS SEPOMEX REALES DE CDMX
# ══════════════════════════════════════════════════════════════════════════════

RUTA_CP = os.path.join(_DIR, "data", "cdmx_codigos_postales.json")

# Prefijo de CP → alcaldía (aprox oficial SEPOMEX)
CP_ALCALDIA = {
    "01": "Álvaro Obregón", "02": "Azcapotzalco", "03": "Benito Juárez",
    "04": "Coyoacán", "05": "Cuajimalpa", "06": "Cuauhtémoc",
    "07": "Gustavo A. Madero", "08": "Iztacalco", "09": "Iztapalapa",
    "10": "Magdalena Contreras", "11": "Miguel Hidalgo", "12": "Tlalpan",
    "13": "Tláhuac", "14": "Tlalpan", "15": "Venustiano Carranza",
    "16": "Xochimilco",
}

# Núcleos premium y corredores emergentes reales de CDMX (para sintetizar
# el gradiente de precio/potencial a falta de microdatos abiertos por CP)
NUCLEOS_CDMX = [   # (lng, lat, peso MXN/m², sigma)
    (-99.190, 19.433, 30000, 0.020),   # Polanco
    (-99.168, 19.414, 22000, 0.018),   # Roma–Condesa
    (-99.259, 19.359, 18000, 0.020),   # Santa Fe
    (-99.170, 19.386, 15000, 0.015),   # Del Valle–Nápoles
    (-99.162, 19.350, 9000, 0.015),    # Coyoacán centro
]
EMERGENTES_CDMX = [  # (lng, lat, peso 0-1, sigma) — dónde muta primero
    (-99.186, 19.489, 0.85, 0.025),    # Vallejo / Azcapotzalco
    (-99.143, 19.417, 0.70, 0.015),    # Doctores–Obrera
    (-99.187, 19.402, 0.60, 0.015),    # Tacubaya–Observatorio
    (-99.090, 19.395, 0.55, 0.030),    # Oriente (Iztacalco–Iztapalapa)
]

DETONANTES_CDMX = {
    "— Sin detonante —": None,
    "Cablebús + Metro norte (Vallejo)": dict(lng=-99.186, lat=19.489, año=1, fuerza=0.55, radio=0.030),
    "Corredor Reforma Norte": dict(lng=-99.155, lat=19.445, año=2, fuerza=0.50, radio=0.025),
    "Regeneración oriente (Iztapalapa)": dict(lng=-99.065, lat=19.355, año=1, fuerza=0.60, radio=0.040),
}


URL_CP = ("https://raw.githubusercontent.com/open-mexico/mexico-geojson/"
          "master/09-Cdmx.geojson")


@st.cache_data(show_spinner="🏘 Cargando 1,182 códigos postales SEPOMEX…", max_entries=1)
def cargar_cp() -> gpd.GeoDataFrame:
    """Polígonos postales reales de CDMX (SEPOMEX vía open-mexico/mexico-geojson)."""
    geo = _cargar_geojson(RUTA_CP, URL_CP)
    gdf = gpd.GeoDataFrame.from_features(geo["features"], crs="EPSG:4326")
    gdf = gdf.rename(columns={"d_codigo": "cp"}) if "d_codigo" in gdf.columns else gdf
    gdf["cp"] = gdf["cp"].astype(str).str.zfill(5)
    gdf["alcaldia"] = gdf["cp"].str[:2].map(CP_ALCALDIA).fillna("CDMX")
    cen = gdf.geometry.representative_point()
    gdf["lng"], gdf["lat"] = cen.x, cen.y
    return gdf[["cp", "alcaldia", "lng", "lat", "geometry"]].reset_index(drop=True)


@st.cache_data(show_spinner="🧠 Tejiendo contigüidad postal…", max_entries=1)
def vecindad_cp() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return _vecindad(cargar_cp().geometry.tolist(), 0.0025)


@st.cache_data(max_entries=1)
def contornos_cp() -> pd.DataFrame:
    filas = []
    for idx, geom in enumerate(cargar_cp().geometry):
        geoms = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
        for g in geoms:
            filas.append({"idx_cp": idx,
                          "contorno": [[[round(x, 5), round(y, 5)]
                                        for x, y in g.exterior.coords]]})
    return pd.DataFrame(filas)


@st.cache_data(max_entries=1)
def datos_cp() -> pd.DataFrame:
    """
    Expediente por código postal: el precio se sintetiza con el gradiente de
    los núcleos premium reales (Polanco, Roma, Santa Fe…) y el potencial con
    los corredores emergentes (Vallejo, Doctores, Tacubaya, oriente).
    """
    rng = np.random.default_rng(SEMILLA)
    gdf = cargar_cp()
    lng, lat = gdf["lng"].to_numpy(), gdf["lat"].to_numpy()

    precio = np.full(len(gdf), 16000.0)
    for nx, ny, peso, sigma in NUCLEOS_CDMX:
        precio += peso * np.exp(-((lng - nx) ** 2 + (lat - ny) ** 2)
                                / (2 * sigma ** 2))
    precio *= rng.lognormal(0.0, 0.09, len(gdf))

    potencial = rng.uniform(0.05, 0.20, len(gdf))
    for nx, ny, peso, sigma in EMERGENTES_CDMX:
        potencial += peso * np.exp(-((lng - nx) ** 2 + (lat - ny) ** 2)
                                   / (2 * sigma ** 2))
    potencial = np.clip(potencial + 0.15 * (1 - norm01(precio)), 0.02, 1)

    df = pd.DataFrame({
        "cp": gdf["cp"], "alcaldia": gdf["alcaldia"],
        "lng": lng, "lat": lat,
        "precio_actual": precio.round(0),
        "potencial_crecimiento": potencial.round(3),
        "airbnb": 0, "n_estab": 0, "empleo": 0, "resiliencia": 0.0,
        "indicadoras": 0,
    })

    # 🏪 Vitalidad económica REAL del DENUE por código postal (CDMX), generada
    # al agregar el DENUE de CDMX por cod_postal. Ancla precio y potencial en
    # la densidad de negocios/empleo observada por CP.
    ruta_den = os.path.join(_DIR, "data", "denue_cp_cdmx.csv")
    if os.path.exists(ruta_den):
        den = pd.read_csv(ruta_den, dtype={"cp": str})
        den["cp"] = den["cp"].str.zfill(5)
        df = df.merge(den, on="cp", how="left", suffixes=("", "_r"))
        for c in ["n_estab_r", "empleo_r", "resiliencia_r", "indicadoras_r"]:
            df[c[:-2]] = df[c].fillna(df[c[:-2]])
            df.drop(columns=c, inplace=True)
        tiene = df["n_estab"].to_numpy() > 0
        vital = norm01(np.log1p(df["n_estab"].to_numpy())
                       + 0.6 * norm01(np.log1p(df["empleo"].to_numpy())))
        precio_real = 14000 + 26000 * vital
        df.loc[tiene, "precio_actual"] = (precio_real
                                          * rng.lognormal(0, 0.05, len(df))
                                          )[tiene].round(0)
        ind = norm01(df["indicadoras"].to_numpy()) if "indicadoras" in df else 0
        df.loc[tiene, "potencial_crecimiento"] = np.clip(
            0.55 * potencial + 0.25 * (1 - vital) + 0.20 * ind, 0.02, 1
        )[tiene].round(3)

    # 💰 calibración contra anclajes de precio REALES (si fueron muestreados)
    df["precio_actual"], df.attrs["anclas_precio"] = calibrar_con_precios(
        df["lng"].to_numpy(), df["lat"].to_numpy(),
        df["precio_actual"].to_numpy(dtype=float))

    # 🛰 Señal alternativa auto-detectada: presión Airbnb por CP
    # (generada por scripts/ingerir_senales.py con datos de InsideAirbnb)
    ruta_abnb = os.path.join(_DIR, "data", "senal_airbnb_cdmx.csv")
    if os.path.exists(ruta_abnb):
        abnb = pd.read_csv(ruta_abnb, dtype={"cp": str})
        df = df.merge(abnb, on="cp", how="left").fillna(
            {"n_listados": 0, "precio_noche": 0})
        df["airbnb"] = df["n_listados"].astype(int)
        # la presión de renta corta acelera la receptividad de la célula
        df["potencial_crecimiento"] = np.clip(
            df["potencial_crecimiento"]
            + 0.20 * norm01(np.log1p(df["n_listados"].to_numpy())),
            0.02, 1).round(3)
    return df


def _args_cp(rho: float, detonante: str, clic: tuple = None) -> dict:
    """Argumentos del núcleo SAR para la escala postal."""
    df = datos_cp()
    pi, pj, g = vecindad_cp()
    det = DETONANTES_CDMX.get(detonante)
    mask = None
    if det is not None:
        mask = np.exp(-((df["lng"].to_numpy() - det["lng"]) ** 2
                        + (df["lat"].to_numpy() - det["lat"]) ** 2)
                      / (2 * det["radio"] ** 2))
    m_clic = _shock_clic(df["lng"].to_numpy(), df["lat"].to_numpy(),
                         clic, 0.022)
    if m_clic is not None:
        mask, det = m_clic, dict(año=1, fuerza=0.60)
    return dict(v0=df["precio_actual"].to_numpy(dtype=float),
                potencial=df["potencial_crecimiento"].to_numpy(dtype=float),
                g_propio=np.full(len(df), 0.051 * 0.55),   # plusvalía CDMX
                pares_i=pi, pares_j=pj, grados=g,
                rho=rho, escala_rho=0.15,
                shock_mask=mask,
                shock_año=det["año"] if det else 0,
                shock_fuerza=det["fuerza"] if det else 0)


@st.cache_data(show_spinner="🧬 Simulando morfogénesis postal (SEPOMEX, max_entries=8)…")
def simular_cp(rho: float, detonante: str, clic: tuple = None) -> np.ndarray:
    return _sar(**_args_cp(rho, detonante, clic))


def construir_deck_cp(valores: np.ndarray, año: float, fase: float,
                      mostrar_flujos: bool,
                      mostrar_lisa: bool = False) -> pdk.Deck:
    """1,182 células postales reales de CDMX latiendo."""
    df = datos_cp()
    v_t, tasa = estado_en(valores, año)
    acum = v_t / valores[0] - 1
    t = 0.45 * norm01(v_t) + 0.55 * norm01(acum)
    rgb = paleta_marca(t ** 0.85)
    alfa = np.clip((75 + 145 * t) * _respiracion(t, fase), 40, 235)
    base = pd.DataFrame({
        "nombre": "CP " + df["cp"] + " · " + df["alcaldia"],
        "lng": df["lng"], "lat": df["lat"],
        "color": np.column_stack([rgb, alfa]).astype(int).tolist(),
        "estado_bio": clasificar_bio(tasa),
        "precio_txt": [f"${p:,.0f} MXN/m²" for p in v_t],
        "crec_txt": [f"+{r * 100:.1f}% anual" for r in tasa],
        "plusvalia_txt": [f"+{a * 100:.0f}% vs hoy" for a in acum],
        "extra_txt": [f"potencial {q:.2f}"
                      for q in df["potencial_crecimiento"]],
    })
    capas = [pdk.Layer(
        "PolygonLayer", id="celulas",
        data=contornos_cp().join(base, on="idx_cp"),
        get_polygon="contorno", get_fill_color="color",
        get_line_color=RGB_LIMA + [22], line_width_min_pixels=0.5,
        stroked=True, pickable=True, auto_highlight=True,
        highlight_color=RGB_CREMA + [110],
    )]
    if mostrar_lisa:
        capas.append(capa_frente_onda(contornos_cp(), "idx_cp",
                                      frente_de_onda(v_t, vecindad_cp())))
    # nombres de las 16 alcaldías sobre el tejido postal (centroides)
    alc = df.groupby("alcaldia")[["lng", "lat"]].mean().reset_index()
    capas.append(pdk.Layer(
        "TextLayer",
        data=pd.DataFrame({
            "pos": [[float(a), float(b)] for a, b in zip(alc["lng"],
                                                         alc["lat"])],
            "nombre": alc["alcaldia"]}),
        get_position="pos", get_text="nombre", get_size=13,
        get_color=RGB_CREMA + [210],
    ))
    if mostrar_flujos:
        # corazones = CP más caros; emergentes = mayor contagio
        fuentes = np.argsort(v_t)[-5:]
        dest = [c for c in np.argsort(tasa)[::-1]
                if c not in set(fuentes)][:18]
        lngs, lats = df["lng"].to_numpy(), df["lat"].to_numpy()
        filas = []
        for k, d in enumerate(dest):
            dist = np.hypot(lngs[fuentes] - lngs[d], lats[fuentes] - lats[d])
            f = fuentes[int(np.argmax(v_t[fuentes] / (dist + 1e-3)))]
            filas.append({"origen": [float(lngs[f]), float(lats[f])],
                          "destino": [float(lngs[d]), float(lats[d])],
                          "intensidad": float(tasa[d] / (tasa.max() + 1e-9)),
                          "desfase": (k * 0.13) % 1.0})
        capas += _capas_circulatorias(pd.DataFrame(filas), fase, escala=0.03)
    return pdk.Deck(layers=capas,
                    initial_view_state=_vista(-99.14, 19.38, 10.6, pitch=45),
                    map_style=ESTILO_MAPA, tooltip=_tooltip())


# ══════════════════════════════════════════════════════════════════════════════
# 8C · ESCALA CALLE · ESTABLECIMIENTO — DENUE REAL (si existe) O DEMO
#      La app detecta data/calles_azcapotzalco.json +
#      data/establecimientos_azcapotzalco.csv.gz generados por
#      scripts/ingerir_denue.py (INEGI). Sin ellos, usa una red de
#      demostración claramente etiquetada.
# ══════════════════════════════════════════════════════════════════════════════

RUTA_ESTAB_TPL = os.path.join(_DIR, "data", "establecimientos_{s}.csv.gz")
RUTA_CALLES_TPL = os.path.join(_DIR, "data", "calles_{s}.json")
RUTA_SISMO_TPL = os.path.join(_DIR, "data", "sismografo_{s}.json")
RUTA_VALID_TPL = os.path.join(_DIR, "data", "validacion_{s}.json")

SECTORES = {
    "Comercio": [183, 196, 137],      # oliva
    "Servicios": [111, 162, 135],     # salvia
    "Industria": [245, 237, 227],     # crema
    "Alimentos": [85, 153, 126],      # salvia profunda
}

# Anclas de reserva (demo Azcapotzalco) si un municipio no trae datos reales
ANCLAS_AZC = [
    ("🏬 Parque Vía Vallejo", -99.1757, 19.4887, 0.95),
    ("🚇 Metro El Rosario", -99.2003, 19.5048, 0.80),
    ("🚇 Metro Camarones", -99.1745, 19.4790, 0.65),
    ("🎓 UAM Azcapotzalco", -99.2052, 19.5043, 0.60),
    ("🏥 Hospital La Raza", -99.1690, 19.4700, 0.70),
]
EMOJI_SECTOR = {"Comercio": "🏬", "Servicios": "🏢",
                "Industria": "🏭", "Alimentos": "🍽"}


@st.cache_data(max_entries=1)
def municipios_calle() -> list[dict]:
    """
    Descubre los municipios con datos de calle ingeridos (data/calles_*.json
    + su CSV de establecimientos). Lee el nombre real del municipio/estado
    del propio JSON. Es lo que puebla el selector de la escala calle.
    """
    import glob
    salida = []
    for ruta in sorted(glob.glob(os.path.join(_DIR, "data", "calles_*.json"))):
        suf = os.path.basename(ruta)[len("calles_"):-len(".json")]
        if not os.path.exists(RUTA_ESTAB_TPL.format(s=suf)):
            continue
        muni, edo = suf.replace("_", " ").title(), ""
        try:
            with open(ruta, encoding="utf-8") as f:
                meta = json.load(f)
            muni = meta.get("municipio", muni)
            edo = meta.get("estado", "")
        except (OSError, json.JSONDecodeError):
            pass
        salida.append({"suffix": suf, "municipio": muni, "estado": edo,
                       "label": f"{muni}" + (f" · {edo}" if edo else "")})
    # ordena por estado y municipio para navegar decenas de ciudades
    return sorted(salida, key=lambda m: (m["estado"], m["municipio"]))


def hay_datos_denue(suffix: str = None) -> bool:
    """¿Existen datos reales de calle? (para un municipio, o para cualquiera)."""
    if suffix is None:
        return len(municipios_calle()) > 0
    return (os.path.exists(RUTA_CALLES_TPL.format(s=suffix))
            and os.path.exists(RUTA_ESTAB_TPL.format(s=suffix)))


@st.cache_data(show_spinner="🛣 Construyendo la red vial…", max_entries=4)
def cargar_red_vial(suffix: str = "azcapotzalco"
                    ) -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    """
    Devuelve (calles, establecimientos, es_real) para el municipio `suffix`.
    REAL: DENUE/INEGI ingerido con scripts/ingerir_denue.py. DEMO: retícula
    sintética etiquetada (solo si no hay ningún dato real).
    """
    rc, re_ = RUTA_CALLES_TPL.format(s=suffix), RUTA_ESTAB_TPL.format(s=suffix)
    if os.path.exists(rc) and os.path.exists(re_):
        with open(rc, encoding="utf-8") as f:
            calles = pd.DataFrame(json.load(f)["calles"])
        # Saneo geométrico CRÍTICO: las polilíneas PCA traen vértices
        # consecutivos duplicados (calles cortas pueden tener los 12 puntos
        # idénticos). Un segmento de longitud cero con uniones redondeadas
        # produce normales NaN en el PathLayer y, según el GPU, se dibuja
        # como triángulos gigantes o deja el mapa EN BLANCO.
        def _sanear(camino):
            limpio = [camino[0]]
            for p in camino[1:]:
                if p[0] != limpio[-1][0] or p[1] != limpio[-1][1]:
                    limpio.append(p)
            return limpio
        calles["camino"] = calles["camino"].map(_sanear)
        calles = calles[calles["camino"].map(len) >= 2].reset_index(drop=True)
        return calles, pd.read_csv(re_), True
    return _red_demo()


# Red sintética de reserva (nombres/anclas reales de Azcapotzalco)
_VIAS_NS = ["Av. Aquiles Serdán", "Av. Tezozómoc", "Av. de las Granjas",
            "Calz. Vallejo", "Av. Ceylán", "Poniente 116", "Poniente 128",
            "Poniente 134", "Poniente 140", "Poniente 146", "Poniente 152",
            "Av. Jardín", "Calle 22 de Febrero", "Av. Granjas Norte"]
_VIAS_EO = ["Av. Azcapotzalco", "Av. Cuitláhuac", "Eje 5 Norte", "Eje 4 Norte",
            "Calz. Camarones", "Av. El Rosario", "Norte 45", "Norte 59",
            "Norte 77", "Norte 87", "Av. San Pablo Xalpa", "Av. Renacimiento"]
_GIROS = {"Comercio": ["Abarrotes", "Ferretería", "Papelería", "Miscelánea"],
          "Servicios": ["Taller mecánico", "Estética", "Consultorio", "Ciber"],
          "Industria": ["Taller metalmecánico", "Bodega", "Imprenta"],
          "Alimentos": ["Taquería", "Fonda", "Panadería", "Cocina económica"]}
_NOMBRES = ["La Esperanza", "El Fénix", "San José", "Doña Mary", "El Águila",
            "Vallejo", "La Central", "Don Beto", "La Norteña", "El Porvenir"]


@st.cache_data(max_entries=1)
def _red_demo() -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    """Retícula vial sintética con nombres y anclas reales de Azcapotzalco."""
    w, e, s, n = -99.215, -99.155, 19.462, 19.508
    rng = np.random.default_rng(SEMILLA)
    filas = []
    for x, nombre in zip(np.linspace(w, e, len(_VIAS_NS)), _VIAS_NS):
        pts = [[float(x + rng.normal(0, 3e-4)), float(y)]
               for y in np.linspace(s, n, 6)]
        filas.append({"nombre": nombre, "camino": pts})
    for y, nombre in zip(np.linspace(s, n, len(_VIAS_EO)), _VIAS_EO):
        pts = [[float(x), float(y + rng.normal(0, 3e-4))]
               for x in np.linspace(w, e, 6)]
        filas.append({"nombre": nombre, "camino": pts})
    calles = pd.DataFrame(filas)
    ax = np.array([a[1] for a in ANCLAS_AZC])
    ay = np.array([a[2] for a in ANCLAS_AZC])
    aw = np.array([a[3] for a in ANCLAS_AZC])
    registros = []
    for _, c in calles.iterrows():
        pts = np.array(c["camino"])
        mid = pts.mean(axis=0)
        cerca = (aw * np.exp(-((ax - mid[0]) ** 2 + (ay - mid[1]) ** 2)
                             / (2 * 0.012 ** 2))).sum()
        num = rng.poisson(16 + 46 * min(cerca, 1.2))
        for _ in range(num):
            u = rng.uniform()
            k = min(int(u * (len(pts) - 1)), len(pts) - 2)
            frac = u * (len(pts) - 1) - k
            lng = pts[k, 0] + (pts[k + 1, 0] - pts[k, 0]) * frac + rng.normal(0, 1.2e-4)
            lat = pts[k, 1] + (pts[k + 1, 1] - pts[k, 1]) * frac + rng.normal(0, 1.2e-4)
            sector = rng.choice(list(SECTORES), p=[0.40, 0.30, 0.15, 0.15])
            registros.append({
                "nombre": f"{rng.choice(_GIROS[sector])} {rng.choice(_NOMBRES)}",
                "sector": sector, "calle": c["nombre"],
                "lat": float(lat), "lng": float(lng),
                "empleo": int(rng.choice([2, 4, 8, 18, 45],
                                         p=[.45, .28, .16, .08, .03]))})
    return calles, pd.DataFrame(registros), False


@st.cache_data(show_spinner="⚓ Detectando anclas económicas…", max_entries=4)
def anclas_municipio(suffix: str = "azcapotzalco") -> pd.DataFrame:
    """
    Anclas económicas DERIVADAS del DENUE real: los focos de empleo del
    municipio (rejilla ~250 m, top por empleo), cada uno nombrado por su
    mayor establecimiento. De aquí nace el crecimiento — sin hardcodear nada.
    """
    _, estab, real = cargar_red_vial(suffix)
    if not real or estab.empty or "lng" not in estab.columns:
        return pd.DataFrame({"nombre": [a[0] for a in ANCLAS_AZC],
                             "lng": [a[1] for a in ANCLAS_AZC],
                             "lat": [a[2] for a in ANCLAS_AZC],
                             "peso": [a[3] for a in ANCLAS_AZC]})
    lng, lat = estab["lng"].to_numpy(), estab["lat"].to_numpy()
    paso = 0.0025
    gx = np.round((lng - lng.min()) / paso).astype(int)
    gy = np.round((lat - lat.min()) / paso).astype(int)
    est = estab.assign(celda=gx * 100000 + gy)
    agg = est.groupby("celda").agg(emp=("empleo", "sum"),
                                   lng=("lng", "mean"),
                                   lat=("lat", "mean")).reset_index()
    filas = []
    for _, c in agg.nlargest(6, "emp").iterrows():
        cerca = est[est["celda"] == c["celda"]]
        big = cerca.loc[cerca["empleo"].idxmax()]
        emo = EMOJI_SECTOR.get(big.get("sector", ""), "📍")
        nom = str(big["nombre"]).title()[:26]
        filas.append({"nombre": f"{emo} {nom}", "lng": float(c["lng"]),
                      "lat": float(c["lat"]), "peso": float(c["emp"])})
    d = pd.DataFrame(filas)
    d["peso"] = (0.45 + 0.55 * norm01(d["peso"].to_numpy())).round(3)
    return d


@st.cache_data(max_entries=4)
def expediente_calles(suffix: str = "azcapotzalco") -> pd.DataFrame:
    """
    Expediente por calle: vitalidad económica (establecimientos + empleo del
    DENUE), cercanía a anclas y valor sintetizado. AQUÍ nace el crecimiento:
    cada peso proyectado es rastreable a la actividad económica observada.
    """
    calles, estab, _ = cargar_red_vial(suffix)
    agg = estab.groupby("calle").agg(
        n_estab=("nombre", "size"), empleo=("empleo", "sum"),
        sector=("sector", lambda s: s.mode().iat[0])).reset_index()
    df = calles.merge(agg, left_on="nombre", right_on="calle", how="left") \
        .fillna({"n_estab": 0, "empleo": 0, "sector": "Servicios"})

    mids = np.array([np.mean(c, axis=0) for c in df["camino"]])
    anc = anclas_municipio(suffix)
    ax, ay = anc["lng"].to_numpy(), anc["lat"].to_numpy()
    aw = anc["peso"].to_numpy()
    ancla = np.stack([w * np.exp(-((mids[:, 0] - x) ** 2 + (mids[:, 1] - y) ** 2)
                                 / (2 * 0.012 ** 2))
                      for x, y, w in zip(ax, ay, aw)]).sum(axis=0)

    vital = norm01(np.log1p(df["n_estab"]) + 0.6 * np.log1p(df["empleo"]))
    df["vitalidad"] = vital.round(3)
    df["cercania_ancla"] = np.clip(ancla, 0, 1.3).round(3)
    df["valor_actual"] = (9000 + 9500 * vital + 6500 * np.clip(ancla, 0, 1)
                          ).round(0)
    df["potencial_crecimiento"] = np.clip(
        0.50 * np.clip(ancla, 0, 1) + 0.35 * (1 - vital)
        + 0.15 * norm01(df["n_estab"]), 0.02, 1).round(3)

    mix = estab.groupby(["calle", "sector"]).size().unstack(fill_value=0)
    p = mix.div(mix.sum(axis=1), axis=0).clip(lower=1e-9)
    entropia = (-(p * np.log(p)).sum(axis=1) / math.log(len(SECTORES)))
    df["resiliencia"] = df["nombre"].map(entropia).fillna(0.0).round(3)

    # 💰 calibración contra anclajes de precio REALES (si fueron muestreados)
    df["valor_actual"], df.attrs["anclas_precio"] = calibrar_con_precios(
        mids[:, 0], mids[:, 1], df["valor_actual"].to_numpy(dtype=float))

    # 🏚 riesgo de estancamiento por calle: tejido antiguo sin aperturas
    if "anio" in estab.columns:
        rec = estab[estab["anio"] >= estab["anio"].quantile(0.6)] \
            .groupby("calle").size()
        df["altas_rec"] = df["nombre"].map(rec).fillna(0).astype(int)
        df["estancada"] = ((df["altas_rec"] == 0) & (df["n_estab"] >= 10))
    else:
        df["altas_rec"], df["estancada"] = 0, False
    return df


ESPECIES_INDICADORAS = ["Café de especialidad", "Coworking", "Galería",
                        "Barbería premium", "Estudio de yoga",
                        "Panadería artesanal", "Veterinaria", "Gym boutique"]


@st.cache_data(max_entries=4)
def sismografo_calles(suffix: str = "azcapotzalco") -> tuple[pd.DataFrame, bool]:
    """
    Metabolismo de cada calle: aperturas recientes y ESPECIES INDICADORAS de
    gentrificación. Real desde data/sismografo_<suffix>.json (fecha_alta del
    DENUE); demo etiquetada si no existe.
    """
    df = expediente_calles(suffix)
    ruta = RUTA_SISMO_TPL.format(s=suffix)
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            sismo = pd.DataFrame(json.load(f)["calles"])
        sismo = df[["nombre"]].merge(sismo, on="nombre", how="left")
        sismo[["altas", "bajas", "indicadoras"]] = sismo[
            ["altas", "bajas", "indicadoras"]].fillna(0)
        sismo["especies"] = sismo["especies"].fillna("—")
        es_real = True
    else:
        rng = np.random.default_rng(SEMILLA + 7)
        pot = df["potencial_crecimiento"].to_numpy()
        vit = df["vitalidad"].to_numpy()
        altas = rng.poisson(2 + 9 * pot)
        bajas = rng.poisson(1 + 4 * (1 - vit) * (1 - pot))
        indicadoras = rng.binomial(altas, np.clip(pot * 0.55, 0, 1))
        especies = [", ".join(rng.choice(ESPECIES_INDICADORAS,
                                         size=min(int(k), 3), replace=False))
                    if k > 0 else "—" for k in indicadoras]
        sismo = pd.DataFrame({"nombre": df["nombre"], "altas": altas,
                              "bajas": bajas, "indicadoras": indicadoras,
                              "especies": especies})
        es_real = False
    sismo["magnitud"] = norm01(2.2 * sismo["indicadoras"] + sismo["altas"]
                               - 0.8 * sismo["bajas"]).round(3)
    return sismo, es_real


@st.cache_data(show_spinner="🧠 Detectando cruces entre calles…", max_entries=4)
def vecindad_calles(suffix: str = "azcapotzalco"
                    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Dos calles son vecinas si se cruzan (<60 m): el contagio viaja por
    las intersecciones, como el tráfico."""
    from shapely.geometry import LineString
    geoms = [LineString(c) for c in expediente_calles(suffix)["camino"]]
    return _vecindad(geoms, 0.0006)


def _vista_calles(calles: pd.DataFrame) -> pdk.ViewState:
    """
    Centro y zoom automáticos, ROBUSTOS a outliers: centra en la mediana y
    encuadra el núcleo denso (percentiles 5–95), para que un municipio grande
    no se vea diminuto por unas pocas calles en el borde.
    """
    pts = np.array([p for c in calles["camino"] for p in c])
    # centra en el corazón denso (mediana ponderada por densidad de puntos)
    gx = np.round(pts[:, 0] / 0.01).astype(int)
    gy = np.round(pts[:, 1] / 0.01).astype(int)
    celdas, cuenta = np.unique(np.stack([gx, gy], 1), axis=0,
                               return_counts=True)
    cx, cy = celdas[cuenta.argmax()]
    nucleo = pts[(np.abs(gx - cx) <= 3) & (np.abs(gy - cy) <= 3)]
    clng, clat = float(np.median(nucleo[:, 0])), float(np.median(nucleo[:, 1]))
    # encuadra un distrito legible: núcleo denso, acotado a ~7 km
    span = max(float(np.percentile(pts[:, 0], 92) - np.percentile(pts[:, 0], 8)),
               float(np.percentile(pts[:, 1], 92) - np.percentile(pts[:, 1], 8)),
               1e-3)
    # cuanto más densa la red, más se enfoca el corazón (retícula legible)
    n_pts = len(calles)
    tope = 0.085 if n_pts < 900 else (0.055 if n_pts < 1600 else 0.042)
    span = min(span, tope)
    zoom = float(np.clip(13.2 - math.log2(span / 0.05), 11.0, 14.4))
    return _vista(clng, clat, zoom, pitch=42, bearing=-12)


def _args_calles(rho: float, catalizador: str, clic: tuple = None,
                 suffix: str = "azcapotzalco") -> dict:
    df = expediente_calles(suffix)
    pi, pj, g = vecindad_calles(suffix)
    mids = np.array([np.mean(c, axis=0) for c in df["camino"]])
    cat = CATALIZADORES.get(catalizador)
    mask = None
    if cat is not None:
        mask = np.exp(-((mids[:, 0] - cat["lng"]) ** 2
                        + (mids[:, 1] - cat["lat"]) ** 2)
                      / (2 * cat["radio"] ** 2))
    m_clic = _shock_clic(mids[:, 0], mids[:, 1], clic, 0.008)
    if m_clic is not None:
        mask, cat = m_clic, dict(año=1, fuerza=0.75)
    return dict(v0=df["valor_actual"].to_numpy(dtype=float),
                potencial=df["potencial_crecimiento"].to_numpy(dtype=float),
                g_propio=(0.018 + 0.022 * df["vitalidad"].to_numpy()),
                pares_i=pi, pares_j=pj, grados=g,
                rho=rho, escala_rho=0.17,
                shock_mask=mask,
                shock_año=cat["año"] if cat else 0,
                shock_fuerza=cat["fuerza"] if cat else 0)


@st.cache_data(show_spinner="🧬 Simulando morfogénesis vial…", max_entries=8)
def simular_calles(rho: float, catalizador: str, clic: tuple = None,
                   suffix: str = "azcapotzalco") -> np.ndarray:
    return _sar(**_args_calles(rho, catalizador, clic, suffix))


def _liston(camino: list, medio_m: float) -> list | None:
    """
    Polilínea → polígono "listón" de ancho 2*medio_m metros (cerrado).
    Motivo: el PathLayer/LineLayer de la build de deck.gl que empaca
    Streamlit está roto (según el GPU inunda la pantalla o la deja EN
    BLANCO), mientras que el PolygonLayer —el que usan las demás escalas—
    renderiza perfecto. Así que las calles se dibujan como polígonos.
    """
    P = np.asarray(camino, dtype=float)
    keep = np.ones(len(P), bool)
    keep[1:] = (np.abs(np.diff(P, axis=0)).sum(axis=1) > 0)
    P = P[keep]
    if len(P) < 2:
        return None
    kx = 111320 * math.cos(math.radians(float(P[:, 1].mean())))
    ky = 111320.0
    X = np.column_stack([(P[:, 0] - P[0, 0]) * kx, (P[:, 1] - P[0, 1]) * ky])
    dif = np.diff(X, axis=0)
    seg = dif / (np.linalg.norm(dif, axis=1, keepdims=True) + 1e-9)
    nrm = np.column_stack([-seg[:, 1], seg[:, 0]])
    vn = np.vstack([nrm[:1], (nrm[:-1] + nrm[1:]) / 2, nrm[-1:]])
    vn = vn / (np.linalg.norm(vn, axis=1, keepdims=True) + 1e-9)
    izq, der = X + vn * medio_m, X - vn * medio_m
    anillo = np.vstack([izq, der[::-1], izq[:1]])          # anillo cerrado
    return np.column_stack([anillo[:, 0] / kx + P[0, 0],
                            anillo[:, 1] / ky + P[0, 1]]).tolist()


def construir_deck_calles(valores: np.ndarray, año: float, fase: float,
                          mostrar_estab: bool, mostrar_flujos: bool,
                          suffix: str = "azcapotzalco") -> pdk.Deck:
    """La zona vista desde la banqueta: calles que laten, negocios que
    alimentan el crecimiento y anclas que lo detonan."""
    df = expediente_calles(suffix)
    _, estab, _ = cargar_red_vial(suffix)
    anc = anclas_municipio(suffix)
    v_t, tasa = estado_en(valores, año)
    acum = v_t / valores[0] - 1
    t = 0.45 * norm01(v_t) + 0.55 * norm01(acum)
    rgb = paleta_marca(t ** 0.85)
    # densidad adaptativa: en municipios con muchas calles, líneas más finas y
    # translúcidas para que se lea la retícula y no se sature (Azcapotzalco
    # intacto). Sólo las calles en mutación brillan; el resto queda tenue.
    vis = float(np.clip(650 / max(len(df), 250), 0.32, 1.0))
    alfa = np.clip((32 + 125 * t ** 1.3) * _respiracion(t, fase)
                   * (0.5 + 0.5 * vis), 26, 200)

    mids_c = np.array([np.mean(c, axis=0) for c in df["camino"]])
    anchos = 0.8 + (0.6 + 6.0 * df["vitalidad"].to_numpy()) * vis
    # calles como LISTONES PolygonLayer (ver _liston): medio ancho en metros,
    # proporcional a la vitalidad — las calles vivas se ven más gruesas
    contornos_c = [_liston(c, m) for c, m in
                   zip(df["camino"], (4.5 + 3.2 * anchos))]
    calles_render = pd.DataFrame({
        "contorno": contornos_c,
        "lng": mids_c[:, 0], "lat": mids_c[:, 1],
        "color": np.column_stack([rgb, alfa]).astype(int).tolist(),
        "nombre": df["nombre"].fillna(""),
        "estado_bio": clasificar_bio(tasa),
        "precio_txt": [f"${p:,.0f} índice/m²" for p in v_t],
        "crec_txt": [f"+{r * 100:.1f}% anual" for r in tasa],
        "plusvalia_txt": [f"+{a * 100:.0f}% vs hoy" for a in acum],
        "extra_txt": [f"{int(n)} negocios · {int(e)} empleos · {s}"
                      for n, e, s in zip(df["n_estab"], df["empleo"],
                                         df["sector"])],
    }).dropna(subset=["contorno"])
    capas = [pdk.Layer(
        "PolygonLayer", id="celulas", data=calles_render,
        get_polygon="contorno", get_fill_color="color",
        stroked=False, extruded=False,
        pickable=True, auto_highlight=True,
        highlight_color=RGB_CREMA + [160],
    )]

    if mostrar_estab:
        # en municipios grandes se muestran los de mayor empleo para que los
        # puntos no tapen el tejido vial (en los chicos, todos). El tooltip
        # conserva el detalle de cada negocio.
        tope_e = 2500 if len(estab) > 2500 else len(estab)
        est_v = estab.nlargest(tope_e, "empleo").copy()
        # DENUE trae negocios con nombre/calle/sector faltantes: un NaN en un
        # campo del deck se serializa como token JSON inválido y deja el mapa
        # ENTERO en blanco. Saneamos texto (y coordenadas por si acaso).
        for _c in ("nombre", "sector", "calle"):
            if _c in est_v:
                est_v[_c] = est_v[_c].fillna("")
        est_v = est_v.dropna(subset=["lng", "lat", "empleo"])
        er = pd.DataFrame({
            "pos": [[float(a), float(b)] for a, b in zip(est_v["lng"],
                                                         est_v["lat"])],
            "color": [SECTORES.get(s, RGB_CREMA) + [120]
                      for s in est_v["sector"]],
            "radio": (8 + np.sqrt(est_v["empleo"].to_numpy()) * 5).tolist(),
            "nombre": est_v["nombre"],
            "estado_bio": "",
            "precio_txt": est_v["sector"],
            "crec_txt": est_v["calle"],
            "plusvalia_txt": est_v["empleo"].astype(str) + " empleos",
            "extra_txt": "",
        })
        capas.append(pdk.Layer(
            "ScatterplotLayer", data=er, get_position="pos",
            get_fill_color="color", get_radius="radio",
            radius_min_pixels=0.8, radius_max_pixels=5,
            pickable=True, opacity=0.4,
        ))

    # anclas económicas: los corazones que bombean el crecimiento
    pulso = 0.5 + 0.5 * math.sin(2 * math.pi * fase)
    anclas = pd.DataFrame({
        "pos": [[float(x), float(y)] for x, y in zip(anc["lng"], anc["lat"])],
        "nombre": anc["nombre"], "peso": anc["peso"],
    })
    capas.append(pdk.Layer(
        "ScatterplotLayer", data=anclas, get_position="pos",
        get_radius=140 + 110 * pulso, get_fill_color=RGB_LIMA + [int(45 + 55 * pulso)],
        stroked=True, get_line_color=RGB_CREMA + [int(120 + 90 * pulso)],
        line_width_min_pixels=2,
    ))
    capas.append(pdk.Layer(
        "TextLayer", data=anclas, get_position="pos", get_text="nombre",
        get_size=12, get_color=RGB_CREMA + [235],
        get_alignment_baseline="'bottom'", get_pixel_offset=[0, -12],
    ))

    if mostrar_flujos:
        mids = np.array([np.mean(c, axis=0) for c in df["camino"]])
        ax, ay = anc["lng"].to_numpy(), anc["lat"].to_numpy()
        # cada ancla bombea capital a sus calles emergentes CERCANAS (<~2.5 km),
        # para que los arcos sean locales y legibles en municipios grandes
        filas, k = [], 0
        for fa in range(len(ax)):
            dist = np.hypot(mids[:, 0] - ax[fa], mids[:, 1] - ay[fa])
            cerca = np.where(dist < 0.024)[0]
            if len(cerca) == 0:
                cerca = np.argsort(dist)[:8]
            top = cerca[np.argsort(tasa[cerca])[::-1][:3]]
            for d in top:
                filas.append({"origen": [float(ax[fa]), float(ay[fa])],
                              "destino": [float(mids[d, 0]), float(mids[d, 1])],
                              "intensidad": float(tasa[d] / (tasa.max() + 1e-9)),
                              "desfase": (k * 0.13) % 1.0})
                k += 1
        if filas:
            capas += _capas_circulatorias(pd.DataFrame(filas), fase, escala=0.006)

    # ── Red de sucursales del usuario (modo franquicia) ──────────────────────
    # Sucursales en terracota #c07a66 con borde crema; huecos de cobertura en
    # salvia #6fa287. Solo cuando hay sucursales cargadas para ESTE municipio.
    if st.session_state.get("bb_red_suffix") == suffix:
        suc = st.session_state.get("bb_red_suc")
        if suc is not None and len(suc):
            suc_r = pd.DataFrame({
                "pos": [[float(a), float(b)] for a, b in zip(suc["lng"],
                                                             suc["lat"])],
                "nombre": suc["nombre"].astype(str)})
            capas.append(pdk.Layer(
                "ScatterplotLayer", id="red-sucursales", data=suc_r,
                get_position="pos", get_radius=70,
                get_fill_color=[192, 122, 102, 235],       # terracota
                stroked=True, get_line_color=RGB_CREMA + [255],
                line_width_min_pixels=2, radius_min_pixels=6,
                radius_max_pixels=14))
            capas.append(pdk.Layer(
                "TextLayer", data=suc_r, get_position="pos",
                get_text="nombre", get_size=11,
                get_color=[207, 146, 139, 235],
                get_alignment_baseline="'top'", get_pixel_offset=[0, 10]))
        huecos = st.session_state.get("bb_red_huecos")
        if huecos is not None and len(huecos):
            hue_r = pd.DataFrame({
                "pos": [[float(a), float(b)] for a, b in
                        zip(huecos["lng"], huecos["lat"])]})
            capas.append(pdk.Layer(
                "ScatterplotLayer", id="red-huecos", data=hue_r,
                get_position="pos", get_radius=160,
                get_fill_color=[111, 162, 135, 70],        # salvia
                stroked=True, get_line_color=[111, 162, 135, 220],
                line_width_min_pixels=2, radius_min_pixels=9,
                radius_max_pixels=26))

    # ── Sitio elegido en la tabla "¿Dónde abro mi negocio?" ──────────────────
    # Sin esto, el top-10 del selector B2B es una lista de nombres de calle que
    # hay que buscar a ojo en la retícula. Al marcarlo, la tabla y el mapa
    # hablan del mismo lugar. Oliva #b7c489 con borde crema: no se confunde ni
    # con las sucursales (terracota) ni con los huecos de cobertura (salvia),
    # y el ámbar queda libre para lo que sí es estimación.
    vista = _vista_calles(df)
    sitio = sitio_marcado(suffix)
    if sitio:
        marca = pd.DataFrame([{
            "pos": [sitio["lng"], sitio["lat"]],
            "etiqueta": f"{sitio['rank']}° · {sitio['calle']}"}])
        capas.append(pdk.Layer(
            "ScatterplotLayer", id="b2b-sitio-halo", data=marca,
            get_position="pos", get_radius=210,
            get_fill_color=[183, 196, 137, 55],            # oliva translúcido
            stroked=True, get_line_color=[183, 196, 137, 200],
            line_width_min_pixels=2, radius_min_pixels=16, radius_max_pixels=52))
        capas.append(pdk.Layer(
            "ScatterplotLayer", id="b2b-sitio", data=marca,
            get_position="pos", get_radius=55,
            get_fill_color=[183, 196, 137, 240],
            stroked=True, get_line_color=RGB_CREMA + [255],
            line_width_min_pixels=2, radius_min_pixels=6, radius_max_pixels=13))
        capas.append(pdk.Layer(
            "TextLayer", id="b2b-sitio-txt", data=marca, get_position="pos",
            get_text="etiqueta", get_size=13, get_color=RGB_CREMA + [245],
            get_alignment_baseline="'bottom'", get_pixel_offset=[0, -18]))
        # acercar la cámara al sitio: de nada sirve marcarlo si queda fuera de
        # cuadro en un municipio grande
        vista = pdk.ViewState(longitude=sitio["lng"], latitude=sitio["lat"],
                              zoom=14.6, pitch=vista.pitch, bearing=vista.bearing)

    return pdk.Deck(layers=capas, initial_view_state=vista,
                    map_style=ESTILO_MAPA, tooltip=_tooltip())


# ══════════════════════════════════════════════════════════════════════════════
# 9 · LABORATORIO ANALÍTICO — RANKING · TRAYECTORIAS · DIAGRAMA DE FASES
# ══════════════════════════════════════════════════════════════════════════════

_PLOTLY_MARCA = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(29,23,19,.55)",
    font=dict(family="Space Mono, monospace", color=TEXTO_SUAVE),
    colorway=NEON, margin=dict(l=10, r=10, t=42, b=10),
)


def tab_ranking_estados(valores: np.ndarray, año: float,
                        flujos: pd.DataFrame,
                        score: np.ndarray = None) -> None:
    """Expediente completo y ordenable de los 32 estados en el año t."""
    df = datos_estatales()
    v_t, tasa = estado_en(valores, año)
    presion = flujos["ciudad_destino"].map(
        pd.DataFrame(CIUDADES, columns=["ciudad", "estado", *["_"] * 6])
        .set_index("ciudad")["estado"]).value_counts()
    tabla = pd.DataFrame({
        "Estado": df["estado"],
        "Score BrickBit": score if score is not None
        else score_brickbit(v_t, valores[0], df["potencial"], tasa),
        "ZM principal": df["ciudad"],
        "Precio hoy (m²)": df["precio_m2"],
        f"Precio año {año:.0f} (m²)": v_t.round(0),
        "Plusvalía acumulada": (v_t / valores[0] - 1),
        "Tasa anual": tasa,
        "Potencial": df["potencial"],
        "Población (M)": df["poblacion"],
        "PIB pc (k MXN)": df["pib_pc"],
        "Arterias entrantes": df["estado"].map(presion).fillna(0).astype(int),
    }).sort_values("Plusvalía acumulada", ascending=False)
    _tabla_ranking(tabla, año)


def tab_ranking_municipios(valores: np.ndarray, año: float,
                           score: np.ndarray = None) -> None:
    """Los 40 municipios con mutación más agresiva en el año t."""
    df = datos_municipales()
    v_t, tasa = estado_en(valores, año)
    hay_real = "n_estab" in df.columns and df["n_estab"].sum() > 0
    cols = {
        "Municipio": df["municipio"],
        "Score BrickBit": score if score is not None
        else score_brickbit(v_t, valores[0],
                            df["potencial_crecimiento"], tasa),
        "Estado": df["estado"],
        "Precio hoy (m²)": df["precio_actual"],
        f"Precio año {año:.0f} (m²)": v_t.round(0),
        "Plusvalía acumulada": (v_t / valores[0] - 1),
        "Tasa anual": tasa,
        "Potencial": df["potencial_crecimiento"],
    }
    if hay_real:                       # columnas de vitalidad REAL del DENUE
        cols["Negocios (DENUE)"] = df["n_estab"].astype(int)
        cols["Empleo (DENUE)"] = df["empleo"].astype(int)
        cols["Resiliencia"] = df["resiliencia"]
    cols["ZM más cercana"] = df["zm_cercana"]
    cols["Dist. ZM (km)"] = df["dist_zm_km"]
    tabla = pd.DataFrame(cols).nlargest(40, "Plusvalía acumulada")
    st.caption(
        ("Top 40 de 2,436 municipios — precio y potencial anclados en la "
         "**vitalidad económica REAL del DENUE** (negocios y empleo por "
         "municipio)." if hay_real else
         "Top 40 de 2,436 municipios por plusvalía acumulada — "
         "el anillo periurbano de las ZM domina la mutación."))
    _tabla_ranking(tabla, año)


def _tabla_ranking(tabla: pd.DataFrame, año: float) -> None:
    st.dataframe(
        tabla, height=430, hide_index=True, width="stretch",
        column_config={
            "Plusvalía acumulada": st.column_config.ProgressColumn(
                format="percent", min_value=0,
                max_value=max(0.01, float(tabla["Plusvalía acumulada"].max()))),
            "Tasa anual": st.column_config.NumberColumn(format="percent"),
            "Potencial": st.column_config.ProgressColumn(
                min_value=0, max_value=1),
            "Resiliencia": st.column_config.ProgressColumn(
                min_value=0, max_value=1),
            "Score BrickBit": st.column_config.NumberColumn(format="%.1f"),
            "Negocios (DENUE)": st.column_config.NumberColumn(format="%d"),
            "Empleo (DENUE)": st.column_config.NumberColumn(format="%d"),
            "Precio hoy (m²)": st.column_config.NumberColumn(format="$%d"),
            f"Precio año {año:.0f} (m²)": st.column_config.NumberColumn(
                format="$%d"),
        })


def tab_trayectorias(valores: np.ndarray, año: float,
                     nombres: pd.Series, titulo: str,
                     banda: np.ndarray = None) -> None:
    """Evolución proyectada del precio: las 8 mutaciones más agresivas,
    con banda de confianza P10–P90 (Monte Carlo) para la líder."""
    acum = valores[-1] / valores[0] - 1
    top = np.argsort(acum)[::-1][:8]
    fig = go.Figure()
    if banda is not None:                       # banda de la unidad líder
        i0 = int(top[0])
        xs = list(range(AÑOS + 1))
        fig.add_trace(go.Scatter(
            x=xs + xs[::-1],
            y=list(banda[2, :, i0]) + list(banda[0, :, i0])[::-1],
            fill="toself", fillcolor="rgba(183,196,137,0.13)",
            line=dict(width=0), hoverinfo="skip",
            name=f"P10–P90 · {str(nombres.iloc[i0])[:22]}"))
    for c, i in zip(NEON, top):
        fig.add_trace(go.Scatter(
            x=list(range(AÑOS + 1)), y=valores[:, i],
            name=str(nombres.iloc[i]), mode="lines+markers",
            line=dict(width=2.4, color=c), marker=dict(size=5)))
    fig.add_vline(x=año, line_dash="dot", line_color=CREMA,
                  annotation_text=f"año {año:.1f}",
                  annotation_font_color=CREMA)
    fig.update_layout(title=titulo, xaxis_title="año",
                      yaxis_title="MXN/m²", height=420, **_PLOTLY_MARCA)
    st.plotly_chart(fig, width="stretch")


def tab_fases_estados(valores: np.ndarray, año: float) -> None:
    """Diagrama de fases estatal: precio vs contagio (burbuja = población)."""
    df = datos_estatales()
    v_t, tasa = estado_en(valores, año)
    fig = go.Figure(go.Scatter(
        x=v_t, y=tasa * 100, mode="markers+text",
        text=df["estado"], textposition="top center",
        textfont=dict(size=9, color=TEXTO_SUAVE),
        marker=dict(size=np.sqrt(df["poblacion"]) * 11 + 6,
                    color=df["potencial"], cmin=0, cmax=1,
                    colorscale=ESCALA_PLOTLY,
                    colorbar=dict(title="potencial"), opacity=0.88,
                    line=dict(width=1, color=ARCILLA_SUAVE)),
        hovertemplate="<b>%{text}</b><br>precio $%{x:,.0f}/m²"
                      "<br>contagio +%{y:.1f}%/año<extra></extra>"))
    fig.update_layout(
        title=f"⚗️ Diagrama de fases — año {año:.1f} "
              "(arriba-izquierda = oportunidad)",
        xaxis_title="precio proyectado MXN/m²",
        yaxis_title="velocidad de contagio (%/año)", height=460,
        **_PLOTLY_MARCA)
    st.plotly_chart(fig, width="stretch")


def tab_fases_municipios(valores: np.ndarray, año: float) -> None:
    """Nube de fases de los 2,436 municipios (WebGL)."""
    df = datos_municipales()
    v_t, tasa = estado_en(valores, año)
    fig = go.Figure(go.Scattergl(
        x=v_t, y=tasa * 100, mode="markers",
        marker=dict(size=5, color=df["potencial_crecimiento"],
                    cmin=0, cmax=1, colorscale=ESCALA_PLOTLY,
                    colorbar=dict(title="potencial"), opacity=0.75),
        text=df["municipio"] + " · " + df["estado"],
        hovertemplate="<b>%{text}</b><br>precio $%{x:,.0f}/m²"
                      "<br>contagio +%{y:.1f}%/año<extra></extra>"))
    fig.update_layout(
        title=f"⚗️ Nube de fases municipal — 2,436 células · año {año:.1f}",
        xaxis_title="precio proyectado MXN/m² (síntesis)",
        yaxis_title="velocidad de contagio (%/año)", height=460,
        **_PLOTLY_MARCA)
    st.plotly_chart(fig, width="stretch")


def descomponer_crecimiento(idx: int, v0, potencial, g_propio,
                            pares_i, pares_j, grados, rho, escala_rho,
                            shock_mask, shock_año, shock_fuerza
                            ) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """
    EL ORIGEN DEL CRECIMIENTO, peso por peso. Re-ejecuta el SAR rastreando,
    para la unidad `idx`, cuánto de cada incremento anual viene de:

      · crecimiento PROPIO (su plusvalía/vitalidad intrínseca), y
      · CONTAGIO vecinal (y de CUÁL vecino exactamente).

    Devuelve (df_por_año, aporte_por_vecino_MXN, índices_de_vecinos).
    """
    pot = np.asarray(potencial, dtype=float).copy()
    v = np.asarray(v0, dtype=float).copy()
    g_propio = np.asarray(g_propio, dtype=float)
    vecinos = pares_j[pares_i == idx]
    aporte_vec = np.zeros(len(vecinos))
    filas = []
    for t in range(AÑOS):
        if shock_mask is not None and t == shock_año:
            pot = np.clip(pot + shock_fuerza * shock_mask, 0, 1.35)
        vn = norm01(v)
        g_c = rho * escala_rho * (vn[vecinos].sum() / grados[idx]) * pot[idx]
        filas.append({"año": t + 1,
                      "Propio (MXN/m²)": v[idx] * g_propio[idx],
                      "Contagio vecinal (MXN/m²)": v[idx] * g_c})
        aporte_vec += v[idx] * rho * escala_rho * pot[idx] \
            * vn[vecinos] / grados[idx]
        derrame = np.bincount(pares_i, weights=vn[pares_j],
                              minlength=v.size) / grados
        v = v * (1.0 + g_propio + rho * escala_rho * derrame * pot)
    return pd.DataFrame(filas), aporte_vec, vecinos


def tab_origen(nombres: pd.Series, args_sar: dict, idx_defecto: int,
               unidad: str, banda: np.ndarray = None) -> None:
    """
    Pestaña '¿De dónde viene el crecimiento?': elige una unidad y el motor
    desglosa su plusvalía en crecimiento propio vs contagio, identificando a
    los vecinos exactos que lo bombean. Con rango de confianza P10–P90.
    """
    opciones = list(nombres)
    sel = st.selectbox(f"Elige {unidad} para auditar su crecimiento",
                       opciones, index=int(idx_defecto))
    idx = opciones.index(sel)
    df_a, aporte_vec, vecinos = descomponer_crecimiento(idx=idx, **args_sar)

    total_p = df_a["Propio (MXN/m²)"].sum()
    total_c = df_a["Contagio vecinal (MXN/m²)"].sum()
    total = total_p + total_c + 1e-9
    v0 = float(np.asarray(args_sar["v0"])[idx])

    cols = st.columns(4 if banda is not None else 3)
    cols[0].metric("Crecimiento total a 10 años",
                   f"+${total:,.0f} /m²", f"+{total / v0 * 100:.0f}% sobre hoy")
    cols[1].metric("Crecimiento propio", f"{total_p / total * 100:.0f}%",
                   "plusvalía/vitalidad intrínseca")
    cols[2].metric("Contagio vecinal", f"{total_c / total * 100:.0f}%",
                   f"desde {len(vecinos)} vecinos directos")
    if banda is not None:
        p10 = (banda[0, -1, idx] / v0 - 1) * 100
        p90 = (banda[2, -1, idx] / v0 - 1) * 100
        cols[3].metric("Rango de confianza (10a)",
                       f"+{p10:.0f}% a +{p90:.0f}%",
                       "P10–P90 · Monte Carlo n=24")

    col_a, col_b = st.columns(2)
    with col_a:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_a["año"], y=df_a["Propio (MXN/m²)"],
                             name="Propio", marker_color=ARCILLA_SUAVE))
        fig.add_trace(go.Bar(x=df_a["año"],
                             y=df_a["Contagio vecinal (MXN/m²)"],
                             name="Contagio vecinal", marker_color=LIMA))
        fig.update_layout(barmode="stack",
                          title=f"🔎 Anatomía del crecimiento anual — {sel}",
                          xaxis_title="año",
                          yaxis_title="incremento MXN/m²", height=380,
                          **_PLOTLY_MARCA)
        st.plotly_chart(fig, width="stretch")
    with col_b:
        orden = np.argsort(aporte_vec)[::-1][:10]
        fig2 = go.Figure(go.Bar(
            x=aporte_vec[orden][::-1],
            y=[str(nombres.iloc[v]) for v in vecinos[orden]][::-1],
            orientation="h", marker_color=ARCILLA_SUAVE,
            marker_line=dict(color=LIMA, width=1)))
        fig2.update_layout(
            title="🩸 ¿Quién bombea el contagio? — top vecinos",
            xaxis_title="aporte acumulado MXN/m² (10 años)", height=380,
            **_PLOTLY_MARCA)
        st.plotly_chart(fig2, width="stretch")

    lider, pct_lider = "—", 0.0
    if len(vecinos):
        lider = str(nombres.iloc[vecinos[int(np.argmax(aporte_vec))]])
        pct_lider = aporte_vec.max() / (total_c + 1e-9) * 100
        st.markdown(
            f"<div class='leyenda'>💡 Lectura: el <b>{total_c / total * 100:.0f}%</b> "
            f"del crecimiento de <b>{sel}</b> es contagio vecinal; "
            f"<b>{lider}</b> encabeza ese bombeo con el "
            f"<b>{pct_lider:.0f}%</b> del contagio total.</div>",
            unsafe_allow_html=True)

    # ── Tesis de inversión narrada (el organismo habla) ───────────────────────
    with st.expander("Tesis de inversión narrada"):
        v_fin = v0 + total
        fase_txt = ("mutación temprana — la ventana de entrada está abierta"
                    if total_c / total > 0.55 else
                    "crecimiento orgánico consolidado — menor riesgo, menor alfa")
        st.markdown(f"""
**Tesis BrickBit — {sel}**

*Punto de partida:* ${v0:,.0f}/m² hoy → **${v_fin:,.0f}/m² proyectado a 10
años** (+{total / v0 * 100:.0f}%).

*Anatomía del crecimiento:* el **{total_p / total * 100:.0f}%** es metabolismo
propio (plusvalía/vitalidad intrínseca) y el
**{total_c / total * 100:.0f}%** llega por contagio de sus {len(vecinos)}
vecinos directos. El vector dominante es **{lider}**, responsable del
{pct_lider:.0f}% del contagio: si esa zona sostiene su trayectoria, arrastra
a {sel} con ella — y viceversa: es también su principal exposición.

*Diagnóstico:* {fase_txt}.

*Regla de lectura BrickBit:* comprar contagio temprano (vecino fuerte,
célula aún barata) rinde más que comprar el núcleo ya consolidado.

<span style='color:{TEXTO_SUAVE};font-size:.8rem'>Generado por el motor SAR
con datos {'reales DENUE' if hay_datos_denue() else 'simulados'} —
no es asesoría de inversión.</span>
        """, unsafe_allow_html=True)

    # ── 📄 Dossier descargable de la unidad (entregable de asesoría, PDF) ────
    from datetime import date as _date
    pdf_d = PDFBrickBit(titulo=f"Dossier · {sel}")
    pdf_d.add_page()
    pdf_h1(pdf_d, f"Dossier BrickBit - {sel}")
    pdf_parrafo(pdf_d, "Generado por el Motor de Morfogénesis Urbana · "
                f"{_date.today().isoformat()}", color=PDF_GRIS, estilo="I")
    pdf_h2(pdf_d, "Resumen ejecutivo")
    pdf_vineta(pdf_d, f"Valor hoy: ${v0:,.0f}/m² -> proyección 10 años: "
               f"${v0 + total:,.0f}/m² (+{total / v0 * 100:.0f}%)")
    if banda is not None:
        pdf_vineta(pdf_d, "Rango de confianza (P10-P90): "
                   f"+{(banda[0, -1, idx] / v0 - 1) * 100:.0f}% a "
                   f"+{(banda[2, -1, idx] / v0 - 1) * 100:.0f}%")
    pdf_vineta(pdf_d, f"Anatomía: {total_p / total * 100:.0f}% crecimiento "
               f"propio · {total_c / total * 100:.0f}% contagio de "
               f"{len(vecinos)} vecinos")
    pdf_vineta(pdf_d, f"Vector dominante: {lider} ({pct_lider:.0f}% del "
               "contagio)")
    pdf_h2(pdf_d, "Desglose anual (MXN/m²)")
    pdf_tabla(pdf_d, df_a.apply(lambda s: s.map(lambda v: f"{v:,.0f}")))
    pdf_h2(pdf_d, "Top vecinos que bombean el crecimiento")
    pdf_tabla(pdf_d, pd.DataFrame({
        "Vecino": [str(nombres.iloc[v])
                   for v in vecinos[np.argsort(aporte_vec)[::-1][:8]]],
        "Aporte MXN/m² (10 años)":
            np.sort(aporte_vec)[::-1][:8].round(0).astype(int)}))
    pdf_callout(pdf_d, "Metodología: modelo espacial autorregresivo (SAR) "
                "sobre contigüidad geográfica real; vitalidad económica del "
                "DENUE/INEGI. Las proyecciones son simulaciones calibradas, "
                "no garantía de rendimiento. Este documento no constituye "
                "asesoría de inversión en términos de la regulación "
                "aplicable.")
    st.download_button("Descargar dossier (PDF)", pdf_bytes(pdf_d),
                       file_name=f"dossier_brickbit_{sel[:30].replace(' ', '_')}.pdf",
                       mime="application/pdf")

    # ── 🧭 Lectura para el desarrollador — interpretación accionable ─────────
    # 1) Ventana de entrada: año del pico de crecimiento anual simulado
    incr_anual = (df_a["Propio (MXN/m²)"]
                  + df_a["Contagio vecinal (MXN/m²)"]).to_numpy()
    i_pico = int(np.argmax(incr_anual))
    if i_pico == 0:
        b_ventana = ("<b>Ventana de entrada:</b> el momentum ya está aquí — "
                     "el crecimiento anual simulado arranca en su punto "
                     "máximo. Entrada tardía, paga prima.")
    else:
        año_pico = int(df_a["año"].iloc[i_pico])
        b_ventana = (f"<b>Ventana de entrada:</b> la ola alcanza su punto "
                     f"máximo aquí hacia el año ~{año_pico}: la ventana de "
                     "compra de suelo es ANTES de ese punto.")
    # 2) Contagio del vecindario: valor de la unidad vs sus vecinas directas
    #    + percentil dentro de todo el organismo
    v_todos = np.asarray(args_sar["v0"], dtype=float)
    pctl = float((v_todos <= v0).mean() * 100)
    temperatura = ("caliente" if pctl >= 67
                   else "incubando" if pctl >= 33 else "fría")
    if len(vecinos):
        med_vec = float(v_todos[vecinos].mean())
        rel_vec = ("por debajo de" if v0 < 0.95 * med_vec
                   else "por encima de" if v0 > 1.05 * med_vec
                   else "a la par de")
        b_contagio = (f"<b>Contagio del vecindario:</b> hoy vale {rel_vec} "
                      f"sus vecinas (${v0:,.0f} vs ${med_vec:,.0f}/m² "
                      f"promedio vecinal) y está en el percentil "
                      f"{pctl:.0f} del organismo: <b>{temperatura}</b>.")
    else:
        b_contagio = (f"<b>Contagio del vecindario:</b> está en el percentil "
                      f"{pctl:.0f} del organismo: <b>{temperatura}</b>.")
    # 3) Ancla de realidad: mercado vivo C21 si la unidad empata por slug
    reg_c21 = _c21_registro(sel, cargar_mercado_vivo())
    if reg_c21 is not None and reg_c21.get("pm2v"):
        _nv = int(reg_c21.get("nV") or 0)
        b_ancla = (f"<b>Ancla de realidad:</b> precio real hoy: "
                   f"${float(reg_c21['pm2v']):,.0f}/m² de lista"
                   + (f" ({_nv:,} ventas)" if _nv else "")
                   + " — mercado vivo C21.")
    else:
        b_ancla = ("<b>Ancla de realidad:</b> sin inventario C21 aquí: "
                   "valida precio en campo.")
    st.markdown(
        "<div style='background:#1d1713;border:1px solid #6fa287;"
        "border-radius:10px;padding:0.9rem 1.1rem;margin:0.6rem 0;"
        "color:#f5ede3'>"
        "<b>🧭 Lectura para el desarrollador</b>"
        "<ul style='margin:0.5rem 0 0.4rem 1.1rem;padding:0'>"
        f"<li style='margin-bottom:0.35rem'>{b_ventana}</li>"
        f"<li style='margin-bottom:0.35rem'>{b_contagio}</li>"
        f"<li style='margin-bottom:0.35rem'>{b_ancla}</li>"
        "</ul>"
        "<span style='color:#F5C277;font-size:0.82rem'>Simulación "
        "exploratoria SAR — úsala para priorizar dónde investigar, no como "
        "promesa de plusvalía.</span></div>",
        unsafe_allow_html=True)

    # ── 🔗 Deep links al resto del ecosistema BrickBit ────────────────────────
    # Si la selección empata (por slug) con el inventario vivo C21, saltamos
    # directo a sus herramientas con la zona precargada; si no, al mapa
    # nacional. El nombre viaja TAL CUAL (urlencoded).
    if reg_c21 is not None:
        col_l1, col_l2 = st.columns(2)
        col_l1.link_button(
            "Analizar como inversión →",
            f"https://brickbit.co/analizador.html?zona={quote(sel)}",
            width="stretch")
        col_l2.link_button(
            "Ver propiedades reales →",
            f"https://brickbit.co/mapa.html?zona={quote(sel)}&modo=inmuebles",
            width="stretch")
    else:
        st.link_button("Explorar el inventario nacional →",
                       "https://brickbit.co/mapa.html", width="stretch")
    st.caption("Continúa el análisis con datos vivos en las herramientas "
               "BrickBit.")


def _banda(args: dict, n: int = 24) -> np.ndarray:
    """
    Bandas de confianza por Monte Carlo: re-corre el SAR n veces perturbando
    ρ (±20%), el potencial (σ=0.05) y el crecimiento propio (±15%). Devuelve
    percentiles [P10, P50, P90] × años × células. Sin esto no hay asesoría:
    un número sin rango es una adivinanza con buena tipografía.
    """
    rng = np.random.default_rng(SEMILLA + 11)
    sims = []
    for _ in range(n):
        a = dict(args)
        a["rho"] = args["rho"] * rng.uniform(0.80, 1.20)
        a["potencial"] = np.clip(np.asarray(args["potencial"], dtype=float)
                                 + rng.normal(0, 0.05,
                                              len(args["potencial"])), 0, 1.35)
        a["g_propio"] = np.asarray(args["g_propio"],
                                   dtype=float) * rng.uniform(0.85, 1.15)
        sims.append(_sar(**a))
    return np.percentile(np.stack(sims), [10, 50, 90], axis=0)


@st.cache_data(show_spinner="🎲 Calculando bandas de confianza…", max_entries=4)
def banda_municipios(rho: float, det: str, clic: tuple = None) -> np.ndarray:
    return _banda(_args_municipios(rho, det, clic))


@st.cache_data(show_spinner="🎲 Calculando bandas de confianza…", max_entries=4)
def banda_calles(rho: float, det: str, clic: tuple = None,
                 suffix: str = "azcapotzalco") -> np.ndarray:
    return _banda(_args_calles(rho, det, clic, suffix))


def tab_estancamiento(valores: np.ndarray, año: float) -> None:
    """
    🏚 El lado oscuro del crecimiento: municipios urbanos cuyo tejido
    económico NO se renueva. El inverso del sismógrafo — alerta temprana de
    declive para riesgo crediticio y para NO recomendar una zona.
    """
    df = datos_municipales()
    if "estancado" not in df.columns or not df["estancado"].any():
        st.info("Requiere la vitalidad real del DENUE (denue_municipal.csv).")
        return
    est = df[df["estancado"]].copy()
    est = est.sort_values("tasa_renovacion")
    c1, c2, c3 = st.columns(3)
    c1.metric("Municipios en estancamiento", f"{len(est)}",
              "urbanos, renovación en percentil 15")
    c2.metric("Renovación mediana (estancados)",
              f"{est['tasa_renovacion'].median() * 100:.1f}%",
              f"vs {df.loc[df['n_estab'] >= 300, 'tasa_renovacion'].median() * 100:.1f}% urbano nacional")
    peor = est.iloc[0]
    c3.metric("Caso más frío", f"{peor['municipio']}",
              f"{peor['estado']} · {peor['tasa_renovacion'] * 100:.1f}% renovación")
    st.dataframe(
        est.head(25)[["municipio", "estado", "n_estab", "empleo",
                      "altas_recientes", "tasa_renovacion", "resiliencia"]]
        .rename(columns={"municipio": "Municipio", "estado": "Estado",
                         "n_estab": "Negocios", "empleo": "Empleo",
                         "altas_recientes": "Aperturas recientes",
                         "tasa_renovacion": "Tasa de renovación",
                         "resiliencia": "Resiliencia"}),
        hide_index=True, width="stretch",
        column_config={"Tasa de renovación": st.column_config.NumberColumn(
            format="percent")})
    st.markdown(
        "<div class='leyenda'>🏦 Uso en asesoría: una zona estancada con "
        "precio 'atractivo' es una trampa de valor — el motor la penaliza y "
        "esta lista la expone. También es señal de riesgo para colaterales "
        "hipotecarios. Datos: aperturas recientes del DENUE por negocio "
        "existente.</div>", unsafe_allow_html=True)


def tab_gemelos(nombres: pd.Series, X: np.ndarray, idx_defecto: int,
                unidad: str) -> None:
    """
    🧬 ADN urbano: cada célula tiene un genoma (precio, potencial, mezcla,
    trayectoria). Esta pestaña encuentra sus GEMELOS GENÉTICOS: células con
    el mismo ADN en otro punto del país/ciudad — posibles 'Roma Norte 2012'
    aún baratas.
    """
    opciones = list(nombres)
    sel = st.selectbox(f"Elige {unidad} de referencia", opciones,
                       index=int(idx_defecto), key=f"gemelos_{unidad}")
    idx = opciones.index(sel)
    Xs = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-9)
    ref = Xs[idx]
    sim = (Xs @ ref) / (np.linalg.norm(Xs, axis=1)
                        * np.linalg.norm(ref) + 1e-9)
    sim[idx] = -np.inf
    orden = np.argsort(sim)[::-1][:10]
    st.dataframe(pd.DataFrame({
        "Gemelo genético": [str(nombres.iloc[i]) for i in orden],
        "Similitud de ADN": np.clip(sim[orden], 0, 1),
        "Score BrickBit": [f"{s:.1f}" for s in X[orden, -1] * 10]
        if X.shape[1] else "",
    }), hide_index=True, width="stretch",
        column_config={"Similitud de ADN": st.column_config.ProgressColumn(
            format="percent", min_value=0, max_value=1)})
    st.markdown(f"<div class='leyenda'>🧬 El genoma incluye precio relativo, "
                f"potencial, velocidad de contagio y trayectoria. Un gemelo "
                f"con ADN ≈ al de <b>{sel}</b> pero más barato es la tesis "
                f"de inversión clásica de BrickBit.</div>",
                unsafe_allow_html=True)


def tab_carteras(valores: np.ndarray) -> None:
    """💼 Carteras sintéticas por tesis: canastas de células con retorno
    proyectado y riesgo (dispersión), listas para tokenizar."""
    df = datos_municipales()
    acum = valores[-1] / valores[0] - 1
    tasa = valores[1] / valores[0] - 1
    v5, _ = estado_en(valores, 5.0)
    frente = frente_de_onda(v5, vecindad_municipios())
    tesis = {
        "Anillo periurbano del sureste": (
            df["estado"].isin(["Yucatán", "Quintana Roo", "Campeche"])
            & df["dist_zm_km"].between(8, 45)),
        "Corredor nearshoring norte": (
            df["estado"].isin(["Nuevo León", "Coahuila", "Chihuahua",
                               "Tamaulipas", "Baja California", "Sonora"])
            & (df["dist_zm_km"] < 35)),
        "Frente de onda (LISA)": pd.Series(frente, index=df.index),
    }
    cols = st.columns(3)
    resumen = []
    for col, (nombre, mask) in zip(cols, tesis.items()):
        n = int(mask.sum())
        ret = float(acum[mask].mean() * 100) if n else 0.0
        riesgo = float(acum[mask].std() * 100) if n else 0.0
        top = df.loc[mask].assign(a=acum[mask]).nlargest(4, "a")
        with col:
            st.metric(nombre, f"+{ret:.0f}% / 10 años",
                      f"{n} municipios · σ {riesgo:.0f}%")
            st.markdown("<div class='leyenda'>" + "<br/>".join(
                f"· {m} ({e})" for m, e in zip(top["municipio"],
                                               top["estado"]))
                + "</div>", unsafe_allow_html=True)
        resumen.append((nombre, ret, riesgo))
    fig = go.Figure(go.Bar(
        x=[r[0] for r in resumen], y=[r[1] for r in resumen],
        error_y=dict(type="data", array=[r[2] for r in resumen],
                     color=CREMA),
        marker_color=[LIMA, ARCILLA_SUAVE, ARCILLA]))
    fig.update_layout(title="💼 Retorno proyectado por tesis (± dispersión)",
                      yaxis_title="% acumulado a 10 años", height=340,
                      **_PLOTLY_MARCA)
    st.plotly_chart(fig, width="stretch")
    st.caption("Canastas ilustrativas generadas por el motor — el paso "
               "natural hacia carteras tokenizadas BrickBit por tesis.")


def tab_sismografo(suffix: str = "azcapotzalco") -> None:
    """🌡 Sismógrafo de gentrificación: metabolismo de establecimientos y
    especies indicadoras que anticipan la mutación 2-3 años."""
    sismo, es_real = sismografo_calles(suffix)
    if not es_real:
        st.info("🧪 Churn de demostración. Con dos cortes reales del DENUE "
                "(`ingerir_denue.py --csv-anterior denue_2023.csv`) el "
                "sismógrafo detecta altas/bajas y especies indicadoras "
                "reales calle por calle.")
    top = sismo.nlargest(12, "magnitud")
    c1, c2 = st.columns([2, 3])
    with c1:
        lider = sismo.loc[sismo["magnitud"].idxmax()]
        st.metric("Epicentro de mutación", lider["nombre"],
                  f"{int(lider['indicadoras'])} especies indicadoras")
        st.dataframe(top[["nombre", "altas", "bajas", "especies"]].rename(
            columns={"nombre": "Calle", "altas": "Altas", "bajas": "Bajas",
                     "especies": "Especies indicadoras"}),
            hide_index=True, width="stretch", height=300)
    with c2:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=top["nombre"], y=top["altas"],
                             name="Altas", marker_color=LIMA))
        fig.add_trace(go.Bar(x=top["nombre"], y=-top["bajas"],
                             name="Bajas", marker_color="#8a5a44"))
        fig.add_trace(go.Scatter(x=top["nombre"], y=top["indicadoras"],
                                 name="Especies indicadoras",
                                 mode="markers",
                                 marker=dict(size=12, color=CREMA,
                                             symbol="diamond")))
        fig.update_layout(barmode="relative",
                          title="🌡 Metabolismo por calle (altas/bajas entre "
                                "cortes DENUE)",
                          height=380, **_PLOTLY_MARCA)
        st.plotly_chart(fig, width="stretch")
    st.markdown("<div class='leyenda'>📚 Las <b>especies indicadoras</b> "
                "(café de especialidad, coworking, galería, barbería premium…) "
                "preceden a la plusvalía 2-3 años según la literatura de "
                "gentrificación: son el canario en la mina, pero al revés — "
                "anuncian el oro.</div>", unsafe_allow_html=True)


def _validacion_contagio(suffix: str = "azcapotzalco") -> None:
    """
    Muestra la validación empírica del término espacial del SAR con datos
    reales del DENUE (generada por scripts/backtesting.py denue).
    """
    ruta = RUTA_VALID_TPL.format(s=suffix)
    if not os.path.exists(ruta):
        return
    with open(ruta, encoding="utf-8") as f:
        v = json.load(f)
    st.success(
        f"🔬 **Modelo validado con datos reales del DENUE** — prueba temporal "
        f"out-of-sample sobre {v['celdas']} celdas (corte {v['corte']}): la "
        f"vitalidad económica **propia** predice las aperturas posteriores con "
        f"**r = {v['r_propio']}**, y la de las **celdas vecinas** con "
        f"**r = {v['r_vecinas']}**. El contagio espacial —el término ρ·W·v del "
        f"motor— no es una hipótesis: es medible en la realidad de "
        f"Azcapotzalco.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Predicción propia", f"r = {v['r_propio']}",
              "vitalidad → aperturas")
    c2.metric("Contagio de vecinas", f"r = {v['r_vecinas']}",
              "spillover espacial real")
    c3.metric("Muestra", f"{v['celdas']} celdas",
              f"corte temporal {v['corte']}")


# Giros B2B detectables por palabra clave en el nombre real del negocio
GIROS_B2B = {
    "Farmacia": ["FARMACIA"],
    "Cafetería": ["CAFE", "CAFETERIA"],
    "Gimnasio": ["GIMNASIO", "GYM", "FITNESS", "CROSSFIT"],
    "Veterinaria": ["VETERINAR"],
    "Panadería": ["PANADERIA"],
    "Ferretería": ["FERRETER"],
    "Lavandería": ["LAVANDER"],
    "Consultorio dental": ["DENTAL", "DENTISTA", "ODONTO"],
    "Papelería": ["PAPELER"],
    "Tortillería": ["TORTILLER"],
    "Gasolinera": ["GASOLINER", "COMBUSTIBLE", "ESTACION DE SERVICIO",
                   "PEMEX"],
    "Autolavado": ["AUTOLAVADO", "CAR WASH", "LAVADO DE AUTOS"],
    "Guardería": ["GUARDERIA", "ESTANCIA INFANTIL"],
    "Refaccionaria": ["REFACCION"],
}


@st.cache_data(show_spinner="📍 Buscando la ubicación óptima…", max_entries=8)
def _txt_comp_cercano(m) -> str:
    """'competencia más cercana a 410 m' | 'sin competencia del giro en la ciudad'."""
    try:
        if m is None or (isinstance(m, float) and np.isnan(m)):
            return "sin competencia del giro en la ciudad"
        m = float(m)
    except (TypeError, ValueError):
        return "sin competencia del giro en la ciudad"
    if m >= 1000:
        return f"competencia más cercana a {m / 1000:.1f} km"
    return f"competencia más cercana a {int(m):,} m"


@st.cache_data(show_spinner=False)
def ubicacion_optima(suffix: str, giro: str) -> pd.DataFrame | None:
    """
    📍 MOTOR DE UBICACIÓN B2B: rejilla ~300 m sobre la ciudad; demanda =
    empleo del entorno (clientela cautiva real del DENUE), oferta =
    competidores del giro detectados por nombre. Score = demanda sin atender.
    """
    calles, estab, real = cargar_red_vial(suffix)
    if not real:
        return None
    kws = GIROS_B2B[giro]
    nom = estab["nombre"].fillna("").str.upper()
    es_comp = nom.apply(lambda s: any(k in s for k in kws))

    paso = 0.0028
    gx = np.round(estab["lng"].to_numpy() / paso).astype(int)
    gy = np.round(estab["lat"].to_numpy() / paso).astype(int)
    celda = pd.DataFrame({"gx": gx, "gy": gy,
                          "empleo": estab["empleo"].to_numpy(),
                          "comp": es_comp.to_numpy()})
    agg = celda.groupby(["gx", "gy"]).agg(
        empleo=("empleo", "sum"), comp=("comp", "sum"),
        n=("empleo", "size")).reset_index()
    axv, ayv = agg["gx"].to_numpy(), agg["gy"].to_numpy()
    emp, comp = agg["empleo"].to_numpy(float), agg["comp"].to_numpy(float)
    dem_v, of_v = np.zeros(len(agg)), np.zeros(len(agg))
    for i in range(len(agg)):          # vecindad reina en la rejilla
        m = (np.abs(axv - axv[i]) <= 1) & (np.abs(ayv - ayv[i]) <= 1)
        dem_v[i], of_v[i] = emp[m].sum(), comp[m].sum()
    agg["demanda"], agg["competidores"] = dem_v.astype(int), of_v.astype(int)
    agg = agg[agg["n"] >= 8]           # solo zonas con tejido comercial real
    agg["score"] = norm01(np.log1p(agg["demanda"].to_numpy())
                          / (1 + 1.2 * agg["competidores"].to_numpy()))
    agg["lng"] = (agg["gx"] + 0.5) * paso
    agg["lat"] = (agg["gy"] + 0.5) * paso

    # nombra cada celda con su calle más cercana
    mids = np.array([np.mean(c, axis=0) for c in calles["camino"]])
    idx = [int(np.argmin(np.hypot(mids[:, 0] - x, mids[:, 1] - y)))
           for x, y in zip(agg["lng"], agg["lat"])]
    agg["calle"] = calles["nombre"].to_numpy()[idx]
    top = agg.nlargest(10, "score").reset_index(drop=True)
    # Distancia REAL (metros, haversine) a la competencia más cercana en TODA
    # la ciudad: para decidir un sitio dice más que un conteo en radio fijo.
    comp_pts = estab.loc[es_comp, ["lat", "lng"]].dropna().to_numpy()
    if len(comp_pts):
        la1 = np.radians(top["lat"].to_numpy())[:, None]
        lo1 = np.radians(top["lng"].to_numpy())[:, None]
        la2 = np.radians(comp_pts[:, 0].astype(float))[None, :]
        lo2 = np.radians(comp_pts[:, 1].astype(float))[None, :]
        h = (np.sin((la2 - la1) / 2) ** 2
             + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2)
        top["comp_cercano_m"] = np.round(
            (2 * 6371000.0 * np.arcsin(np.sqrt(h))).min(axis=1))
    else:
        top["comp_cercano_m"] = np.nan
    return top


def clave_tabla_b2b(suffix: str) -> str:
    return f"b2b_tabla_{suffix}"


def clave_tabla_gentri(suffix: str) -> str:
    return f"gentri_tabla_{suffix}"


def _fila_elegida(clave: str):
    """Índice de la fila seleccionada en un st.dataframe, o None.

    Se lee del estado del propio widget, no de una copia guardada, para que el
    mapa —que se dibuja ANTES que las tablas en el guion— ya conozca la
    selección en el mismo rerun del clic. Con una copia iría un clic atrasado.
    """
    ev = st.session_state.get(clave)
    try:
        filas = ev["selection"]["rows"]
    except (KeyError, TypeError):
        return None
    return int(filas[0]) if filas else None


def sitio_marcado(suffix: str):
    """Calle que el usuario seleccionó en alguna tabla, para marcarla en el mapa.

    Dos tablas pueden marcar el mapa —el selector de sitio B2B y el índice de
    gentrificación— y comparten el mismo marcador. Gana la última en el guion
    si ambas tuvieran selección viva.
    """
    i = _fila_elegida(clave_tabla_b2b(suffix))
    giro = st.session_state.get(f"giro_{suffix}")
    if i is not None and giro:
        top = ubicacion_optima(suffix, giro)
        if top is not None and not top.empty and i < len(top):
            f = top.iloc[i]
            return {"rank": i + 1, "calle": str(f["calle"]),
                    "lat": float(f["lat"]), "lng": float(f["lng"]),
                    "fuente": "b2b", "detalle": str(giro)}

    i = _fila_elegida(clave_tabla_gentri(suffix))
    if i is not None:
        g = indice_gentrificacion(suffix)
        if g is not None and not g.empty and i < len(g):
            f = g.iloc[i]
            if pd.notna(f["lat"]) and pd.notna(f["lng"]):
                return {"rank": i + 1, "calle": str(f["nombre"]),
                        "lat": float(f["lat"]), "lng": float(f["lng"]),
                        "fuente": "gentri",
                        "detalle": f"índice {int(f['indice'])}/100"}
    return None


# ══════════════════════════════════════════════════════════════════════════════
# 8D · CANARIOS DE LA PLUSVALÍA · MODO FRANQUICIA · INFORMES PDF (escala calle)
# ══════════════════════════════════════════════════════════════════════════════

# Giros "canario": su llegada precede a la gentrificación (detectados por
# palabra clave en el nombre real DENUE; misma técnica que GIROS_B2B).
GIROS_CANARIO = {
    "Café de especialidad": ["CAFE"],
    "Barbería": ["BARBER"],
    "Galería / arte": ["GALERIA", "ARTE "],
    "Yoga / pilates": ["YOGA", "PILATES"],
    "Coworking": ["COWORK"],
    "Cerveza artesanal / vinoteca": ["CERVEC", "VINOT", "TAP ROOM"],
    "Panadería artesanal": ["PANADER"],
}


@st.cache_data(show_spinner="Buscando canarios de la plusvalía…",
               max_entries=8)
def canarios_calle(suffix: str) -> pd.DataFrame | None:
    """
    Time machine comercial: celdas ~300 m (mismo paso 0.0028 que
    ubicacion_optima) donde ACABAN de llegar giros canario (alta DENUE en los
    últimos 2 años) a un tejido donde antes había pocos. Score 0-100 =
    llegada nueva ponderada por la ausencia previa. Devuelve el top-10 con la
    calle más cercana, las especies recientes y el total histórico.
    """
    calles, estab, real = cargar_red_vial(suffix)
    if not real or estab.empty or "anio" not in estab.columns:
        return None
    nom = estab["nombre"].fillna("").str.upper()
    es_can = np.zeros(len(estab), dtype=bool)
    esp = np.array([""] * len(estab), dtype=object)
    for nombre_esp, kws in GIROS_CANARIO.items():
        m = nom.apply(lambda s: any(k in s for k in kws)).to_numpy() & ~es_can
        es_can |= m
        esp[m] = nombre_esp
    if not es_can.any():
        return None
    can = estab.loc[es_can, ["lng", "lat", "anio"]].copy()
    can["especie"] = esp[es_can]
    anios = pd.to_numeric(estab["anio"], errors="coerce")
    max_anio = int(anios.max())
    can["reciente"] = (pd.to_numeric(can["anio"], errors="coerce")
                       .fillna(0) >= max_anio - 2)

    paso = 0.0028                       # misma rejilla que ubicacion_optima
    can["gx"] = np.round(can["lng"].to_numpy() / paso).astype(int)
    can["gy"] = np.round(can["lat"].to_numpy() / paso).astype(int)
    agg = can.groupby(["gx", "gy"]).agg(
        recientes=("reciente", "sum"), historico=("reciente", "size"),
        lng=("lng", "mean"), lat=("lat", "mean")).reset_index()
    esp_rec = (can[can["reciente"]].groupby(["gx", "gy"])["especie"]
               .agg(lambda s: ", ".join(sorted(set(s)))).rename("especies")
               .reset_index())
    agg = agg.merge(esp_rec, on=["gx", "gy"], how="left")
    agg["especies"] = agg["especies"].fillna("-")
    agg["previos"] = agg["historico"] - agg["recientes"]
    agg = agg[agg["recientes"] >= 1]
    if agg.empty:
        return None
    # llegada nueva donde antes había pocos canarios → señal de despegue
    bruto = agg["recientes"].to_numpy(float) \
        / (1.0 + 0.8 * agg["previos"].to_numpy(float))
    agg["score"] = (norm01(bruto) * 100).round(0).astype(int)

    mids = np.array([np.mean(c, axis=0) for c in calles["camino"]])
    idx = [int(np.argmin(np.hypot(mids[:, 0] - x, mids[:, 1] - y)))
           for x, y in zip(agg["lng"], agg["lat"])]
    agg["calle"] = calles["nombre"].to_numpy()[idx]
    top = agg.sort_values(["score", "recientes"],
                          ascending=False).head(10)
    return top[["calle", "recientes", "especies", "historico", "score",
                "lng", "lat"]].reset_index(drop=True)


@st.cache_data(show_spinner=False, ttl=3600, max_entries=8)
def _listados_zona(slug: str) -> list:
    """Inventario C21 vivo de una zona. Cualquier fallo devuelve [] en
    silencio: esta capa nunca debe tumbar la app."""
    try:
        import requests
        import urllib.parse
        r = requests.get(URL_MERCADO_VIVO.split("?", 1)[0]
                         + "?zona=" + urllib.parse.quote(slug), timeout=8)
        r.raise_for_status()
        d = r.json()
        return d if isinstance(d, list) else []
    except Exception:                                          # noqa: BLE001
        return []


@st.cache_data(show_spinner="Midiendo el gradiente de precio…", ttl=3600,
               max_entries=8)
def gradiente_hedonico(suffix: str, nombre_muni: str) -> dict | None:
    """Cuánto cae el precio/m² por cada km de distancia al foco de empleo.

    MEDIDO, no supuesto. Los catalizadores del simulador usan hoy una `fuerza`
    y un `radio` que alguien eligió a mano; esto es la contraparte empírica:
    se toma el inventario C21 vivo de la zona (precio y coordenadas reales),
    se calcula la distancia de cada propiedad al ancla de empleo más cercana
    del DENUE, y se ajusta log(precio/m²) = a + b·km por mínimos cuadrados.

    Devuelve el gradiente en % por km con su R², el n y el intervalo del 90%
    del coeficiente. Es CORRELACIONAL: mide cómo varían hoy los precios con la
    distancia, no lo que pasaría si se construyera un ancla nueva. Con menos de
    40 propiedades no devuelve nada, porque el ajuste no se sostendría.
    """
    props = _listados_zona(slugificar(nombre_muni))
    if not props or len(props) < 40:
        return None
    filas = [p for p in props
             if isinstance(p, dict) and p.get("operacion") == "venta"
             and isinstance(p.get("pm2"), (int, float)) and 3000 < p["pm2"] < 200000
             and isinstance(p.get("lat"), (int, float))
             and isinstance(p.get("lng"), (int, float))]
    if len(filas) < 40:
        return None
    anc = anclas_municipio(suffix)
    if anc is None or anc.empty:
        return None

    lat = np.radians(np.array([f["lat"] for f in filas], dtype=float))
    lng = np.radians(np.array([f["lng"] for f in filas], dtype=float))
    ala = np.radians(anc["lat"].to_numpy(dtype=float))[None, :]
    alo = np.radians(anc["lng"].to_numpy(dtype=float))[None, :]
    h = (np.sin((ala - lat[:, None]) / 2) ** 2
         + np.cos(lat[:, None]) * np.cos(ala) * np.sin((alo - lng[:, None]) / 2) ** 2)
    km = (2 * 6371.0 * np.arcsin(np.sqrt(h))).min(axis=1)
    y = np.log(np.array([f["pm2"] for f in filas], dtype=float))

    # recorte de colas: un outlier de precio o una propiedad a 60 km del centro
    # dominarían la pendiente de una muestra de unos cientos
    ok = (km <= np.quantile(km, 0.97)) & (y >= np.quantile(y, 0.02)) \
        & (y <= np.quantile(y, 0.98))
    km, y = km[ok], y[ok]
    n = int(len(km))
    if n < 40 or km.std() < 0.2:
        return None

    b, a = np.polyfit(km, y, 1)
    pred = a + b * km
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    # error estándar de la pendiente e intervalo del 90% (t≈1.645 con n grande)
    se = float(np.sqrt(ss_res / max(n - 2, 1) / ((km - km.mean()) ** 2).sum()))
    return {
        "pct_km": float((np.exp(b) - 1) * 100),
        "ic_bajo": float((np.exp(b - 1.645 * se) - 1) * 100),
        "ic_alto": float((np.exp(b + 1.645 * se) - 1) * 100),
        "r2": float(r2), "n": n,
        "km_medio": float(km.mean()), "km_max": float(km.max()),
        "pm2_en_ancla": float(np.exp(a)),
    }


@st.cache_data(show_spinner="Midiendo gentrificación temprana…", max_entries=8)
def indice_gentrificacion(suffix: str) -> pd.DataFrame | None:
    """Índice compuesto de gentrificación TEMPRANA, por calle.

    Tres señales observadas del DENUE, no una predicción:
      · Canarios — llegada reciente (últimos 2 años de alta) de los giros que
        preceden al despegue, donde antes casi no había. Es la señal adelantada.
      · Saldo — aperturas menos cierres de la calle. Un tejido que crece neto
        aguanta el cambio; uno que se vacía no está gentrificándose, se está
        muriendo, y sin esto el índice confundiría las dos cosas.
      · Especies indicadoras — cuántos giros del catálogo ya operan ahí.

    Deliberadamente NO entra el precio: el inventario C21 da mediana por ZONA,
    no por calle, y mezclar una señal de calle con una de ciudad produciría un
    número que parece más fino de lo que es. El precio se muestra aparte, como
    contexto de la ciudad.

    Es una SEÑAL, no una predicción validada: con un solo corte del DENUE se
    puede reconstruir cuándo llegó cada negocio, pero no contrastar el índice
    contra lo que pasó después con los precios de esa calle.
    """
    can = canarios_calle(suffix)
    sis, real = sismografo_calles(suffix)
    if not real or sis is None or sis.empty:
        return None

    base = sis[["nombre", "altas", "bajas", "indicadoras"]].copy()
    base["saldo"] = base["altas"].to_numpy() - base["bajas"].to_numpy()
    # el score de canarios vive en celdas de ~300 m, nombradas por su calle más
    # cercana: se queda el máximo por calle
    if can is not None and not can.empty:
        porc = can.groupby("calle").agg(
            canarios=("score", "max"), recientes=("recientes", "sum"),
            especies_nuevas=("especies", "first")).reset_index()
        base = base.merge(porc, left_on="nombre", right_on="calle", how="left")
    else:
        base[["canarios", "recientes", "especies_nuevas"]] = [0.0, 0, "—"]
    base["canarios"] = base["canarios"].fillna(0.0)
    base["recientes"] = base["recientes"].fillna(0).astype(int)
    base["especies_nuevas"] = base["especies_nuevas"].fillna("—")
    # Las coordenadas salen de la GEOMETRÍA de la calle, no de las celdas de
    # canarios: una calle puede entrar al índice por saldo o por especies ya
    # instaladas, sin canarios recientes, y aun así hay que poder señalarla en
    # el mapa. Tomarlas del merge dejaba esas filas sin punto.
    calles_geo, _, _ = cargar_red_vial(suffix)
    medio = {str(n): [float(np.mean([p[0] for p in c])),
                      float(np.mean([p[1] for p in c]))]
             for n, c in zip(calles_geo["nombre"], calles_geo["camino"])}
    base["lng"] = [medio.get(str(n), [np.nan, np.nan])[0] for n in base["nombre"]]
    base["lat"] = [medio.get(str(n), [np.nan, np.nan])[1] for n in base["nombre"]]

    # Sin canarios en toda la ciudad no hay señal adelantada que reportar.
    if base["canarios"].max() <= 0:
        return None
    base["indice"] = (100 * (
        0.50 * norm01(base["canarios"].to_numpy(float))
        + 0.30 * norm01(np.clip(base["saldo"].to_numpy(float), 0, None))
        + 0.20 * norm01(base["indicadoras"].to_numpy(float))
    )).round(0).astype(int)

    top = base[base["indice"] > 0].sort_values(
        ["indice", "recientes"], ascending=False).head(12)
    return top[["nombre", "indice", "canarios", "recientes", "saldo",
                "indicadoras", "especies_nuevas", "lng", "lat"]].reset_index(
        drop=True)


@st.cache_data(max_entries=8)
def rejilla_demanda(suffix: str) -> pd.DataFrame | None:
    """
    Rejilla de demanda ~300 m (idéntica a la de ubicacion_optima, sin giro):
    demanda = empleo DENUE del entorno (vecindad reina), con la calle más
    cercana como nombre. Base del análisis de cobertura de una red.
    """
    calles, estab, real = cargar_red_vial(suffix)
    if not real or estab.empty:
        return None
    paso = 0.0028
    gx = np.round(estab["lng"].to_numpy() / paso).astype(int)
    gy = np.round(estab["lat"].to_numpy() / paso).astype(int)
    celda = pd.DataFrame({"gx": gx, "gy": gy,
                          "empleo": estab["empleo"].to_numpy()})
    agg = celda.groupby(["gx", "gy"]).agg(
        empleo=("empleo", "sum"), n=("empleo", "size")).reset_index()
    axv, ayv = agg["gx"].to_numpy(), agg["gy"].to_numpy()
    emp = agg["empleo"].to_numpy(float)
    dem = np.zeros(len(agg))
    for i in range(len(agg)):
        m = (np.abs(axv - axv[i]) <= 1) & (np.abs(ayv - ayv[i]) <= 1)
        dem[i] = emp[m].sum()
    agg["demanda"] = dem.astype(int)
    agg = agg[agg["n"] >= 8]
    if agg.empty:
        return None
    agg["lng"] = (agg["gx"] + 0.5) * paso
    agg["lat"] = (agg["gy"] + 0.5) * paso
    mids = np.array([np.mean(c, axis=0) for c in calles["camino"]])
    idx = [int(np.argmin(np.hypot(mids[:, 0] - x, mids[:, 1] - y)))
           for x, y in zip(agg["lng"], agg["lat"])]
    agg["calle"] = calles["nombre"].to_numpy()[idx]
    return agg[["lng", "lat", "demanda", "calle"]].reset_index(drop=True)


def _haversine_m(lat1, lng1, lat2, lng2) -> np.ndarray:
    """Distancia haversine en metros (vectorizada)."""
    la1, lo1, la2, lo2 = map(np.radians, (np.asarray(lat1, float),
                                          np.asarray(lng1, float),
                                          np.asarray(lat2, float),
                                          np.asarray(lng2, float)))
    a = (np.sin((la2 - la1) / 2) ** 2
         + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2)
    return 6371000.0 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def parsear_sucursales(texto: str, archivo=None
                       ) -> tuple[pd.DataFrame, int, int]:
    """
    Parse defensivo de sucursales `lat,lng[,nombre]` desde texto pegado y/o
    CSV subido. Ignora líneas malas; devuelve (df, leídas, intentadas).
    """
    filas, intentadas = [], 0

    def _agregar(lat, lng, nombre):
        try:
            lat, lng = float(lat), float(lng)
        except (TypeError, ValueError):
            return False
        if not (-90 <= lat <= 90 and -180 <= lng <= 180) \
                or not (math.isfinite(lat) and math.isfinite(lng)):
            return False
        nom = str(nombre).strip() if nombre is not None else ""
        if not nom or nom.lower() == "nan":
            nom = f"Sucursal {len(filas) + 1}"
        filas.append({"nombre": nom[:40], "lat": lat, "lng": lng})
        return True

    for linea in (texto or "").splitlines():
        li = linea.strip()
        if not li or li.lower().startswith("lat"):
            continue
        intentadas += 1
        partes = [p.strip() for p in li.split(",")]
        if len(partes) >= 2:
            _agregar(partes[0], partes[1],
                     partes[2] if len(partes) > 2 else None)
    if archivo is not None:
        try:
            dfc = pd.read_csv(archivo)
            dfc.columns = [str(c).strip().lower() for c in dfc.columns]
            if "lat" in dfc.columns and "lng" in dfc.columns:
                for _, r in dfc.iterrows():
                    intentadas += 1
                    _agregar(r.get("lat"), r.get("lng"), r.get("nombre"))
        except Exception:                                  # noqa: BLE001
            pass
    return pd.DataFrame(filas, columns=["nombre", "lat", "lng"]), \
        len(filas), intentadas


def canibalizacion_red(suc: pd.DataFrame,
                       umbral_m: float = 600.0) -> pd.DataFrame:
    """Pares de sucursales a menos de `umbral_m` metros (haversine)."""
    pares = []
    for i in range(len(suc)):
        for j in range(i + 1, len(suc)):
            d = float(_haversine_m(suc["lat"].iloc[i], suc["lng"].iloc[i],
                                   suc["lat"].iloc[j], suc["lng"].iloc[j]))
            if d < umbral_m:
                pares.append({"Sucursal A": suc["nombre"].iloc[i],
                              "Sucursal B": suc["nombre"].iloc[j],
                              "Distancia (m)": int(round(d))})
    return pd.DataFrame(pares,
                        columns=["Sucursal A", "Sucursal B",
                                 "Distancia (m)"]).sort_values(
        "Distancia (m)").reset_index(drop=True) if pares else \
        pd.DataFrame(columns=["Sucursal A", "Sucursal B", "Distancia (m)"])


def huecos_cobertura(suffix: str, suc: pd.DataFrame,
                     radio_km: float = 1.2, n: int = 5
                     ) -> pd.DataFrame | None:
    """
    Huecos de cobertura: las `n` celdas de demanda (rejilla ~300 m) con más
    empleo que quedan a más de `radio_km` de TODA sucursal de la red.
    """
    rej = rejilla_demanda(suffix)
    if rej is None or rej.empty or suc is None or suc.empty:
        return None
    dmin = np.full(len(rej), np.inf)
    for _, s in suc.iterrows():
        d = _haversine_m(rej["lat"].to_numpy(), rej["lng"].to_numpy(),
                         s["lat"], s["lng"])
        dmin = np.minimum(dmin, d)
    lejos = rej.assign(dist_m=dmin)[dmin > radio_km * 1000]
    if lejos.empty:
        return lejos.assign(**{"Distancia a la red (km)": []})[
            ["calle", "demanda", "Distancia a la red (km)", "lng", "lat"]]
    top = lejos.nlargest(n, "demanda").copy()
    top["Distancia a la red (km)"] = (top["dist_m"] / 1000).round(2)
    return top[["calle", "demanda", "Distancia a la red (km)",
                "lng", "lat"]].reset_index(drop=True)


def _meta_municipio(suffix: str) -> tuple[str, str]:
    """(municipio, estado) reales desde data/calles_<suffix>.json."""
    muni, edo = suffix.replace("_", " ").title(), ""
    try:
        with open(RUTA_CALLES_TPL.format(s=suffix), encoding="utf-8") as f:
            meta = json.load(f)
        muni = meta.get("municipio", muni)
        edo = meta.get("estado", "")
    except (OSError, json.JSONDecodeError):
        pass
    return muni, edo


def _sin_acentos_minusculas(texto: str) -> str:
    t = unicodedata.normalize("NFD", str(texto))
    return "".join(c for c in t
                   if unicodedata.category(c) != "Mn").lower().strip()


_ETIQUETAS_SEQUIA = {0: "Sin sequía", 1: "D0 - anormalmente seco",
                     2: "D1 - sequía moderada", 3: "D2 - sequía severa",
                     4: "D3 - sequía extrema", 5: "D4 - sequía excepcional"}


def sequia_municipio(muni: str, edo: str) -> tuple[int, str] | None:
    """
    Nivel de sequía CONAGUA del municipio desde data/agua.json (clave
    'municipio|entidad' normalizada sin acentos, minúsculas). None si no
    empata o el archivo no existe — jamás se inventa.
    """
    try:
        with open(os.path.join(_DIR, "data", "agua.json"),
                  encoding="utf-8") as f:
            agua = json.load(f)
        clave = (f"{_sin_acentos_minusculas(muni)}|"
                 f"{_sin_acentos_minusculas(edo)}")
        nivel = agua.get("municipios", {}).get(clave)
        if nivel is None:
            return None
        nivel = int(nivel)
        return nivel, _ETIQUETAS_SEQUIA.get(nivel, f"nivel {nivel}")
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def informe_sitio_pdf(suffix: str, giro: str) -> bytes:
    """
    Informe de selección de sitio (PDF multipágina): portada + resumen,
    análisis del top-10, contexto del municipio (DENUE + mercado vivo C21 +
    sequía CONAGUA cuando empatan) y metodología con descargos. Se construye
    100% con datos locales/cacheados: si algo no empata, se omite.
    """
    from datetime import date as _date
    calles, estab, real = cargar_red_vial(suffix)
    top = ubicacion_optima(suffix, giro)
    can = canarios_calle(suffix)
    muni, edo = _meta_municipio(suffix)
    ciudad = muni + (f", {edo}" if edo else "")

    pdf = PDFBrickBit(titulo=f"Informe de sitio · {muni}")

    # ── PÁG 1 · portada + resumen ejecutivo ──────────────────────────────────
    pdf_portada(pdf, "Informe de selección de sitio",
                f"{giro} en {ciudad}")
    if top is None or top.empty:
        pdf_parrafo(pdf, "No se encontraron celdas con tejido comercial "
                    "suficiente para este giro en esta ciudad.")
        mejor = None
    else:
        mejor = top.iloc[0]
        pdf_h2(pdf, "Resumen ejecutivo")
        pdf_vineta(pdf, f"Mejor sitio: {mejor['calle']}")
        pdf_vineta(pdf, "Score de demanda desatendida: "
                   f"{mejor['score'] * 100:.0f}/100")
        pdf_vineta(pdf, f"Demanda: {int(mejor['demanda']):,} empleos DENUE "
                   "en el entorno (~450 m, clientela cautiva)")
        pdf_vineta(pdf, "Distancia a la competencia: "
               + _txt_comp_cercano(mejor.get("comp_cercano_m")))
        n_comp_ciudad = int(top["competidores"].sum())
        frase_can = ""
        if can is not None and not can.empty:
            frase_can = (f"Además, {can['calle'].iloc[0]} muestra llegada "
                         "reciente de giros canario (señal temprana de "
                         "gentrificación) a corta distancia del tejido "
                         "analizado.")
        else:
            frase_can = ("No se detectan señales de gentrificación temprana "
                         "relevantes: la tesis se sostiene en demanda "
                         "laboral, no en moda.")
        conclusiones = (
            f"1) {mejor['calle']} concentra {int(mejor['demanda']):,} "
            f"empleos de clientela cautiva con solo "
            f"{int(mejor['competidores'])} competidores de {giro}: la mejor "
            "relación demanda/oferta de la ciudad. "
            f"2) En el conjunto del top-10 se observan "
            f"{n_comp_ciudad} competidores del giro: hay espacio real antes "
            "de saturar. "
            f"3) {frase_can}")
        pdf_h2(pdf, "Conclusiones")
        pdf_parrafo(pdf, conclusiones)

    # ── PÁG 2 · análisis del top-10 ──────────────────────────────────────────
    pdf.add_page()
    pdf_h1(pdf, "Análisis: los 10 mejores sitios")
    if top is not None and not top.empty:
        tabla = pd.DataFrame({
            "#": range(1, len(top) + 1),
            "Calle": top["calle"],
            "Empleos": top["demanda"].astype(int).map("{:,}".format),
            "Comp. cercana": [_txt_comp_cercano(m).replace(
                "competencia más cercana a ", "").replace(
                "sin competencia del giro en la ciudad", "sin comp.")
                for m in top.get("comp_cercano_m", [np.nan] * len(top))],
            "Score": (top["score"] * 100).round(0).astype(int),
            "Por qué": [f"{int(d):,} empleos alrededor · {_txt_comp_cercano(m)}"
                        for d, m in zip(top["demanda"],
                                        top.get("comp_cercano_m",
                                                [np.nan] * len(top)))]})
        pdf_tabla(pdf, tabla)
        pdf_h2(pdf, "Lectura del número 1")
        pdf_parrafo(pdf, f"{mejor['calle']} encabeza el ranking porque "
                    f"combina la mayor demanda desatendida "
                    f"({int(mejor['demanda']):,} empleos formales alrededor) "
                    f"con la {_txt_comp_cercano(mejor.get('comp_cercano_m'))} "
                    f"para el giro {giro} (detección por nombre comercial). "
                    "El empleo cercano es clientela cautiva de lunes a "
                    "viernes.")
        if len(top) >= 3:
            alt = top.iloc[1:3]
            pdf_h2(pdf, "Alternativas 2 y 3")
            pdf_parrafo(
                pdf,
                f"Si el sitio 1 no consigue local o el uso de suelo no lo "
                f"permite, {alt['calle'].iloc[0]} "
                f"({int(alt['demanda'].iloc[0]):,} empleos, "
                f"{int(alt['competidores'].iloc[0])} competidores) y "
                f"{alt['calle'].iloc[1]} "
                f"({int(alt['demanda'].iloc[1]):,} empleos, "
                f"{int(alt['competidores'].iloc[1])} competidores) ofrecen "
                "un perfil demanda/competencia comparable.")
    else:
        pdf_parrafo(pdf, "Sin celdas candidatas para este giro.")
    if can is not None and not can.empty:
        pdf_h2(pdf, "Señales de gentrificación temprana cercanas")
        for _, c in can.head(3).iterrows():
            pdf_vineta(pdf, f"{c['calle']}: {int(c['recientes'])} negocios "
                       f"canario en los últimos 2 años ({c['especies']}); "
                       f"score {int(c['score'])}/100")
        pdf_parrafo(pdf, "La llegada de estos giros suele preceder a los "
                    "despegues de precio; es señal exploratoria, no "
                    "garantía.", color=PDF_GRIS, estilo="I")

    # ── PÁG 3 · contexto del municipio ───────────────────────────────────────
    pdf.add_page()
    pdf_h1(pdf, f"Contexto del municipio: {ciudad}")
    pdf_h2(pdf, "Tejido económico (DENUE/INEGI)")
    pdf_vineta(pdf, f"Establecimientos registrados: {len(estab):,}")
    if "empleo" in estab.columns:
        pdf_vineta(pdf, "Empleo formal estimado por estratos: "
                   f"{int(estab['empleo'].sum()):,} puestos")
    pdf_vineta(pdf, f"Calles con actividad mapeadas: {len(calles):,}")
    if "anio" in estab.columns:
        pdf_vineta(pdf, "Corte del CSV DENUE: altas registradas hasta "
                   f"{int(pd.to_numeric(estab['anio'], errors='coerce').max())}")
    reg = _c21_registro(f"{muni} · {edo}" if edo else muni,
                        cargar_mercado_vivo())
    if reg is not None and reg.get("pm2v"):
        pdf_h2(pdf, "Mercado vivo Century 21 (precios de lista, "
               "refresco diario)")
        pdf_vineta(pdf, f"Mediana de venta: ${float(reg['pm2v']):,.0f}/m²")
        _nv = int(reg.get("nV") or 0)
        if _nv:
            pdf_vineta(pdf, f"Inventario en venta observado: {_nv:,} "
                       "propiedades")
        _yld = reg.get("yield") or reg.get("yld") or reg.get("yieldReal")
        if _yld:
            pdf_vineta(pdf, f"Yield bruto real (renta/venta): "
                       f"{float(_yld):.1f}% anual")
    agua = sequia_municipio(muni, edo)
    if agua is not None:
        nivel, etiqueta = agua
        pdf_h2(pdf, "Contexto hídrico (Monitor de Sequía CONAGUA/SMN)")
        pdf_vineta(pdf, f"Nivel de sequía del municipio: {etiqueta}")
        if nivel >= 3:
            nota_agua = ("El municipio está en sequía severa o peor: trata "
                         "la factibilidad hídrica como riesgo de proyecto y "
                         "confírmala con el organismo operador ANTES de "
                         "firmar.")
        elif nivel >= 1:
            nota_agua = ("Hay condición de sequía ligera/moderada: la "
                         "factibilidad de servicio la dicta el organismo "
                         "operador local; confírmala en la prospección.")
        else:
            nota_agua = ("Sin sequía al corte vigente. Aun así, la dotación "
                         "de agua de un local la dicta el organismo "
                         "operador local.")
        pdf_parrafo(pdf, nota_agua, color=PDF_GRIS)

    # ── PÁG 4 · metodología y descargos ──────────────────────────────────────
    pdf.add_page()
    pdf_h1(pdf, "Metodología y descargos")
    pdf_h2(pdf, "Cómo se calcula")
    pdf_parrafo(pdf, "Demanda: suma de empleo DENUE en la celda de ~300 m y "
                "sus 8 vecinas (radio efectivo ~450 m): la clientela "
                "cautiva que trabaja alrededor del sitio. Competencia: "
                "establecimientos del giro detectados por palabra clave en "
                "su nombre comercial real. Score: log(1+demanda) / "
                "(1 + 1.2 x competidores), normalizado 0-100; premia "
                "demanda alta sin oferta. Solo se consideran celdas con "
                "tejido comercial real (8+ establecimientos).")
    pdf_parrafo(pdf, "Canarios de la plusvalía: giros indicadores (café de "
                "especialidad, barbería, galería, yoga/pilates, coworking, "
                "cerveza artesanal, panadería artesanal) con alta DENUE en "
                "los últimos 2 años, ponderados donde antes había pocos: "
                "llegada nueva, no stock viejo.")
    pdf_h2(pdf, "Fuentes")
    pdf_vineta(pdf, "DENUE / INEGI: establecimientos, empleo por estratos y "
               "año de alta (corte del CSV ingerido)")
    pdf_vineta(pdf, "Century 21 México: medianas de precios de lista, con "
               "autorización, refresco diario (cuando el municipio empata)")
    pdf_vineta(pdf, "CONAGUA / SMN: Monitor de Sequía de México, corte "
               "municipal quincenal (cuando el municipio empata)")
    pdf_callout(pdf, "Este informe es un FILTRO DE PROSPECCIÓN estadística, "
                "no un estudio de mercado terminado: valida en campo el "
                "flujo peatonal, el uso de suelo y la normativa local antes "
                "de decidir. La competencia se detecta por nombre comercial "
                "y puede omitir negocios con nombres atípicos. BrickBit no "
                "garantiza resultados comerciales.")
    return pdf_bytes(pdf)


def informe_red_pdf(suffix: str, suc: pd.DataFrame, pares: pd.DataFrame,
                    huecos: pd.DataFrame | None) -> bytes:
    """Informe de red de sucursales (PDF, 2 páginas): resumen de
    canibalización y huecos + metodología con descargo honesto."""
    muni, edo = _meta_municipio(suffix)
    ciudad = muni + (f", {edo}" if edo else "")
    pdf = PDFBrickBit(titulo=f"Informe de red · {muni}")

    # ── PÁG 1 · resumen de la red ────────────────────────────────────────────
    pdf.add_page()
    pdf_h1(pdf, f"Informe de red de sucursales - {ciudad}")
    pdf_h2(pdf, "Resumen")
    pdf_vineta(pdf, f"Sucursales analizadas: {len(suc)}")
    pdf_vineta(pdf, "Pares en riesgo de canibalización (<600 m): "
               f"{0 if pares is None else len(pares)}")
    n_huecos = 0 if huecos is None or huecos.empty else len(huecos)
    pdf_vineta(pdf, f"Huecos de cobertura detectados (>1.2 km de toda "
               f"sucursal): {n_huecos}")
    if pares is not None and not pares.empty:
        pdf_h2(pdf, "Canibalización: pares a menos de 600 m")
        pdf_tabla(pdf, pares)
    else:
        pdf_h2(pdf, "Canibalización")
        pdf_parrafo(pdf, "Ningún par de sucursales queda a menos de 600 m: "
                    "sin canibalización geométrica aparente.")
    if huecos is not None and not huecos.empty:
        pdf_h2(pdf, "Huecos de cobertura: demanda lejos de tu red")
        pdf_tabla(pdf, huecos.rename(columns={
            "calle": "Calle", "demanda": "Empleos (demanda)"})[
            ["Calle", "Empleos (demanda)", "Distancia a la red (km)"]])
    else:
        pdf_h2(pdf, "Huecos de cobertura")
        pdf_parrafo(pdf, "Toda la demanda relevante queda a menos de 1.2 km "
                    "de alguna sucursal (o no hay rejilla de demanda para "
                    "esta ciudad).")

    # ── PÁG 2 · metodología + descargo ───────────────────────────────────────
    pdf.add_page()
    pdf_h1(pdf, "Metodología y alcance")
    pdf_parrafo(pdf, "Canibalización: distancia haversine entre cada par de "
                "sucursales; se reporta todo par a menos de 600 m. Huecos: "
                "rejilla de demanda de ~300 m sobre el empleo DENUE "
                "(vecindad reina, radio efectivo ~450 m); se reportan las 5 "
                "celdas con más demanda cuya distancia a TODA sucursal "
                "supera 1.2 km, nombradas por su calle más cercana.")
    pdf_vineta(pdf, "Fuente de demanda: DENUE / INEGI (empleo por estratos, "
               "corte del CSV ingerido)")
    pdf_vineta(pdf, "Coordenadas de sucursales: proporcionadas por el "
               "usuario, sin verificación en campo")
    pdf_callout(pdf, "Análisis geométrico sobre demanda DENUE: la "
                "canibalización real depende de tu ticket promedio, tu "
                "catchment y las barreras urbanas (avenidas, ríos, vías). "
                "Úsalo como radiografía inicial de la red, no como decisión "
                "final. BrickBit no garantiza resultados comerciales.")
    return pdf_bytes(pdf)


@st.cache_data(show_spinner="🧪 Midiendo el impacto real de las anclas…")
def impacto_anclas(suffix: str) -> pd.DataFrame | None:
    """
    🧪 EVENT STUDY con datos reales: para cada gran empleador que abrió entre
    2022 y 2024, compara la tasa de aperturas a <400 m ANTES vs DESPUÉS de su
    llegada, normalizada por la tendencia de toda la ciudad (diferencia en
    diferencias simple). El 'multiplicador de atracción' deja de ser un
    supuesto del simulador: se MIDE.
    """
    _, estab, real = cargar_red_vial(suffix)
    if not real or "anio" not in estab.columns:
        return None
    e = estab.dropna(subset=["anio", "lng", "lat"]).copy()
    e["anio"] = e["anio"].astype(int)
    tot = e.groupby("anio").size()
    anclas = e[(e["empleo"] >= 75) & e["anio"].between(2022, 2024)]
    lng, lat, an = e["lng"].to_numpy(), e["lat"].to_numpy(), e["anio"].to_numpy()
    filas = []
    for _, a in anclas.iterrows():
        d = np.hypot(lng - a["lng"], lat - a["lat"])
        cerca = (d < 0.004) & (d > 1e-9)         # ~400 m, sin contar el ancla
        y = int(a["anio"])
        antes_l = int(((an >= y - 2) & (an <= y - 1) & cerca).sum())
        desp_l = int(((an >= y + 1) & (an <= y + 2) & cerca).sum())
        antes_c = int(tot.reindex(range(y - 2, y), fill_value=0).sum())
        desp_c = int(tot.reindex(range(y + 1, y + 3), fill_value=0).sum())
        if antes_l >= 3 and antes_c > 0 and desp_c > 0 and desp_l > 0:
            mult = (desp_l / antes_l) / (desp_c / antes_c)
            filas.append({"Ancla": str(a["nombre"]).title()[:34],
                          "Año llegada": y,
                          "Aperturas antes (2a)": antes_l,
                          "Aperturas después (2a)": desp_l,
                          "Multiplicador medido": round(mult, 2)})
    if not filas:
        return pd.DataFrame()
    return pd.DataFrame(filas).sort_values("Multiplicador medido",
                                           ascending=False)


def bloque_gradiente(suffix: str, nombre_muni: str) -> None:
    """El precio contra la distancia al foco de empleo, MEDIDO en el mercado.

    Es la contraparte empírica de los catalizadores del simulador, cuya fuerza
    y radio son parámetros elegidos a mano. Aquí no hay perilla: la pendiente
    sale del inventario C21 vivo de esta ciudad.
    """
    g = gradiente_hedonico(suffix, nombre_muni)
    st.markdown("##### Gradiente de precio por distancia · medido en el mercado")
    if not g:
        st.info("Aún no hay inventario C21 suficiente en esta ciudad para "
                "medir el gradiente (se necesitan 40+ propiedades en venta "
                "con precio/m² y coordenadas). En cuanto el inventario diario "
                "las acumule, aparece solo.")
        return
    signo = "menos" if g["pct_km"] < 0 else "más"
    c1, c2, c3 = st.columns(3)
    c1.metric("Gradiente", f"{g['pct_km']:+.1f}% / km",
              f"IC 90%: {g['ic_bajo']:+.1f}% a {g['ic_alto']:+.1f}%")
    c2.metric("Ajuste (R²)", f"{g['r2']:.2f}",
              f"{g['n']} propiedades")
    c3.metric("Precio/m² junto al ancla", f"${g['pm2_en_ancla']:,.0f}",
              f"alcance medido: {g['km_max']:.1f} km")
    st.markdown(
        f"<div class='leyenda'>En <b>{nombre_muni}</b>, cada kilómetro de "
        f"distancia al foco de empleo más cercano se asocia con "
        f"<b>{abs(g['pct_km']):.1f}% {signo}</b> de precio por m², sobre "
        f"{g['n']} propiedades reales en venta del inventario Century 21. "
        "Este número sustituye a la intuición: los catalizadores del simulador "
        "usan una fuerza y un radio elegidos a mano; esto es lo que el mercado "
        "de esta ciudad realmente hace.</div>", unsafe_allow_html=True)
    if g["r2"] < 0.15:
        st.warning(
            f"El ajuste es débil (R² {g['r2']:.2f}): la distancia al empleo "
            "explica poco del precio aquí. En ciudades policéntricas o "
            "turísticas manda más la playa, la vista o la colonia que la "
            "cercanía al trabajo. Tómalo como referencia floja, no como regla.",
            icon="⚠️")
    st.caption("Es CORRELACIONAL: mide cómo varían hoy los precios con la "
               "distancia, no lo que pasaría si se construyera un ancla nueva. "
               "No controla por antigüedad, superficie ni calidad del inmueble.")
    st.markdown("---")


def tab_impacto(suffix: str) -> None:
    """🧪 El detonante deja de ser hipótesis: impacto medido de anclas reales."""
    df = impacto_anclas(suffix)
    if df is None:
        st.info("Requiere datos reales del DENUE con año de alta.")
        return
    if df.empty:
        st.info("Esta ciudad no tiene suficientes anclas grandes (75+ "
                "empleos) llegadas en 2022-2024 con tejido previo medible. "
                "Prueba otra ciudad (las metrópolis grandes tienen más).")
        return
    med = float(df["Multiplicador medido"].median())
    c1, c2, c3 = st.columns(3)
    c1.metric("Multiplicador de atracción medido", f"{med:.2f}×",
              "mediana de anclas reales")
    c2.metric("Anclas analizadas", f"{len(df)}",
              "grandes empleadores 2022-2024")
    c3.metric("Método", "Dif-en-dif",
              "±2 años · <400 m · vs tendencia ciudad")
    st.dataframe(df.head(15), hide_index=True, width="stretch",
                 column_config={"Multiplicador medido":
                                st.column_config.NumberColumn(format="%.2f×")})
    lectura = ("las anclas ACELERAN la apertura de negocios a su alrededor"
               if med > 1.05 else
               "en esta ciudad las anclas no muestran efecto acelerador claro"
               if med < 0.95 else
               "el efecto de las anclas es neutro en esta ciudad")
    st.markdown(
        f"<div class='leyenda'>💡 Un multiplicador de {med:.2f}× significa "
        f"que, tras llegar un gran empleador, la zona a 400 m abrió negocios "
        f"a {med:.2f} veces el ritmo esperado por la tendencia de la ciudad: "
        f"{lectura}. Este número MEDIDO es el que justifica la 'fuerza' del "
        f"catalizador en el simulador. Nota: usa cohortes de registro del "
        f"DENUE (2020+), no fechas de operación exactas.</div>",
        unsafe_allow_html=True)


def tab_huecos(suffix: str = "azcapotzalco") -> None:
    """🕳 Radar de huecos de mercado: dónde hay demanda (empleo/vitalidad)
    sin oferta de un giro — inteligencia B2B para retail y franquicias."""
    df = expediente_calles(suffix)
    _, estab, es_real = cargar_red_vial(suffix)

    # ── 📍 Ubicación óptima por giro (con nombres reales del DENUE) ──────────
    if es_real:
        st.markdown("#### ¿Dónde abro mi negocio? · selector de sitio B2B")
        st.caption("Demanda = empleo DENUE real alrededor; competencia = "
                   "coincidencia por nombre comercial. Es un filtro de "
                   "prospección: valida en campo y con normativa de uso "
                   "de suelo.")
        giro = st.selectbox("¿Qué giro quieres abrir?",
                            list(GIROS_B2B.keys()), key=f"giro_{suffix}")
        top = ubicacion_optima(suffix, giro)
        if top is not None and not top.empty:
            # línea narrativa destacada del #1
            _d1 = int(top["demanda"].iloc[0])
            _c1n = int(top["competidores"].iloc[0])
            st.markdown(
                f"<div class='leyenda'>🥇 <b>Mejor sitio: "
                f"{str(top['calle'].iloc[0])}</b> — {_d1:,} empleos de "
                f"clientela cautiva con solo {_c1n} competidores del giro. "
                f"Score de demanda desatendida: "
                f"{top['score'].iloc[0] * 100:.0f}/100.</div>",
                unsafe_allow_html=True)
            top = top.copy()
            top["porque"] = [f"{int(d):,} empleos alrededor · {_txt_comp_cercano(m)}"
                             for d, m in zip(top["demanda"],
                                             top.get("comp_cercano_m",
                                                     [float("nan")] * len(top)))]
            c1, c2 = st.columns([3, 2])
            with c1:
                st.caption("Haz clic en una fila para ubicarla en el mapa de "
                           "arriba.")
                st.dataframe(
                    top[["calle", "demanda", "competidores", "porque",
                         "score"]].rename(
                        columns={"calle": "Zona (calle más cercana)",
                                 "demanda": "Empleos en el entorno",
                                 "competidores": f"Competidores {giro}",
                                 "porque": "Por qué",
                                 "score": "Score de hueco"}),
                    hide_index=True, width="stretch",
                    key=clave_tabla_b2b(suffix),
                    on_select="rerun", selection_mode="single-row",
                    column_config={"Score de hueco":
                                   st.column_config.ProgressColumn(
                                       min_value=0, max_value=1)})
                _sel = sitio_marcado(suffix)
                if _sel:
                    st.markdown(
                        f"<div class='leyenda'>📍 <b>{_sel['calle']}</b> "
                        f"(sitio {_sel['rank']}° para {_sel['giro']}) marcado "
                        f"en el mapa · {_sel['lat']:.4f}, {_sel['lng']:.4f}"
                        "</div>", unsafe_allow_html=True)
            with c2:
                st.metric("Mejor ubicación", str(top["calle"].iloc[0])[:28],
                          f"{int(top['demanda'].iloc[0]):,} empleos cerca · "
                          f"{int(top['competidores'].iloc[0])} competidores")
                st.markdown(
                    "<div class='leyenda'>Demanda = empleo real del DENUE en "
                    "un radio de ~450 m (clientela cautiva). Competidores = "
                    "negocios del giro detectados por su nombre real. El "
                    "score premia demanda alta sin oferta.</div>",
                    unsafe_allow_html=True)
                st.download_button(
                    "Informe de sitio (PDF)",
                    informe_sitio_pdf(suffix, giro),
                    file_name=f"informe_sitio_{suffix}_{slugificar(giro)}.pdf",
                    mime="application/pdf",
                    help="Entregable de 4 páginas: resumen ejecutivo, "
                         "análisis del top-10, contexto del municipio y "
                         "metodología.")

        # ── Índice de gentrificación temprana (canarios + saldo + especies) ──
        st.markdown("---")
        st.markdown("#### Gentrificación temprana · índice compuesto por calle")
        gen = indice_gentrificacion(suffix)
        if gen is not None and not gen.empty:
            lider_g = gen.iloc[0]
            st.markdown(
                f"<div class='leyenda'>🔎 <b>{lider_g['nombre']}</b> encabeza "
                f"con {int(lider_g['indice'])}/100: "
                f"{int(lider_g['recientes'])} negocios canario recién "
                f"llegados, saldo de {int(lider_g['saldo']):+d} negocios "
                f"(aperturas menos cierres) y {int(lider_g['indicadoras'])} "
                "especies indicadoras ya operando.</div>",
                unsafe_allow_html=True)
            st.caption("Haz clic en una fila para ubicarla en el mapa de arriba.")
            st.dataframe(
                gen[["nombre", "indice", "recientes", "saldo", "indicadoras",
                     "especies_nuevas"]].rename(columns={
                    "nombre": "Calle",
                    "indice": "Índice de gentrificación",
                    "recientes": "Canarios recién llegados",
                    "saldo": "Saldo de negocios",
                    "indicadoras": "Especies indicadoras",
                    "especies_nuevas": "Qué llegó"}),
                hide_index=True, width="stretch",
                key=clave_tabla_gentri(suffix),
                on_select="rerun", selection_mode="single-row",
                column_config={"Índice de gentrificación":
                               st.column_config.ProgressColumn(
                                   format="%d", min_value=0, max_value=100)})
            _selg = sitio_marcado(suffix)
            if _selg and _selg["fuente"] == "gentri":
                st.markdown(
                    f"<div class='leyenda'>📍 <b>{_selg['calle']}</b> "
                    f"({_selg['detalle']}) marcada en el mapa · "
                    f"{_selg['lat']:.4f}, {_selg['lng']:.4f}</div>",
                    unsafe_allow_html=True)
            st.markdown(
                "<div class='leyenda'>Se compone de tres señales observadas "
                "del DENUE: llegada reciente de giros canario (50%), saldo de "
                "aperturas menos cierres (30%) y especies indicadoras ya "
                "instaladas (20%). El <b>saldo</b> está para no confundir "
                "gentrificación con vaciamiento: una calle que pierde "
                "negocios no se está encareciendo, se está apagando."
                "</div>", unsafe_allow_html=True)
            st.warning(
                "**Es una señal, no una predicción validada.** Con un solo "
                "corte del DENUE se reconstruye cuándo llegó cada negocio, "
                "pero no se puede contrastar el índice contra lo que pasó "
                "después con los precios de esa calle. El precio no entra en "
                "el índice: el inventario C21 da mediana por zona, no por "
                "calle, y mezclarlos daría un número más fino de lo que es.",
                icon="⚠️")
        else:
            st.info("Sin señal de gentrificación medible aquí: hacen falta "
                    "nombres y años de alta del DENUE con giros canario.")

        # ── Canarios de la plusvalía (detalle de la señal adelantada) ────────
        st.markdown("---")
        st.markdown("#### Canarios de la plusvalía · llegada temprana de "
                    "giros indicadores")
        canarios = canarios_calle(suffix)
        if canarios is not None and not canarios.empty:
            lider_c = canarios.iloc[0]
            st.markdown(
                f"<div class='leyenda'>A <b>{lider_c['calle']}</b> llegaron "
                f"{int(lider_c['recientes'])} negocios canario en los "
                f"últimos 2 años: {lider_c['especies']}. Este patrón "
                "precede a los despegues de precio.</div>",
                unsafe_allow_html=True)
            st.dataframe(
                canarios[["calle", "recientes", "especies", "historico",
                          "score"]].rename(columns={
                    "calle": "Calle",
                    "recientes": "Canarios recientes (2 años)",
                    "especies": "Especies recientes",
                    "historico": "Total histórico",
                    "score": "Score de llegada"}),
                hide_index=True, width="stretch",
                column_config={"Score de llegada":
                               st.column_config.ProgressColumn(
                                   format="%d", min_value=0, max_value=100)})
        else:
            st.info("Sin canarios detectables en esta ciudad: se requieren "
                    "nombres y años de alta del DENUE.")
        st.caption("Señal EXPLORATORIA basada en fechas de alta del DENUE; "
                   "correlación observada en gentrificación urbana, no "
                   "garantía. Cruza con el inventario C21 de la zona.")

        # ── Modo franquicia / cadena ─────────────────────────────────────────
        with st.expander("Mi red de sucursales · canibalización y huecos"):
            texto_suc = st.text_area(
                "Pega tus sucursales: una por línea, `lat,lng[,nombre]`",
                key=f"red_txt_{suffix}", height=120,
                placeholder="19.4870,-99.1840,Sucursal Centro\n"
                            "19.4930,-99.1710")
            archivo_suc = st.file_uploader(
                "...o sube un CSV con columnas lat,lng[,nombre]",
                type=["csv"], key=f"red_csv_{suffix}")
            suc, leidas, intentadas = parsear_sucursales(texto_suc,
                                                         archivo_suc)
            if intentadas and leidas < intentadas:
                st.warning(f"Leí {leidas} de {intentadas} líneas; el resto "
                           "no trae lat,lng válidos y se ignoró.")
            if suc.empty:
                for _k in ("bb_red_suffix", "bb_red_suc", "bb_red_huecos"):
                    st.session_state.pop(_k, None)
                st.caption("Carga al menos una sucursal para analizar tu "
                           "red sobre la demanda DENUE de esta ciudad.")
            else:
                st.caption(f"{leidas} sucursales leídas.")
                pares = canibalizacion_red(suc)
                huecos = huecos_cobertura(suffix, suc)
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    st.markdown("##### Canibalización (pares a <600 m)")
                    if pares.empty:
                        st.markdown("<div class='leyenda'>Ningún par de "
                                    "sucursales a menos de 600 m.</div>",
                                    unsafe_allow_html=True)
                    else:
                        st.dataframe(pares, hide_index=True,
                                     width="stretch")
                with col_r2:
                    st.markdown("##### Huecos de cobertura (>1.2 km de "
                                "toda sucursal)")
                    if huecos is None or huecos.empty:
                        st.markdown("<div class='leyenda'>Sin huecos: toda "
                                    "la demanda queda a menos de 1.2 km de "
                                    "alguna sucursal.</div>",
                                    unsafe_allow_html=True)
                    else:
                        st.dataframe(
                            huecos[["calle", "demanda",
                                    "Distancia a la red (km)"]].rename(
                                columns={"calle": "Calle (hueco)",
                                         "demanda": "Empleos (demanda)"}),
                            hide_index=True, width="stretch")
                # capa en el mapa de la escala calle (terracota + salvia)
                st.session_state["bb_red_suffix"] = suffix
                st.session_state["bb_red_suc"] = suc
                st.session_state["bb_red_huecos"] = huecos
                st.download_button(
                    "Informe de red (PDF)",
                    informe_red_pdf(suffix, suc, pares, huecos),
                    file_name=f"informe_red_{suffix}.pdf",
                    mime="application/pdf")
            st.caption("Análisis geométrico sobre demanda DENUE: la "
                       "canibalización real depende de tu ticket y "
                       "catchment; úsalo como radiografía inicial.")
        st.markdown("---")
    oferta = estab.groupby(["calle", "sector"]).size().unstack(fill_value=0)
    filas = []
    for _, c in df.iterrows():
        of = oferta.loc[c["nombre"]] if c["nombre"] in oferta.index \
            else pd.Series(0, index=list(SECTORES))
        for sector in SECTORES:
            n_of = int(of.get(sector, 0))
            demanda = c["empleo"] * (0.5 + c["cercania_ancla"])
            hueco = demanda / (1 + 2.5 * n_of)
            filas.append({"Calle": c["nombre"], "Giro faltante": sector,
                          "Demanda (empleos zona)": int(c["empleo"]),
                          "Locales del giro hoy": n_of,
                          "Score hueco": hueco})
    tabla = pd.DataFrame(filas)
    tabla["Score hueco"] = norm01(tabla["Score hueco"].to_numpy()).round(2)
    tabla = tabla.nlargest(15, "Score hueco")
    st.dataframe(tabla, hide_index=True, width="stretch",
                 column_config={"Score hueco": st.column_config.ProgressColumn(
                     min_value=0, max_value=1)})
    st.markdown("<div class='leyenda'>🕳 Lectura B2B: una calle con alta "
                "demanda (empleo + anclas) y cero locales de un giro es una "
                "ubicación de apertura con viento a favor — la misma data "
                "que valúa el ladrillo le dice a una franquicia dónde abrir."
                + (" (demo etiquetada)" if not es_real else "")
                + "</div>", unsafe_allow_html=True)


TEXTO_METODOLOGIA = f"""
---
#### 📜 Metodología, fuentes y alcance (léase antes de decidir nada)

| Capa | ¿Real o simulada? | Fuente |
|---|---|---|
| Establecimientos, empleo, giros, fechas de alta | **REAL** | DENUE/INEGI (corte vigente) |
| Geometría de estados, municipios, CP y calles | **REAL** | INEGI · SEPOMEX · DENUE |
| Contagio espacial (término ρ·W·v) | **VALIDADO** | r=0.41 out-of-sample vs DENUE |
| Multiplicador de anclas | **MEDIDO** | dif-en-dif sobre cohortes DENUE |
| Precio base | **SINTÉTICO*** | gradiente + densidad económica real |
| Proyección a 10 años | **SIMULACIÓN** | SAR con bandas Monte Carlo P10–P90 |

\\* Se calibra automáticamente contra anclajes de precio reales cuando
existen (`scripts/ingerir_precios.py` o datos propios de BrickBit).

**Aviso legal:** esta herramienta produce análisis estadístico exploratorio
con fines informativos. No constituye asesoría, recomendación de inversión
ni oferta de valores en términos de la LMV ni de la regulación CNBV
aplicable. Rendimientos pasados o simulados no garantizan rendimientos
futuros. Verifica cualquier decisión con un asesor certificado.
"""

TEXTO_MODELO = f"""
**La República no es un mapa: es un organismo.** Cada unidad (estado,
municipio o manzana) es una célula cuyo metabolismo depende de sus
vecinas — la primera ley de la geografía de Tobler, formalizada como un
proceso espacial autorregresivo (SAR):

```
precio[t+1] = precio[t] · (1 + g_propio + ρ · (W · precio_norm[t]) · potencial)
```

- **W**: contigüidad geográfica REAL — 136 fronteras estatales y ~15,000
  fronteras municipales (BCS solo respira a través de BC).
- **ρ**: virulencia del contagio de plusvalía entre vecinos.
- **potencial**: receptividad = plusvalía histórica + yield + accesibilidad
  (dataset BrickBit "Valor Futuro"). A escala municipal, el pico vive en el
  **anillo periurbano** (~25 km de cada ZM): la frontera de expansión.
- **Megaproyectos**: células madre regionales (Tren Maya, nearshoring,
  Interoceánico, Bajío aeroespacial) que detonan la mutación en cadena.
- **Índice de Moran I**: el electrocardiograma espacial — mide si el
  organismo crece cohesionado (I→1) o fragmentado (I→0).
- **Sistema circulatorio**: modelo gravitacional
  `masa económica / distancia^1.2` de las ZM dominantes hacia las zonas
  de mayor crecimiento proyectado.

*Población y PIB per cápita aproximados; el detalle municipal se sintetiza
por proximidad a las ZM (sin microdatos oficiales). Proyecciones 100%
simuladas con fines de visualización — no es asesoría de inversión.*
"""


# ══════════════════════════════════════════════════════════════════════════════
# 10 · INTERFAZ STREAMLIT — IDENTIDAD BRICKBIT
# ══════════════════════════════════════════════════════════════════════════════

def inyectar_css() -> None:
    """Dark mode tierra BrickBit: Fraunces + Hanken Grotesk + Space Mono."""
    st.markdown(f"""
    <style>
      @import url('{FUENTES_URL}');
      .stApp {{
          background: radial-gradient(ellipse at top, #1d1713 0%, {TIERRA} 62%);
          font-family: 'Hanken Grotesk', sans-serif;
      }}
      section[data-testid="stSidebar"] {{
          background: #171210; border-right: 1px solid #2a221c;
      }}
      h1, h2, h3 {{ color: {CREMA} !important;
                    font-family: 'Fraunces', serif !important; }}
      .brand-title {{
          font-family: 'Fraunces', serif; font-size: 2.05rem; font-weight: 600;
          background: linear-gradient(90deg, {CREMA} 15%, {LIMA} 85%);
          -webkit-background-clip: text; -webkit-text-fill-color: transparent;
          letter-spacing: .01em; line-height: 1.1;
      }}
      .brand-sub {{ color: {TEXTO_SUAVE}; font-family: 'Space Mono', monospace;
                    font-size: .85rem; margin-top: .15rem; }}
      div[data-testid="stMetric"] {{
          background: {SUPERFICIE}; border: 1px solid #2a221c;
          border-radius: 14px; padding: .6rem .9rem;
          box-shadow: 0 6px 16px rgba(0,0,0,.28);
      }}
      div[data-testid="stMetricValue"] {{
          color: {LIMA}; font-family: 'Space Mono', monospace;
          font-size: 1.4rem;
      }}
      div[data-testid="stMetricLabel"] {{ color: {TEXTO_SUAVE};
          font-family: 'Hanken Grotesk', sans-serif; }}
      button[data-baseweb="tab"] {{ font-family: 'Space Mono', monospace; }}
      .stButton button {{
          background: {ARCILLA}; color: {CREMA}; border: 1px solid {ARCILLA_SUAVE};
          font-family: 'Hanken Grotesk', sans-serif; font-weight: 600;
      }}
      .stButton button:hover {{ background: {ARCILLA_SUAVE}; color: {TIERRA};
          border-color: {LIMA}; }}
      .leyenda {{ font-family: 'Space Mono', monospace; color: {TEXTO_SUAVE};
                  font-size: .82rem; }}
      .chip-c21 {{
          display: inline-block; margin-top: .45rem; padding: .28rem .8rem;
          font-family: 'Space Mono', monospace; font-size: .74rem;
          color: {CREMA}; background: rgba(111,162,135,.12);
          border: 1px solid {ARCILLA_SUAVE}; border-radius: 99px;
      }}
      .chip-c21 b {{ color: {LIMA}; }}
      .franja-simulacion {{
          background: rgba(245,194,119,.12); border-left: 3px solid #F5C277;
          color: {CREMA}; font-size: 12.5px; line-height: 1.45;
          font-family: 'Hanken Grotesk', sans-serif;
          padding: .32rem .75rem; border-radius: 0 8px 8px 0;
          margin: .15rem 0 .4rem;
      }}
      /* ── ocultar el cromo de Streamlit (menú, header, footer, insignias) ── */
      #MainMenu, header[data-testid="stHeader"], footer,
      [data-testid="stToolbar"], [data-testid="stDecoration"],
      [data-testid="stStatusWidget"],
      .viewerBadge_container__1QSob, [class*="viewerBadge"] {{
          display: none !important; visibility: hidden !important;
      }}
      /* botones de fullscreen / toolbar por elemento */
      button[title="View fullscreen"],
      [data-testid="StyledFullScreenButton"],
      [data-testid="stElementToolbar"] {{ display: none !important; }}
    </style>
    """, unsafe_allow_html=True)


@st.cache_data
def _logo_b64() -> str:
    """Logo BrickBit (blanco/transparente) en base64 para el encabezado."""
    if os.path.exists(RUTA_LOGO):
        with open(RUTA_LOGO, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


def encabezado() -> None:
    """Logo oficial + título Fraunces con degradado crema→lima."""
    logo = _logo_b64()
    img = (f'<img src="data:image/png;base64,{logo}" '
           'style="height:46px;width:auto"/>' if logo else "")
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:18px;'
        f'padding:.2rem 0 .6rem 0">{img}<div>'
        '<div class="brand-title">Motor de Morfogénesis Urbana</div>'
        '<div class="brand-sub">la República como organismo vivo — '
        '2,436 municipios · 1,182 códigos postales · calle y establecimiento '
        'en cualquier municipio · proyección simulada a 10 años</div>'
        '</div></div>',
        unsafe_allow_html=True)


_EXPLICA_COMUN = (
    "**BrickBit trata la ciudad como un organismo vivo.** El desarrollo y la "
    "plusvalía se *contagian* de una zona a sus vecinas, como un tejido que "
    "crece. Esto es lo que ves en el mapa:\n\n"
    "- 🎨 **El color = la “temperatura” de valor y crecimiento** de cada zona. "
    "De más frío a más caliente:  \n"
    "&nbsp;&nbsp;🟫 <span style='color:#0c4a30'>**latente**</span> → "
    "🟩 <span style='color:#24664a'>**despertando**</span> → "
    "🟢 <span style='color:#6fa287'>**en expansión**</span> → "
    "🟡 <span style='color:#b7c489'>**en plena mutación**</span> → "
    "⬜ <span style='color:#f5ede3'>**núcleo consolidado**</span> (lo más caro).\n"
    "- 🫀 **Los arcos verde→oliva** son el *sistema circulatorio del capital*: "
    "dinero que fluye de las zonas ya caras (corazones) hacia las emergentes.\n"
    "- ⏳ **El deslizador “Predicción (años)”** te lleva al futuro: mira cómo se "
    "expande el crecimiento año con año. *Esa proyección es una simulación.*\n"
    "- 🧫 **“Virulencia del contagio (ρ)”** regula qué tan fuerte una zona "
    "contagia a sus vecinas. Súbela y verás el crecimiento saltar más lejos.\n"
    "- 🎯 **Catalizador / detonante**: inyecta un megaproyecto (Metro, AIFA…) y "
    "observa la onda expansiva que provoca.\n"
)
_EXPLICA_ESCALA = {
    "muni": "**Escala municipios:** cada polígono es **uno de los 2,436 municipios** "
         "del país. Su valor y potencial están anclados en la **actividad "
         "económica REAL del DENUE/INEGI** (negocios y empleos observados). Las "
         "torres 3D marcan las grandes metrópolis.",
    "edos": "**Escala estados:** cada polígono es **uno de los 32 estados**. Las "
         "torres 3D representan el peso de cada entidad; el color, su ritmo de "
         "crecimiento proyectado.",
    "cp": "**Escala códigos postales (CDMX):** cada polígono es **un CP real de "
         "SEPOMEX** (1,182 en total). Las etiquetas son las **alcaldías**. La "
         "pestaña «Por alcaldía» resume el crecimiento de cada una.",
    "calle": "**Escala calle · establecimiento:** aquí ves la ciudad **desde la "
         "banqueta**.  \n"
         "- Cada **línea es una calle real** (del DENUE). Entre **más gruesa y "
         "brillante**, más *vitalidad económica* tiene (más negocios y empleo).\n"
         "- Los **puntos de colores** son establecimientos, coloreados por giro "
         "(comercio, servicios, industria).\n"
         "- Los **círculos oliva con nombre** son las **anclas**: los grandes "
         "empleadores que bombean crecimiento a su alrededor.",
    "micro": "**Escala microtejido:** cada **cuadro es una manzana**. En modo 3D, la "
         "**altura = el precio** por m². Aquí ves el contagio calle-a-calle en "
         "su máximo detalle (una alcaldía/municipio en fino, o toda la ZMVM). "
         "El tejido es **simulado**, calibrado con semillas reales de la ZMVM.",
}


def aviso_honestidad(anio: float, rho: float) -> str | None:
    """
    Honestidad de simulación: el pronóstico VALIDADO de BrickBit cubre 1–3
    años; la ola SAR a 10 años con ρ ajustable es SIMULACIÓN exploratoria.
    Devuelve el texto del aviso (franja ámbar) o None si el escenario está
    dentro de lo razonable (0 < año ≤ 3 con la ρ calibrada de 0.85).
    """
    partes = []
    if anio < 0:
        partes.append("Retro-simulación: reconstrucción, no dato histórico "
                      "puntual")
    elif anio > 3:
        partes.append(f"Proyección a {anio:.0f} años: SIMULACIÓN "
                      "exploratoria — el modelo BrickBit está validado por "
                      "backtest a 1–3 años")
    if abs(rho - 0.85) > 1e-9:
        partes.append(f"ρ={rho:g} ajustado a mano (el calibrado es 0.85)")
    return " · ".join(partes) if partes else None


def explicador(esc: str) -> None:
    """Recuadro plegable “¿Qué estoy viendo?” con la lectura del mapa en
    lenguaje simple, adaptado a la escala activa (clave: muni/edos/cp/calle/
    micro). Para que cualquiera —aunque sea su primera vez— entienda de
    inmediato qué representa cada elemento."""
    extra = _EXPLICA_ESCALA.get(esc, "")
    with st.expander("¿Qué estoy viendo? — cómo leer este mapa", expanded=False):
        st.markdown(_EXPLICA_COMUN, unsafe_allow_html=True)
        if extra:
            st.markdown("---")
            st.markdown(extra, unsafe_allow_html=True)
        st.caption("Los conteos de negocios, empleos, calles y geometrías son "
                   "reales (DENUE/INEGI, SEPOMEX). Las proyecciones a futuro son "
                   "una simulación con fines de visualización, no asesoría.")


def animar(lienzo, fabricar_deck, cuadros: int = 90,
           años_span: float = float(AÑOS)) -> None:
    """Reproduce la línea de tiempo completa: el año avanza y todo late."""
    for f in range(cuadros + 1):
        lienzo.pydeck_chart(
            fabricar_deck(años_span * f / cuadros, (f * 0.045) % 1.0),
            width="stretch")
        time.sleep(0.05)
    st.toast("🧬 Morfogénesis completa: año 10 alcanzado", icon="✅")


def render_mapa(lienzo, fabricar, año_idx: float, reproducir: bool,
                cuadros: int, años_span: float, clic_activo: bool,
                clave: str) -> None:
    """
    Renderiza el mapa (o la animación) y, con el detonante-por-clic activo,
    captura la célula seleccionada y la convierte en epicentro del shock.
    """
    if reproducir:
        animar(lienzo, fabricar, cuadros=cuadros, años_span=años_span)
        return
    deck = fabricar(año_idx, (año_idx * 0.4) % 1.0)
    if not clic_activo:
        # con `key` explícita: cuando la clave cambia (p. ej. al elegir un
        # sitio B2B), el componente se remonta y sí obedece el encuadre nuevo,
        # en vez de conservar la cámara donde el usuario la había dejado
        lienzo.pydeck_chart(deck, width="stretch", key=clave)
        return
    ev = lienzo.pydeck_chart(deck, width="stretch", on_select="rerun",
                             selection_mode="single-object", key=clave)
    objetos = {}
    try:
        objetos = ev.selection.objects or {}
    except AttributeError:
        pass
    celda = (objetos.get("celulas") or [None])[0]
    if celda and celda.get("lng") is not None:
        nuevo = (round(float(celda["lng"]), 4), round(float(celda["lat"]), 4))
        if st.session_state.get("clic_epicentro") != nuevo:
            st.session_state["clic_epicentro"] = nuevo
            st.rerun()


def tab_alcaldias(df_cp: pd.DataFrame, valores: np.ndarray,
                  año: float) -> None:
    """Crecimiento agregado por alcaldía: las 16 células mayores de CDMX."""
    v_t, tasa = estado_en(valores, año)
    acum = (v_t / valores[0] - 1) * 100
    d = pd.DataFrame({"alcaldia": df_cp["alcaldia"], "cp": df_cp["cp"],
                      "precio": v_t, "acum": acum, "tasa": tasa * 100,
                      "potencial": df_cp["potencial_crecimiento"]})
    g = d.groupby("alcaldia").agg(
        cps=("cp", "size"), precio_medio=("precio", "mean"),
        crecimiento=("acum", "mean"), tasa_anual=("tasa", "mean"),
        potencial=("potencial", "mean")).reset_index() \
        .sort_values("crecimiento", ascending=False)
    # CP líder de cada alcaldía (el más mutante)
    lider = d.loc[d.groupby("alcaldia")["acum"].idxmax()] \
        .set_index("alcaldia")["cp"]
    g["cp_lider"] = g["alcaldia"].map(lider)
    st.markdown(f"**Las 16 alcaldías ordenadas por crecimiento simulado al "
                f"año {año:.1f}** — promedio de sus códigos postales "
                f"(1,182 polígonos SEPOMEX reales; proyección simulada).")
    st.dataframe(
        g.rename(columns={
            "alcaldia": "Alcaldía", "cps": "CPs",
            "precio_medio": "Índice medio $/m²",
            "crecimiento": "Crecimiento",
            "tasa_anual": "Tasa anual %",
            "potencial": "Potencial",
            "cp_lider": "CP más mutante"}),
        hide_index=True, width="stretch",
        column_config={
            "Índice medio $/m²": st.column_config.NumberColumn(format="$%,.0f"),
            "Tasa anual %": st.column_config.NumberColumn(format="%.1f%%"),
            "Potencial": st.column_config.NumberColumn(format="%.2f"),
            "Crecimiento": st.column_config.ProgressColumn(
                format="+%.1f%%", min_value=0.0,
                max_value=max(0.01, float(g["crecimiento"].max()))),
        })
    st.caption("Mueve el deslizador de años: el ranking de alcaldías se "
               "reordena en vivo conforme el contagio avanza por el tejido.")


def main() -> None:
    st.set_page_config(page_title="BrickBit · Morfogénesis Urbana MX",
                       page_icon="🧬", layout="wide",
                       initial_sidebar_state="expanded")

    # ── 🔗 Escenarios compartibles: la URL es el estado inicial ───────────────
    # brickbit.co/morfogenesis?esc=micro&anio=7&rho=1.2&det=…&retro=1 arranca
    # los widgets exactamente en ese escenario. Lectura defensiva: lo que no
    # valide (escala inexistente, número corrupto…) se ignora en silencio.
    qp = st.query_params
    esc_url = qp.get("esc")
    if esc_url not in ESCALAS:
        esc_url = None
    try:
        anio_url = float(qp.get("anio"))
    except (TypeError, ValueError):
        anio_url = None
    try:
        rho_url = round(min(1.5, max(0.0, float(qp.get("rho")))) * 20) / 20
    except (TypeError, ValueError):
        rho_url = None
    det_url = qp.get("det") or None      # se valida contra el dict de su escala
    retro_url = {"1": True, "0": False}.get(qp.get("retro"))

    inyectar_css()
    if os.path.exists(RUTA_LOGO):
        st.logo(RUTA_LOGO, size="large")
    encabezado()

    # ── Panel lateral: escala + ajustes ───────────────────────────────────────
    with st.sidebar:
        escala_lbl = st.radio("Escala del organismo", list(ESCALAS.values()),
                              index=(list(ESCALAS).index(esc_url)
                                     if esc_url else 0),
                              help="El mismo motor SAR a cinco escalas: de los "
                                   "32 estados hasta la banqueta, negocio a "
                                   "negocio.")
        esc = ESCALA_POR_LABEL[escala_lbl]

        st.markdown("### Línea de tiempo")
        retro = st.checkbox("Time-lapse bidireccional (retro-simulación)",
                            retro_url if retro_url is not None else False,
                            help="Extiende la línea de tiempo 5 años hacia "
                                 "atrás para ver de dónde viene la ola.")

        st.markdown("### Parámetros avanzados")
        rho = st.slider("Virulencia del contagio (ρ)", 0.0, 1.5,
                        rho_url if rho_url is not None else 0.85, 0.05,
                        help="Coeficiente espacial autorregresivo: cuánto pesa "
                             "el vecindario en el crecimiento de cada célula.")

        st.markdown("### Capas")
        mostrar_flujos = st.checkbox("Sistema circulatorio de capital", True)
        if esc == "micro":
            extrusion = st.checkbox("Relieve 3D del tejido", True)
        elif esc == "calle":
            mostrar_estab = st.checkbox("Establecimientos (puntos)", True)
        elif esc != "cp":
            mostrar_torres = st.checkbox("Torres metropolitanas 3D", True)
            mostrar_etiquetas = st.checkbox("Nombres de ciudades", True)

        mostrar_lisa = False
        if esc in ("muni", "cp"):
            mostrar_lisa = st.checkbox("Frente de onda (LISA)", False,
                                       help="Moran local: contorno crema en "
                                            "las células baratas rodeadas de "
                                            "caras — donde romperá la ola.")

        st.markdown("### Detonante por clic")
        clic_activo = st.checkbox("Activar clic-para-detonar", False,
                                  help="Haz clic en cualquier célula del mapa "
                                       "e inyecta ahí una célula madre; mira "
                                       "la onda expansiva (SimCity al revés).")
        clic = st.session_state.get("clic_epicentro") if clic_activo else None
        if clic_activo and clic:
            st.caption(f"Epicentro activo: {clic[1]:.3f}, {clic[0]:.3f}")
            if st.button("Quitar epicentro", width="stretch"):
                del st.session_state["clic_epicentro"]
                st.rerun()

    lienzo_kpi = st.container()
    explicador(esc)

    # ── Controles principales — siempre a la vista, arriba del mapa ───────────
    alcance_micro = "azcapotzalco"
    if esc in ("calle", "micro"):
        col_modo, col_det, col_año, col_play = st.columns(
            [2.6, 2.4, 2.8, 1.6], vertical_alignment="bottom")
    else:
        col_det, col_año, col_play = st.columns(
            [2.8, 3.4, 1.6], vertical_alignment="bottom")
        col_modo = None

    if esc == "calle":
        with col_modo:
            munis = municipios_calle()
            if munis:
                labels = [m["label"] for m in munis]
                # arranca en el corazón de CDMX, no en el primer alfabético
                idx0 = next((i for i, mm in enumerate(munis)
                             if mm["suffix"] == "cuauhtemoc"), 0)
                sel = st.selectbox(
                    f"Elige tu ciudad — {len(munis)} disponibles",
                    labels, index=idx0,
                    help="Todas con DENUE/INEGI real a nivel calle: las 9 "
                         "alcaldías centrales de CDMX, Guadalajara, Monterrey "
                         "y su zona metro, Cancún, Playa del Carmen, Tulum, "
                         "La Paz, Los Cabos y las 32 capitales estatales. "
                         "¿Falta la tuya? Se agrega con ingerir_denue.py.")
                m = munis[labels.index(sel)]
                st.session_state["municipio_suffix"] = m["suffix"]
                st.session_state["municipio_nombre"] = m["municipio"]
    elif esc == "micro":
        with col_modo:
            # "ZMVM completo" primero; luego las 26 unidades en alfabético
            # (CDMX · … / Edomex · …). La clave viaja como alcance_micro.
            _ops_micro = {"zmvm": "ZMVM completo"}
            _ops_micro.update(
                (k, f"{u['zona']} · {u['nombre']}")
                for k, u in sorted(UNIDADES_MICRO.items(),
                                   key=lambda kv: (kv[1]["zona"],
                                                   slugificar(kv[1]["nombre"]))))
            _lbl_micro = st.selectbox(
                "Alcaldía / municipio", list(_ops_micro.values()),
                help="Tejido SIMULADO calibrado con las semillas reales de la "
                     "ZMVM. 'ZMVM completo' cultiva 2,304 células "
                     "metropolitanas; cada alcaldía/municipio cultiva su "
                     "propio grid fino de 676 manzanas con corazón local.")
            alcance_micro = list(_ops_micro)[
                list(_ops_micro.values()).index(_lbl_micro)]

    def _idx_det(dic: dict) -> int:
        """Índice inicial del detonante si la URL trae uno válido para esta
        escala; si no está en el dict, se ignora (defensivo)."""
        return list(dic).index(det_url) if det_url in dic else 0

    with col_det:
        if esc in ("micro", "calle"):
            detonante = st.selectbox("Célula madre (catalizador urbano)",
                                     list(CATALIZADORES.keys()),
                                     index=_idx_det(CATALIZADORES))
        elif esc == "cp":
            detonante = st.selectbox("Detonante urbano CDMX",
                                     list(DETONANTES_CDMX.keys()),
                                     index=_idx_det(DETONANTES_CDMX))
        else:
            detonante = st.selectbox("Megaproyecto detonante",
                                     list(MEGAPROYECTOS.keys()),
                                     index=_idx_det(MEGAPROYECTOS),
                                     help="Célula madre a escala nación: eleva "
                                          "el potencial de toda una región.")
    with col_año:
        año_min = -float(RETRO) if retro else 0.0
        año_ini = 0.0
        if anio_url is not None:    # clamp al rango del slider (paso 0.25)
            año_ini = round(min(float(AÑOS), max(año_min, anio_url)) * 4) / 4
        año = st.slider("Predicción (años)",
                        año_min, float(AÑOS),
                        año_ini, step=0.25, format="%.2f años",
                        help="Mueve el horizonte de la simulación; la "
                             "proyección es simulada, no asesoría.")
    with col_play:
        reproducir = st.button("Reproducir morfogénesis", width="stretch",
                               help="Anima la línea de tiempo completa "
                                    "(10 años).")

    # ── La URL siempre refleja el escenario actual (compartible) ──────────────
    # Solo se tocan nuestras claves: ?embed=… de Streamlit queda intacto.
    _escenario = {"esc": esc, "anio": f"{año:g}", "rho": f"{rho:g}",
                  "det": detonante, "retro": "1" if retro else "0"}
    for _k, _v in _escenario.items():
        if qp.get(_k) != _v:
            qp[_k] = _v

    with st.sidebar:
        with st.expander("Compartir este escenario"):
            st.code("https://brickbit.co/morfogenesis"
                    f"?esc={esc}&anio={año:g}&rho={rho:g}"
                    f"&det={quote(detonante)}&retro={1 if retro else 0}",
                    language=None)
            st.caption("Copia el enlace: quien lo abra verá exactamente "
                       "este escenario.")

    # ── 🟡 Honestidad de simulación: franja ámbar encima del mapa ─────────────
    _aviso = aviso_honestidad(año, rho)
    if _aviso:
        st.markdown(f"<div class='franja-simulacion'>⚠ {_aviso}</div>",
                    unsafe_allow_html=True)

    lienzo = st.empty()
    st.caption("Motor de simulación SAR (exploratorio) · distinto del "
               "pronóstico validado 1–3 años que usan el mapa y el "
               "analizador.")

    # ══ REPÚBLICA · MUNICIPIOS ════════════════════════════════════════════════
    if esc == "muni":
        valores = simular_municipios(rho, detonante, clic)
        valores_edo = simular_nacion(rho, detonante, clic)
        df_m = datos_municipales()
        vv, ve = (extender_pasado(valores), extender_pasado(valores_edo)) \
            if retro else (valores, valores_edo)
        año_idx = año + (RETRO if retro else 0)
        v_t, tasa = estado_en(vv, año_idx)
        flujos = flujos_nacionales(ve, año_idx)

        moran = indice_moran(v_t, vecindad_municipios())
        mutante = int(np.argmax(v_t / valores[0] - 1))
        score = score_brickbit(v_t, valores[0],
                               df_m["potencial_crecimiento"], tasa)
        neg_real = int(df_m["n_estab"].sum())
        with lienzo_kpi:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Precio municipal medio", f"${v_t.mean():,.0f} /m²",
                      f"+{(v_t.mean() / valores[0].mean() - 1) * 100:.1f}% vs hoy")
            c2.metric("Índice de Moran", f"{moran:.3f}",
                      "cohesión espacial" if moran > 0.15 else "tejido fragmentado")
            if neg_real > 0:
                c3.metric("Negocios reales (DENUE)", f"{neg_real / 1e6:.2f} M",
                          f"{int((df_m['n_estab'] > 0).sum())} municipios cubiertos")
            else:
                c3.metric("Capital en rotación",
                          f"${flujos['capital_mmd'].sum():,.0f} mmd/año",
                          f"{len(flujos)} arterias activas")
            c4.metric("Municipio más mutante",
                      df_m["municipio"].iloc[mutante],
                      f"{df_m['estado'].iloc[mutante]} · "
                      f"+{(v_t[mutante] / valores[0][mutante] - 1) * 100:.0f}%")
            c5.metric("Horizonte", f"Año {año:.1f} / {AÑOS}",
                      "epicentro por clic" if clic else
                      (detonante if MEGAPROYECTOS[detonante] else "sin megaproyecto"))
            n_c21 = c21_lineas_municipales()[1]
            if n_c21:
                st.markdown(
                    f"<div class='chip-c21'><b>{n_c21}</b> municipios con "
                    "mercado vivo C21 — medianas reales de precios de lista, "
                    "refresco diario (en el tooltip del mapa)</div>",
                    unsafe_allow_html=True)

        def fabricar(a, f):
            return construir_deck_municipios(
                vv, a, f, mostrar_flujos, mostrar_torres,
                mostrar_etiquetas, flujos_nacionales(ve, a),
                ve, mostrar_lisa)

        render_mapa(lienzo, fabricar, año_idx, reproducir, 48,
                    float(vv.shape[0] - 1), clic_activo, "deck_mun")

        nombres_m = df_m["municipio"] + " · " + df_m["estado"]
        banda_m = banda_municipios(rho, detonante, clic)
        t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(
            ["Ranking municipal", "Origen del crecimiento",
             "Estancamiento", "Gemelos de ADN", "Carteras por tesis",
             "Trayectorias 10 años", "Nube de fases", "El modelo"])
        with t1:
            tab_ranking_municipios(valores, año, score)
        with t2:
            tab_origen(nombres_m, _args_municipios(rho, detonante, clic),
                       mutante, "el municipio", banda_m)
        with t3:
            tab_estancamiento(valores, año)
        with t4:
            acum10 = valores[-1] / valores[0] - 1
            X = np.column_stack([
                norm01(df_m["precio_actual"]),
                df_m["potencial_crecimiento"],
                norm01(df_m["dist_zm_km"]), norm01(acum10),
                score / 10])
            tab_gemelos(nombres_m, X, mutante, "el municipio")
        with t5:
            tab_carteras(valores)
        with t6:
            tab_trayectorias(valores, año,
                             df_m["municipio"] + " (" + df_m["estado"] + ")",
                             "🧬 Trayectoria de precios — top 8 municipios en mutación",
                             banda_m)
        with t7:
            tab_fases_municipios(valores, año)
        with t8:
            st.markdown(TEXTO_MODELO)
            st.markdown(TEXTO_METODOLOGIA)

    # ══ REPÚBLICA · ESTADOS ═══════════════════════════════════════════════════
    elif esc == "edos":
        valores = simular_nacion(rho, detonante, clic)
        df_e = datos_estatales()
        vv = extender_pasado(valores) if retro else valores
        año_idx = año + (RETRO if retro else 0)
        v_t, tasa = estado_en(vv, año_idx)
        flujos = flujos_nacionales(vv, año_idx)

        pob = df_e["poblacion"].to_numpy()
        medio = float((v_t * pob).sum() / pob.sum())
        medio_0 = float((valores[0] * pob).sum() / pob.sum())
        moran = indice_moran(v_t, vecindad_estados())
        mutante = int(np.argmax(v_t / valores[0] - 1))
        score = score_brickbit(v_t, valores[0], df_e["potencial"], tasa)
        with lienzo_kpi:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Valor medio nacional", f"${medio:,.0f} /m²",
                      f"+{(medio / medio_0 - 1) * 100:.1f}% vs hoy")
            c2.metric("Índice de Moran", f"{moran:.3f}",
                      "cohesión espacial" if moran > 0.15 else "tejido fragmentado")
            c3.metric("Capital en rotación",
                      f"${flujos['capital_mmd'].sum():,.0f} mmd/año",
                      f"{len(flujos)} arterias activas")
            c4.metric("Estado más mutante", df_e["estado"].iloc[mutante],
                      f"+{(v_t[mutante] / valores[0][mutante] - 1) * 100:.0f}% acumulado")
            c5.metric("Horizonte", f"Año {año:.1f} / {AÑOS}",
                      "epicentro por clic" if clic else
                      (detonante if MEGAPROYECTOS[detonante] else "sin megaproyecto"))

        def fabricar(a, f):
            return construir_deck_nacion(vv, a, f, mostrar_flujos,
                                         mostrar_torres, mostrar_etiquetas,
                                         flujos_nacionales(vv, a))

        render_mapa(lienzo, fabricar, año_idx, reproducir, 90,
                    float(vv.shape[0] - 1), clic_activo, "deck_edo")

        t1, t2, t3, t4, t5, t6 = st.tabs(["Ranking de mutación",
                                          "Origen del crecimiento",
                                          "Gemelos de ADN",
                                          "Trayectorias 10 años",
                                          "Diagrama de fases",
                                          "El modelo"])
        with t1:
            tab_ranking_estados(valores, año, flujos, score)
        with t2:
            tab_origen(df_e["estado"], _args_nacion(rho, detonante, clic),
                       mutante, "el estado")
        with t3:
            X = np.column_stack([
                norm01(df_e["precio_m2"]), df_e["potencial"],
                norm01(df_e["plusvalia"]), norm01(df_e["yld"]),
                norm01(df_e["pib_pc"]),
                norm01(valores[-1] / valores[0] - 1), score / 10])
            tab_gemelos(df_e["estado"], X, mutante, "el estado")
        with t4:
            tab_trayectorias(valores, año, df_e["estado"],
                             "🧬 Trayectoria de precios — top 8 estados en mutación")
        with t5:
            tab_fases_estados(valores, año)
        with t6:
            st.markdown(TEXTO_MODELO)
            st.markdown(TEXTO_METODOLOGIA)

    # ══ CDMX · CÓDIGOS POSTALES (SEPOMEX real) ════════════════════════════════
    elif esc == "cp":
        valores = simular_cp(rho, detonante, clic)
        df_cp = datos_cp()
        vv = extender_pasado(valores) if retro else valores
        año_idx = año + (RETRO if retro else 0)
        v_t, tasa = estado_en(vv, año_idx)
        moran = indice_moran(v_t, vecindad_cp())
        mutante = int(np.argmax(v_t / valores[0] - 1))
        score = score_brickbit(v_t, valores[0],
                               df_cp["potencial_crecimiento"], tasa)
        with lienzo_kpi:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Precio medio CDMX", f"${v_t.mean():,.0f} /m²",
                      f"+{(v_t.mean() / valores[0].mean() - 1) * 100:.1f}% vs hoy")
            c2.metric("Índice de Moran", f"{moran:.3f}",
                      "cohesión espacial" if moran > 0.15 else "tejido fragmentado")
            c3.metric("Células postales", "1,182",
                      "polígonos SEPOMEX reales")
            c4.metric("CP más mutante", f"CP {df_cp['cp'].iloc[mutante]}",
                      f"{df_cp['alcaldia'].iloc[mutante]} · "
                      f"+{(v_t[mutante] / valores[0][mutante] - 1) * 100:.0f}%")
            c5.metric("Horizonte", f"Año {año:.1f} / {AÑOS}",
                      "epicentro por clic" if clic else
                      (detonante if DETONANTES_CDMX[detonante] else "sin detonante"))

        def fabricar(a, f):
            return construir_deck_cp(vv, a, f, mostrar_flujos, mostrar_lisa)

        render_mapa(lienzo, fabricar, año_idx, reproducir, 60,
                    float(vv.shape[0] - 1), clic_activo, "deck_cp")

        nombres_cp = "CP " + df_cp["cp"] + " · " + df_cp["alcaldia"]
        t0, t1, t2, t3, t4 = st.tabs(["Por alcaldía",
                                      "Origen del crecimiento",
                                      "Gemelos de ADN",
                                      "Trayectorias 10 años",
                                      "El modelo"])
        with t0:
            tab_alcaldias(df_cp, vv, año_idx)
        with t1:
            tab_origen(nombres_cp, _args_cp(rho, detonante, clic), mutante,
                       "el código postal")
        with t2:
            X = np.column_stack([
                norm01(df_cp["precio_actual"]),
                df_cp["potencial_crecimiento"],
                norm01(valores[-1] / valores[0] - 1), score / 10])
            tab_gemelos(nombres_cp, X, mutante, "el código postal")
        with t3:
            tab_trayectorias(valores, año, nombres_cp,
                             "🧬 Trayectoria de precios — top 8 CP en mutación")
        with t4:
            st.markdown(TEXTO_MODELO)
            st.markdown(TEXTO_METODOLOGIA)
            st.caption("Polígonos postales reales de SEPOMEX (vía "
                       "open-mexico/mexico-geojson); precio y potencial "
                       "sintetizados desde los núcleos premium y corredores "
                       "emergentes reales de CDMX.")

    # ══ CALLE · ESTABLECIMIENTO (DENUE real de CUALQUIER municipio) ═══════════
    elif esc == "calle":
        suf = st.session_state.get("municipio_suffix", "azcapotzalco")
        calles_df = expediente_calles(suf)
        _, estab_df, es_real = cargar_red_vial(suf)
        muni_nom = st.session_state.get("municipio_nombre", "Azcapotzalco")
        valores = simular_calles(rho, detonante, clic, suf)
        vv = extender_pasado(valores) if retro else valores
        año_idx = año + (RETRO if retro else 0)
        v_t, tasa = estado_en(vv, año_idx)
        mutante = int(np.argmax(v_t / valores[0] - 1))
        score = score_brickbit(v_t, valores[0],
                               calles_df["potencial_crecimiento"], tasa)

        if es_real:
            st.success(f"✅ **DATOS REALES DENUE/INEGI · {muni_nom}** — "
                       f"{len(estab_df):,} establecimientos y {len(calles_df)} "
                       "calles reales, con anclas económicas derivadas del "
                       "empleo observado.")
            anc_p = precios_reales()
            if anc_p is not None:
                st.info(f"💰 Precios calibrados con **{len(anc_p)} zonas "
                        f"ancla reales** de portales inmobiliarios "
                        f"({int(anc_p['n_muestras'].sum())} anuncios muestreados).")
        else:
            st.warning("🧪 **RED DE DEMOSTRACIÓN** — geometría sintética. "
                       "Ingiere un municipio real con "
                       "`python scripts/ingerir_denue.py --estado EE "
                       "--municipio NOMBRE` y aparecerá en el selector.")

        with lienzo_kpi:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Calles vivas", f"{len(calles_df)}",
                      f"red vial · {muni_nom}")
            c2.metric("Establecimientos", f"{len(estab_df):,}",
                      "DENUE real" if es_real else "demo etiquetada")
            c3.metric("Índice de valor medio", f"${v_t.mean():,.0f} /m²",
                      f"+{(v_t.mean() / valores[0].mean() - 1) * 100:.1f}% vs hoy")
            c4.metric("Calle más mutante",
                      calles_df["nombre"].iloc[mutante],
                      f"+{(v_t[mutante] / valores[0][mutante] - 1) * 100:.0f}% acumulado")
            c5.metric("Horizonte", f"Año {año:.1f} / {AÑOS}",
                      "epicentro por clic" if clic else
                      (detonante if CATALIZADORES[detonante] else "sin catalizador"))

        def fabricar(a, f):
            return construir_deck_calles(vv, a, f, mostrar_estab,
                                         mostrar_flujos, suf)

        _sitio = sitio_marcado(suf)
        render_mapa(lienzo, fabricar, año_idx, reproducir, 60,
                    float(vv.shape[0] - 1), clic_activo,
                    f"deck_calle_{suf}_{_sitio['rank'] if _sitio else 0}")

        banda_c = banda_calles(rho, detonante, clic, suf)
        t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(
            ["Origen del crecimiento", "Sismógrafo",
             "Impacto medido", "Ubicación B2B", "Gemelos de ADN",
             "Ranking de calles", "Trayectorias", "El modelo"])
        with t1:
            tab_origen(calles_df["nombre"],
                       _args_calles(rho, detonante, clic, suf),
                       mutante, "la calle", banda_c)
        with t2:
            tab_sismografo(suf)
            if es_real and "estancada" in calles_df.columns \
                    and calles_df["estancada"].any():
                st.markdown("#### Calles en riesgo de estancamiento")
                est_c = calles_df[calles_df["estancada"]] \
                    .nlargest(12, "n_estab")
                st.dataframe(
                    est_c[["nombre", "n_estab", "empleo", "altas_rec"]]
                    .rename(columns={"nombre": "Calle", "n_estab": "Negocios",
                                     "empleo": "Empleos",
                                     "altas_rec": "Aperturas recientes"}),
                    hide_index=True, width="stretch")
                st.caption("Tejido establecido (10+ negocios) sin UNA sola "
                           "apertura reciente: el inverso del sismógrafo — "
                           "alerta de declive.")
        with t3:
            bloque_gradiente(suf, muni_nom)
            tab_impacto(suf)
        with t4:
            tab_huecos(suf)
        with t5:
            mezcla = pd.get_dummies(calles_df["sector"]).to_numpy(dtype=float)
            X = np.column_stack([
                calles_df["vitalidad"], calles_df["cercania_ancla"],
                calles_df["resiliencia"], mezcla,
                norm01(valores[-1] / valores[0] - 1), score / 10])
            tab_gemelos(calles_df["nombre"], X, mutante, "la calle")
        with t6:
            tabla = pd.DataFrame({
                "Calle": calles_df["nombre"],
                "Score BrickBit": score,
                "Negocios": calles_df["n_estab"].astype(int),
                "Empleos": calles_df["empleo"].astype(int),
                "Sector dominante": calles_df["sector"],
                "Resiliencia": calles_df["resiliencia"],
                "Precio hoy (m²)": calles_df["valor_actual"],
                f"Precio año {año:.0f} (m²)": v_t.round(0),
                "Plusvalía acumulada": (v_t / valores[0] - 1),
                "Potencial": calles_df["potencial_crecimiento"],
            }).sort_values("Plusvalía acumulada", ascending=False)
            _tabla_ranking(tabla, año)
        with t7:
            tab_trayectorias(valores, año, calles_df["nombre"],
                             "🧬 Trayectoria — top 8 calles en mutación",
                             banda_c)
        with t8:
            _validacion_contagio(suf)
            st.markdown(TEXTO_MODELO)
            st.markdown(TEXTO_METODOLOGIA)
            st.caption("A esta escala, el crecimiento NACE de la actividad "
                       "económica observable: cada negocio suma vitalidad a "
                       "su calle, las anclas (los focos de empleo reales del "
                       "DENUE) bombean potencial, y el contagio viaja por los "
                       "cruces viales.")

    # ══ MICROTEJIDO (motor original) ══════════════════════════════════════════
    else:
        gdf = generar_tejido_urbano(alcance_micro)
        valores = simular_micro(rho, detonante, alcance_micro)
        precio_t, tasa = estado_en(valores, año)
        with lienzo_kpi:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Valor medio del tejido", f"${precio_t.mean():,.0f} /m²",
                      f"+{(precio_t.mean() / valores[0].mean() - 1) * 100:.1f}% vs hoy")
            c2.metric("Células en mutación",
                      f"{int((tasa >= np.quantile(tasa, 0.90)).sum())}",
                      f"top 10% de {len(gdf):,} células"
                      + (" · ZMVM" if alcance_micro == "zmvm"
                         else f" · {UNIDADES_MICRO[alcance_micro]['nombre']}"
                         if alcance_micro in UNIDADES_MICRO else ""))
            c3.metric("Pulso de capital", "22 flujos activos", f"ρ = {rho:.2f}")
            c4.metric("Horizonte", f"Año {año:.1f} / {AÑOS}",
                      detonante if CATALIZADORES[detonante] else "sin catalizador")

        def fabricar(a, f):
            return construir_deck_micro(gdf, valores, a, f,
                                        mostrar_flujos, extrusion)

        if reproducir:
            animar(lienzo, fabricar)
        else:
            lienzo.pydeck_chart(fabricar(año, (año * 0.4) % 1.0),
                                width="stretch")

    # ── Leyenda de marca ──────────────────────────────────────────────────────
    st.markdown(
        f"<div class='leyenda'>"
        f"<span style='color:{ARCILLA_PROF}'>■</span> latente&nbsp;&nbsp;"
        f"<span style='color:{ARCILLA}'>■</span> despertando&nbsp;&nbsp;"
        f"<span style='color:{ARCILLA_SUAVE}'>■</span> expansión&nbsp;&nbsp;"
        f"<span style='color:{LIMA}'>■</span> mutación&nbsp;&nbsp;"
        f"<span style='color:{CREMA}'>■</span> núcleo consolidado"
        "&nbsp;&nbsp;·&nbsp;&nbsp; arcos verde→oliva = capital fluyendo "
        "de corazones a zonas emergentes</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    # Red de seguridad: en Streamlit Cloud (1 GB de RAM, CPU compartida) un pico
    # de memoria o un dato inesperado no debe dejar la app muerta en gris.
    # Convertimos cualquier explosión en un mensaje accionable + recuperación.
    try:
        main()
    except Exception as _exc:                              # noqa: BLE001
        import gc
        import traceback

        st.error(
            "🧬 El organismo tuvo un espasmo (posible falta de memoria del "
            "servidor gratuito de Streamlit, o un dato inesperado). "
            "Pulsa **Liberar memoria y reintentar** — la app se recupera sola."
        )
        if st.button("Liberar memoria y reintentar", type="primary"):
            st.cache_data.clear()
            gc.collect()
            st.rerun()
        with st.expander("Detalle técnico (para soporte)"):
            st.code("".join(traceback.format_exception(_exc)), language="text")
