"""
BrickBit Atlas — CONSOLA DE DIAGNÓSTICO (interna, no es el producto).

    cd atlas
    streamlit run consola.py

ESTA NO ES LA APP PÚBLICA. La app pública es `app.py`, y sirve para valuar un
inmueble. Esto de aquí sirve para AUDITAR EL MODELO: cobertura por segmento,
σ̂, I de Moran, SDM, SHAP, correcciones de Mondrian, el campo espacial y el
índice temporal. A un cliente no le importa qué es un segmento de Mondrian;
a quien mantiene el motor, le importa todo.

Se separó porque se estaba pidiendo a un banco de pruebas que fuera un
producto, y esa confusión era la causa de que la pantalla se sintiera inútil:
cada decisión de diseño aquí es para verificar que el modelo no mienta, no para
que alguien decida si compra un departamento. Las dos cosas son legítimas y
necesitan pantallas distintas.

Hace visible lo que las fases 0 a 3 dejaron en parquet. Tres pestañas, tres
preguntas: cuánto vale este inmueble, cómo está el precio en la ciudad, y cómo
se ha movido el mercado en veintiún años.

UNA REGLA QUE ATRAVIESA TODO: ningún número aparece sin su incertidumbre y sin
su procedencia. El valor puntual va siempre con su intervalo; el mapa lleva su
capa de "cuánto no sé"; y en todas partes se recuerda que son precios de OFERTA.
Un número solo, grande y sin contexto, miente por omisión.

SOBRE EL DISEÑO, Y QUÉ SE ARREGLÓ EN CADA PASADA.

La primera versión tenía texto gris oscuro sobre fondo casi negro, `st.markdown`
crudo peleando con los componentes nativos, y ninguna jerarquía. Se subió el
contraste, se fijó una escala tipográfica de tres niveles y cada bloque pasó a
vivir en una tarjeta.

No alcanzó, y el motivo no era estético: **faltaba el tema de Streamlit**. La
raíz del repo tiene `.streamlit/config.toml`, pero el Atlas se corre desde
`atlas/` y Streamlit busca esa configuración relativa al directorio de trabajo.
Así que la app pintaba su fondo oscuro con CSS mientras los widgets nativos
—selectbox, slider, number input, st.metric, ejes de las gráficas, celdas del
dataframe— usaban los colores del tema CLARO. Ninguna cantidad de CSS lo
arreglaba, porque el CSS no gobierna los canvas de Vega ni los temas internos de
los widgets. Está en `atlas/.streamlit/config.toml`, con su explicación.

Y se arregló algo que no era diseño sino honestidad: la app enseñaba
"cobertura 95%" —la global— a quien valuaba un inmueble de un segmento que
cubrió 86.5% medido. El promedio tapaba justo al grupo que falla. Ahora la
cobertura del SEGMENTO viaja con el modelo y se muestra cuando difiere.
"""
from __future__ import annotations

import json
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
# El ámbar está reservado: marca lo estimado. No se usa de adorno, y por eso
# tampoco es el `primaryColor` del tema (ver .streamlit/config.toml).
TIERRA = "#100c0a"      # fondo
SUP = "#1d1713"         # superficie de tarjeta
SUP2 = "#272019"        # borde
CREMA = "#f5ede3"       # texto principal
TENUE = "#a89c90"       # texto secundario — sube de #9c9188 para llegar a 4.5:1
BOSQUE = "#24664a"
SALVIA = "#6fa287"
OLIVA = "#b7c489"
AMBAR = "#F5C277"
TERRACOTA = "#c07a66"
ESCALA = [[191, 91, 82], [207, 146, 71], [224, 187, 131], [183, 196, 137], [36, 102, 74]]

st.set_page_config(page_title="Atlas · consola", page_icon="🔬", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown(f"""<style>
  .stApp {{ background:{TIERRA}; }}
  .block-container {{ padding-top:2rem; max-width:1280px; }}

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
  .aviso {{ border-left:3px solid {AMBAR}; background:{AMBAR}14;
            padding:.7rem .95rem; border-radius:0 8px 8px 0; margin:.8rem 0 0 0; }}
  .aviso p {{ margin:0; color:{CREMA}; font-size:.86rem; line-height:1.5; }}

  /* La cifra grande y su banda. */
  .cifra {{ font-size:2.9rem; font-weight:700; color:{AMBAR};
            line-height:1.05; letter-spacing:-.03em; }}
  .banda {{ font-size:1.25rem; font-weight:600; color:{CREMA}; }}
  .etq {{ font-size:.78rem; color:{TENUE}; text-transform:uppercase;
          letter-spacing:.09em; }}

  /* Barra del intervalo. Deliberadamente PLANA y de un solo color: un
     degradado con el centro más intenso sugeriría que el valor es más probable
     en medio, y un intervalo conforme no afirma nada de eso. Dice "en algún
     lugar de aquí", y se ve como lo que dice. */
  .riel {{ position:relative; height:10px; border-radius:6px;
           margin:1.1rem 0 .45rem 0; background:{SALVIA}3d;
           border:1px solid {SALVIA}55; }}
  .pin {{ position:absolute; top:-5px; width:3px; height:20px;
          border-radius:2px; background:{AMBAR}; }}
  .extremos {{ display:flex; justify-content:space-between; align-items:baseline; }}

  /* Componentes nativos de Streamlit, alineados con la paleta. */
  [data-testid="stMetric"] {{ background:{SUP}; border:1px solid {SUP2};
      border-radius:12px; padding:.85rem 1rem; }}
  [data-testid="stMetricValue"] {{ color:{CREMA}; font-size:1.45rem; }}
  [data-testid="stMetricLabel"] {{ color:{TENUE}; }}
  .stTabs [data-baseweb="tab-list"] {{ gap:.35rem; border-bottom:1px solid {SUP2}; }}
  .stTabs [data-baseweb="tab"] {{ background:transparent; color:{TENUE};
      padding:.55rem 1.1rem; font-weight:500; }}
  /* El subrayado de la pestaña activa va en oliva, no en ámbar: el ámbar
     significa "estimado" y gastarlo en un adorno de navegación lo devalúa. */
  .stTabs [aria-selected="true"] {{ color:{CREMA} !important;
      border-bottom:2px solid {OLIVA}; }}
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


@st.cache_data(show_spinner=False)
def _alcaldias() -> pd.DataFrame:
    """
    Las 16 alcaldías con un punto aproximado, para orientar y para elegir.

    Sale de `data/mexico_municipios.json`, que ya está en el repo. Los
    polígonos vienen muy simplificados —entre 5 y 20 vértices— así que NO se
    dibujan como mapa base: quedarían heptágonos y parecería un mapa falso. Se
    usa sólo el centro del anillo exterior, y se declara como aproximado donde
    se muestra.
    """
    ruta = _cfg().ruta("municipios")
    try:
        crudo = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
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


def _falta(que: str, comando: str) -> None:
    st.warning(f"Falta **{que}**.")
    st.code(comando, language="bash")


def _dinero(x: float) -> str:
    """Millones cuando los hay: '$4.2 M' se lee de un vistazo, '$4,183,920' no."""
    return f"${x / 1e6:.2f} M" if abs(x) >= 1e6 else f"${x:,.0f}"


def _par(lo: float, hi: float) -> tuple[str, str]:
    """
    Los dos extremos de un intervalo, en la MISMA unidad.

    Con `_dinero` suelto salía «$648,276» junto a «$1.32 M», y el ojo tiene que
    convertir para comparar los dos números que existen precisamente para ser
    comparados. Si alguno llega a millones, los dos van en millones.
    """
    if max(abs(lo), abs(hi)) >= 1e6:
        return f"${lo / 1e6:.2f} M", f"${hi / 1e6:.2f} M"
    return f"${lo:,.0f}", f"${hi:,.0f}"


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
        st.markdown("### Dónde está")
        # Antes había que escribir 19.4326 a mano, que no es algo que nadie
        # sepa de memoria. Se elige la alcaldía y las coordenadas quedan
        # disponibles para afinarlas si hace falta.
        alc = _alcaldias()
        lat, lng = 19.4326, -99.1650
        if not alc.empty:
            nombres = alc["alcaldia"].tolist()
            i = nombres.index("Cuauhtémoc") if "Cuauhtémoc" in nombres else 0
            elegida = st.selectbox("Alcaldía", nombres, index=i)
            fila = alc.loc[alc["alcaldia"] == elegida].iloc[0]
            lat, lng = float(fila["lat"]), float(fila["lng"])

        with st.expander("Ajustar el punto exacto"):
            nota("El centro de la alcaldía es <b>aproximado</b>. Dentro de una "
                 "misma alcaldía el precio cambia mucho —la pendiente mediana "
                 "es de 8%/km— así que para una valuación seria conviene el "
                 "punto real.")
            c1, c2 = st.columns(2)
            lat = c1.number_input("Latitud", 19.00, 19.65, lat, format="%.5f")
            lng = c2.number_input("Longitud", -99.37, -98.93, lng, format="%.5f")

        st.markdown("### El inmueble")
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
        # leer dos cifras sueltas. La mediana NO está en el centro porque el
        # intervalo es multiplicativo, y eso es información, no un error.
        pos = (v.precio_total - v.lo_total) / max(v.hi_total - v.lo_total, 1e-9)
        s_lo, s_hi = _par(v.lo_total, v.hi_total)
        tarjeta(
            f"<div class='etq'>Estimación · mediana</div>"
            f"<div class='cifra'>{_dinero(v.precio_total)}</div>"
            f"<div class='nota' style='margin-top:.1rem'>"
            f"${v.precio_m2:,.0f} por m² · segmento «{v.segmento}»</div>"
            f"<div class='riel'><div class='pin' style='left:{pos * 100:.1f}%'></div></div>"
            f"<div class='extremos'>"
            f"<span class='banda'>{s_lo}</span>"
            f"<span class='etq'>en algún lugar de aquí</span>"
            f"<span class='banda'>{s_hi}</span></div>"
            f"<div class='nota'>Intervalo al {(1 - v.alpha) * 100:.0f}% "
            f"— ancho ±{v.ancho_pct:.0f}%. La banda es plana a propósito: la "
            f"garantía dice que el valor cae dentro, <b>no</b> que sea más "
            f"probable en el centro.</div>")

        m = p.metricas
        a, b, c = st.columns(3)
        a.metric("Error mediano", f"{m.get('mdape_pct', float('nan')):.0f}%")
        b.metric("Cobertura global", f"{m.get('cobertura_95', 0) * 100:.0f}%")
        c.metric("Entrenado con", f"{p.n_entrenamiento:,}")
        nota(f"Medido sobre barrios que el modelo <b>nunca vio</b>. "
             f"Inventario de {p.fecha_datos[:10]}.")

        _aviso_de_segmento(p, v)
        _precio_de_la_certeza(p, X, sup, v)

    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
    tarjeta(
        "<div class='etq'>Qué es y qué no es este número</div>"
        "<p class='nota'>Es el precio al que se <b>ofrecería</b> un inmueble así, "
        "no aquel al que se vende. En México no hay MLS abierto ni Registro "
        "Público accesible, así que el precio de cierre no es observable y no se "
        "le aplica ningún descuento inventado. <b>No es un avalúo con validez "
        "legal</b> salvo que lo suscriba un perito valuador.</p>")


def _aviso_de_segmento(p, v) -> None:
    """
    Si el segmento de ESTE inmueble cubrió menos de lo prometido, decirlo.

    La cobertura global tapa a los segmentos que fallan: en la última corrida el
    conjunto entero cubrió 95.5% y `depto·medio` cubrió 86.5%. Alguien valuando
    un departamento de precio medio veía el 95.5% y no el 86.5%, que es el
    número que le toca. Un promedio no es una garantía para cada grupo.
    """
    por_seg = (p.metricas or {}).get("cobertura_por_segmento") or {}
    if not por_seg:
        # Paquete de antes de que esto se guardara: se dice, no se finge.
        nota("La cobertura por segmento no viaja en este paquete. Para verla, "
             "vuelve a correr <b>python -m pipelines.fase2</b>.")
        return

    d = por_seg.get(str(v.segmento))
    if not d:
        return
    cob = float(d.get("cobertura", float("nan"))) * 100
    n = int(d.get("n", 0))
    objetivo = float((p.metricas or {}).get("objetivo_95", 0.95)) * 100

    if not np.isfinite(cob):
        return
    if cob < objetivo - 2:
        st.markdown(
            f"<div class='aviso'><p><b>Este segmento cubre menos de lo que "
            f"promete.</b> En «{v.segmento}» el intervalo del "
            f"{objetivo:.0f}% cubrió <b>{cob:.1f}%</b> sobre {n} inmuebles de "
            f"prueba. La banda de arriba es más angosta de lo que este grupo "
            f"justifica — trátala como optimista, no como garantía.</p></div>",
            unsafe_allow_html=True)
    else:
        nota(f"En «{v.segmento}» la cobertura medida fue "
             f"<b>{cob:.1f}%</b> sobre {n} inmuebles de prueba.")


def _precio_de_la_certeza(p, X: pd.DataFrame, sup: float, actual) -> None:
    """
    Qué cuesta cada nivel de confianza EN ESTE inmueble, no en el promedio.

    El informe de la Fase 2 trae esta tabla para la ciudad entera, y ahí sirve
    para juzgar el método. A quien está valuando le sirve otra cosa: ver que
    pedir 95% en vez de 80% le duplica la banda de SU propiedad. Sale gratis —
    el paquete ya guarda la corrección conforme de los cuatro niveles y cambiar
    de nivel con el score normalizado no reentrena nada—.
    """
    niveles = sorted(p.alphas, reverse=True)      # alpha grande = confianza baja
    if len(niveles) < 2:
        return
    filas = []
    for a in niveles:
        try:
            w = persistencia.valuar(p, X, sup, alpha=a)
        except Exception:                          # noqa: BLE001 — un nivel roto no tumba la vista
            continue
        lo, hi = _par(w.lo_total, w.hi_total)
        filas.append({"Confianza": f"{(1 - w.alpha) * 100:.0f}%",
                      "Desde": lo, "Hasta": hi, "Ancho": f"±{w.ancho_pct:.0f}%"})
    if len(filas) < 2:
        return
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    st.markdown("### Qué cuesta cada nivel, en este inmueble")
    st.dataframe(pd.DataFrame(filas), width="stretch", hide_index=True)
    nota("Subir la confianza no mejora la estimación: <b>ensancha la banda</b>. "
         "La cifra de arriba no se mueve en ninguna fila — lo único que cambia "
         "es cuánto se admite no saber.")


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
    d["precio_m2"] = np.exp(d["ln_precio_m2"]).round(0).astype(int)
    d["incert_pct"] = (d["sigma_nivel"] * 100).round(0).astype(int)
    d["pend"] = d["pendiente_pct_km"].round(1)

    capas = [pdk.Layer(
        "ColumnLayer", data=d, get_position=["lng", "lat"],
        get_elevation="alto", elevation_scale=900, radius=105,
        get_fill_color=["r", "g", "b", 205], pickable=True, auto_highlight=True,
    )]
    # ORIENTACIÓN. Sin mapa base —las teselas de CARTO ya piden cuenta— un
    # bosque de columnas no dice en qué parte de la ciudad estás. Los nombres de
    # las alcaldías bastan para ubicarse y no fingen una geometría que no
    # tenemos: los polígonos del repo traen 7 vértices y dibujarlos daría un
    # mapa falso de aspecto convincente.
    alc = _alcaldias()
    if not alc.empty:
        capas.append(pdk.Layer(
            "TextLayer", data=alc, get_position=["lng", "lat"],
            get_text="alcaldia", get_size=11, get_color=[245, 237, 227, 165],
            get_alignment_baseline="'bottom'", pickable=False,
        ))

    st.pydeck_chart(pdk.Deck(
        map_style=None,
        initial_view_state=pdk.ViewState(latitude=19.395, longitude=-99.14,
                                         zoom=9.7, pitch=42, bearing=12),
        layers=capas,
        tooltip={"html": "<b>${precio_m2}</b> por m²<br/>"
                         "incertidumbre ±{incert_pct}%<br/>"
                         "pendiente {pend} %/km",
                 "style": {"backgroundColor": SUP, "color": CREMA,
                           "fontSize": "12px", "borderRadius": "8px"}},
    ), height=520)

    nota(explicacion + " <span style='opacity:.8'>Los nombres marcan el centro "
         "<b>aproximado</b> de cada alcaldía, sólo para orientar.</span>")

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
        st.dataframe(tabla, width="stretch", hide_index=True,
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
    st.markdown("# 🔬 Atlas · consola")
    st.markdown(
        f"<p class='nota' style='margin-top:-.5rem'>Diagnóstico del modelo · "
        f"<b>uso interno</b>. La app pública es <code>app.py</code> · "
        f"<span style='color:{AMBAR}'>precios de oferta, no de cierre</span></p>",
        unsafe_allow_html=True)
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
