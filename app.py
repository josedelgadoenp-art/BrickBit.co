# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
 BrickBit · MOTOR DE MORFOGÉNESIS URBANA
═══════════════════════════════════════════════════════════════════════════════
 La ciudad como organismo vivo: cada manzana es una célula del tejido urbano.
 La plusvalía no "sube": SE CONTAGIA. El capital no "se invierte": CIRCULA.

 · Células de crecimiento  → PolygonLayer extruido con paleta bioluminiscente.
 · Sistema circulatorio    → ArcLayer (venas) + TripsLayer (pulsos de capital).
 · Motor SAR (mock)        → autocorrelación espacial: el valor de una manzana
                             contagia a sus vecinas (contigüidad tipo reina).

 Ejecución:
     pip install -r requirements.txt
     streamlit run app.py

 Zona simulada: Azcapotzalco / Vallejo, CDMX (reconversión industrial → alto valor).
═══════════════════════════════════════════════════════════════════════════════
"""

import math
import time

import numpy as np
import pandas as pd
import geopandas as gpd
import pydeck as pdk
import streamlit as st
from shapely.geometry import box

# ══════════════════════════════════════════════════════════════════════════════
# 1 · CONFIGURACIÓN GLOBAL
# ══════════════════════════════════════════════════════════════════════════════

SEMILLA = 42                       # reproducibilidad del tejido
NX, NY = 26, 26                    # retícula de manzanas (26×26 = 676 células)
CENTRO_LNG, CENTRO_LAT = -99.186, 19.482   # Azcapotzalco, CDMX
PASO_LNG, PASO_LAT = 0.00245, 0.00228      # ~250 m por manzana
FACTOR_MANZANA = 0.80              # la célula ocupa 80% de la celda → se ven "calles"
AÑOS = 10                          # horizonte de simulación
CRECIMIENTO_BASE = 0.018           # inflación inmobiliaria de fondo (1.8% anual)

ESTILO_MAPA = "https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json"

# Colonias reales de Azcapotzalco para dar sabor al tooltip (asignadas por cuadrante 3×3)
BARRIOS = [
    "El Rosario", "San Martín Xochinahuac", "Santa Bárbara",
    "Vallejo Industrial", "Clavería", "Ángel Zimbrón",
    "San Álvaro", "Nueva Santa María", "Santo Tomás",
]

# Catalizadores urbanos: "células madre" que el usuario puede inyectar al tejido.
# (lng, lat) del epicentro, año de activación, intensidad y radio del shock.
CATALIZADORES = {
    "— Sin catalizador —": None,
    "🚇 Nueva línea de Metro (norte)": dict(lng=-99.192, lat=19.497, año=2, fuerza=0.85, radio=0.011),
    "🏬 Centro comercial (poniente)": dict(lng=-99.203, lat=19.478, año=3, fuerza=0.70, radio=0.009),
    "🌳 Parque lineal Vallejo (centro)": dict(lng=-99.184, lat=19.486, año=1, fuerza=0.55, radio=0.013),
}

# Paleta bioluminiscente: violeta profundo → azul eléctrico → cian → magenta → blanco solar
_STOPS_T = np.array([0.00, 0.32, 0.58, 0.82, 1.00])
_STOPS_R = np.array([26.0, 0.0, 0.0, 255.0, 255.0])
_STOPS_G = np.array([8.0, 105.0, 245.0, 46.0, 226.0])
_STOPS_B = np.array([64.0, 255.0, 255.0, 154.0, 168.0])


# ══════════════════════════════════════════════════════════════════════════════
# 2 · GENERACIÓN DEL TEJIDO URBANO (MOCK GEOESPACIAL)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner="🧫 Cultivando tejido urbano…")
def generar_tejido_urbano() -> gpd.GeoDataFrame:
    """
    Genera un GeoDataFrame de manzanas sintéticas con:
      · precio_actual         (MXN/m²)  — núcleos consolidados + ruido lognormal
      · potencial_crecimiento (0–1)     — receptividad de la célula al contagio
      · flujo_capital         (0–1)     — propensión a emitir/recibir inversión

    Los núcleos de precio imitan a Clavería / Nueva Santa María (consolidadas)
    y el potencial se concentra en Vallejo (reconversión industrial).
    """
    rng = np.random.default_rng(SEMILLA)

    # --- retícula de polígonos ------------------------------------------------
    ix, iy = np.meshgrid(np.arange(NX), np.arange(NY))
    ix, iy = ix.ravel(), iy.ravel()
    lng0 = CENTRO_LNG + (ix - NX / 2) * PASO_LNG
    lat0 = CENTRO_LAT + (iy - NY / 2) * PASO_LAT
    margen_lng = PASO_LNG * (1 - FACTOR_MANZANA) / 2
    margen_lat = PASO_LAT * (1 - FACTOR_MANZANA) / 2

    geometrias = [
        box(x + margen_lng, y + margen_lat,
            x + PASO_LNG - margen_lng, y + PASO_LAT - margen_lat)
        for x, y in zip(lng0, lat0)
    ]
    cx, cy = lng0 + PASO_LNG / 2, lat0 + PASO_LAT / 2   # centroides

    # --- helper: campo gaussiano centrado en (lng, lat) ------------------------
    def nucleo(lng, lat, sigma):
        return np.exp(-((cx - lng) ** 2 + (cy - lat) ** 2) / (2 * sigma ** 2))

    # --- precio actual: núcleos consolidados al sureste + ruido ----------------
    precio = (
        13500
        + 14000 * nucleo(-99.176, 19.470, 0.010)   # Clavería / Nueva Santa María
        + 9000 * nucleo(-99.170, 19.492, 0.008)    # corredor Cuitláhuac
        + 5500 * nucleo(-99.200, 19.472, 0.007)    # borde poniente
    )
    precio *= rng.lognormal(mean=0.0, sigma=0.10, size=precio.size)

    # --- potencial de crecimiento: zonas industriales listas para "mutar" ------
    potencial = (
        0.90 * nucleo(-99.186, 19.489, 0.011)      # Vallejo Industrial
        + 0.65 * nucleo(-99.199, 19.494, 0.009)    # norponiente emergente
        + 0.40 * nucleo(-99.174, 19.478, 0.010)    # anillo de consolidadas
        + rng.uniform(0.05, 0.22, size=precio.size)
    )
    potencial = np.clip(potencial, 0.0, 1.0)

    # --- flujo de capital: liquidez donde precio y potencial coexisten ---------
    precio_n = (precio - precio.min()) / np.ptp(precio)
    flujo = np.clip(0.55 * precio_n + 0.45 * potencial
                    + rng.normal(0, 0.05, precio.size), 0, 1)

    # --- colonia por cuadrante 3×3 (solo estética del tooltip) ------------------
    qx = np.minimum(ix * 3 // NX, 2)
    qy = np.minimum(iy * 3 // NY, 2)
    barrio = [BARRIOS[int(b)] for b in (qy * 3 + qx)]

    gdf = gpd.GeoDataFrame(
        {
            "id_celula": np.arange(precio.size),
            "ix": ix, "iy": iy,
            "barrio": barrio,
            "precio_actual": precio.round(0),
            "potencial_crecimiento": potencial.round(3),
            "flujo_capital": flujo.round(3),
            "lng": cx, "lat": cy,
        },
        geometry=geometrias,
        crs="EPSG:4326",
    )
    # contorno pre-serializado para PyDeck (lista de [lng, lat])
    gdf["contorno"] = gdf.geometry.apply(lambda g: [list(map(list, g.exterior.coords))])
    return gdf


@st.cache_data
def vecindad_reina() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Matriz de contigüidad tipo REINA sobre la retícula, expresada como pares
    (i, j) → la célula i es vecina de la célula j. Es la 'W' del modelo SAR.
    """
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
    pares_i = np.asarray(pares_i)
    pares_j = np.asarray(pares_j)
    grados = np.bincount(pares_i, minlength=NX * NY).astype(float)  # normaliza W por fila
    return pares_i, pares_j, grados


# ══════════════════════════════════════════════════════════════════════════════
# 3 · MOTOR SAR — LA "INFECCIÓN POSITIVA" DE LA PLUSVALÍA
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner="🧬 Simulando morfogénesis (SAR)…")
def simular_morfogenesis(rho: float, catalizador: str) -> np.ndarray:
    """
    Simulación espacial autorregresiva simplificada, año a año:

        precio[t+1] = precio[t] · (1 + g_base + ρ · (W·precio_norm[t]) · potencial)

    · ρ (rho)      → virulencia del contagio espacial (cuánto pesa el vecindario).
    · W·precio_norm→ promedio del valor normalizado de las vecinas (spillover).
    · potencial    → receptividad de cada célula: el mismo vecindario "infecta"
                     más a una zona industrial barata que a una ya consolidada.

    Un catalizador ("célula madre") eleva el potencial alrededor de su epicentro
    en su año de activación, detonando la reacción en cadena.

    Devuelve una matriz (AÑOS+1, n_células) con el precio de cada año.
    """
    gdf = generar_tejido_urbano()
    pares_i, pares_j, grados = vecindad_reina()

    precio = gdf["precio_actual"].to_numpy(dtype=float)
    potencial = gdf["potencial_crecimiento"].to_numpy(dtype=float).copy()
    cx, cy = gdf["lng"].to_numpy(), gdf["lat"].to_numpy()

    cat = CATALIZADORES.get(catalizador)
    valores = np.empty((AÑOS + 1, precio.size))
    valores[0] = precio

    for t in range(AÑOS):
        v = valores[t]

        # activación de la célula madre: shock gaussiano sobre el potencial
        if cat is not None and t == cat["año"]:
            campo = np.exp(-((cx - cat["lng"]) ** 2 + (cy - cat["lat"]) ** 2)
                           / (2 * cat["radio"] ** 2))
            potencial = np.clip(potencial + cat["fuerza"] * campo, 0, 1.4)

        # spillover espacial: media del valor normalizado de las vecinas (W·v)
        v_norm = (v - v.min()) / (np.ptp(v) + 1e-9)
        derrame = np.bincount(pares_i, weights=v_norm[pares_j],
                              minlength=v.size) / grados

        crecimiento = CRECIMIENTO_BASE + rho * 0.16 * derrame * potencial
        valores[t + 1] = v * (1.0 + crecimiento)

    return valores


def estado_en(valores: np.ndarray, año: float) -> tuple[np.ndarray, np.ndarray]:
    """
    Interpola linealmente entre años enteros para que el slider se sienta
    continuo (la ciudad "respira" en vez de saltar). Devuelve el precio en el
    instante `año` y la tasa de crecimiento instantánea de cada célula.
    """
    t0 = int(np.clip(math.floor(año), 0, AÑOS))
    t1 = int(np.clip(t0 + 1, 0, AÑOS))
    f = año - t0
    precio_t = valores[t0] * (1 - f) + valores[t1] * f
    tasa = (valores[t1] - valores[t0]) / valores[t0] if t1 > t0 \
        else (valores[t0] - valores[t0 - 1]) / valores[t0 - 1]
    return precio_t, tasa


# ══════════════════════════════════════════════════════════════════════════════
# 4 · SISTEMA CIRCULATORIO — FLUJOS DE CAPITAL
# ══════════════════════════════════════════════════════════════════════════════

def construir_flujos(gdf: gpd.GeoDataFrame, valores: np.ndarray,
                     año: float, n_fuentes: int = 6,
                     n_destinos: int = 22) -> pd.DataFrame:
    """
    Modela la rotación del capital: los nodos más desarrollados (corazones)
    bombean liquidez hacia las células emergentes con mayor crecimiento
    proyectado. Cada destino se conecta con la fuente "gravitacionalmente"
    más fuerte:  atracción = valor_fuente / distancia.
    """
    precio_t, tasa = estado_en(valores, año)
    cx, cy = gdf["lng"].to_numpy(), gdf["lat"].to_numpy()

    fuentes = np.argsort(precio_t)[-n_fuentes:]              # corazones del tejido
    candidatos = np.argsort(tasa)[::-1]                      # emergentes por tasa
    destinos = [c for c in candidatos if c not in set(fuentes)][:n_destinos]

    filas = []
    for k, d in enumerate(destinos):
        dist = np.hypot(cx[fuentes] - cx[d], cy[fuentes] - cy[d])
        f = fuentes[int(np.argmax(precio_t[fuentes] / (dist + 1e-4)))]
        filas.append({
            "origen": [float(cx[f]), float(cy[f])],
            "destino": [float(cx[d]), float(cy[d])],
            "intensidad": float(tasa[d] / (tasa.max() + 1e-9)),
            "desfase": (k * 0.13) % 1.0,          # desincroniza los pulsos
        })
    return pd.DataFrame(filas)


def construir_trayectos(flujos: pd.DataFrame) -> list[dict]:
    """
    Convierte cada arco en un trayecto curvo con timestamps para el TripsLayer:
    los "glóbulos" de capital que viajan por las venas del tejido.
    """
    trayectos = []
    for _, fl in flujos.iterrows():
        (x0, y0), (x1, y1) = fl["origen"], fl["destino"]
        # curva suave: desplaza el punto medio en dirección perpendicular
        px, py = -(y1 - y0), (x1 - x0)
        s = np.linspace(0.0, 1.0, 14)
        arco = np.sin(s * math.pi) * 0.18
        camino = [[float(x0 + (x1 - x0) * u + px * a),
                   float(y0 + (y1 - y0) * u + py * a)] for u, a in zip(s, arco)]
        marcas = (fl["desfase"] + s * 0.55).tolist()   # ventana temporal del pulso
        trayectos.append({"camino": camino, "marcas": marcas,
                          "intensidad": float(fl["intensidad"])})
    return trayectos


# ══════════════════════════════════════════════════════════════════════════════
# 5 · RENDER — CAPAS PYDECK Y PALETA NEÓN
# ══════════════════════════════════════════════════════════════════════════════

def paleta_neon(t: np.ndarray) -> np.ndarray:
    """Mapea valores normalizados [0,1] a la rampa bioluminiscente RGB."""
    t = np.clip(t, 0, 1)
    return np.stack([np.interp(t, _STOPS_T, _STOPS_R),
                     np.interp(t, _STOPS_T, _STOPS_G),
                     np.interp(t, _STOPS_T, _STOPS_B)], axis=1)


def preparar_celulas(gdf: gpd.GeoDataFrame, valores: np.ndarray,
                     año: float, fase: float, extrusion: bool) -> pd.DataFrame:
    """
    Calcula color, opacidad y altura de cada célula en el instante `año`.
    La "respiración" del tejido: la opacidad late con la fase de animación y
    las células en mutación laten más fuerte (ilusión de expansión orgánica).
    """
    precio_t, tasa = estado_en(valores, año)
    base = valores[0]
    vmin, vmax = base.min(), valores[-1].max()          # escala fija en el tiempo
    t = (precio_t - vmin) / (vmax - vmin)

    rgb = paleta_neon(t ** 0.85)
    tasa_n = tasa / (tasa.max() + 1e-9)
    latido = 0.88 + 0.12 * np.sin(2 * math.pi * (fase + t * 2.0))
    alfa = (95 + 150 * t) * (0.75 + 0.5 * tasa_n) * latido

    p90 = np.quantile(tasa, 0.90)
    p60 = np.quantile(tasa, 0.60)
    estado = np.where(tasa >= p90, "🧬 Mutación activa",
                      np.where(tasa >= p60, "🌱 Expansión", "💤 Latente"))

    df = pd.DataFrame({
        "contorno": gdf["contorno"].tolist(),
        "color": np.column_stack([rgb, np.clip(alfa, 30, 255)])
                   .astype(int).tolist(),
        "altura": ((t ** 1.5) * 900 * (1.0 if extrusion else 0.0)).tolist(),
        "barrio": gdf["barrio"].tolist(),
        "estado": estado.tolist(),
        "precio_txt": [f"${p:,.0f} MXN/m²" for p in precio_t],
        "crec_txt": [f"+{r * 100:.1f}% anual" for r in tasa],
        "plusvalia_txt": [f"+{(pt / b - 1) * 100:.0f}% vs hoy"
                          for pt, b in zip(precio_t, base)],
    })
    return df


def construir_deck(gdf: gpd.GeoDataFrame, valores: np.ndarray, año: float,
                   fase: float, mostrar_flujos: bool,
                   extrusion: bool) -> pdk.Deck:
    """Ensambla todas las capas del organismo urbano en un Deck listo para render."""
    celulas = preparar_celulas(gdf, valores, año, fase, extrusion)
    capas = [
        # ── Tejido celular: polígonos extruidos que respiran ──────────────────
        pdk.Layer(
            "PolygonLayer",
            data=celulas,
            get_polygon="contorno",
            get_fill_color="color",
            get_elevation="altura",
            extruded=extrusion,
            get_line_color=[0, 245, 255, 40],
            line_width_min_pixels=1,
            pickable=True,
            auto_highlight=True,
            highlight_color=[255, 255, 255, 120],
        )
    ]

    if mostrar_flujos:
        flujos = construir_flujos(gdf, valores, año)
        pulso = 0.5 + 0.5 * math.sin(2 * math.pi * fase)

        # ── Venas: arcos que laten entre corazones y zonas emergentes ─────────
        capas.append(pdk.Layer(
            "ArcLayer",
            data=flujos,
            get_source_position="origen",
            get_target_position="destino",
            get_source_color=[0, 245, 255, int(90 + 130 * pulso)],
            get_target_color=[255, 46, 154, int(150 + 100 * pulso)],
            get_width=f"2 + intensidad * {3.5 + 3.0 * pulso}",
            get_height=0.6,
            great_circle=False,
        ))

        # ── Glóbulos: pulsos de capital viajando por las venas (TripsLayer) ───
        capas.append(pdk.Layer(
            "TripsLayer",
            data=construir_trayectos(flujos),
            get_path="camino",
            get_timestamps="marcas",
            get_color=[120, 255, 245],
            width_min_pixels=3,
            trail_length=0.35,
            current_time=(fase * 2.0) % 2.0,
            opacity=0.9,
        ))

        # ── Corazones: glow pulsante sobre los nodos que bombean capital ──────
        nodos = pd.DataFrame({"pos": flujos["origen"].drop_duplicates().tolist()})
        capas.append(pdk.Layer(
            "ScatterplotLayer",
            data=nodos,
            get_position="pos",
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
            zoom=13.1, pitch=52, bearing=-16,
        ),
        map_style=ESTILO_MAPA,
        tooltip={
            "html": (
                "<div style='font-family:monospace'>"
                "<b style='color:#00f5ff'>{barrio}</b> · {estado}<br/>"
                "💰 <b>{precio_txt}</b><br/>"
                "🧬 Contagio: <b style='color:#ff2e9a'>{crec_txt}</b><br/>"
                "📈 Plusvalía acumulada: <b>{plusvalia_txt}</b></div>"
            ),
            "style": {"backgroundColor": "#0b0520", "color": "#e8e6ff",
                      "border": "1px solid #00f5ff", "borderRadius": "8px"},
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# 6 · INTERFAZ STREAMLIT (DARK MODE NEÓN)
# ══════════════════════════════════════════════════════════════════════════════

def inyectar_css() -> None:
    """Dark mode profundo para que el tejido neón resalte."""
    st.markdown("""
    <style>
      .stApp { background: radial-gradient(ellipse at top, #0d0524 0%, #05010f 60%); }
      section[data-testid="stSidebar"] {
          background: #080316; border-right: 1px solid #1d1140;
      }
      h1, h2, h3 { color: #e8e6ff !important; }
      .neon-title {
          font-family: monospace; font-size: 2.1rem; font-weight: 800;
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
      div[data-testid="stMetricValue"] { color: #00f5ff; }
      div[data-testid="stMetricLabel"] { color: #8f88b8; }
      #MainMenu, footer { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="BrickBit · Morfogénesis Urbana",
                       page_icon="🧬", layout="wide",
                       initial_sidebar_state="expanded")
    inyectar_css()

    st.markdown('<div class="neon-title">🧬 MOTOR DE MORFOGÉNESIS URBANA</div>',
                unsafe_allow_html=True)
    st.markdown('<p class="neon-sub">BrickBit · la ciudad como organismo vivo — '
                'Azcapotzalco/Vallejo, CDMX (datos simulados)</p>',
                unsafe_allow_html=True)

    # ── Panel lateral: la máquina del tiempo ──────────────────────────────────
    with st.sidebar:
        st.markdown("### ⏳ Línea de tiempo")
        año = st.slider("Predicción (años hacia el futuro)", 0.0, float(AÑOS),
                        0.0, step=0.25, format="%.2f años",
                        help="Desliza para ver cómo la plusvalía se contagia por el tejido.")

        st.markdown("### 🧫 Parámetros del organismo")
        rho = st.slider("Virulencia del contagio (ρ)", 0.0, 1.5, 0.85, 0.05,
                        help="Coeficiente espacial autorregresivo: cuánto 'infecta' "
                             "una manzana de alto valor a sus vecinas.")
        catalizador = st.selectbox("Célula madre (catalizador urbano)",
                                   list(CATALIZADORES.keys()),
                                   help="Inyecta un desarrollo detonante y observa "
                                        "la mutación en cadena.")

        st.markdown("### 👁 Capas")
        mostrar_flujos = st.checkbox("🫀 Sistema circulatorio de capital", True)
        extrusion = st.checkbox("⛰ Relieve 3D del tejido", True)

        st.markdown("---")
        reproducir = st.button("▶ Reproducir morfogénesis (10 años)",
                               width="stretch")
        st.caption("El tejido late en vivo durante la reproducción; las venas "
                   "cian→magenta bombean capital hacia las células emergentes.")

    # ── Simulación (cacheada por ρ y catalizador) ─────────────────────────────
    gdf = generar_tejido_urbano()
    valores = simular_morfogenesis(rho, catalizador)

    # ── Signos vitales del organismo ──────────────────────────────────────────
    precio_t, tasa = estado_en(valores, año)
    flujos_kpi = construir_flujos(gdf, valores, año)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Valor medio del tejido", f"${precio_t.mean():,.0f} /m²",
              f"+{(precio_t.mean() / valores[0].mean() - 1) * 100:.1f}% vs hoy")
    c2.metric("🧬 Células en mutación",
              f"{int((tasa >= np.quantile(tasa, 0.90)).sum())}",
              "top 10% de contagio")
    c3.metric("🫀 Pulso de capital", f"{len(flujos_kpi)} flujos activos",
              f"ρ = {rho:.2f}")
    c4.metric("📅 Horizonte", f"Año {año:.1f} / {AÑOS}",
              catalizador if CATALIZADORES[catalizador] else "sin catalizador")

    # ── Lienzo del mapa: render estático o animación de la década ─────────────
    lienzo = st.empty()

    if reproducir:
        # La década completa en ~6 s: el año avanza y la fase hace latir todo.
        cuadros = 90
        for f in range(cuadros + 1):
            año_f = AÑOS * f / cuadros
            fase_f = (f * 0.045) % 1.0
            lienzo.pydeck_chart(
                construir_deck(gdf, valores, año_f, fase_f,
                               mostrar_flujos, extrusion),
                width="stretch",
            )
            time.sleep(0.05)
        st.toast("🧬 Morfogénesis completa: año 10 alcanzado", icon="✅")
    else:
        # La fase depende del año → mover el slider también hace latir el tejido
        lienzo.pydeck_chart(
            construir_deck(gdf, valores, año, (año * 0.4) % 1.0,
                           mostrar_flujos, extrusion),
            width="stretch",
        )

    # ── Leyenda + explicación del modelo ──────────────────────────────────────
    st.markdown(
        "<div style='font-family:monospace;color:#8f88b8;font-size:.85rem'>"
        "<span style='color:#1a083e'>■</span> latente&nbsp;&nbsp;"
        "<span style='color:#0069ff'>■</span> despertando&nbsp;&nbsp;"
        "<span style='color:#00f5ff'>■</span> expansión&nbsp;&nbsp;"
        "<span style='color:#ff2e9a'>■</span> mutación&nbsp;&nbsp;"
        "<span style='color:#ffe2a8'>■</span> núcleo consolidado"
        "&nbsp;&nbsp;·&nbsp;&nbsp; arcos cian→magenta = capital fluyendo "
        "de corazones a células emergentes</div>",
        unsafe_allow_html=True,
    )

    with st.expander("🔬 ¿Cómo funciona el modelo? (autocorrelación espacial)"):
        st.markdown("""
        **La ciudad no es una cuadrícula: es un tejido.** Cada manzana es una
        célula cuyo comportamiento depende de sus vecinas — la primera ley de
        la geografía de Tobler, formalizada aquí como un proceso espacial
        autorregresivo (SAR) simplificado:

        ```
        precio[t+1] = precio[t] · (1 + g_base + ρ · (W · precio_norm[t]) · potencial)
        ```

        - **W** es la matriz de contigüidad *reina* (8 vecinas por célula).
        - **ρ** controla la *virulencia* del contagio de plusvalía.
        - El **potencial** hace que una zona industrial barata sea más
          receptiva a la "infección positiva" que un núcleo ya consolidado.
        - Un **catalizador** (metro, centro comercial, parque) actúa como
          célula madre: eleva el potencial de su entorno y detona la
          reacción en cadena — la *mutación urbana*.

        El **sistema circulatorio** conecta los nodos de mayor valor
        (corazones) con las células de mayor crecimiento proyectado, con una
        atracción gravitacional `valor / distancia`. *Datos 100% simulados
        con fines de visualización.*
        """)


if __name__ == "__main__":
    main()
