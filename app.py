# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
 BrickBit · MOTOR DE MORFOGÉNESIS URBANA — ESCALA NACIONAL 🇲🇽
═══════════════════════════════════════════════════════════════════════════════
 La República como ORGANISMO VIVO. Dos escalas de un mismo tejido:

 🇲🇽 ORGANISMO NACIONAL — los 32 estados con delimitación real (GeoJSON),
    32 zonas metropolitanas como órganos, y el capital circulando entre
    ellas como sistema circulatorio. El contagio de plusvalía viaja por
    la matriz de contigüidad REAL entre estados (SAR nacional).

 🧫 MICROTEJIDO — zoom celular a Azcapotzalco/Vallejo (CDMX): cada manzana
    es una célula que muta al ritmo de sus vecinas.

 Analítica integrada: Índice de Moran (cohesión espacial), ranking de
 mutación estatal, trayectorias proyectadas, diagrama de fases del mercado
 y megaproyectos detonantes (Tren Maya, nearshoring, Interoceánico…).

 Ejecución:
     pip install -r requirements.txt
     streamlit run app.py

 Datos: precios/plusvalía/yield del dataset BrickBit (zonas.js) + población
 y PIB per cápita aproximados. Proyecciones 100% simuladas (demo visual).
═══════════════════════════════════════════════════════════════════════════════
"""

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
# 1 · CONFIGURACIÓN GLOBAL Y PALETA BIOLUMINISCENTE
# ══════════════════════════════════════════════════════════════════════════════

SEMILLA = 42
AÑOS = 10                          # horizonte de simulación
CRECIMIENTO_BASE = 0.018           # inflación inmobiliaria de fondo (micro)

RUTA_ESTADOS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "data", "mexico_estados.json")
URL_ESTADOS = ("https://raw.githubusercontent.com/angelnmara/geojson/"
               "master/mexicoHigh.json")

# Estilos de basemap (Carto, sin token). "Voyager" ≈ look Google Maps.
ESTILOS_MAPA = {
    "🌑 Neón profundo": "https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json",
    "🗺 Voyager (estilo Google Maps)": "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
    "☀️ Positron claro": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
}

# Paleta bioluminiscente: violeta profundo → azul eléctrico → cian → magenta → blanco solar
_STOPS_T = np.array([0.00, 0.32, 0.58, 0.82, 1.00])
_STOPS_R = np.array([26.0, 0.0, 0.0, 255.0, 255.0])
_STOPS_G = np.array([8.0, 105.0, 245.0, 46.0, 226.0])
_STOPS_B = np.array([64.0, 255.0, 255.0, 154.0, 168.0])

NEON = ["#00f5ff", "#ff2e9a", "#ffe2a8", "#7c4dff", "#00ff9d",
        "#ff6d3a", "#4da6ff", "#ff4df0"]


def paleta_neon(t: np.ndarray) -> np.ndarray:
    """Mapea valores normalizados [0,1] a la rampa bioluminiscente RGB."""
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


# ══════════════════════════════════════════════════════════════════════════════
# 2 · DATASET NACIONAL — 32 ZONAS METROPOLITANAS · 32 ESTADOS
#     precio_m2 / plusvalía / yield: dataset BrickBit "Valor Futuro" (zonas.js)
#     pob_zm (millones, ZM aprox) · pob_edo (millones, censo 2020 aprox)
#     pib_pc (PIB per cápita estatal aprox, miles MXN/año)
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

# Megaproyectos: "células madre" a escala nación. Elevan el potencial de una
# región en su año de arranque y detonan la mutación en cadena.
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
# 3 · GEOMETRÍA NACIONAL — POLÍGONOS ESTATALES Y CONTIGÜIDAD REAL
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner="🗺 Cargando delimitación estatal…")
def cargar_estados() -> gpd.GeoDataFrame:
    """
    Carga los 32 polígonos estatales (GeoJSON local en /data, con fallback a
    descarga). Devuelve GeoDataFrame con columnas: estado, geometry.
    """
    if os.path.exists(RUTA_ESTADOS):
        with open(RUTA_ESTADOS, encoding="utf-8") as f:
            geo = json.load(f)
    else:  # fallback: descarga y persiste para la siguiente corrida
        with urllib.request.urlopen(URL_ESTADOS, timeout=60) as r:
            geo = json.load(r)
        try:
            os.makedirs(os.path.dirname(RUTA_ESTADOS), exist_ok=True)
            with open(RUTA_ESTADOS, "w", encoding="utf-8") as f:
                json.dump(geo, f)
        except OSError:
            pass
    gdf = gpd.GeoDataFrame.from_features(geo["features"], crs="EPSG:4326")
    gdf = gdf.rename(columns={"name": "estado"})[["estado", "geometry"]]
    return gdf.sort_values("estado").reset_index(drop=True)


@st.cache_data(show_spinner="🧠 Tejiendo la matriz de contigüidad…")
def vecindad_estados() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Matriz W del SAR nacional: pares (i, j) de estados que comparten frontera
    (con tolerancia de 3 km para topologías imperfectas). BCS solo toca a BC:
    el contagio hacia la península viaja por esa única "arteria".
    """
    gdf = cargar_estados()
    geoms = [g.buffer(0.03) for g in gdf.geometry]
    pares_i, pares_j = [], []
    for i in range(len(geoms)):
        for j in range(i + 1, len(geoms)):
            if geoms[i].intersects(geoms[j]):
                pares_i += [i, j]
                pares_j += [j, i]
    pares_i, pares_j = np.asarray(pares_i), np.asarray(pares_j)
    grados = np.bincount(pares_i, minlength=len(geoms)).astype(float)
    grados[grados == 0] = 1.0
    return pares_i, pares_j, grados


@st.cache_data
def contornos_estatales() -> pd.DataFrame:
    """
    Pre-explota MultiPolygons (islas incluidas) a anillos exteriores listos
    para PyDeck: una fila por polígono con el índice de su estado.
    """
    gdf = cargar_estados()
    filas = []
    for idx, fila in gdf.iterrows():
        geoms = fila.geometry.geoms if fila.geometry.geom_type == "MultiPolygon" \
            else [fila.geometry]
        for g in geoms:
            filas.append({"idx_estado": idx,
                          "contorno": [list(map(list, g.exterior.coords))]})
    return pd.DataFrame(filas)


@st.cache_data
def datos_estatales() -> pd.DataFrame:
    """
    Ensambla el expediente completo de cada estado (alineado al orden del
    GeoDataFrame): precio de su capital/ZM principal, plusvalía, yield,
    población, PIB per cápita, masa económica y potencial morfogenético.
    """
    gdf = cargar_estados()
    df_c = pd.DataFrame(CIUDADES, columns=[
        "ciudad", "estado", "lat", "lng", "precio_m2",
        "plusvalia", "yld", "pob_zm"])
    # CDMX aparece una vez como ciudad y una como estado: tomar la primera
    ref = df_c.drop_duplicates("estado").set_index("estado")
    df = pd.DataFrame({"estado": gdf["estado"]})
    for col in ["ciudad", "lat", "lng", "precio_m2", "plusvalia", "yld"]:
        df[col] = df["estado"].map(ref[col])
    df["poblacion"] = df["estado"].map(POB_ESTADO)
    df["pib_pc"] = df["estado"].map(PIB_PC)
    df["masa_economica"] = df["poblacion"] * df["pib_pc"]   # proxy de PIB estatal

    # Potencial morfogenético: qué tan receptivo es el estado a la "infección"
    # de plusvalía → alta plusvalía + buen yield + precio aún accesible.
    df["potencial"] = np.clip(
        0.55 * norm01(df["plusvalia"]) + 0.25 * norm01(df["yld"])
        + 0.20 * (1 - norm01(df["precio_m2"])), 0, 1).round(3)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 4 · MOTOR SAR NACIONAL + ÍNDICE DE MORAN
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner="🧬 Simulando morfogénesis nacional (SAR)…")
def simular_nacion(rho: float, megaproyecto: str) -> np.ndarray:
    """
    SAR a escala República, año a año:

        precio[t+1] = precio[t] · (1 + g_propio + ρ · (W·precio_norm[t]) · potencial)

    · g_propio  → la plusvalía histórica del estado (amortiguada al 55%).
    · W         → contigüidad REAL entre estados: la plusvalía de Quintana Roo
                  contagia a Yucatán, la de Nuevo León a Coahuila…
    · potencial → receptividad estatal (plusvalía + yield + accesibilidad).

    Un megaproyecto eleva el potencial de su región en su año de arranque.
    Devuelve matriz (AÑOS+1, 32) de precios estatales.
    """
    df = datos_estatales()
    pares_i, pares_j, grados = vecindad_estados()

    precio = df["precio_m2"].to_numpy(dtype=float)
    potencial = df["potencial"].to_numpy(dtype=float).copy()
    g_propio = df["plusvalia"].to_numpy(dtype=float) / 100.0 * 0.55

    mega = MEGAPROYECTOS.get(megaproyecto)
    valores = np.empty((AÑOS + 1, precio.size))
    valores[0] = precio

    for t in range(AÑOS):
        v = valores[t]
        if mega is not None and t == mega["año"]:
            afectados = df["estado"].isin(mega["estados"]).to_numpy()
            potencial = np.clip(potencial + mega["fuerza"] * afectados, 0, 1.35)

        v_norm = norm01(v)
        derrame = np.bincount(pares_i, weights=v_norm[pares_j],
                              minlength=v.size) / grados
        crecimiento = g_propio + rho * 0.10 * derrame * potencial
        valores[t + 1] = v * (1.0 + crecimiento)

    return valores


def indice_moran(v: np.ndarray) -> float:
    """
    Índice de Moran I sobre los precios estatales: mide si el organismo crece
    de forma COHESIONADA (valores altos junto a valores altos → I > 0) o
    fragmentada (I ≈ 0). Es el electrocardiograma espacial del mercado.
    """
    pares_i, pares_j, _ = vecindad_estados()
    z = v - v.mean()
    numerador = float((z[pares_i] * z[pares_j]).sum())
    return (len(v) / len(pares_i)) * numerador / float((z ** 2).sum() + 1e-12)


# ══════════════════════════════════════════════════════════════════════════════
# 5 · SISTEMA CIRCULATORIO NACIONAL — CAPITAL ENTRE ZONAS METROPOLITANAS
# ══════════════════════════════════════════════════════════════════════════════

def flujos_nacionales(valores: np.ndarray, año: float,
                      n_fuentes: int = 6, n_destinos: int = 20) -> pd.DataFrame:
    """
    Modelo gravitacional de rotación de capital: las ZM con mayor masa
    económica bombean liquidez hacia los estados con mayor crecimiento
    proyectado. atracción = masa_fuente / distancia^1.2. Cada arco estima el
    capital anual en juego (MXN, mil millones — mock calibrado).
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
    candidatos = np.argsort(tasa_c)[::-1]
    destinos = [c for c in candidatos if c not in set(fuentes)][:n_destinos]

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
    """
    Convierte cada arco en un trayecto curvo con timestamps para el TripsLayer:
    los "glóbulos" de capital que viajan por las venas del organismo.
    """
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
    """
    Las 32 ZM como torres de energía: altura = precio proyectado, color = tasa
    de contagio. Incluye el expediente completo para el tooltip analítico.
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

    rgb = paleta_neon(norm01(tasa_c) ** 0.8)
    return pd.DataFrame({
        "pos": [[float(a), float(b)] for a, b in zip(df_c["lng"], df_c["lat"])],
        "nombre": df_c["ciudad"],
        "altura": (precio_t * 5.5).tolist(),
        "color": np.column_stack([rgb, np.full(len(df_c), 210)])
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
# 6 · RENDER NACIONAL — EL ORGANISMO REPÚBLICA EN PYDECK
# ══════════════════════════════════════════════════════════════════════════════

def preparar_estados_render(valores: np.ndarray, año: float,
                            fase: float) -> pd.DataFrame:
    """
    Colorea cada polígono estatal según su mutación: mezcla de valor proyectado
    (45%) y plusvalía acumulada (55%), con opacidad que "respira" con la fase.
    """
    df = datos_estatales()
    v_t, tasa = estado_en(valores, año)
    acum = v_t / valores[0] - 1

    t = 0.45 * norm01(v_t) + 0.55 * norm01(acum)
    rgb = paleta_neon(t ** 0.85)
    latido = 0.88 + 0.12 * np.sin(2 * math.pi * (fase + t * 2.0))
    alfa = np.clip((80 + 130 * t) * latido, 45, 235)

    p85, p55 = np.quantile(tasa, 0.85), np.quantile(tasa, 0.55)
    estado_bio = np.where(tasa >= p85, "🧬 Mutación activa",
                          np.where(tasa >= p55, "🌱 Expansión", "💤 Latente"))

    base = pd.DataFrame({
        "nombre": df["estado"],
        "color": np.column_stack([rgb, alfa]).astype(int).tolist(),
        "estado_bio": estado_bio,
        "precio_txt": [f"${p:,.0f} MXN/m²" for p in v_t],
        "crec_txt": [f"+{r * 100:.1f}% anual" for r in tasa],
        "plusvalia_txt": [f"+{a * 100:.0f}% vs hoy" for a in acum],
        "extra_txt": [f"👥 {p:.2f}M hab · PIB pc ${g:.0f}k · potencial {q:.2f}"
                      for p, g, q in zip(df["poblacion"], df["pib_pc"],
                                         df["potencial"])],
    })
    # une atributos estatales a cada polígono explotado (islas incluidas)
    return contornos_estatales().join(base, on="idx_estado")


def construir_deck_nacion(valores: np.ndarray, año: float, fase: float,
                          mostrar_flujos: bool, mostrar_torres: bool,
                          mostrar_etiquetas: bool, estilo: str) -> pdk.Deck:
    """Ensambla el organismo nacional: piel (estados), órganos (ZM) y sangre (capital)."""
    pulso = 0.5 + 0.5 * math.sin(2 * math.pi * fase)

    capas = [
        # ── Piel del organismo: estados que respiran, con frontera neón ───────
        pdk.Layer(
            "PolygonLayer",
            data=preparar_estados_render(valores, año, fase),
            get_polygon="contorno",
            get_fill_color="color",
            get_line_color=[0, 245, 255, 110],
            line_width_min_pixels=1,
            stroked=True,
            pickable=True,
            auto_highlight=True,
            highlight_color=[255, 255, 255, 90],
        )
    ]

    torres = torres_metropolitanas(valores, año)
    if mostrar_torres:
        # ── Órganos: cada zona metropolitana como torre de energía ────────────
        capas.append(pdk.Layer(
            "ColumnLayer",
            data=torres,
            get_position="pos",
            get_elevation="altura",
            get_fill_color="color",
            radius=16000,
            elevation_scale=1.0,
            pickable=True,
            auto_highlight=True,
        ))

    if mostrar_flujos:
        flujos = flujos_nacionales(valores, año)
        # ── Venas: arcos pulsantes de capital interestatal ─────────────────────
        capas.append(pdk.Layer(
            "ArcLayer",
            data=flujos,
            get_source_position="origen",
            get_target_position="destino",
            get_source_color=[0, 245, 255, int(80 + 120 * pulso)],
            get_target_color=[255, 46, 154, int(140 + 110 * pulso)],
            get_width=f"1.5 + intensidad * {3.0 + 3.0 * pulso}",
            get_height=0.35,
            great_circle=False,
        ))
        # ── Glóbulos: pulsos de capital viajando por las venas ─────────────────
        capas.append(pdk.Layer(
            "TripsLayer",
            data=construir_trayectos(flujos),
            get_path="camino",
            get_timestamps="marcas",
            get_color=[120, 255, 245],
            width_min_pixels=3,
            trail_length=0.30,
            current_time=(fase * 2.0) % 2.0,
            opacity=0.9,
        ))
        # ── Corazones: glow pulsante en los nodos que bombean ─────────────────
        nodos = pd.DataFrame({"pos": flujos["origen"]
                             .apply(tuple).drop_duplicates().apply(list).tolist()})
        capas.append(pdk.Layer(
            "ScatterplotLayer",
            data=nodos,
            get_position="pos",
            get_radius=26000 + 16000 * pulso,
            get_fill_color=[255, 46, 154, int(45 + 55 * pulso)],
            stroked=True,
            get_line_color=[255, 226, 168, int(110 + 90 * pulso)],
            line_width_min_pixels=2,
        ))

    if mostrar_etiquetas:
        # ── Rótulos de las 14 ZM con mayor masa económica ──────────────────────
        top = torres.nlargest(14, "masa")
        capas.append(pdk.Layer(
            "TextLayer",
            data=top,
            get_position="pos",
            get_text="nombre",
            get_size=13,
            get_color=[210, 208, 235, 210],
            get_alignment_baseline="'top'",
            get_pixel_offset=[0, 10],
        ))

    return pdk.Deck(
        layers=capas,
        initial_view_state=pdk.ViewState(
            longitude=-102.4, latitude=23.9, zoom=4.4, pitch=46, bearing=-8,
        ),
        map_style=ESTILOS_MAPA[estilo],
        tooltip={
            "html": (
                "<div style='font-family:monospace'>"
                "<b style='color:#00f5ff'>{nombre}</b> {estado_bio}<br/>"
                "💰 <b>{precio_txt}</b><br/>"
                "🧬 Contagio: <b style='color:#ff2e9a'>{crec_txt}</b> · "
                "📈 {plusvalia_txt}<br/>"
                "<span style='color:#8f88b8'>{extra_txt}</span></div>"
            ),
            "style": {"backgroundColor": "#0b0520", "color": "#e8e6ff",
                      "border": "1px solid #00f5ff", "borderRadius": "8px"},
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# 7 · ESCALA MICRO — TEJIDO CELULAR AZCAPOTZALCO/VALLEJO (motor original)
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
    flujo = np.clip(0.55 * norm01(precio) + 0.45 * potencial
                    + rng.normal(0, 0.05, precio.size), 0, 1)
    qx, qy = np.minimum(ix * 3 // NX, 2), np.minimum(iy * 3 // NY, 2)
    gdf = gpd.GeoDataFrame({
        "barrio": [BARRIOS[int(b)] for b in (qy * 3 + qx)],
        "precio_actual": precio.round(0),
        "potencial_crecimiento": potencial.round(3),
        "flujo_capital": flujo.round(3),
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
    """SAR celular: precio[t+1] = precio[t]·(1 + g + ρ·(W·v_norm)·potencial)."""
    gdf = generar_tejido_urbano()
    pares_i, pares_j, grados = vecindad_reina()
    potencial = gdf["potencial_crecimiento"].to_numpy(dtype=float).copy()
    cx, cy = gdf["lng"].to_numpy(), gdf["lat"].to_numpy()
    cat = CATALIZADORES.get(catalizador)

    valores = np.empty((AÑOS + 1, len(gdf)))
    valores[0] = gdf["precio_actual"].to_numpy(dtype=float)
    for t in range(AÑOS):
        v = valores[t]
        if cat is not None and t == cat["año"]:
            campo = np.exp(-((cx - cat["lng"]) ** 2 + (cy - cat["lat"]) ** 2)
                           / (2 * cat["radio"] ** 2))
            potencial = np.clip(potencial + cat["fuerza"] * campo, 0, 1.4)
        derrame = np.bincount(pares_i, weights=norm01(v)[pares_j],
                              minlength=v.size) / grados
        valores[t + 1] = v * (1 + CRECIMIENTO_BASE
                              + rho * 0.16 * derrame * potencial)
    return valores


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
    t = (precio_t - base.min()) / (valores[-1].max() - base.min())
    rgb = paleta_neon(np.clip(t, 0, 1) ** 0.85)
    latido = 0.88 + 0.12 * np.sin(2 * math.pi * (fase + t * 2.0))
    alfa = (95 + 150 * t) * (0.75 + 0.5 * norm01(tasa)) * latido
    p90, p60 = np.quantile(tasa, 0.90), np.quantile(tasa, 0.60)
    estado_bio = np.where(tasa >= p90, "🧬 Mutación activa",
                          np.where(tasa >= p60, "🌱 Expansión", "💤 Latente"))
    return pd.DataFrame({
        "contorno": gdf["contorno"].tolist(),
        "color": np.column_stack([rgb, np.clip(alfa, 30, 255)])
                   .astype(int).tolist(),
        "altura": ((np.clip(t, 0, 1) ** 1.5) * 900
                   * (1.0 if extrusion else 0.0)).tolist(),
        "nombre": gdf["barrio"].tolist(),
        "estado_bio": estado_bio.tolist(),
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
        get_polygon="contorno",
        get_fill_color="color",
        get_elevation="altura",
        extruded=extrusion,
        get_line_color=[0, 245, 255, 40],
        line_width_min_pixels=1,
        pickable=True,
        auto_highlight=True,
        highlight_color=[255, 255, 255, 120],
    )]
    if mostrar_flujos:
        flujos = flujos_micro(gdf, valores, año)
        pulso = 0.5 + 0.5 * math.sin(2 * math.pi * fase)
        capas.append(pdk.Layer(
            "ArcLayer", data=flujos,
            get_source_position="origen", get_target_position="destino",
            get_source_color=[0, 245, 255, int(90 + 130 * pulso)],
            get_target_color=[255, 46, 154, int(150 + 100 * pulso)],
            get_width=f"2 + intensidad * {3.5 + 3.0 * pulso}",
            get_height=0.6, great_circle=False,
        ))
        capas.append(pdk.Layer(
            "TripsLayer", data=construir_trayectos(flujos),
            get_path="camino", get_timestamps="marcas",
            get_color=[120, 255, 245], width_min_pixels=3,
            trail_length=0.35, current_time=(fase * 2.0) % 2.0, opacity=0.9,
        ))
        nodos = pd.DataFrame({"pos": flujos["origen"]
                             .apply(tuple).drop_duplicates().apply(list).tolist()})
        capas.append(pdk.Layer(
            "ScatterplotLayer", data=nodos, get_position="pos",
            get_radius=110 + 90 * pulso,
            get_fill_color=[255, 46, 154, int(50 + 60 * pulso)],
            stroked=True,
            get_line_color=[255, 226, 168, int(120 + 100 * pulso)],
            line_width_min_pixels=2,
        ))
    return pdk.Deck(
        layers=capas,
        initial_view_state=pdk.ViewState(
            longitude=CENTRO_LNG, latitude=CENTRO_LAT,
            zoom=13.1, pitch=52, bearing=-16),
        map_style=ESTILOS_MAPA[estilo],
        tooltip={
            "html": (
                "<div style='font-family:monospace'>"
                "<b style='color:#00f5ff'>{nombre}</b> {estado_bio}<br/>"
                "💰 <b>{precio_txt}</b><br/>"
                "🧬 Contagio: <b style='color:#ff2e9a'>{crec_txt}</b> · "
                "📈 {plusvalia_txt}</div>"
            ),
            "style": {"backgroundColor": "#0b0520", "color": "#e8e6ff",
                      "border": "1px solid #00f5ff", "borderRadius": "8px"},
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# 8 · LABORATORIO ANALÍTICO — RANKING · TRAYECTORIAS · DIAGRAMA DE FASES
# ══════════════════════════════════════════════════════════════════════════════

_PLOTLY_OSCURO = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(11,5,32,.6)",
    font=dict(family="monospace", color="#c9c6e8"),
    colorway=NEON, margin=dict(l=10, r=10, t=40, b=10),
)


def tab_ranking(valores: np.ndarray, año: float,
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


def tab_trayectorias(valores: np.ndarray, año: float) -> None:
    """Evolución proyectada del precio: las 8 mutaciones más agresivas."""
    df = datos_estatales()
    acum = valores[-1] / valores[0] - 1
    top = np.argsort(acum)[::-1][:8]
    fig = go.Figure()
    for c, i in zip(NEON, top):
        fig.add_trace(go.Scatter(
            x=list(range(AÑOS + 1)), y=valores[:, i],
            name=df["estado"].iloc[i], mode="lines+markers",
            line=dict(width=2.4, color=c), marker=dict(size=5)))
    fig.add_vline(x=año, line_dash="dot", line_color="#ffe2a8",
                  annotation_text=f"año {año:.1f}",
                  annotation_font_color="#ffe2a8")
    fig.update_layout(
        title="🧬 Trayectoria de precios — top 8 estados en mutación",
        xaxis_title="año", yaxis_title="MXN/m²", height=420,
        **_PLOTLY_OSCURO)
    st.plotly_chart(fig, width="stretch")


def tab_fases(valores: np.ndarray, año: float) -> None:
    """
    Diagrama de fases del organismo: precio (accesibilidad) vs velocidad de
    contagio; el tamaño es la población y el color el potencial. Los estados
    del cuadrante superior-izquierdo son las oportunidades: baratos y mutando.
    """
    df = datos_estatales()
    v_t, tasa = estado_en(valores, año)
    fig = go.Figure(go.Scatter(
        x=v_t, y=tasa * 100, mode="markers+text",
        text=df["estado"], textposition="top center",
        textfont=dict(size=9, color="#8f88b8"),
        marker=dict(
            size=np.sqrt(df["poblacion"]) * 11 + 6,
            color=df["potencial"], cmin=0, cmax=1,
            colorscale=[[0.0, "#1a083e"], [0.35, "#0069ff"],
                        [0.60, "#00f5ff"], [0.85, "#ff2e9a"],
                        [1.0, "#ffe2a8"]],
            colorbar=dict(title="potencial"), opacity=0.85,
            line=dict(width=1, color="#00f5ff")),
        hovertemplate="<b>%{text}</b><br>precio $%{x:,.0f}/m²"
                      "<br>contagio +%{y:.1f}%/año<extra></extra>"))
    fig.update_layout(
        title=f"⚗️ Diagrama de fases del mercado — año {año:.1f} "
              "(arriba-izquierda = oportunidad)",
        xaxis_title="precio proyectado MXN/m²",
        yaxis_title="velocidad de contagio (%/año)", height=460,
        **_PLOTLY_OSCURO)
    st.plotly_chart(fig, width="stretch")


# ══════════════════════════════════════════════════════════════════════════════
# 9 · INTERFAZ STREAMLIT — DARK MODE NEÓN
# ══════════════════════════════════════════════════════════════════════════════

def inyectar_css() -> None:
    """Dark mode profundo para que el organismo neón resalte."""
    st.markdown("""
    <style>
      .stApp { background: radial-gradient(ellipse at top, #0d0524 0%, #05010f 60%); }
      section[data-testid="stSidebar"] {
          background: #080316; border-right: 1px solid #1d1140;
      }
      h1, h2, h3 { color: #e8e6ff !important; }
      .neon-title {
          font-family: monospace; font-size: 2.0rem; font-weight: 800;
          background: linear-gradient(90deg, #00f5ff, #ff2e9a 70%, #ffe2a8);
          -webkit-background-clip: text; -webkit-text-fill-color: transparent;
          letter-spacing: .02em;
      }
      .neon-sub { color: #8f88b8; font-family: monospace; margin-top: -.6rem; }
      div[data-testid="stMetric"] {
          background: #0b0520; border: 1px solid #1d1140; border-radius: 12px;
          padding: .6rem .9rem;
          box-shadow: 0 0 18px rgba(0,245,255,.07);
      }
      div[data-testid="stMetricValue"] { color: #00f5ff; font-size: 1.45rem; }
      div[data-testid="stMetricLabel"] { color: #8f88b8; }
      button[data-baseweb="tab"] { font-family: monospace; }
      #MainMenu, footer { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)


def animar(lienzo, fabricar_deck) -> None:
    """Reproduce la década completa (~6 s): el año avanza y todo late."""
    cuadros = 90
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

    st.markdown('<div class="neon-title">🧬 MOTOR DE MORFOGÉNESIS URBANA · MÉXICO</div>',
                unsafe_allow_html=True)
    st.markdown('<p class="neon-sub">BrickBit · la República como organismo vivo — '
                '32 estados · 32 zonas metropolitanas · proyección simulada a 10 años</p>',
                unsafe_allow_html=True)

    # ── Panel lateral ─────────────────────────────────────────────────────────
    with st.sidebar:
        escala = st.radio("🔭 Escala del organismo",
                          ["🇲🇽 Organismo nacional", "🧫 Microtejido (CDMX)"],
                          help="El mismo motor SAR a dos escalas: estados que "
                               "se contagian entre sí, o manzanas célula a célula.")

        st.markdown("### ⏳ Línea de tiempo")
        año = st.slider("Predicción (años hacia el futuro)", 0.0, float(AÑOS),
                        0.0, step=0.25, format="%.2f años")

        st.markdown("### 🧫 Parámetros del organismo")
        rho = st.slider("Virulencia del contagio (ρ)", 0.0, 1.5, 0.85, 0.05,
                        help="Coeficiente espacial autorregresivo: cuánto pesa "
                             "el vecindario en el crecimiento de cada unidad.")
        if escala.startswith("🇲🇽"):
            detonante = st.selectbox("Megaproyecto detonante",
                                     list(MEGAPROYECTOS.keys()),
                                     help="Célula madre a escala nación: eleva el "
                                          "potencial de toda una región.")
        else:
            detonante = st.selectbox("Célula madre (catalizador urbano)",
                                     list(CATALIZADORES.keys()))

        st.markdown("### 👁 Capas y estilo")
        estilo = st.selectbox("Estilo de mapa", list(ESTILOS_MAPA.keys()))
        mostrar_flujos = st.checkbox("🫀 Sistema circulatorio de capital", True)
        if escala.startswith("🇲🇽"):
            mostrar_torres = st.checkbox("🏙 Torres metropolitanas 3D", True)
            mostrar_etiquetas = st.checkbox("🏷 Nombres de ciudades", True)
        else:
            extrusion = st.checkbox("⛰ Relieve 3D del tejido", True)

        st.markdown("---")
        reproducir = st.button("▶ Reproducir morfogénesis (10 años)",
                               width="stretch")
        st.caption("Las venas cian→magenta bombean capital de los corazones "
                   "hacia las zonas emergentes. Datos simulados.")

    lienzo_kpi = st.container()
    lienzo = st.empty()

    # ══ ESCALA NACIONAL ═══════════════════════════════════════════════════════
    if escala.startswith("🇲🇽"):
        valores = simular_nacion(rho, detonante)
        df_e = datos_estatales()
        v_t, tasa = estado_en(valores, año)
        flujos = flujos_nacionales(valores, año)

        # ── Signos vitales de la República ────────────────────────────────────
        pob = df_e["poblacion"].to_numpy()
        medio = float((v_t * pob).sum() / pob.sum())
        medio_0 = float((valores[0] * pob).sum() / pob.sum())
        moran = indice_moran(v_t)
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
                                         estilo)

        if reproducir:
            animar(lienzo, fabricar)
        else:
            lienzo.pydeck_chart(fabricar(año, (año * 0.4) % 1.0),
                                width="stretch")

        # ── Laboratorio analítico ─────────────────────────────────────────────
        t1, t2, t3, t4 = st.tabs(["🏆 Ranking de mutación",
                                  "📈 Trayectorias 10 años",
                                  "⚗️ Diagrama de fases",
                                  "🔬 El modelo"])
        with t1:
            tab_ranking(valores, año, flujos)
        with t2:
            tab_trayectorias(valores, año)
        with t3:
            tab_fases(valores, año)
        with t4:
            st.markdown("""
            **La República no es un mapa: es un organismo.** Cada estado es un
            órgano cuyo metabolismo depende de sus fronteras — formalizado como
            un proceso espacial autorregresivo (SAR) sobre la matriz de
            contigüidad **real** entre los 32 estados:

            ```
            precio[t+1] = precio[t] · (1 + g_propio + ρ · (W · precio_norm[t]) · potencial)
            ```

            - **W**: contigüidad geográfica real (Quintana Roo contagia a
              Yucatán; Nuevo León a Coahuila; BCS solo respira a través de BC).
            - **ρ**: virulencia del contagio de plusvalía entre estados vecinos.
            - **potencial**: receptividad estatal = plusvalía histórica + yield
              + accesibilidad de precio (dataset BrickBit "Valor Futuro").
            - **Megaproyectos**: células madre regionales (Tren Maya,
              nearshoring, Interoceánico, Bajío aeroespacial) que elevan el
              potencial de su región y detonan la mutación en cadena.
            - **Índice de Moran I**: el electrocardiograma espacial — mide si
              el organismo crece cohesionado (I→1) o fragmentado (I→0).
            - **Sistema circulatorio**: modelo gravitacional
              `masa económica / distancia^1.2` de las ZM dominantes hacia los
              estados de mayor crecimiento proyectado.

            *Población y PIB per cápita aproximados; proyecciones 100%
            simuladas con fines de visualización — no es asesoría de inversión.*
            """)

    # ══ ESCALA MICRO (motor original) ═════════════════════════════════════════
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

    # ── Leyenda común ─────────────────────────────────────────────────────────
    st.markdown(
        "<div style='font-family:monospace;color:#8f88b8;font-size:.85rem'>"
        "<span style='color:#1a083e'>■</span> latente&nbsp;&nbsp;"
        "<span style='color:#0069ff'>■</span> despertando&nbsp;&nbsp;"
        "<span style='color:#00f5ff'>■</span> expansión&nbsp;&nbsp;"
        "<span style='color:#ff2e9a'>■</span> mutación&nbsp;&nbsp;"
        "<span style='color:#ffe2a8'>■</span> núcleo consolidado"
        "&nbsp;&nbsp;·&nbsp;&nbsp; arcos cian→magenta = capital fluyendo "
        "de corazones a zonas emergentes</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
