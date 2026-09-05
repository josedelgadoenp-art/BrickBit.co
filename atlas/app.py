"""
BrickBit Atlas — la app.

    cd atlas
    streamlit run app.py

Es la Fase 4: hacer visible lo que las fases 0 a 3 dejaron en parquet. Tres
pestañas, cada una contestando una pregunta distinta:

  · **Valuar** — cuánto vale este inmueble, con su banda y de dónde sale.
  · **Mapa**   — cómo está el precio en la ciudad, y dónde el modelo no sabe.
  · **Ciudad** — cómo se ha movido el mercado en veintiún años.

UNA REGLA QUE ATRAVIESA TODA LA APP: ningún número aparece sin su incertidumbre
y sin su procedencia. El valor puntual va siempre acompañado de su intervalo; el
mapa lleva su capa de "cuánto no sé"; y en todas partes se recuerda que son
precios de OFERTA, no de cierre. Es el principio de honestidad de BrickBit
llevado a la interfaz: un número solo, grande y sin contexto, miente por omisión.

No se despliega en Netlify —el sitio de brickbit.co es estático— sino donde ya
vive el Motor de Morfogénesis. Son dos apps distintas a propósito.
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

# Paleta v2 de BrickBit. El ámbar está reservado: marca lo estimado.
TIERRA, CREMA, BOSQUE = "#100c0a", "#f5ede3", "#24664a"
SALVIA, TERRACOTA, AMBAR = "#6fa287", "#c07a66", "#F5C277"
ESCALA = [[191, 91, 82], [207, 146, 71], [224, 187, 131], [183, 196, 137], [36, 102, 74]]

st.set_page_config(page_title="BrickBit Atlas", page_icon="🧭", layout="wide")
st.markdown(f"""<style>
  .stApp {{ background:{TIERRA}; color:{CREMA}; }}
  [data-testid="stMetricValue"] {{ color:{CREMA}; }}
  .est {{ color:{AMBAR}; font-weight:600; }}
  .nota {{ color:#9c9188; font-size:.85rem; line-height:1.45; }}
</style>""", unsafe_allow_html=True)


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
    st.warning(f"Falta **{que}**. Córrelo y recarga:")
    st.code(comando, language="bash")


# ═══════════════════════════════════════════════════════════════════ valuar
def pestana_valuar() -> None:
    p = _paquete()
    feats = _capa("features_malla")
    if p is None:
        _falta("el AVM entrenado", "cd atlas\npython -m pipelines.fase2")
        return
    if feats is None:
        _falta("la malla de variables", "python -m pipelines.fase1")
        return

    dias = p.antiguedad_dias()
    if dias > 90:
        st.warning(
            f"El modelo se entrenó con inventario de hace **{dias} días**. "
            "Un AVM viejo sigue dando números convincentes mucho después de "
            "dejar de ser cierto: vuelve a correr `tools\\actualizar-atlas.bat`."
        )

    izq, der = st.columns([1, 1.3])
    with izq:
        st.subheader("El inmueble")
        c1, c2 = st.columns(2)
        lat = c1.number_input("Latitud", 19.00, 19.65, 19.4326, format="%.5f")
        lng = c2.number_input("Longitud", -99.37, -98.93, -99.1650, format="%.5f")

        tipos = sorted({c.replace("tipo_", "") for c in p.columnas if c.startswith("tipo_")}
                       | {p.tipo_referencia or "otro"})
        tipo = st.selectbox("Tipo", tipos, index=tipos.index("depto") if "depto" in tipos else 0)
        sup = st.number_input("Superficie construida (m²)", 20, 2000, 90)

        c3, c4, c5 = st.columns(3)
        rec = c3.number_input("Recámaras", 0, 10, 2)
        ban = c4.number_input("Baños", 0, 10, 2)
        est = c5.number_input("Estacion.", 0, 6, 1)
        ant = st.slider("Antigüedad (años)", 0, 70, 10)

        nivel = st.select_slider(
            "Nivel de confianza del intervalo",
            options=[0.50, 0.80, 0.90, 0.95], value=0.80,
            format_func=lambda v: f"{v * 100:.0f}%",
        )
        st.markdown(
            "<p class='nota'>El 80% es el número con el que se puede conversar. "
            "El 95% es tan ancho que dice poco más que «no sé», y eso no es "
            "defecto del método: es el error del modelo, que hoy ronda el 27%.</p>",
            unsafe_allow_html=True)

    X = persistencia.fila_de_inmueble(
        lat, lng,
        {"tipo": tipo, "superficie_construida_m2": sup, "recamaras": rec,
         "banos": ban, "estacionamientos": est, "antiguedad_anios": ant},
        feats, p.columnas, p.tipo_referencia, _cfg())
    v = persistencia.valuar(p, X, sup, alpha=round(1 - nivel, 2))

    with der:
        st.subheader("Estimación")
        st.markdown(
            f"<div style='font-size:2.6rem;color:{AMBAR};font-weight:700;line-height:1'>"
            f"${v.precio_total:,.0f}</div>"
            f"<div class='nota'>${v.precio_m2:,.0f} por m² · mediana, no media</div>",
            unsafe_allow_html=True)
        st.markdown(
            f"<div style='margin-top:1rem;font-size:1.25rem'>"
            f"entre <b>${v.lo_total:,.0f}</b> y <b>${v.hi_total:,.0f}</b></div>"
            f"<div class='nota'>intervalo al {(1 - v.alpha) * 100:.0f}% "
            f"(±{v.ancho_pct:.0f}%) · segmento «{v.segmento}»</div>",
            unsafe_allow_html=True)

        st.divider()
        m = p.metricas
        a, b, c = st.columns(3)
        a.metric("Error mediano", f"{m.get('mdape_pct', float('nan')):.0f}%")
        b.metric("Cobertura al 95%", f"{m.get('cobertura_95', 0) * 100:.1f}%")
        c.metric("Entrenado con", f"{p.n_entrenamiento:,}")
        st.markdown(
            f"<p class='nota'>Cobertura medida sobre barrios que el modelo "
            f"NUNCA vio. Datos de {p.fecha_datos[:10]}.</p>", unsafe_allow_html=True)

    st.divider()
    st.markdown(
        "<p class='nota'><b>Qué es y qué no es este número.</b> Es el precio al que "
        "se OFRECERÍA un inmueble así, no aquel al que se vende: en México no hay "
        "MLS abierto ni Registro Público accesible, así que el precio de cierre no "
        "es observable y no se le aplica ningún descuento inventado. "
        "<b>No es un avalúo con validez legal</b> salvo que lo suscriba un perito "
        "valuador.</p>", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════ mapa
def pestana_mapa() -> None:
    campo = _capa("campo_cdmx")
    if campo is None:
        _falta("el campo espacial", "cd atlas\npython -m pipelines.fase3")
        return
    import pydeck as pdk

    capa = st.radio(
        "Qué pintar", ["Precio por m²", "Cuánto NO sé", "Pendiente del precio"],
        horizontal=True)
    col = {"Precio por m²": "ln_precio_m2", "Cuánto NO sé": "sigma_nivel",
           "Pendiente del precio": "pendiente_pct_km"}[capa]

    d = campo.copy()
    v = d[col].to_numpy(dtype=float)
    lo, hi = np.nanpercentile(v, [5, 95])
    t = np.clip((v - lo) / max(hi - lo, 1e-9), 0, 1)
    if col == "sigma_nivel":                 # más incertidumbre = más rojo
        t = 1 - t
    idx = (t * (len(ESCALA) - 1)).astype(int)
    d[["r", "g", "b"]] = np.array(ESCALA)[idx]

    st.pydeck_chart(pdk.Deck(
        map_style=None,
        initial_view_state=pdk.ViewState(latitude=19.40, longitude=-99.15,
                                         zoom=9.6, pitch=35),
        layers=[pdk.Layer(
            "ColumnLayer", data=d, get_position=["lng", "lat"],
            get_elevation=("pendiente_pct_km" if col != "ln_precio_m2" else "ln_precio_m2"),
            elevation_scale=(30 if col != "ln_precio_m2" else 60),
            radius=90, get_fill_color=["r", "g", "b", 190], pickable=True,
        )],
        tooltip={"text": "${ln_precio_m2} ln($/m²)\n±{sigma_nivel}\n{pendiente_pct_km} %/km"},
    ))

    a, b, c = st.columns(3)
    a.metric("Celdas", f"{len(d):,}")
    b.metric("Pendiente mediana", f"{d['pendiente_pct_km'].median():.1f} %/km")
    c.metric("Incertidumbre del nivel", f"±{d['sigma_nivel'].median() * 100:.0f}%")

    st.markdown(
        "<p class='nota'><b>«Cuánto NO sé» no es un hueco: es una respuesta.</b> "
        "Donde no hay comparables la incertidumbre se dispara, y verla evita "
        "confiar en una cifra que el modelo no puede sostener. Ojo con no "
        "confundirla con la dispersión ENTRE anuncios de una misma zona, que es "
        "mayor y no baja por poner más modelo: dos departamentos de la misma "
        "cuadra se anuncian a precios distintos.</p>", unsafe_allow_html=True)

    fr = _capa("frontera_cdmx")
    if fr is not None and "es_frontera" in fr.columns:
        n = int(fr["es_frontera"].sum())
        st.divider()
        st.subheader(f"Frente de precio · {n} inmuebles")
        st.markdown(
            "<p class='nota'>Baratos rodeados de caros. Es un diferencial "
            "<b>presente</b>, no una plusvalía futura: que el mercado lo cierre "
            "depende de POR QUÉ está abierto, y esa razón puede ser una barrera "
            "física, un uso de suelo o una diferencia real de calidad que ninguna "
            "de estas variables ve.</p>", unsafe_allow_html=True)
        if n:
            st.dataframe(
                fr.loc[fr["es_frontera"], ["lat", "lng", "brecha_vecinos"]]
                .assign(**{"por_debajo_%": lambda x: (np.exp(x["brecha_vecinos"]) - 1) * 100})
                .drop(columns="brecha_vecinos")
                .sort_values("por_debajo_%", ascending=False).head(25),
                use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════ ciudad
def pestana_ciudad() -> None:
    from atlas.temporal import indice

    panel = indice.cargar_panel(_cfg())
    zona = st.selectbox("Zona", list(panel.nivel.columns),
                        index=list(panel.nivel.columns).index("Ciudad de México"))
    r = indice.resumen_zona(panel, zona).dropna()
    a0, a1 = panel.anios[0], panel.anios[-1]
    acum = indice.acumulado(panel, zona, a0, a1)

    a, b, c = st.columns(3)
    a.metric(f"Acumulado {a0}–{a1}", f"×{acum:.2f}")
    b.metric("Anual compuesto", f"{(acum ** (1 / (a1 - a0)) - 1) * 100:.2f}%")
    c.metric("Último año", f"{r['crec_%'].iloc[-1]:+.2f}%")

    st.line_chart(r[["indice"]], height=280, color=BOSQUE)
    st.bar_chart(r[["crec_%"]], height=200, color=SALVIA)

    st.markdown(
        "<p class='nota'><b>Es NOMINAL.</b> No está deflactado, así que una parte "
        "de ese crecimiento es inflación y no plusvalía. Decir «subió 7.9% al año» "
        "y decir «subió 7.9% más que todo lo demás» no es lo mismo ni de lejos, y "
        "aquí sólo se puede afirmar lo primero. Fuente: SHF, avalúos de vivienda "
        "con crédito hipotecario garantizado — transacciones reales, no ofertas.</p>",
        unsafe_allow_html=True)

    st.divider()
    st.subheader("¿El crecimiento se contagia entre zonas vecinas?")
    st.markdown(
        "<p class='nota'>Puesto a prueba con validación hacia adelante sobre 480 "
        "predicciones fuera de muestra, el término espacial <b>no aporta</b>: "
        "añadir el crecimiento del vecindario empeora el error un 2.6% frente a "
        "usar sólo el momentum propio. Agrupamiento no es contagio — dos vecinos "
        "pueden crecer igual por un choque común, sin que uno empuje al otro—, y "
        "la prueba es predecir. Corre <code>python -m pipelines.fase3</code> para "
        "reproducirlo con los datos de hoy.</p>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════ main
st.title("🧭 BrickBit Atlas")
st.caption("Inteligencia inmobiliaria de la Ciudad de México · precios de oferta")

t1, t2, t3 = st.tabs(["Valuar", "Mapa", "La ciudad en el tiempo"])
with t1:
    pestana_valuar()
with t2:
    pestana_mapa()
with t3:
    pestana_ciudad()
