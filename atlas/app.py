"""
BrickBit Atlas — ¿cuánto vale? La app pública.

    cd atlas
    streamlit run app.py

PARA QUIÉN ES, Y POR QUÉ SE REESCRIBIÓ. La versión anterior de este archivo era
una consola de diagnóstico del modelo: cobertura por segmento, σ̂, I de Moran,
SDM, SHAP, correcciones de Mondrian. Toda esa información es necesaria —para
auditar el motor—, y ninguna le sirve a alguien que quiere saber cuánto vale su
departamento. Se le estaba pidiendo a un banco de pruebas que fuera un
producto, y por eso la pantalla se sentía inútil por más que se le arreglara el
contraste. La consola sigue existiendo, entera, en `consola.py`.

Esta pantalla contesta UNA pregunta —¿cuánto vale este inmueble?— y se embebe
en brickbit.co igual que el Motor de Morfogénesis: un iframe a Streamlit Cloud.

LO QUE NO SE SIMPLIFICA, AUNQUE SEA PÚBLICO. Que el público sea más amplio no
autoriza a esconder lo incómodo; al contrario. Se queda:

  · el intervalo, siempre y del mismo tamaño visual que la cifra;
  · que son precios de OFERTA y no de cierre;
  · que no es un avalúo con validez legal;
  · la advertencia cuando el segmento del inmueble cubre menos de lo prometido.

Un valuador que enseña una cifra sola y grande es más bonito y es mentira por
omisión. La regla de la casa —lo estimado va en ámbar— aquí aplica a la cifra
principal, porque la cifra principal es una estimación.

SOBRE LOS COMPARABLES QUE SE MUESTRAN. Sólo agregados: cuántos hay cerca y a
qué precio mediano. Nunca el anuncio individual, ni su dirección, ni su precio
exacto — el inventario viene de un convenio con Century 21 y publicarlo pieza
por pieza sería redistribuirlo.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from atlas import here                                     # noqa: E402
from atlas import lago                                     # noqa: E402
from atlas.config import cargar                            # noqa: E402
from atlas.modelos import persistencia                     # noqa: E402

# ── Paleta v2 de BrickBit ────────────────────────────────────────────────────
TIERRA = "#100c0a"
SUP = "#1d1713"
SUP2 = "#272019"
CREMA = "#f5ede3"
TENUE = "#a89c90"
SALVIA = "#6fa287"
OLIVA = "#b7c489"
AMBAR = "#F5C277"       # intocable: marca lo estimado

st.set_page_config(page_title="¿Cuánto vale? · BrickBit", page_icon="🧭",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown(f"""<style>
  .stApp {{ background:{TIERRA}; }}
  .block-container {{ padding-top:1.4rem; padding-bottom:2rem; max-width:1180px; }}
  html, body, [class*="css"] {{ color:{CREMA}; }}
  h1 {{ font-size:1.75rem !important; font-weight:700; letter-spacing:-.02em;
        margin-bottom:.15rem; }}
  h3 {{ font-size:.78rem !important; font-weight:600; color:{TENUE};
        text-transform:uppercase; letter-spacing:.09em; margin:0 0 .5rem 0; }}

  .tarjeta {{ background:{SUP}; border:1px solid {SUP2}; border-radius:14px;
              padding:1.3rem 1.45rem; margin-bottom:.9rem; }}
  .nota {{ color:{TENUE}; font-size:.86rem; line-height:1.55; margin:.4rem 0 0 0; }}
  .nota b {{ color:{CREMA}; font-weight:600; }}
  .aviso {{ border-left:3px solid {AMBAR}; background:{AMBAR}14;
            padding:.75rem 1rem; border-radius:0 8px 8px 0; margin:.85rem 0 0 0; }}
  .aviso p {{ margin:0; color:{CREMA}; font-size:.87rem; line-height:1.5; }}

  /* La cifra y su banda pesan visualmente lo mismo, a propósito: si la cifra
     fuera el doble de grande, el ojo se quedaría con ella y el intervalo
     sería decorativo. */
  .cifra {{ font-size:3rem; font-weight:700; color:{AMBAR};
            line-height:1.04; letter-spacing:-.03em; }}
  .banda {{ font-size:1.3rem; font-weight:600; color:{CREMA}; }}
  .etq {{ font-size:.76rem; color:{TENUE}; text-transform:uppercase;
          letter-spacing:.09em; }}
  .riel {{ position:relative; height:10px; border-radius:6px;
           margin:1.15rem 0 .5rem 0; background:{SALVIA}3d;
           border:1px solid {SALVIA}55; }}
  .pin {{ position:absolute; top:-5px; width:3px; height:20px;
          border-radius:2px; background:{AMBAR}; }}
  .extremos {{ display:flex; justify-content:space-between; align-items:baseline; }}

  [data-testid="stMetric"] {{ background:{SUP}; border:1px solid {SUP2};
      border-radius:12px; padding:.8rem .95rem; }}
  [data-testid="stMetricValue"] {{ color:{CREMA}; font-size:1.35rem; }}
  [data-testid="stMetricLabel"] {{ color:{TENUE}; }}
  label, .stSelectbox label, .stSlider label, .stTextInput label {{
      color:{TENUE} !important; font-size:.85rem !important; }}
  .stTabs [data-baseweb="tab-list"] {{ gap:.35rem; border-bottom:1px solid {SUP2}; }}
  .stTabs [data-baseweb="tab"] {{ background:transparent; color:{TENUE};
      padding:.5rem 1rem; font-weight:500; }}
  .stTabs [aria-selected="true"] {{ color:{CREMA} !important;
      border-bottom:2px solid {OLIVA}; }}
  hr {{ border-color:{SUP2}; }}
</style>""", unsafe_allow_html=True)


def nota(t: str) -> None:
    st.markdown(f"<p class='nota'>{t}</p>", unsafe_allow_html=True)


@st.cache_resource
def _cfg():
    return cargar()


@st.cache_resource
def _paquete():
    return persistencia.cargar_paquete(_cfg())


@st.cache_data(show_spinner=False)
def _feats():
    cfg = _cfg()
    return lago.leer("features_malla", cfg) if lago.existe("features_malla", cfg) else None


@st.cache_data(show_spinner=False, ttl=3600)
def _buscar(texto: str) -> list[tuple[str, float, float]]:
    """
    Geocodificación con memoria: la misma dirección no se pide dos veces.

    El TTL de una hora no es por frescura —una dirección no se mueve— sino para
    que la memoria de una app de larga vida no crezca sin tope.
    """
    return [(l.titulo, l.lat, l.lng) for l in here.buscar(texto, _cfg())]


def _dinero(x: float) -> str:
    return f"${x / 1e6:.2f} M" if abs(x) >= 1e6 else f"${x:,.0f}"


def _par(lo: float, hi: float) -> tuple[str, str]:
    """Los dos extremos en la MISMA unidad: existen para compararse."""
    if max(abs(lo), abs(hi)) >= 1e6:
        return f"${lo / 1e6:.2f} M", f"${hi / 1e6:.2f} M"
    return f"${lo:,.0f}", f"${hi:,.0f}"


# ─────────────────────────────────────────────────────────────── ubicación
def _ubicacion(cfg) -> tuple[float, float, str]:
    """
    Dónde está el inmueble. Por dirección si hay HERE; por alcaldía si no.

    El estado vive en `st.session_state` porque Streamlit reejecuta el script
    entero en cada interacción: sin eso, mover el slider de antigüedad borraría
    la dirección que la persona acaba de buscar.
    """
    ss = st.session_state
    ss.setdefault("lat", 19.4326)
    ss.setdefault("lng", -99.1650)
    ss.setdefault("etiqueta", "Centro de la Ciudad de México")

    if here.disponible():
        with st.form("buscar", clear_on_submit=False):
            c1, c2 = st.columns([4, 1])
            q = c1.text_input("Dirección, colonia o punto de referencia",
                              placeholder="Av. Ámsterdam 240, Condesa",
                              label_visibility="collapsed")
            enviar = c2.form_submit_button("Buscar", width="stretch")
        # Se busca al ENVIAR y no al teclear: autosuggest en cada tecla
        # convierte una dirección de 30 caracteres en 30 peticiones, y la
        # cuota de un plan gratuito se va en una tarde.
        if enviar and q.strip():
            res = _buscar(q.strip())
            if not res:
                st.warning(
                    "No encontré esa dirección **dentro de la Ciudad de "
                    "México**. El Atlas sólo está entrenado aquí: fuera de la "
                    "ciudad daría un número inventado con apariencia de "
                    "cálculo, así que prefiere no encontrarla.")
            elif len(res) == 1:
                ss["etiqueta"], ss["lat"], ss["lng"] = res[0]
            else:
                ss["opciones"] = res
        if ss.get("opciones"):
            elegido = st.radio("¿Cuál de estas?",
                               [o[0] for o in ss["opciones"]], index=0)
            for o in ss["opciones"]:
                if o[0] == elegido:
                    ss["etiqueta"], ss["lat"], ss["lng"] = o
    else:
        # Sin llave de HERE no se finge un buscador: se dice y se ofrece lo que
        # sí hay. Un campo de texto que nunca encuentra nada es peor que no
        # tenerlo, porque parece que el usuario escribe mal.
        alc = _alcaldias()
        if not alc.empty:
            nombres = alc["alcaldia"].tolist()
            i = nombres.index("Cuauhtémoc") if "Cuauhtémoc" in nombres else 0
            elegida = st.selectbox("Alcaldía", nombres, index=i)
            fila = alc.loc[alc["alcaldia"] == elegida].iloc[0]
            ss["lat"], ss["lng"] = float(fila["lat"]), float(fila["lng"])
            ss["etiqueta"] = f"{elegida} (centro aproximado)"

    with st.expander("Ajustar el punto en el mapa"):
        c1, c2 = st.columns(2)
        ss["lat"] = c1.number_input("Latitud", 19.00, 19.65,
                                    float(ss["lat"]), format="%.5f")
        ss["lng"] = c2.number_input("Longitud", -99.37, -98.93,
                                    float(ss["lng"]), format="%.5f")
    return float(ss["lat"]), float(ss["lng"]), str(ss["etiqueta"])


@st.cache_data(show_spinner=False)
def _alcaldias() -> pd.DataFrame:
    """Las 16 alcaldías con su centro aproximado. Respaldo sin HERE."""
    import json

    try:
        crudo = json.loads(Path(_cfg().ruta("municipios")).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return pd.DataFrame(columns=["alcaldia", "lat", "lng"])
    filas = []
    for f in crudo.get("features", []):
        pr = f.get("properties", {})
        if int(pr.get("state_code", 0) or 0) != 9:
            continue
        g = f.get("geometry", {})
        anillos = (g.get("coordinates", []) if g.get("type") == "Polygon"
                   else [r for poly in g.get("coordinates", []) for r in poly])
        if not anillos:
            continue
        c = np.asarray(anillos[0], dtype=float)
        filas.append({"alcaldia": str(pr.get("mun_name", "?")),
                      "lat": float(c[:, 1].mean()), "lng": float(c[:, 0].mean())})
    return pd.DataFrame(filas).sort_values("alcaldia").reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────── mapa
def _mapa(lat: float, lng: float) -> None:
    """
    El punto sobre la ciudad. Sólo si hay teselas que poner debajo.

    SIN TESELAS NO SE DIBUJA NADA. Un recuadro negro de 260 px con un punto
    flotando en medio no informa de dónde está el inmueble —que es lo único
    que el mapa tiene que hacer— y parece que la app está rota. Es mejor
    decir que falta la llave que enseñar un mapa que no es un mapa.
    """
    import pydeck as pdk

    url = here.url_de_teselas()
    if not url:
        nota("El mapa necesita la llave de HERE (<code>HERE_API_KEY</code>). "
             "Sin ella no se dibuja, para no enseñar un recuadro vacío: "
             "<b>la valuación y el punto son correctos igual</b>.")
        return

    st.pydeck_chart(pdk.Deck(
        map_style=None,
        initial_view_state=pdk.ViewState(latitude=lat, longitude=lng,
                                         zoom=15, pitch=0),
        layers=[
            pdk.Layer("TileLayer", data=url, min_zoom=0, max_zoom=19,
                      tile_size=512, opacity=1.0),
            pdk.Layer(
                "ScatterplotLayer",
                data=pd.DataFrame([{"lat": lat, "lng": lng}]),
                get_position=["lng", "lat"],
                get_radius=9, radius_min_pixels=7, radius_max_pixels=14,
                get_fill_color=[245, 194, 119, 240],
                get_line_color=[16, 12, 10, 255], line_width_min_pixels=2,
                stroked=True, pickable=False,
            ),
        ],
    ), height=250)


# ───────────────────────────────────────────────────────── el vecindario
def _vecindario(p, lat: float, lng: float, precio_m2: float | None = None) -> None:
    """
    A qué precio se ofrece lo de alrededor. Agregado, nunca pieza por pieza.

    Es el dato que más confianza da y el más fácil de convertir en una fuga: el
    inventario viene de un convenio con Century 21, así que se publica la
    MEDIANA de un puñado de vecinos y su conteo, nunca un anuncio con su
    dirección y su precio.
    """
    if p.fuentes_xy is None or p.fuentes_y is None or not len(p.fuentes_y):
        return
    from atlas.geo import _xy, puntos

    cfg = _cfg()
    try:
        xy = _xy(puntos(pd.DataFrame([{"lat": lat, "lng": lng}]), cfg=cfg), cfg)
    except Exception:                        # noqa: BLE001 — el vecindario es un extra
        return
    d = np.hypot(p.fuentes_xy[:, 0] - xy[0, 0], p.fuentes_xy[:, 1] - xy[0, 1])

    filas = []
    for radio in (1000.0, 3000.0):
        sel = d <= radio
        n = int(sel.sum())
        if n < 5:                            # con menos de cinco, la mediana no dice nada
            filas.append((radio, n, None))
            continue
        filas.append((radio, n, float(np.exp(np.median(p.fuentes_y[sel])))))

    st.markdown("### A qué precio se ofrece lo de alrededor")
    cols = st.columns(len(filas))
    for c, (radio, n, med) in zip(cols, filas):
        etiqueta = f"En {radio / 1000:.0f} km"
        if med is None:
            c.metric(etiqueta, "—", help="Menos de 5 inmuebles: la mediana no dice nada.")
        else:
            c.metric(etiqueta, f"${med:,.0f}/m²", f"{n} inmuebles")
    nota("Medianas del inventario con el que se entrenó, no anuncios "
         "individuales. Es lo que un perito mira primero, y explica buena parte "
         "de la cifra de arriba.")

    # CÓMO QUEDA CONTRA SU ZONA. Es la pregunta que la gente trae de verdad
    # —"¿me están pidiendo caro?"— y sale de comparar dos números que ya
    # tenemos. Se usa el radio más amplio que tenga suficientes vecinos: con
    # cuatro comparables la mediana es una anécdota.
    referencia = next((m for _, n, m in filas if m is not None and n >= 15), None)
    if referencia is None or precio_m2 is None or not np.isfinite(precio_m2):
        return
    brecha = (precio_m2 / referencia - 1) * 100
    if abs(brecha) < 8:
        veredicto = "prácticamente en línea con su zona"
    elif brecha > 0:
        veredicto = f"<b>{abs(brecha):.0f}% por encima</b> de la mediana de su zona"
    else:
        veredicto = f"<b>{abs(brecha):.0f}% por debajo</b> de la mediana de su zona"
    st.markdown(
        f"<div class='tarjeta' style='margin-top:.6rem'>"
        f"<div class='etq'>Cómo queda contra su zona</div>"
        f"<p class='nota' style='font-size:.95rem;color:{CREMA}'>"
        f"A ${precio_m2:,.0f}/m², este inmueble está {veredicto}.</p>"
        f"<p class='nota'>La diferencia no es buena ni mala por sí sola: un "
        f"inmueble más nuevo, más grande o mejor ubicado dentro de la misma "
        f"zona <b>debe</b> salirse de la mediana. Sirve como punto de partida "
        f"para preguntar por qué, no como veredicto.</p></div>",
        unsafe_allow_html=True)


# ────────────────────────────────────────────────────────────── principal
def principal() -> None:
    p, feats = _paquete(), _feats()
    if p is None or feats is None:
        st.error("El motor de valuación no está disponible en este momento.")
        nota("Si eres de BrickBit: falta correr <code>python -m pipelines.fase2</code>.")
        return

    cfg = _cfg()
    izq, der = st.columns([1, 1.15], gap="large")

    with izq:
        st.markdown("### Dónde está")
        lat, lng, etiqueta = _ubicacion(cfg)
        _mapa(lat, lng)

        st.markdown("### Cómo es")
        tipos = sorted({c.replace("tipo_", "") for c in p.columnas
                        if c.startswith("tipo_")} | {p.tipo_referencia or "otro"})
        nombres = {"depto": "Departamento", "casa": "Casa",
                   "terreno": "Terreno", "otro": "Otro"}
        c1, c2 = st.columns([1, 1])
        tipo = c1.selectbox("Tipo", tipos, format_func=lambda t: nombres.get(t, t.title()),
                            index=tipos.index("depto") if "depto" in tipos else 0)
        sup = c2.number_input("Superficie (m²)", 20, 2000, 90, step=5)
        c3, c4, c5 = st.columns(3)
        rec = c3.number_input("Recámaras", 0, 10, 2)
        ban = c4.number_input("Baños", 0, 10, 2)
        est = c5.number_input("Estacionamientos", 0, 6, 1)
        ant = st.slider("Antigüedad (años)", 0, 70, 10)

    X = persistencia.fila_de_inmueble(
        lat, lng,
        {"tipo": tipo, "superficie_construida_m2": sup, "recamaras": rec,
         "banos": ban, "estacionamientos": est, "antiguedad_anios": ant},
        feats, p.columnas, p.tipo_referencia, cfg,
        fuentes=(p.fuentes_xy, p.fuentes_y) if p.fuentes_xy is not None else None)
    # El 80% es el nivel de producto y está fijado, no ofrecido: elegir el nivel
    # de confianza es una decisión de estadístico, no de quien compra una casa.
    # El 95% se guarda para la consola, donde alguien sabe qué está pidiendo.
    v = persistencia.valuar(p, X, sup, alpha=0.20)

    with der:
        pos = (v.precio_total - v.lo_total) / max(v.hi_total - v.lo_total, 1e-9)
        s_lo, s_hi = _par(v.lo_total, v.hi_total)
        st.markdown(
            f"<div class='tarjeta'>"
            f"<div class='etq'>Se ofrecería en torno a</div>"
            f"<div class='cifra'>{_dinero(v.precio_total)}</div>"
            f"<div class='nota' style='margin-top:.15rem'>"
            f"${v.precio_m2:,.0f} por m² · {etiqueta}</div>"
            f"<div class='riel'><div class='pin' style='left:{pos * 100:.1f}%'></div></div>"
            f"<div class='extremos'><span class='banda'>{s_lo}</span>"
            f"<span class='etq'>en algún lugar de aquí</span>"
            f"<span class='banda'>{s_hi}</span></div>"
            f"<div class='nota'>4 de cada 5 inmuebles así se ofrecen dentro de "
            f"esa banda. Es ancha porque el mercado de la CDMX lo es: dos "
            f"departamentos idénticos en la misma cuadra se anuncian con "
            f"diferencias de esta magnitud.</div>"
            f"</div>", unsafe_allow_html=True)

        _aviso_de_segmento(p, v)
        _vecindario(p, lat, lng, v.precio_m2)

    st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
    _letra_chica(p)


def _aviso_de_segmento(p, v) -> None:
    """
    Si el segmento de ESTE inmueble cubre menos de lo prometido, decirlo.

    La cobertura global tapa a los segmentos que fallan: medido, el conjunto
    entero cubrió 95.5% y `depto·medio` cubrió 86.5%. Quien valúa un
    departamento de precio medio merece el 86.5%, que es su número, y no el
    promedio de todos. Se dice en castellano, sin nombrar a Mondrian.
    """
    m = p.metricas or {}
    por_seg = m.get("cobertura_por_segmento") or {}
    d = por_seg.get(str(v.segmento))
    if not d:
        return
    cob = float(d.get("cobertura", float("nan"))) * 100
    objetivo = float(m.get("objetivo_95", 0.95)) * 100
    if not np.isfinite(cob) or cob >= objetivo - 2:
        return
    st.markdown(
        f"<div class='aviso'><p><b>Para inmuebles como éste, la banda es "
        f"optimista.</b> Al comprobarlo sobre barrios que el modelo nunca "
        f"había visto, este tipo de propiedad se salió de su banda más seguido "
        f"de lo previsto. Tómala como un punto de partida para negociar, no "
        f"como un techo ni un piso.</p></div>", unsafe_allow_html=True)


def _letra_chica(p) -> None:
    dias = p.antiguedad_dias()
    fresco = (f"Inventario de {p.fecha_datos[:10]}"
              + (f" — hace {dias} días" if dias >= 0 else ""))
    st.markdown(
        f"<div class='tarjeta'>"
        f"<div class='etq'>Lo que esta cifra es, y lo que no</div>"
        f"<p class='nota'>Es el precio al que un inmueble así se "
        f"<b>ofrecería</b>, no aquel al que se vende. En México no hay MLS "
        f"abierto ni Registro Público accesible, así que el precio de cierre no "
        f"es observable; preferimos decirlo a aplicarle un descuento inventado. "
        f"<b>No es un avalúo con validez legal</b> salvo que lo suscriba un "
        f"perito valuador.<br><br>"
        f"Se calcula con {p.n_entrenamiento:,} inmuebles de la Ciudad de "
        f"México y se comprueba en barrios que el modelo nunca vio. "
        f"{fresco}.</p></div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════ main
st.markdown("# 🧭 ¿Cuánto vale?")
st.markdown(
    f"<p class='nota' style='margin-top:-.35rem;margin-bottom:1.1rem'>"
    f"Valuación de inmuebles en la Ciudad de México · "
    f"<span style='color:{AMBAR}'>la cifra en ámbar es una estimación, "
    f"siempre con su rango</span></p>", unsafe_allow_html=True)

principal()
