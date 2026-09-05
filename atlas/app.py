"""
BrickBit Atlas — la app.

    cd atlas
    streamlit run app.py

Hace visible lo que las fases 0 a 3 dejaron en parquet. Tres pestañas, tres
preguntas: cuánto vale este inmueble, cómo está el precio en la ciudad, y cómo
se ha movido el mercado en veintiún años.

UNA REGLA QUE ATRAVIESA TODO: ningún número aparece sin su incertidumbre y sin
su procedencia. El valor puntual va siempre con su intervalo; el mapa lleva su
capa de "cuánto no sé"; y en todas partes se recuerda que son precios de OFERTA.
Un número solo, grande y sin contexto, miente por omisión.

SOBRE EL DISEÑO. La primera versión tenía tres problemas que se veían en
pantalla: texto gris oscuro sobre fondo casi negro (ilegible), el `st.markdown`
crudo peleando con los componentes nativos de Streamlit, y ninguna jerarquía —
todo del mismo tamaño, así que la vista no sabía dónde caer—. Aquí el contraste
se sube al mínimo accesible, se usa una escala tipográfica de tres niveles y
cada bloque de información vive en una tarjeta con su propio aire.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from atlas import lago                                    # noqa: E402
from atlas.config import cargar                           # noqa: E402
from atlas.modelos import persistencia                    # noqa: E402

# ── Paleta v2 de BrickBit ────────────────────────────────────────────────────
# El ámbar está reservado: marca lo estimado. No se usa de adorno.
TIERRA = "#100c0a"      # fondo
SUP = "#1d1713"         # superficie de tarjeta
SUP2 = "#272019"        # borde
CREMA = "#f5ede3"       # texto principal
TENUE = "#a89c90"       # texto secundario — sube de #9c9188 para llegar a 4.5:1
BOSQUE = "#24664a"
SALVIA = "#6fa287"
AMBAR = "#F5C277"
TERRACOTA = "#c07a66"
ESCALA = [[191, 91, 82], [207, 146, 71], [224, 187, 131], [183, 196, 137], [36, 102, 74]]

st.set_page_config(page_title="BrickBit Atlas", page_icon="🧭", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown(f"""<style>
  .stApp {{ background:{TIERRA}; }}
  .block-container {{ padding-top:2.2rem; max-width:1280px; }}

  /* Tipografía: tres niveles y no más, para que la vista sepa dónde caer. */
  html, body, [class*="css"] {{ color:{CREMA}; }}
  h1 {{ font-size:1.9rem !important; font-weight:700; letter-spacing:-.02em; }}
  h2 {{ font-size:1.15rem !important; font-weight:600; color:{CREMA}; margin-top:0; }}
  h3 {{ font-size:.82rem !important; font-weight:600; color:{TENUE};
        text-transform:uppercase; letter-spacing:.09em; margin:0 0 .6rem 0; }}

  /* Tarjetas: cada bloque con su aire, en vez de todo pegado al fondo. */
  .tarjeta {{ background:{SUP}; border:1px solid {SUP2}; border-radius:14px;
              padding:1.25rem 1.4rem; margin-bottom:1rem; }}
  .nota {{ color:{TENUE}; font-size:.86rem; line-height:1.55; margin:.4rem 0 0 0; }}
  .nota b {{ color:{CREMA}; font-weight:600; }}

  /* La cifra grande y su banda. */
  .cifra {{ font-size:2.9rem; font-weight:700; color:{AMBAR};
            line-height:1.05; letter-spacing:-.03em; }}
  .banda {{ font-size:1.35rem; font-weight:600; color:{CREMA}; margin-top:.15rem; }}
  .etq {{ font-size:.78rem; color:{TENUE}; text-transform:uppercase;
          letter-spacing:.09em; }}

  /* Barra del intervalo: ver el ancho vale más que leerlo. */
  .riel {{ position:relative; height:8px; border-radius:5px; margin:1.1rem 0 .4rem 0;
           background:linear-gradient(90deg,{TERRACOTA}44,{SALVIA}66,{TERRACOTA}44); }}
  .pin {{ position:absolute; top:-4px; width:3px; height:16px;
          border-radius:2px; background:{AMBAR}; }}

  /* Componentes nativos de Streamlit, alineados con la paleta. */
  [data-testid="stMetric"] {{ background:{SUP}; border:1px solid {SUP2};
      border-radius:12px; padding:.85rem 1rem; }}
  [data-testid="stMetricValue"] {{ color:{CREMA}; font-size:1.5rem; }}
  [data-testid="stMetricLabel"] {{ color:{TENUE}; }}
  .stTabs [data-baseweb="tab-list"] {{ gap:.35rem; border-bottom:1px solid {SUP2}; }}
  .stTabs [data-baseweb="tab"] {{ background:transparent; color:{TENUE};
      padding:.55rem 1.1rem; font-weight:500; }}
  .stTabs [aria-selected="true"] {{ color:{CREMA} !important;
      border-bottom:2px solid {AMBAR}; }}
  div[data-testid="stDataFrame"] {{ border:1px solid {SUP2}; border-radius:12px; }}
  label, .stSelectbox label, .stSlider label {{ color:{TENUE} !important;
      font-size:.85rem !important; }}
  hr {{ border-color:{SUP2}; }}
</style>""", unsafe_allow_html=True)


def tarjeta(cuerpo: str) -> None:
    st.markdown(f"<div class='tarjeta'>{cuerpo}</div>", unsafe_allow_html=True)


def nota(texto: str) -> None:
    st.markdown(f"<p class='nota'>{texto}</p>", unsafe_allow_html=True)


@st.cache_resource
def _cfg():
    return cargar()


@st.cache_data(show_spinner=False)
def _capa(nombre: str):
    cfg = _cfg()
    return lago.leer(nombre, cfg) if lago.existe(nombre, cfg) else None


@st.cache_resource
def _paquete():
    return persistencia.cargar_paquete(_cfg())


def _falta(que: str, comando: str) -> None:
    st.warning(f"Falta **{que}**.")
    st.code(comando, language="bash")


def _dinero(x: float) -> str:
    """Millones cuando los hay: '$4.2 M' se lee de un vistazo, '$4,183,920' no."""
    return f"${x / 1e6:.2f} M" if abs(x) >= 1e6 else f"${x:,.0f}"


# ═══════════════════════════════════════════════════════════════════ valuar
def pestana_valuar() -> None:
    p, feats = _paquete(), _capa("features_malla")
    if p is None:
        _falta("el AVM entrenado", "cd atlas\npython -m pipelines.fase2")
        return
    if feats is None:
        _falta("la malla de variables", "python -m pipelines.fase1")
        return

    dias = p.antiguedad_dias()
    if dias > 90:
        st.warning(
            f"Modelo entrenado con inventario de hace **{dias} días**. Un AVM "
            "viejo sigue dando números convincentes mucho después de dejar de "
            "ser cierto — corre `tools\\actualizar-atlas.bat`.")

    izq, der = st.columns([0.9, 1.1], gap="large")

    with izq:
        st.markdown("### El inmueble")
        c1, c2 = st.columns(2)
        lat = c1.number_input("Latitud", 19.00, 19.65, 19.4326, format="%.5f")
        lng = c2.number_input("Longitud", -99.37, -98.93, -99.1650, format="%.5f")

        tipos = sorted({c.replace("tipo_", "") for c in p.columnas if c.startswith("tipo_")}
                       | {p.tipo_referencia or "otro"})
        c3, c4 = st.columns([1, 1])
        tipo = c3.selectbox("Tipo", tipos,
                            index=tipos.index("depto") if "depto" in tipos else 0)
        sup = c4.number_input("Superficie (m²)", 20, 2000, 90, step=5)

        c5, c6, c7 = st.columns(3)
        rec = c5.number_input("Recámaras", 0, 10, 2)
        ban = c6.number_input("Baños", 0, 10, 2)
        est = c7.number_input("Estac.", 0, 6, 1)
        ant = st.slider("Antigüedad (años)", 0, 70, 10)

        st.markdown("### Confianza")
        nivel = st.select_slider(
            "nivel", options=[0.50, 0.80, 0.90, 0.95], value=0.80,
            format_func=lambda v: f"{v * 100:.0f}%", label_visibility="collapsed")
        nota("El <b>80%</b> es la banda con la que se puede conversar. El 95% es "
             "tan ancho que dice poco más que «no sé», y no por defecto del "
             "método: es el error del modelo.")

    X = persistencia.fila_de_inmueble(
        lat, lng,
        {"tipo": tipo, "superficie_construida_m2": sup, "recamaras": rec,
         "banos": ban, "estacionamientos": est, "antiguedad_anios": ant},
        feats, p.columnas, p.tipo_referencia, _cfg(),
        fuentes=(p.fuentes_xy, p.fuentes_y) if p.fuentes_xy is not None else None)
    v = persistencia.valuar(p, X, sup, alpha=round(1 - nivel, 2))

    with der:
        # Dónde cae la estimación dentro de su propia banda: verlo dice más que
        # leer dos cifras sueltas.
        pos = (v.precio_total - v.lo_total) / max(v.hi_total - v.lo_total, 1e-9)
        tarjeta(
            f"<div class='etq'>Estimación · mediana</div>"
            f"<div class='cifra'>{_dinero(v.precio_total)}</div>"
            f"<div class='nota' style='margin-top:.1rem'>"
            f"${v.precio_m2:,.0f} por m² · segmento «{v.segmento}»</div>"
            f"<div class='riel'><div class='pin' style='left:{pos * 100:.1f}%'></div></div>"
            f"<div style='display:flex;justify-content:space-between'>"
            f"<span class='banda'>{_dinero(v.lo_total)}</span>"
            f"<span class='banda'>{_dinero(v.hi_total)}</span></div>"
            f"<div class='nota'>Intervalo al {(1 - v.alpha) * 100:.0f}% "
            f"— ancho ±{v.ancho_pct:.0f}%</div>")

        m = p.metricas
        a, b, c = st.columns(3)
        a.metric("Error mediano", f"{m.get('mdape_pct', float('nan')):.0f}%")
        b.metric("Cobertura 95%", f"{m.get('cobertura_95', 0) * 100:.0f}%")
        c.metric("Entrenado con", f"{p.n_entrenamiento:,}")
        nota(f"Medido sobre barrios que el modelo <b>nunca vio</b>. "
             f"Inventario de {p.fecha_datos[:10]}.")

    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
    tarjeta(
        "<div class='etq'>Qué es y qué no es este número</div>"
        "<p class='nota'>Es el precio al que se <b>ofrecería</b> un inmueble así, "
        "no aquel al que se vende. En México no hay MLS abierto ni Registro "
        "Público accesible, así que el precio de cierre no es observable y no se "
        "le aplica ningún descuento inventado. <b>No es un avalúo con validez "
        "legal</b> salvo que lo suscriba un perito valuador.</p>")


# ═════════════════════════════════════════════════════════════════════ mapa
def pestana_mapa() -> None:
    campo = _capa("campo_cdmx")
    if campo is None:
        _falta("el campo espacial", "cd atlas\npython -m pipelines.fase3")
        return
    import pydeck as pdk

    CAPAS = {
        "Precio por m²": ("ln_precio_m2", False,
                          "Verde donde es caro. Es la superficie suavizada, no los "
                          "anuncios sueltos: dos departamentos de la misma cuadra se "
                          "ofrecen a precios distintos y eso es ruido, no geografía."),
        "Cuánto NO sé": ("sigma_nivel", True,
                         "Rojo donde el modelo tiene menos comparables. <b>No es un "
                         "hueco, es una respuesta</b>: saber dónde no se sabe evita "
                         "confiar en una cifra que el modelo no puede sostener."),
        "Pendiente del precio": ("pendiente_pct_km", False,
                                 "Cuánto sube el precio por kilómetro. Verde donde la "
                                 "pendiente es fuerte — ahí un par de cuadras cambian "
                                 "mucho el valor."),
    }
    capa = st.radio("capa", list(CAPAS), horizontal=True, label_visibility="collapsed")
    col, invertir, explicacion = CAPAS[capa]

    d = campo.copy()
    v = d[col].to_numpy(dtype=float)
    lo, hi = np.nanpercentile(v, [5, 95])
    t = np.clip((v - lo) / max(hi - lo, 1e-9), 0, 1)
    if invertir:
        t = 1 - t
    d[["r", "g", "b"]] = np.array(ESCALA)[(t * (len(ESCALA) - 1)).astype(int)]
    # La altura la da SIEMPRE el precio: mover el relieve con cada capa
    # desorienta, y el relieve es lo que ancla la vista a la ciudad.
    d["alto"] = np.clip(d["ln_precio_m2"] - np.nanmin(d["ln_precio_m2"]), 0, None)
    d["precio_m2"] = np.exp(d["ln_precio_m2"]).round(0)
    d["incert_pct"] = (d["sigma_nivel"] * 100).round(0)
    d["pend"] = d["pendiente_pct_km"].round(1)

    st.pydeck_chart(pdk.Deck(
        map_style=None,
        initial_view_state=pdk.ViewState(latitude=19.395, longitude=-99.14,
                                         zoom=9.7, pitch=42, bearing=12),
        layers=[pdk.Layer(
            "ColumnLayer", data=d, get_position=["lng", "lat"],
            get_elevation="alto", elevation_scale=900, radius=105,
            get_fill_color=["r", "g", "b", 205], pickable=True, auto_highlight=True,
        )],
        tooltip={"html": "<b>${precio_m2}</b> por m²<br/>"
                         "incertidumbre ±{incert_pct}%<br/>"
                         "pendiente {pend} %/km",
                 "style": {"backgroundColor": SUP, "color": CREMA,
                           "fontSize": "12px", "borderRadius": "8px"}},
    ), height=520)

    nota(explicacion)

    a, b, c = st.columns(3)
    a.metric("Celdas", f"{len(d):,}")
    b.metric("Pendiente mediana", f"{d['pendiente_pct_km'].median():.1f} %/km")
    c.metric("Incertidumbre típica", f"±{d['sigma_nivel'].median() * 100:.0f}%")

    fr = _capa("frontera_cdmx")
    if fr is not None and "es_frontera" in fr.columns and int(fr["es_frontera"].sum()):
        n = int(fr["es_frontera"].sum())
        st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
        st.markdown(f"## Frente de precio · {n} inmuebles")
        nota("Baratos rodeados de caros. Es un diferencial <b>presente</b>, no una "
             "plusvalía futura: que el mercado lo cierre depende de POR QUÉ está "
             "abierto, y esa razón puede ser una barrera física, un uso de suelo o "
             "una diferencia real de calidad que ninguna de estas variables ve.")
        tabla = (fr.loc[fr["es_frontera"], ["lat", "lng", "ln_precio_m2", "brecha_vecinos"]]
                 .assign(**{"$/m²": lambda x: np.exp(x["ln_precio_m2"]).round(0),
                            "bajo sus vecinos": lambda x:
                                ((np.exp(x["brecha_vecinos"]) - 1) * 100).round(0)})
                 .drop(columns=["ln_precio_m2", "brecha_vecinos"])
                 .sort_values("bajo sus vecinos", ascending=False).head(20))
        st.dataframe(tabla, use_container_width=True, hide_index=True,
                     column_config={"bajo sus vecinos": st.column_config.NumberColumn(
                         "bajo sus vecinos", format="%d %%")})


# ═══════════════════════════════════════════════════════════════════ ciudad
def pestana_ciudad() -> None:
    from atlas.temporal import indice

    panel = indice.cargar_panel(_cfg())
    zonas = list(panel.nivel.columns)
    zona = st.selectbox("Zona", zonas, index=zonas.index("Ciudad de México"))
    r = indice.resumen_zona(panel, zona).dropna()
    a0, a1 = panel.anios[0], panel.anios[-1]
    acum = indice.acumulado(panel, zona, a0, a1)

    a, b, c = st.columns(3)
    a.metric(f"Acumulado {a0}–{a1}", f"×{acum:.2f}")
    b.metric("Anual compuesto", f"{(acum ** (1 / (a1 - a0)) - 1) * 100:.2f}%")
    c.metric(f"Último año ({a1})", f"{r['crec_%'].iloc[-1]:+.2f}%")

    izq, der = st.columns([1.4, 1], gap="large")
    with izq:
        st.markdown("### Índice de precios")
        st.line_chart(r[["indice"]], height=260, color=SALVIA)
    with der:
        st.markdown("### Crecimiento anual")
        st.bar_chart(r[["crec_%"]], height=260, color=BOSQUE)

    tarjeta(
        "<div class='etq'>Es nominal</div>"
        "<p class='nota'>No está deflactado, así que una parte de ese crecimiento "
        "es inflación y no plusvalía. Decir «subió 7.9% al año» y decir «subió "
        "7.9% <b>más que todo lo demás</b>» no es lo mismo ni de lejos, y con "
        "estos datos sólo se puede afirmar lo primero.<br><br>"
        "Fuente: SHF, avalúos de vivienda con crédito hipotecario garantizado — "
        "<b>transacciones reales</b>, no ofertas. Es la mitad que a los listados "
        "les falta; a cambio es estatal, así que dice cuánto se movió la ciudad "
        "entera y no qué colonia.</p>")

    tarjeta(
        "<div class='etq'>¿El crecimiento se contagia entre zonas vecinas?</div>"
        "<p class='nota'>Puesto a prueba con validación hacia adelante sobre 480 "
        "predicciones fuera de muestra, el término espacial <b>no aporta</b>: "
        "añadir el crecimiento del vecindario empeora el error un 2.6% frente a "
        "usar sólo el momentum propio. Agrupamiento no es contagio —dos vecinos "
        "pueden crecer igual por un choque común, sin que uno empuje al otro— y "
        "la prueba es predecir.</p>")


# ══════════════════════════════════════════════════════════════════════ main
c1, c2 = st.columns([3, 1])
with c1:
    st.markdown("# 🧭 BrickBit Atlas")
    st.markdown(
        f"<p class='nota' style='margin-top:-.5rem'>Inteligencia inmobiliaria de "
        f"la Ciudad de México · <span style='color:{AMBAR}'>precios de oferta, "
        f"no de cierre</span></p>", unsafe_allow_html=True)
with c2:
    _p = _paquete()
    if _p is not None:
        st.markdown(
            f"<div style='text-align:right;padding-top:1rem'>"
            f"<div class='etq'>Inventario</div>"
            f"<div style='font-size:1.1rem;color:{CREMA};font-weight:600'>"
            f"{_p.fecha_datos[:10]}</div></div>", unsafe_allow_html=True)

t1, t2, t3 = st.tabs(["  Valuar  ", "  Mapa  ", "  La ciudad en el tiempo  "])
with t1:
    pestana_valuar()
with t2:
    pestana_mapa()
with t3:
    pestana_ciudad()
