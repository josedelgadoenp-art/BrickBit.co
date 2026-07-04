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
    t0 = int(np.clip(math.floor(año), 0, AÑOS))
    t1 = int(np.clip(t0 + 1, 0, AÑOS))
    f = año - t0
    v_t = valores[t0] * (1 - f) + valores[t1] * f
    tasa = (valores[t1] - valores[t0]) / valores[t0] if t1 > t0 \
        else (valores[t0] - valores[t0 - 1]) / valores[t0 - 1]
    return v_t, tasa


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


@st.cache_data(show_spinner="🧬 Simulando morfogénesis estatal (SAR)…")
def simular_nacion(rho: float, megaproyecto: str) -> np.ndarray:
    """SAR sobre la contigüidad real de los 32 estados."""
    df = datos_estatales()
    pi, pj, g = vecindad_estados()
    mega = MEGAPROYECTOS.get(megaproyecto)
    mask = df["estado"].isin(mega["estados"]).to_numpy().astype(float) \
        if mega else None
    return _sar(df["precio_m2"].to_numpy(dtype=float),
                df["potencial"].to_numpy(dtype=float),
                df["plusvalia"].to_numpy(dtype=float) / 100.0 * 0.55,
                pi, pj, g, rho, 0.10, mask,
                mega["año"] if mega else 0, mega["fuerza"] if mega else 0)


@st.cache_data(show_spinner="🧬 Simulando morfogénesis municipal (2,436 células)…")
def simular_municipios(rho: float, megaproyecto: str) -> np.ndarray:
    """
    SAR sobre las ~15,000 fronteras municipales reales: la plusvalía se
    contagia municipio a municipio, como células de un mismo tejido.
    """
    df = datos_municipales()
    pi, pj, g = vecindad_municipios()
    mega = MEGAPROYECTOS.get(megaproyecto)
    mask = df["estado"].isin(mega["estados"]).to_numpy().astype(float) \
        if mega else None
    return _sar(df["precio_actual"].to_numpy(dtype=float),
                df["potencial_crecimiento"].to_numpy(dtype=float),
                df["plusvalia_estatal"].to_numpy(dtype=float) / 100.0 * 0.45,
                pi, pj, g, rho, 0.14, mask,
                mega["año"] if mega else 0,
                (mega["fuerza"] * 0.9) if mega else 0)


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
        "PolygonLayer", data=preparar_estados_render(valores, año, fase),
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
                              valores_edo: np.ndarray) -> pdk.Deck:
    """
    Escala municipios: 2,436 células reales + delimitación estatal encima
    (como Google Maps) + el mismo sistema circulatorio metropolitano.
    """
    capas = [
        pdk.Layer(
            "PolygonLayer",
            data=preparar_municipios_render(valores, año, fase),
            get_polygon="contorno", get_fill_color="color",
            get_line_color=RGB_LIMA + [22], line_width_min_pixels=0.5,
            stroked=True, pickable=True, auto_highlight=True,
            highlight_color=RGB_CREMA + [110],
        ),
        capa_bordes_estatales(),
    ]
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
# 9 · LABORATORIO ANALÍTICO — RANKING · TRAYECTORIAS · DIAGRAMA DE FASES
# ══════════════════════════════════════════════════════════════════════════════

_PLOTLY_MARCA = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(29,23,19,.55)",
    font=dict(family="Space Mono, monospace", color=TEXTO_SUAVE),
    colorway=NEON, margin=dict(l=10, r=10, t=42, b=10),
)


def tab_ranking_estados(valores: np.ndarray, año: float,
                        flujos: pd.DataFrame) -> None:
    """Expediente completo y ordenable de los 32 estados en el año t."""
    df = datos_estatales()
    v_t, tasa = estado_en(valores, año)
    presion = flujos["ciudad_destino"].map(
        pd.DataFrame(CIUDADES, columns=["ciudad", "estado", *["_"] * 6])
        .set_index("ciudad")["estado"]).value_counts()
    tabla = pd.DataFrame({
        "Estado": df["estado"],
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


def tab_ranking_municipios(valores: np.ndarray, año: float) -> None:
    """Los 40 municipios con mutación más agresiva en el año t."""
    df = datos_municipales()
    v_t, tasa = estado_en(valores, año)
    tabla = pd.DataFrame({
        "Municipio": df["municipio"],
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
        '2,436 municipios · 32 estados · proyección simulada a 10 años</div>'
        '</div></div>',
        unsafe_allow_html=True)


def animar(lienzo, fabricar_deck, cuadros: int = 90) -> None:
    """Reproduce la década completa: el año avanza y todo el organismo late."""
    for f in range(cuadros + 1):
        lienzo.pydeck_chart(
            fabricar_deck(AÑOS * f / cuadros, (f * 0.045) % 1.0),
            width="stretch")
        time.sleep(0.05)
    st.toast("🧬 Morfogénesis completa: año 10 alcanzado", icon="✅")


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
                           "🧫 Microtejido (CDMX)"],
                          help="El mismo motor SAR a tres escalas: 2,436 "
                               "municipios, 32 estados o manzana a manzana.")

        st.markdown("### ⏳ Línea de tiempo")
        año = st.slider("Predicción (años hacia el futuro)", 0.0, float(AÑOS),
                        0.0, step=0.25, format="%.2f años")

        st.markdown("### 🧫 Parámetros del organismo")
        rho = st.slider("Virulencia del contagio (ρ)", 0.0, 1.5, 0.85, 0.05,
                        help="Coeficiente espacial autorregresivo: cuánto pesa "
                             "el vecindario en el crecimiento de cada célula.")
        if escala.startswith("🧫"):
            detonante = st.selectbox("Célula madre (catalizador urbano)",
                                     list(CATALIZADORES.keys()))
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
        else:
            mostrar_torres = st.checkbox("🏙 Torres metropolitanas 3D", True)
            mostrar_etiquetas = st.checkbox("🏷 Nombres de ciudades", True)

        st.markdown("---")
        reproducir = st.button("▶ Reproducir morfogénesis (10 años)",
                               width="stretch")
        st.caption("Las venas verdes→lima bombean capital de los corazones "
                   "hacia las zonas emergentes. Datos simulados.")

    lienzo_kpi = st.container()
    lienzo = st.empty()

    # ══ REPÚBLICA · MUNICIPIOS ════════════════════════════════════════════════
    if escala.startswith("🏛"):
        valores = simular_municipios(rho, detonante)
        valores_edo = simular_nacion(rho, detonante)
        df_m = datos_municipales()
        v_t, tasa = estado_en(valores, año)
        flujos = flujos_nacionales(valores_edo, año)

        moran = indice_moran(v_t, vecindad_municipios())
        mutante = int(np.argmax(v_t / valores[0] - 1))
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
                      detonante if MEGAPROYECTOS[detonante] else "sin megaproyecto")

        def fabricar(a, f):
            return construir_deck_municipios(
                valores, a, f, mostrar_flujos, mostrar_torres,
                mostrar_etiquetas, estilo, flujos_nacionales(valores_edo, a),
                valores_edo)

        if reproducir:
            animar(lienzo, fabricar, cuadros=48)
        else:
            lienzo.pydeck_chart(fabricar(año, (año * 0.4) % 1.0),
                                width="stretch")

        t1, t2, t3, t4 = st.tabs(["🏆 Ranking municipal",
                                  "📈 Trayectorias 10 años",
                                  "⚗️ Nube de fases",
                                  "🔬 El modelo"])
        with t1:
            tab_ranking_municipios(valores, año)
        with t2:
            tab_trayectorias(valores, año,
                             df_m["municipio"] + " (" + df_m["estado"] + ")",
                             "🧬 Trayectoria de precios — top 8 municipios en mutación")
        with t3:
            tab_fases_municipios(valores, año)
        with t4:
            st.markdown(TEXTO_MODELO)

    # ══ REPÚBLICA · ESTADOS ═══════════════════════════════════════════════════
    elif escala.startswith("🇲🇽"):
        valores = simular_nacion(rho, detonante)
        df_e = datos_estatales()
        v_t, tasa = estado_en(valores, año)
        flujos = flujos_nacionales(valores, año)

        pob = df_e["poblacion"].to_numpy()
        medio = float((v_t * pob).sum() / pob.sum())
        medio_0 = float((valores[0] * pob).sum() / pob.sum())
        moran = indice_moran(v_t, vecindad_estados())
        mutante = int(np.argmax(v_t / valores[0] - 1))
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
                      detonante if MEGAPROYECTOS[detonante] else "sin megaproyecto")

        def fabricar(a, f):
            return construir_deck_nacion(valores, a, f, mostrar_flujos,
                                         mostrar_torres, mostrar_etiquetas,
                                         estilo, flujos_nacionales(valores, a))

        if reproducir:
            animar(lienzo, fabricar)
        else:
            lienzo.pydeck_chart(fabricar(año, (año * 0.4) % 1.0),
                                width="stretch")

        t1, t2, t3, t4 = st.tabs(["🏆 Ranking de mutación",
                                  "📈 Trayectorias 10 años",
                                  "⚗️ Diagrama de fases",
                                  "🔬 El modelo"])
        with t1:
            tab_ranking_estados(valores, año, flujos)
        with t2:
            tab_trayectorias(valores, año, df_e["estado"],
                             "🧬 Trayectoria de precios — top 8 estados en mutación")
        with t3:
            tab_fases_estados(valores, año)
        with t4:
            st.markdown(TEXTO_MODELO)

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
