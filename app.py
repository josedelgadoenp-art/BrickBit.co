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
import time
import urllib.request

import numpy as np
import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st
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
ARCILLA = "#1a7d50"         # --clay        verde marca
ARCILLA_SUAVE = "#57c389"   # --clay-soft
LIMA = "#cdf25a"            # --lime        acento eléctrico
LIMA_PROF = "#a9d23f"       # --lime-deep

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

# Estilos de basemap (Carto, sin token). "Voyager" ≈ look Google Maps.
ESTILOS_MAPA = {
    "🌱 Tierra BrickBit (oscuro)": "https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json",
    "🗺 Voyager (estilo Google Maps)": "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
    "☀️ Positron claro": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
}

# Rampa "vegetal" BrickBit: arcilla profunda → arcilla → arcilla suave → lima → crema
_STOPS_T = np.array([0.00, 0.30, 0.55, 0.80, 1.00])
_STOPS_R = np.array([12.0, 26.0, 87.0, 205.0, 245.0])
_STOPS_G = np.array([74.0, 125.0, 195.0, 242.0, 237.0])
_STOPS_B = np.array([48.0, 80.0, 137.0, 90.0, 227.0])

# Colorway Plotly de marca
NEON = [LIMA, ARCILLA_SUAVE, CREMA, LIMA_PROF, ARCILLA,
        "#7ce0a8", "#e8ffb0", "#3da06c"]
ESCALA_PLOTLY = [[0.0, ARCILLA_PROF], [0.30, ARCILLA],
                 [0.55, ARCILLA_SUAVE], [0.80, LIMA], [1.0, CREMA]]

# Colores RGBA de capas (sistema circulatorio en verdes/lima de marca)
RGB_ARCILLA_SUAVE = [87, 195, 137]
RGB_LIMA = [205, 242, 90]
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


def score_brickbit(v_t: np.ndarray, v0: np.ndarray, potencial: np.ndarray,
                   tasa: np.ndarray) -> np.ndarray:
    """
    Score BrickBit 0–10 por célula: plusvalía proyectada (40%) + potencial
    morfogenético (25%) + velocidad de contagio (20%) + accesibilidad de
    entrada (15%). Cada punto es auditable en '🔎 Origen del crecimiento'.
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
    "🚄 Tren Maya + Riviera (sureste)": dict(
        estados=["Yucatán", "Quintana Roo", "Campeche", "Tabasco", "Chiapas"],
        año=1, fuerza=0.50),
    "🏭 Nearshoring · corredor norte": dict(
        estados=["Nuevo León", "Coahuila", "Chihuahua", "Tamaulipas",
                 "Baja California", "Sonora"], año=2, fuerza=0.45),
    "🌊 Corredor Interoceánico (Istmo)": dict(
        estados=["Oaxaca", "Veracruz", "Tabasco"], año=2, fuerza=0.55),
    "✈️ Polo aeroespacial del Bajío": dict(
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


@st.cache_data(show_spinner="🗺 Cargando delimitación estatal…")
def cargar_estados() -> gpd.GeoDataFrame:
    """Los 32 polígonos estatales → GeoDataFrame(estado, geometry)."""
    geo = _cargar_geojson(RUTA_ESTADOS, URL_ESTADOS)
    gdf = gpd.GeoDataFrame.from_features(geo["features"], crs="EPSG:4326")
    gdf = gdf.rename(columns={"name": "estado"})[["estado", "geometry"]]
    return gdf.sort_values("estado").reset_index(drop=True)


@st.cache_data(show_spinner="🏛 Cargando los 2,436 municipios…")
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
    cen = gdf.geometry.representative_point()
    gdf["lng"], gdf["lat"] = cen.x, cen.y
    return gdf[["municipio", "estado", "lng", "lat", "geometry"]] \
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


@st.cache_data(show_spinner="🧠 Tejiendo contigüidad estatal…")
def vecindad_estados() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return _vecindad(cargar_estados().geometry.tolist(), 0.03)


@st.cache_data(show_spinner="🧠 Tejiendo las ~15,000 fronteras municipales…")
def vecindad_municipios() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return _vecindad(cargar_municipios().geometry.tolist(), 0.015)


@st.cache_data
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


@st.cache_data
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

@st.cache_data
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


@st.cache_data(show_spinner="🧫 Sintetizando el expediente municipal…")
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

    return pd.DataFrame({
        "municipio": gdf["municipio"], "estado": gdf["estado"],
        "lng": lng, "lat": lat,
        "precio_actual": precio.round(0),
        "potencial_crecimiento": potencial.round(3),
        "plusvalia_estatal": plusv_e,
        "zm_cercana": [CIUDADES[i][0] for i in zm_idx],
        "dist_zm_km": (d_zm * 105).round(0),
    })


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


@st.cache_data(show_spinner="🧬 Simulando morfogénesis estatal (SAR)…")
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


@st.cache_data(show_spinner="🧬 Simulando morfogénesis municipal (2,436 células)…")
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
            get_color=[232, 255, 176], width_min_pixels=3,
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
        "extra_txt": [f"ZM más cercana: {z} ({d:.0f} km) · potencial {q:.2f}"
                      for z, d, q in zip(df["zm_cercana"], df["dist_zm_km"],
                                         df["potencial_crecimiento"])],
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
                          mostrar_etiquetas: bool, estilo: str,
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
                    map_style=ESTILOS_MAPA[estilo], tooltip=_tooltip())


def construir_deck_municipios(valores: np.ndarray, año: float, fase: float,
                              mostrar_flujos: bool, mostrar_torres: bool,
                              mostrar_etiquetas: bool, estilo: str,
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
                    map_style=ESTILOS_MAPA[estilo], tooltip=_tooltip())


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
    "🚇 Nueva línea de Metro (norte)": dict(lng=-99.192, lat=19.497, año=2, fuerza=0.85, radio=0.011),
    "🏬 Centro comercial (poniente)": dict(lng=-99.203, lat=19.478, año=3, fuerza=0.70, radio=0.009),
    "🌳 Parque lineal Vallejo (centro)": dict(lng=-99.184, lat=19.486, año=1, fuerza=0.55, radio=0.013),
}


@st.cache_data(show_spinner="🧫 Cultivando tejido urbano…")
def generar_tejido_urbano() -> gpd.GeoDataFrame:
    """GeoDataFrame de 676 manzanas simuladas con precio, potencial y flujo."""
    rng = np.random.default_rng(SEMILLA)
    ix, iy = np.meshgrid(np.arange(NX), np.arange(NY))
    ix, iy = ix.ravel(), iy.ravel()
    lng0 = CENTRO_LNG + (ix - NX / 2) * PASO_LNG
    lat0 = CENTRO_LAT + (iy - NY / 2) * PASO_LAT
    m_lng = PASO_LNG * (1 - FACTOR_MANZANA) / 2
    m_lat = PASO_LAT * (1 - FACTOR_MANZANA) / 2
    geometrias = [box(x + m_lng, y + m_lat,
                      x + PASO_LNG - m_lng, y + PASO_LAT - m_lat)
                  for x, y in zip(lng0, lat0)]
    cx, cy = lng0 + PASO_LNG / 2, lat0 + PASO_LAT / 2

    def nucleo(lng, lat, sigma):
        return np.exp(-((cx - lng) ** 2 + (cy - lat) ** 2) / (2 * sigma ** 2))

    precio = (13500 + 14000 * nucleo(-99.176, 19.470, 0.010)
              + 9000 * nucleo(-99.170, 19.492, 0.008)
              + 5500 * nucleo(-99.200, 19.472, 0.007))
    precio *= rng.lognormal(0.0, 0.10, precio.size)
    potencial = np.clip(0.90 * nucleo(-99.186, 19.489, 0.011)
                        + 0.65 * nucleo(-99.199, 19.494, 0.009)
                        + 0.40 * nucleo(-99.174, 19.478, 0.010)
                        + rng.uniform(0.05, 0.22, precio.size), 0, 1)
    qx, qy = np.minimum(ix * 3 // NX, 2), np.minimum(iy * 3 // NY, 2)
    gdf = gpd.GeoDataFrame({
        "barrio": [BARRIOS[int(b)] for b in (qy * 3 + qx)],
        "precio_actual": precio.round(0),
        "potencial_crecimiento": potencial.round(3),
        "lng": cx, "lat": cy,
    }, geometry=geometrias, crs="EPSG:4326")
    gdf["contorno"] = gdf.geometry.apply(
        lambda g: [list(map(list, g.exterior.coords))])
    return gdf


@st.cache_data
def vecindad_reina() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Contigüidad reina de la retícula micro: la W del SAR celular."""
    pares_i, pares_j = [], []
    for y in range(NY):
        for x in range(NX):
            i = y * NX + x
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx_, ny_ = x + dx, y + dy
                    if 0 <= nx_ < NX and 0 <= ny_ < NY:
                        pares_i.append(i)
                        pares_j.append(ny_ * NX + nx_)
    pares_i, pares_j = np.asarray(pares_i), np.asarray(pares_j)
    grados = np.bincount(pares_i, minlength=NX * NY).astype(float)
    return pares_i, pares_j, grados


@st.cache_data(show_spinner="🧬 Simulando morfogénesis celular…")
def simular_micro(rho: float, catalizador: str) -> np.ndarray:
    """SAR celular con catalizador gaussiano (célula madre puntual)."""
    gdf = generar_tejido_urbano()
    pi, pj, g = vecindad_reina()
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
                         extrusion: bool, estilo: str) -> pdk.Deck:
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
    return pdk.Deck(layers=capas,
                    initial_view_state=_vista(CENTRO_LNG, CENTRO_LAT, 13.1,
                                              pitch=52, bearing=-16),
                    map_style=ESTILOS_MAPA[estilo], tooltip=_tooltip())


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
    "🚠 Cablebús + Metro norte (Vallejo)": dict(lng=-99.186, lat=19.489, año=1, fuerza=0.55, radio=0.030),
    "🏗 Corredor Reforma Norte": dict(lng=-99.155, lat=19.445, año=2, fuerza=0.50, radio=0.025),
    "🌳 Regeneración oriente (Iztapalapa)": dict(lng=-99.065, lat=19.355, año=1, fuerza=0.60, radio=0.040),
}


URL_CP = ("https://raw.githubusercontent.com/open-mexico/mexico-geojson/"
          "master/09-Cdmx.geojson")


@st.cache_data(show_spinner="🏘 Cargando 1,182 códigos postales SEPOMEX…")
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


@st.cache_data(show_spinner="🧠 Tejiendo contigüidad postal…")
def vecindad_cp() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return _vecindad(cargar_cp().geometry.tolist(), 0.0025)


@st.cache_data
def contornos_cp() -> pd.DataFrame:
    filas = []
    for idx, geom in enumerate(cargar_cp().geometry):
        geoms = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
        for g in geoms:
            filas.append({"idx_cp": idx,
                          "contorno": [[[round(x, 5), round(y, 5)]
                                        for x, y in g.exterior.coords]]})
    return pd.DataFrame(filas)


@st.cache_data
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
        "airbnb": 0,
    })

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


@st.cache_data(show_spinner="🧬 Simulando morfogénesis postal (SEPOMEX)…")
def simular_cp(rho: float, detonante: str, clic: tuple = None) -> np.ndarray:
    return _sar(**_args_cp(rho, detonante, clic))


def construir_deck_cp(valores: np.ndarray, año: float, fase: float,
                      mostrar_flujos: bool, estilo: str,
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
                    map_style=ESTILOS_MAPA[estilo], tooltip=_tooltip())


# ══════════════════════════════════════════════════════════════════════════════
# 8C · ESCALA CALLE · ESTABLECIMIENTO — DENUE REAL (si existe) O DEMO
#      La app detecta data/calles_azcapotzalco.json +
#      data/establecimientos_azcapotzalco.csv.gz generados por
#      scripts/ingerir_denue.py (INEGI). Sin ellos, usa una red de
#      demostración claramente etiquetada.
# ══════════════════════════════════════════════════════════════════════════════

RUTA_CALLES = os.path.join(_DIR, "data", "calles_azcapotzalco.json")
RUTA_ESTAB = os.path.join(_DIR, "data", "establecimientos_azcapotzalco.csv.gz")

# Anclas económicas reales de Azcapotzalco: de aquí "nace" el crecimiento
ANCLAS_AZC = [
    ("🏬 Parque Vía Vallejo", -99.1757, 19.4887, 0.95),
    ("🚇 Metro El Rosario", -99.2003, 19.5048, 0.80),
    ("🚇 Metro Camarones", -99.1745, 19.4790, 0.65),
    ("🎓 UAM Azcapotzalco", -99.2052, 19.5043, 0.60),
    ("🏥 Hospital La Raza", -99.1690, 19.4700, 0.70),
]

SECTORES = {
    "Comercio": [205, 242, 90],       # lima
    "Servicios": [87, 195, 137],      # arcilla suave
    "Industria": [245, 237, 227],     # crema
    "Alimentos": [124, 224, 168],     # verde medio
}

_AZC_W, _AZC_E = -99.215, -99.155    # bounding box Azcapotzalco aprox
_AZC_S, _AZC_N = 19.462, 19.508

# Nombres viales reales de Azcapotzalco para la red (demo o etiquetas)
_VIAS_NS = ["Av. Aquiles Serdán", "Av. Tezozómoc", "Av. de las Granjas",
            "Calz. Vallejo", "Av. Ceylán", "Poniente 116", "Poniente 128",
            "Poniente 134", "Poniente 140", "Poniente 146", "Poniente 152",
    "Av. Jardín", "Calle 22 de Febrero", "Av. Granjas Norte"]
_VIAS_EO = ["Av. Azcapotzalco", "Av. Cuitláhuac", "Eje 5 Norte",
            "Eje 4 Norte", "Calz. Camarones", "Av. El Rosario", "Norte 45",
            "Norte 59", "Norte 77", "Norte 87", "Av. San Pablo Xalpa",
            "Av. Renacimiento"]

_GIROS = {
    "Comercio": ["Abarrotes", "Ferretería", "Papelería", "Refaccionaria",
                 "Tienda de ropa", "Miscelánea"],
    "Servicios": ["Taller mecánico", "Estética", "Consultorio", "Lavandería",
                  "Despacho contable", "Ciber"],
    "Industria": ["Taller metalmecánico", "Bodega logística", "Imprenta",
                  "Fábrica de alimentos", "Maquiladora textil"],
    "Alimentos": ["Taquería", "Fonda", "Panadería", "Juguería", "Cocina económica"],
}
_NOMBRES = ["La Esperanza", "El Fénix", "San José", "Doña Mary", "El Águila",
            "Vallejo", "La Central", "Don Beto", "La Norteña", "El Porvenir",
            "Santa Cruz", "El Trébol", "La Guadalupana", "Azcapotzalco"]


def hay_datos_denue() -> bool:
    """¿Existen los archivos reales generados por scripts/ingerir_denue.py?"""
    return os.path.exists(RUTA_CALLES) and os.path.exists(RUTA_ESTAB)


@st.cache_data(show_spinner="🛣 Construyendo la red vial…")
def cargar_red_vial() -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    """
    Devuelve (calles, establecimientos, es_real).

    · REAL: calles del DENUE/vialidades (scripts/ingerir_denue.py) con
      establecimientos INEGI georreferenciados.
    · DEMO: retícula sintética con nombres viales y anclas reales de
      Azcapotzalco, claramente etiquetada en la interfaz.
    """
    if hay_datos_denue():
        with open(RUTA_CALLES, encoding="utf-8") as f:
            calles = pd.DataFrame(json.load(f)["calles"])
        estab = pd.read_csv(RUTA_ESTAB)
        return calles, estab, True

    # ── DEMO sintético ─────────────────────────────────────────────────────────
    rng = np.random.default_rng(SEMILLA)
    xs = np.linspace(_AZC_W, _AZC_E, len(_VIAS_NS))
    ys = np.linspace(_AZC_S, _AZC_N, len(_VIAS_EO))
    filas = []
    for x, nombre in zip(xs, _VIAS_NS):
        pts = [[float(x + rng.normal(0, 3e-4)), float(y)]
               for y in np.linspace(_AZC_S, _AZC_N, 6)]
        filas.append({"nombre": nombre, "camino": pts, "eje": "NS"})
    for y, nombre in zip(ys, _VIAS_EO):
        pts = [[float(x), float(y + rng.normal(0, 3e-4))]
               for x in np.linspace(_AZC_W, _AZC_E, 6)]
        filas.append({"nombre": nombre, "camino": pts, "eje": "EO"})
    calles = pd.DataFrame(filas)

    # establecimientos: densidad alta cerca de anclas y del corredor Vallejo
    ax = np.array([a[1] for a in ANCLAS_AZC])
    ay = np.array([a[2] for a in ANCLAS_AZC])
    aw = np.array([a[3] for a in ANCLAS_AZC])
    registros = []
    for i, c in calles.iterrows():
        pts = np.array(c["camino"])
        mid = pts.mean(axis=0)
        cerca = (aw * np.exp(-((ax - mid[0]) ** 2 + (ay - mid[1]) ** 2)
                             / (2 * 0.012 ** 2))).sum()
        es_avenida = not c["nombre"].startswith(("Poniente", "Norte", "Calle"))
        n = rng.poisson(14 + 46 * min(cerca, 1.2) + (22 if es_avenida else 0))
        for _ in range(n):
            u = rng.uniform()
            k = min(int(u * (len(pts) - 1)), len(pts) - 2)
            frac = u * (len(pts) - 1) - k
            lng = pts[k, 0] + (pts[k + 1, 0] - pts[k, 0]) * frac \
                + rng.normal(0, 1.2e-4)
            lat = pts[k, 1] + (pts[k + 1, 1] - pts[k, 1]) * frac \
                + rng.normal(0, 1.2e-4)
            industrial = lng > -99.19 and lat > 19.478    # Vallejo Industrial
            pesos = [0.38, 0.27, 0.22 if industrial else 0.07,
                     0.13 if not industrial else 0.08]
            sector = rng.choice(list(SECTORES.keys()),
                                p=np.array(pesos) / np.sum(pesos))
            registros.append({
                "nombre": f"{rng.choice(_GIROS[sector])} {rng.choice(_NOMBRES)}",
                "sector": sector, "calle": c["nombre"],
                "lat": float(lat), "lng": float(lng),
                "empleo": int(rng.choice([2, 4, 8, 18, 45],
                                         p=[.45, .28, .16, .08, .03])),
            })
    return calles, pd.DataFrame(registros), False


@st.cache_data
def expediente_calles() -> pd.DataFrame:
    """
    Expediente por calle: vitalidad económica (establecimientos + empleo del
    DENUE o demo), cercanía a anclas y valor sintetizado. AQUÍ nace el
    crecimiento: cada peso proyectado es rastreable a la actividad económica
    observada sobre la vialidad.
    """
    calles, estab, _ = cargar_red_vial()
    agg = estab.groupby("calle").agg(
        n_estab=("nombre", "size"), empleo=("empleo", "sum"),
        sector=("sector", lambda s: s.mode().iat[0])).reset_index()
    df = calles.merge(agg, left_on="nombre", right_on="calle", how="left") \
        .fillna({"n_estab": 0, "empleo": 0, "sector": "Servicios"})

    mids = np.array([np.mean(c, axis=0) for c in df["camino"]])
    ax = np.array([a[1] for a in ANCLAS_AZC])
    ay = np.array([a[2] for a in ANCLAS_AZC])
    aw = np.array([a[3] for a in ANCLAS_AZC])
    ancla = np.stack([w * np.exp(-((mids[:, 0] - x) ** 2 + (mids[:, 1] - y) ** 2)
                                 / (2 * 0.012 ** 2))
                      for x, y, w in zip(ax, ay, aw)]).sum(axis=0)

    vital = norm01(np.log1p(df["n_estab"]) + 0.6 * np.log1p(df["empleo"]))
    df["vitalidad"] = vital.round(3)
    df["cercania_ancla"] = np.clip(ancla, 0, 1.3).round(3)
    df["valor_actual"] = (9000 + 9500 * vital + 6500 * np.clip(ancla, 0, 1)
                          ).round(0)
    # potencial: anclas cerca + margen de crecimiento (calles aún baratas)
    df["potencial_crecimiento"] = np.clip(
        0.50 * np.clip(ancla, 0, 1) + 0.35 * (1 - vital)
        + 0.15 * norm01(df["n_estab"]), 0.02, 1).round(3)

    # resiliencia: entropía de Shannon del mix sectorial — una calle
    # monocultivo (todo talleres) es frágil; una diversificada aguanta shocks
    mix = estab.groupby(["calle", "sector"]).size().unstack(fill_value=0)
    p = mix.div(mix.sum(axis=1), axis=0).clip(lower=1e-9)
    entropia = (-(p * np.log(p)).sum(axis=1) / math.log(len(SECTORES)))
    df["resiliencia"] = df["nombre"].map(entropia).fillna(0.0).round(3)
    return df


# ── Sismógrafo de gentrificación: especies indicadoras del DENUE ─────────────
RUTA_SISMO = os.path.join(_DIR, "data", "sismografo_azcapotzalco.json")

# Giros cuya APARICIÓN precede a la plusvalía 2-3 años (literatura de
# gentrificación). scripts/ingerir_denue.py --csv-anterior los detecta
# comparando dos cortes reales del DENUE.
ESPECIES_INDICADORAS = ["Café de especialidad", "Coworking", "Galería",
                        "Barbería premium", "Estudio de yoga",
                        "Panadería artesanal", "Veterinaria", "Gym boutique"]


@st.cache_data
def sismografo_calles() -> tuple[pd.DataFrame, bool]:
    """
    Metabolismo de cada calle entre dos cortes del DENUE: altas y bajas de
    establecimientos, con foco en las ESPECIES INDICADORAS que anticipan la
    mutación. Real si existe data/sismografo_*.json (ingesta INEGI);
    demo etiquetada si no.
    """
    df = expediente_calles()
    if os.path.exists(RUTA_SISMO):
        with open(RUTA_SISMO, encoding="utf-8") as f:
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


@st.cache_data(show_spinner="🧠 Detectando cruces entre calles…")
def vecindad_calles() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Dos calles son vecinas si se cruzan (o pasan a <60 m). El contagio
    viaja por las intersecciones, como el tráfico."""
    from shapely.geometry import LineString
    geoms = [LineString(c) for c in expediente_calles()["camino"]]
    return _vecindad(geoms, 0.0006)


def _args_calles(rho: float, catalizador: str, clic: tuple = None) -> dict:
    df = expediente_calles()
    pi, pj, g = vecindad_calles()
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


@st.cache_data(show_spinner="🧬 Simulando morfogénesis vial…")
def simular_calles(rho: float, catalizador: str,
                   clic: tuple = None) -> np.ndarray:
    return _sar(**_args_calles(rho, catalizador, clic))


def construir_deck_calles(valores: np.ndarray, año: float, fase: float,
                          mostrar_estab: bool, mostrar_flujos: bool,
                          estilo: str) -> pdk.Deck:
    """La zona vista desde la banqueta: calles que laten, negocios que
    alimentan el crecimiento y anclas que lo detonan."""
    df = expediente_calles()
    _, estab, _ = cargar_red_vial()
    v_t, tasa = estado_en(valores, año)
    acum = v_t / valores[0] - 1
    t = 0.45 * norm01(v_t) + 0.55 * norm01(acum)
    rgb = paleta_marca(t ** 0.85)
    alfa = np.clip((110 + 130 * t) * _respiracion(t, fase), 60, 255)

    mids_c = np.array([np.mean(c, axis=0) for c in df["camino"]])
    calles_render = pd.DataFrame({
        "camino": df["camino"],
        "lng": mids_c[:, 0], "lat": mids_c[:, 1],
        "color": np.column_stack([rgb, alfa]).astype(int).tolist(),
        "ancho": (2.5 + 9 * df["vitalidad"].to_numpy()).tolist(),
        "nombre": df["nombre"],
        "estado_bio": clasificar_bio(tasa),
        "precio_txt": [f"${p:,.0f} índice/m²" for p in v_t],
        "crec_txt": [f"+{r * 100:.1f}% anual" for r in tasa],
        "plusvalia_txt": [f"+{a * 100:.0f}% vs hoy" for a in acum],
        "extra_txt": [f"{int(n)} negocios · {int(e)} empleos · {s}"
                      for n, e, s in zip(df["n_estab"], df["empleo"],
                                         df["sector"])],
    })
    capas = [pdk.Layer(
        "PathLayer", id="celulas", data=calles_render, get_path="camino",
        get_color="color", get_width="ancho", width_units="pixels",
        width_min_pixels=2, pickable=True, auto_highlight=True,
        highlight_color=RGB_CREMA + [160], cap_rounded=True,
        joint_rounded=True,
    )]

    if mostrar_estab:
        er = pd.DataFrame({
            "pos": [[float(a), float(b)] for a, b in zip(estab["lng"],
                                                         estab["lat"])],
            "color": [SECTORES.get(s, RGB_CREMA) + [190]
                      for s in estab["sector"]],
            "radio": (14 + np.sqrt(estab["empleo"].to_numpy()) * 7).tolist(),
            "nombre": estab["nombre"],
            "estado_bio": "",
            "precio_txt": estab["sector"],
            "crec_txt": estab["calle"],
            "plusvalia_txt": estab["empleo"].astype(str) + " empleos",
            "extra_txt": "",
        })
        capas.append(pdk.Layer(
            "ScatterplotLayer", data=er, get_position="pos",
            get_fill_color="color", get_radius="radio",
            radius_min_pixels=1.5, radius_max_pixels=9,
            pickable=True, opacity=0.75,
        ))

    # anclas económicas: los corazones que bombean el crecimiento
    pulso = 0.5 + 0.5 * math.sin(2 * math.pi * fase)
    anclas = pd.DataFrame({
        "pos": [[a[1], a[2]] for a in ANCLAS_AZC],
        "nombre": [a[0] for a in ANCLAS_AZC],
        "peso": [a[3] for a in ANCLAS_AZC],
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
        dest = np.argsort(tasa)[::-1][:14]
        ax = np.array([a[1] for a in ANCLAS_AZC])
        ay = np.array([a[2] for a in ANCLAS_AZC])
        aw = np.array([a[3] for a in ANCLAS_AZC])
        filas = []
        for k, d in enumerate(dest):
            dist = np.hypot(ax - mids[d, 0], ay - mids[d, 1])
            f = int(np.argmax(aw / (dist + 1e-3)))
            filas.append({"origen": [float(ax[f]), float(ay[f])],
                          "destino": [float(mids[d, 0]), float(mids[d, 1])],
                          "intensidad": float(tasa[d] / (tasa.max() + 1e-9)),
                          "desfase": (k * 0.13) % 1.0})
        capas += _capas_circulatorias(pd.DataFrame(filas), fase, escala=0.006)

    return pdk.Deck(layers=capas,
                    initial_view_state=_vista(-99.185, 19.485, 13.4,
                                              pitch=48, bearing=-12),
                    map_style=ESTILOS_MAPA[estilo], tooltip=_tooltip())


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
    tabla = pd.DataFrame({
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
        "ZM más cercana": df["zm_cercana"],
        "Dist. ZM (km)": df["dist_zm_km"],
    }).nlargest(40, "Plusvalía acumulada")
    st.caption("🏆 Top 40 de 2,436 municipios por plusvalía acumulada — "
               "el anillo periurbano de las ZM domina la mutación.")
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
            "Score BrickBit": st.column_config.NumberColumn(format="%.1f ⚡"),
            "Precio hoy (m²)": st.column_config.NumberColumn(format="$%d"),
            f"Precio año {año:.0f} (m²)": st.column_config.NumberColumn(
                format="$%d"),
        })


def tab_trayectorias(valores: np.ndarray, año: float,
                     nombres: pd.Series, titulo: str) -> None:
    """Evolución proyectada del precio: las 8 mutaciones más agresivas."""
    acum = valores[-1] / valores[0] - 1
    top = np.argsort(acum)[::-1][:8]
    fig = go.Figure()
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
               unidad: str) -> None:
    """
    Pestaña '¿De dónde viene el crecimiento?': elige una unidad y el motor
    desglosa su plusvalía en crecimiento propio vs contagio, identificando a
    los vecinos exactos que lo bombean.
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

    c1, c2, c3 = st.columns(3)
    c1.metric("📈 Crecimiento total a 10 años",
              f"+${total:,.0f} /m²", f"+{total / v0 * 100:.0f}% sobre hoy")
    c2.metric("🌱 Crecimiento propio", f"{total_p / total * 100:.0f}%",
              "plusvalía/vitalidad intrínseca")
    c3.metric("🧬 Contagio vecinal", f"{total_c / total * 100:.0f}%",
              f"desde {len(vecinos)} vecinos directos")

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
    with st.expander("🧠 Tesis de inversión narrada"):
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
        "🌅 Anillo periurbano del sureste": (
            df["estado"].isin(["Yucatán", "Quintana Roo", "Campeche"])
            & df["dist_zm_km"].between(8, 45)),
        "🏭 Corredor nearshoring norte": (
            df["estado"].isin(["Nuevo León", "Coahuila", "Chihuahua",
                               "Tamaulipas", "Baja California", "Sonora"])
            & (df["dist_zm_km"] < 35)),
        "🌊 Frente de onda (LISA)": pd.Series(frente, index=df.index),
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


def tab_sismografo() -> None:
    """🌡 Sismógrafo de gentrificación: metabolismo de establecimientos y
    especies indicadoras que anticipan la mutación 2-3 años."""
    sismo, es_real = sismografo_calles()
    if not es_real:
        st.info("🧪 Churn de demostración. Con dos cortes reales del DENUE "
                "(`ingerir_denue.py --csv-anterior denue_2023.csv`) el "
                "sismógrafo detecta altas/bajas y especies indicadoras "
                "reales calle por calle.")
    top = sismo.nlargest(12, "magnitud")
    c1, c2 = st.columns([2, 3])
    with c1:
        lider = sismo.loc[sismo["magnitud"].idxmax()]
        st.metric("🌡 Epicentro de mutación", lider["nombre"],
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


def tab_huecos() -> None:
    """🕳 Radar de huecos de mercado: dónde hay demanda (empleo/vitalidad)
    sin oferta de un giro — inteligencia B2B para retail y franquicias."""
    df = expediente_calles()
    _, estab, es_real = cargar_red_vial()
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
          box-shadow: 0 0 18px rgba(205,242,90,.06);
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
      #MainMenu, footer {{ visibility: hidden; }}
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
        '· proyección simulada a 10 años</div>'
        '</div></div>',
        unsafe_allow_html=True)


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
        lienzo.pydeck_chart(deck, width="stretch")
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


def main() -> None:
    st.set_page_config(page_title="BrickBit · Morfogénesis Urbana MX",
                       page_icon="🧬", layout="wide",
                       initial_sidebar_state="expanded")
    inyectar_css()
    if os.path.exists(RUTA_LOGO):
        st.logo(RUTA_LOGO, size="large")
    encabezado()

    # ── Panel lateral ─────────────────────────────────────────────────────────
    with st.sidebar:
        escala = st.radio("🔭 Escala del organismo",
                          ["🏛 República · municipios",
                           "🇲🇽 República · estados",
                           "🏘 CDMX · códigos postales",
                           "🛣 Calle · establecimiento (AZC)",
                           "🧫 Microtejido (CDMX)"],
                          help="El mismo motor SAR a cinco escalas: de los 32 "
                               "estados hasta la banqueta, negocio a negocio.")

        st.markdown("### ⏳ Línea de tiempo")
        retro = st.checkbox("⏪ Time-lapse bidireccional (retro-simulación)",
                            False,
                            help="Extiende la línea de tiempo 5 años hacia "
                                 "atrás para ver de dónde viene la ola.")
        año = st.slider("Predicción (años)",
                        -float(RETRO) if retro else 0.0, float(AÑOS),
                        0.0, step=0.25, format="%.2f años")

        st.markdown("### 🧫 Parámetros del organismo")
        rho = st.slider("Virulencia del contagio (ρ)", 0.0, 1.5, 0.85, 0.05,
                        help="Coeficiente espacial autorregresivo: cuánto pesa "
                             "el vecindario en el crecimiento de cada célula.")
        if escala.startswith(("🧫", "🛣")):
            detonante = st.selectbox("Célula madre (catalizador urbano)",
                                     list(CATALIZADORES.keys()))
        elif escala.startswith("🏘"):
            detonante = st.selectbox("Detonante urbano CDMX",
                                     list(DETONANTES_CDMX.keys()))
        else:
            detonante = st.selectbox("Megaproyecto detonante",
                                     list(MEGAPROYECTOS.keys()),
                                     help="Célula madre a escala nación: eleva "
                                          "el potencial de toda una región.")

        st.markdown("### 👁 Capas y estilo")
        estilo = st.selectbox("Estilo de mapa", list(ESTILOS_MAPA.keys()))
        mostrar_flujos = st.checkbox("🫀 Sistema circulatorio de capital", True)
        if escala.startswith("🧫"):
            extrusion = st.checkbox("⛰ Relieve 3D del tejido", True)
        elif escala.startswith("🛣"):
            mostrar_estab = st.checkbox("🏪 Establecimientos (puntos)", True)
        elif not escala.startswith("🏘"):
            mostrar_torres = st.checkbox("🏙 Torres metropolitanas 3D", True)
            mostrar_etiquetas = st.checkbox("🏷 Nombres de ciudades", True)

        mostrar_lisa = False
        if escala.startswith(("🏛", "🏘")):
            mostrar_lisa = st.checkbox("🌊 Frente de onda (LISA)", False,
                                       help="Moran local: contorno crema en "
                                            "las células baratas rodeadas de "
                                            "caras — donde romperá la ola.")

        st.markdown("### 🎯 Detonante por clic")
        clic_activo = st.checkbox("Activar clic-para-detonar", False,
                                  help="Haz clic en cualquier célula del mapa "
                                       "e inyecta ahí una célula madre; mira "
                                       "la onda expansiva (SimCity al revés).")
        clic = st.session_state.get("clic_epicentro") if clic_activo else None
        if clic_activo and clic:
            st.caption(f"Epicentro activo: {clic[1]:.3f}, {clic[0]:.3f}")
            if st.button("🧹 Quitar epicentro", width="stretch"):
                del st.session_state["clic_epicentro"]
                st.rerun()

        st.markdown("---")
        reproducir = st.button("▶ Reproducir morfogénesis (10 años)",
                               width="stretch")
        st.caption("Las venas verdes→lima bombean capital de los corazones "
                   "hacia las zonas emergentes. Datos simulados.")

    lienzo_kpi = st.container()
    lienzo = st.empty()

    # ══ REPÚBLICA · MUNICIPIOS ════════════════════════════════════════════════
    if escala.startswith("🏛"):
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
        with lienzo_kpi:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("💰 Precio municipal medio", f"${v_t.mean():,.0f} /m²",
                      f"+{(v_t.mean() / valores[0].mean() - 1) * 100:.1f}% vs hoy")
            c2.metric("🧲 Índice de Moran", f"{moran:.3f}",
                      "cohesión espacial" if moran > 0.15 else "tejido fragmentado")
            c3.metric("🫀 Capital en rotación",
                      f"${flujos['capital_mmd'].sum():,.0f} mmd/año",
                      f"{len(flujos)} arterias activas")
            c4.metric("🧬 Municipio más mutante",
                      df_m["municipio"].iloc[mutante],
                      f"{df_m['estado'].iloc[mutante]} · "
                      f"+{(v_t[mutante] / valores[0][mutante] - 1) * 100:.0f}%")
            c5.metric("📅 Horizonte", f"Año {año:.1f} / {AÑOS}",
                      "🎯 epicentro por clic" if clic else
                      (detonante if MEGAPROYECTOS[detonante] else "sin megaproyecto"))

        def fabricar(a, f):
            return construir_deck_municipios(
                vv, a, f, mostrar_flujos, mostrar_torres,
                mostrar_etiquetas, estilo, flujos_nacionales(ve, a),
                ve, mostrar_lisa)

        render_mapa(lienzo, fabricar, año_idx, reproducir, 48,
                    float(vv.shape[0] - 1), clic_activo, "deck_mun")

        nombres_m = df_m["municipio"] + " · " + df_m["estado"]
        t1, t2, t3, t4, t5, t6, t7 = st.tabs(
            ["🏆 Ranking municipal", "🔎 Origen del crecimiento",
             "🧬 Gemelos de ADN", "💼 Carteras por tesis",
             "📈 Trayectorias 10 años", "⚗️ Nube de fases", "🔬 El modelo"])
        with t1:
            tab_ranking_municipios(valores, año, score)
        with t2:
            tab_origen(nombres_m, _args_municipios(rho, detonante, clic),
                       mutante, "el municipio")
        with t3:
            acum10 = valores[-1] / valores[0] - 1
            X = np.column_stack([
                norm01(df_m["precio_actual"]),
                df_m["potencial_crecimiento"],
                norm01(df_m["dist_zm_km"]), norm01(acum10),
                score / 10])
            tab_gemelos(nombres_m, X, mutante, "el municipio")
        with t4:
            tab_carteras(valores)
        with t5:
            tab_trayectorias(valores, año,
                             df_m["municipio"] + " (" + df_m["estado"] + ")",
                             "🧬 Trayectoria de precios — top 8 municipios en mutación")
        with t6:
            tab_fases_municipios(valores, año)
        with t7:
            st.markdown(TEXTO_MODELO)

    # ══ REPÚBLICA · ESTADOS ═══════════════════════════════════════════════════
    elif escala.startswith("🇲🇽"):
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
            c1.metric("💰 Valor medio nacional", f"${medio:,.0f} /m²",
                      f"+{(medio / medio_0 - 1) * 100:.1f}% vs hoy")
            c2.metric("🧲 Índice de Moran", f"{moran:.3f}",
                      "cohesión espacial" if moran > 0.15 else "tejido fragmentado")
            c3.metric("🫀 Capital en rotación",
                      f"${flujos['capital_mmd'].sum():,.0f} mmd/año",
                      f"{len(flujos)} arterias activas")
            c4.metric("🧬 Estado más mutante", df_e["estado"].iloc[mutante],
                      f"+{(v_t[mutante] / valores[0][mutante] - 1) * 100:.0f}% acumulado")
            c5.metric("📅 Horizonte", f"Año {año:.1f} / {AÑOS}",
                      "🎯 epicentro por clic" if clic else
                      (detonante if MEGAPROYECTOS[detonante] else "sin megaproyecto"))

        def fabricar(a, f):
            return construir_deck_nacion(vv, a, f, mostrar_flujos,
                                         mostrar_torres, mostrar_etiquetas,
                                         estilo, flujos_nacionales(vv, a))

        render_mapa(lienzo, fabricar, año_idx, reproducir, 90,
                    float(vv.shape[0] - 1), clic_activo, "deck_edo")

        t1, t2, t3, t4, t5, t6 = st.tabs(["🏆 Ranking de mutación",
                                          "🔎 Origen del crecimiento",
                                          "🧬 Gemelos de ADN",
                                          "📈 Trayectorias 10 años",
                                          "⚗️ Diagrama de fases",
                                          "🔬 El modelo"])
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

    # ══ CDMX · CÓDIGOS POSTALES (SEPOMEX real) ════════════════════════════════
    elif escala.startswith("🏘"):
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
            c1.metric("💰 Precio medio CDMX", f"${v_t.mean():,.0f} /m²",
                      f"+{(v_t.mean() / valores[0].mean() - 1) * 100:.1f}% vs hoy")
            c2.metric("🧲 Índice de Moran", f"{moran:.3f}",
                      "cohesión espacial" if moran > 0.15 else "tejido fragmentado")
            c3.metric("🏘 Células postales", "1,182",
                      "polígonos SEPOMEX reales")
            c4.metric("🧬 CP más mutante", f"CP {df_cp['cp'].iloc[mutante]}",
                      f"{df_cp['alcaldia'].iloc[mutante]} · "
                      f"+{(v_t[mutante] / valores[0][mutante] - 1) * 100:.0f}%")
            c5.metric("📅 Horizonte", f"Año {año:.1f} / {AÑOS}",
                      "🎯 epicentro por clic" if clic else
                      (detonante if DETONANTES_CDMX[detonante] else "sin detonante"))

        def fabricar(a, f):
            return construir_deck_cp(vv, a, f, mostrar_flujos, estilo,
                                     mostrar_lisa)

        render_mapa(lienzo, fabricar, año_idx, reproducir, 60,
                    float(vv.shape[0] - 1), clic_activo, "deck_cp")

        nombres_cp = "CP " + df_cp["cp"] + " · " + df_cp["alcaldia"]
        t1, t2, t3, t4 = st.tabs(["🔎 Origen del crecimiento",
                                  "🧬 Gemelos de ADN",
                                  "📈 Trayectorias 10 años", "🔬 El modelo"])
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
            st.caption("Polígonos postales reales de SEPOMEX (vía "
                       "open-mexico/mexico-geojson); precio y potencial "
                       "sintetizados desde los núcleos premium y corredores "
                       "emergentes reales de CDMX.")

    # ══ CALLE · ESTABLECIMIENTO (DENUE real o demo) ═══════════════════════════
    elif escala.startswith("🛣"):
        calles_df = expediente_calles()
        _, estab_df, es_real = cargar_red_vial()
        valores = simular_calles(rho, detonante, clic)
        vv = extender_pasado(valores) if retro else valores
        año_idx = año + (RETRO if retro else 0)
        v_t, tasa = estado_en(vv, año_idx)
        mutante = int(np.argmax(v_t / valores[0] - 1))
        score = score_brickbit(v_t, valores[0],
                               calles_df["potencial_crecimiento"], tasa)

        if es_real:
            st.success("✅ **DATOS REALES DENUE/INEGI** — establecimientos y "
                       "calles ingeridos con `scripts/ingerir_denue.py`.")
        else:
            st.warning("🧪 **RED DE DEMOSTRACIÓN** — nombres viales y anclas "
                       "reales de Azcapotzalco sobre geometría sintética. "
                       "Para datos reales del DENUE (INEGI), ejecuta "
                       "`python scripts/ingerir_denue.py` en una red con "
                       "acceso a inegi.org.mx: la app los detecta sola. "
                       "(La política de red de este entorno bloquea INEGI.)")

        with lienzo_kpi:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("🛣 Calles vivas", f"{len(calles_df)}",
                      "red vial Azcapotzalco")
            c2.metric("🏪 Establecimientos", f"{len(estab_df):,}",
                      "DENUE real" if es_real else "demo etiquetada")
            c3.metric("💰 Índice de valor medio", f"${v_t.mean():,.0f} /m²",
                      f"+{(v_t.mean() / valores[0].mean() - 1) * 100:.1f}% vs hoy")
            c4.metric("🧬 Calle más mutante",
                      calles_df["nombre"].iloc[mutante],
                      f"+{(v_t[mutante] / valores[0][mutante] - 1) * 100:.0f}% acumulado")
            c5.metric("📅 Horizonte", f"Año {año:.1f} / {AÑOS}",
                      "🎯 epicentro por clic" if clic else
                      (detonante if CATALIZADORES[detonante] else "sin catalizador"))

        def fabricar(a, f):
            return construir_deck_calles(vv, a, f, mostrar_estab,
                                         mostrar_flujos, estilo)

        render_mapa(lienzo, fabricar, año_idx, reproducir, 60,
                    float(vv.shape[0] - 1), clic_activo, "deck_calle")

        t1, t2, t3, t4, t5, t6, t7 = st.tabs(
            ["🔎 Origen del crecimiento", "🌡 Sismógrafo",
             "🕳 Huecos de mercado", "🧬 Gemelos de ADN",
             "🏆 Ranking de calles", "📈 Trayectorias", "🔬 El modelo"])
        with t1:
            tab_origen(calles_df["nombre"],
                       _args_calles(rho, detonante, clic),
                       mutante, "la calle")
        with t2:
            tab_sismografo()
        with t3:
            tab_huecos()
        with t4:
            mezcla = pd.get_dummies(calles_df["sector"]).to_numpy(dtype=float)
            X = np.column_stack([
                calles_df["vitalidad"], calles_df["cercania_ancla"],
                calles_df["resiliencia"], mezcla,
                norm01(valores[-1] / valores[0] - 1), score / 10])
            tab_gemelos(calles_df["nombre"], X, mutante, "la calle")
        with t5:
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
        with t6:
            tab_trayectorias(valores, año, calles_df["nombre"],
                             "🧬 Trayectoria — top 8 calles en mutación")
        with t7:
            st.markdown(TEXTO_MODELO)
            st.caption("A esta escala, el crecimiento NACE de la actividad "
                       "económica observable: cada negocio suma vitalidad a "
                       "su calle, las anclas (mall, metro, universidad, "
                       "hospital) bombean potencial, y el contagio viaja por "
                       "los cruces viales.")

    # ══ MICROTEJIDO (motor original) ══════════════════════════════════════════
    else:
        gdf = generar_tejido_urbano()
        valores = simular_micro(rho, detonante)
        precio_t, tasa = estado_en(valores, año)
        with lienzo_kpi:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("💰 Valor medio del tejido", f"${precio_t.mean():,.0f} /m²",
                      f"+{(precio_t.mean() / valores[0].mean() - 1) * 100:.1f}% vs hoy")
            c2.metric("🧬 Células en mutación",
                      f"{int((tasa >= np.quantile(tasa, 0.90)).sum())}",
                      "top 10% de contagio")
            c3.metric("🫀 Pulso de capital", "22 flujos activos", f"ρ = {rho:.2f}")
            c4.metric("📅 Horizonte", f"Año {año:.1f} / {AÑOS}",
                      detonante if CATALIZADORES[detonante] else "sin catalizador")

        def fabricar(a, f):
            return construir_deck_micro(gdf, valores, a, f,
                                        mostrar_flujos, extrusion, estilo)

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
        "&nbsp;&nbsp;·&nbsp;&nbsp; arcos verde→lima = capital fluyendo "
        "de corazones a zonas emergentes</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
