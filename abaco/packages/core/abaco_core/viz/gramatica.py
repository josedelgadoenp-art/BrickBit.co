"""Gramatica de graficos por capas, al estilo de ggplot2, renderizada con Plotly.

Un grafico se arma como una pila: un lienzo declara que columna va en cada eje,
y encima se apilan capas (puntos, linea, barras, banda, tendencia). La pila es
un diccionario que viaja de nodo en nodo; `dibujar` lo convierte en figura.

Cada pieza se registra como ayudante por separado, asi que el script exportado
solo carga las capas que el grafico usa de verdad.

Decisiones de diseno que NO son configurables, a proposito:

  · Nunca hay dos ejes Y. Dos medidas de escalas distintas van en dos graficos o
    indexadas a una base comun. Un eje doble deja elegir la conclusion moviendo
    las escalas, y es el error mas repetido de la graficacion economica.
  · El color sigue a la entidad, no a su lugar en el ranking: filtrar series no
    repinta a las que quedan.
  · Las paletas estan validadas para vision con deficiencia de color (protan,
    deutan, tritan) con separacion minima en OKLab, banda de luminosidad y piso
    de croma, en claro y en oscuro. No se eligieron a ojo.
  · El ambar #F5C277 esta RESERVADO para lo estimado, igual que en el resto de
    la casa. Nunca se usa como color de serie.
"""

from __future__ import annotations

from ..registry.base import Ayudante, registrar_ayudante


PALETA = registrar_ayudante(Ayudante(
    nombre="PALETA_CLARO",
    fuente=r'''
# --- Paleta de Abaco -------------------------------------------------------
# Validada para vision con deficiencia de color: separacion minima en OKLab
# (dE >= 8) entre series adyacentes, banda de luminosidad y piso de croma.
PALETA_CLARO = ["#0F8060", "#C85218", "#2B72B8", "#8A7A00", "#AE3A7E", "#5C9A2E", "#8A5AC2"]
PALETA_OSCURO = ["#25A87F", "#DC6A2B", "#4293DE", "#9C8F10", "#D85DA4", "#5FA92F", "#8E6BD8"]
AMBAR = "#F5C277"          # RESERVADO: marca lo estimado. Nunca es color de serie.
SUPERFICIE = {"claro": "#f5ede3", "oscuro": "#1d1713"}
TINTA = {"claro": "#100c0a", "oscuro": "#f5ede3"}
TINTA_SUAVE = {"claro": "#6b6259", "oscuro": "#a89e93"}
REJILLA = {"claro": "rgba(16,12,10,0.10)", "oscuro": "rgba(245,237,227,0.12)"}
'''))

_APILAR = registrar_ayudante(Ayudante(
    nombre="lienzo",
    depende_de=["PALETA_CLARO"],
    fuente=r'''
def lienzo(datos, x, y=None, color=None, tamano=None, texto=None, titulo=None):
    """Empieza un grafico: que columna va en cada eje y que separa las series.

    Si el eje X vive en el indice (lo normal en series de tiempo y en los
    pronosticos), aqui se baja a columna. Un indice sin nombre —los pronosticos
    de statsmodels vienen asi— se bautiza con el nombre que pidio el usuario.
    """
    if x not in datos.columns:
        antes = list(datos.columns)
        datos = datos.reset_index()
        nuevas = [c for c in datos.columns if c not in antes]
        if x not in datos.columns and len(nuevas) == 1:
            datos = datos.rename(columns={nuevas[0]: x})
        if x not in datos.columns:
            raise KeyError(
                f"El eje horizontal pide '{x}' y esa columna no esta en los datos. "
                f"Disponibles: {list(datos.columns)}"
            )
    return {
        "datos": datos,
        "mapeo": {"x": x, "y": y, "color": color, "tamano": tamano, "texto": texto},
        "capas": [], "facetas": None, "escalas": {},
        "tema": {"titulo": titulo, "modo": "claro", "eje_x": None, "eje_y": None, "nota": None},
    }


def _apilar(g, capa):
    nuevo = dict(g)
    nuevo["capas"] = list(g["capas"]) + [capa]
    return nuevo
'''))

registrar_ayudante(Ayudante(
    nombre="capa_puntos",
    depende_de=["lienzo"],
    fuente=r'''
def capa_puntos(g, opacidad=0.85, tamano=9, estimado=False):
    return _apilar(g, {"tipo": "puntos", "opacidad": opacidad, "tamano": tamano, "estimado": estimado})
'''))

registrar_ayudante(Ayudante(
    nombre="capa_linea",
    depende_de=["lienzo"],
    fuente=r'''
def capa_linea(g, ancho=2, guiones=None, estimado=False, marcadores=False):
    return _apilar(g, {"tipo": "linea", "ancho": ancho, "guiones": guiones,
                       "estimado": estimado, "marcadores": marcadores})
'''))

registrar_ayudante(Ayudante(
    nombre="capa_barras",
    depende_de=["lienzo"],
    fuente=r'''
def capa_barras(g, opacidad=0.9, estimado=False):
    return _apilar(g, {"tipo": "barras", "opacidad": opacidad, "estimado": estimado})
'''))

registrar_ayudante(Ayudante(
    nombre="capa_area",
    depende_de=["lienzo"],
    fuente=r'''
def capa_area(g, opacidad=0.35, estimado=False):
    return _apilar(g, {"tipo": "area", "opacidad": opacidad, "estimado": estimado})
'''))

registrar_ayudante(Ayudante(
    nombre="capa_banda",
    depende_de=["lienzo"],
    fuente=r'''
def capa_banda(g, bajo, alto, opacidad=0.20, etiqueta="Intervalo"):
    """Banda de confianza o de pronostico. Siempre va DEBAJO de la linea."""
    return _apilar(g, {"tipo": "banda", "bajo": bajo, "alto": alto,
                       "opacidad": opacidad, "etiqueta": etiqueta, "estimado": True})
'''))

registrar_ayudante(Ayudante(
    nombre="capa_tendencia",
    depende_de=["lienzo"],
    fuente=r'''
def capa_tendencia(g, metodo="lm", intervalo=True, ancho=2):
    """Recta de minimos cuadrados (lm) o suavizado local (lowess)."""
    return _apilar(g, {"tipo": "tendencia", "metodo": metodo,
                       "intervalo": intervalo, "ancho": ancho, "estimado": True})
'''))

registrar_ayudante(Ayudante(
    nombre="capa_referencia",
    depende_de=["lienzo"],
    fuente=r'''
def capa_referencia(g, eje="y", valor=0.0, etiqueta=None):
    return _apilar(g, {"tipo": "referencia", "eje": eje, "valor": valor, "etiqueta": etiqueta})
'''))

registrar_ayudante(Ayudante(
    nombre="facetas",
    depende_de=["lienzo"],
    fuente=r'''
def facetas(g, por, columnas=3, compartir_y=True):
    nuevo = dict(g)
    nuevo["facetas"] = {"por": por, "columnas": int(columnas), "compartir_y": bool(compartir_y)}
    return nuevo
'''))

registrar_ayudante(Ayudante(
    nombre="escala",
    depende_de=["lienzo"],
    fuente=r'''
def escala(g, eje="y", tipo="lineal", minimo=None, maximo=None, formato=None):
    nuevo = dict(g)
    nuevo["escalas"] = dict(g["escalas"])
    nuevo["escalas"][eje] = {"tipo": tipo, "minimo": minimo, "maximo": maximo, "formato": formato}
    return nuevo
'''))

registrar_ayudante(Ayudante(
    nombre="tema",
    depende_de=["lienzo"],
    fuente=r'''
def tema(g, titulo=None, eje_x=None, eje_y=None, modo="claro", nota=None, leyenda=True):
    nuevo = dict(g)
    nuevo["tema"] = dict(g["tema"])
    for clave, valor in [("titulo", titulo), ("eje_x", eje_x), ("eje_y", eje_y),
                         ("modo", modo), ("nota", nota), ("leyenda", leyenda)]:
        if valor is not None:
            nuevo["tema"][clave] = valor
    return nuevo
'''))

registrar_ayudante(Ayudante(
    nombre="dibujar",
    depende_de=["PALETA_CLARO"],
    fuente=r'''
# --- Render ----------------------------------------------------------------

def _series(datos, mapeo):
    """Parte los datos en series. El color sigue a la entidad, no a su ranking:
    el orden es alfabetico y estable, asi que filtrar no repinta lo que queda."""
    col = mapeo.get("color")
    if not col or col not in datos.columns:
        return [(None, datos)]
    return [(str(v), datos[datos[col] == v]) for v in sorted(datos[col].dropna().unique(), key=str)]


def _tendencia_lm(x, y):
    import numpy as np

    xs = np.asarray(x, dtype=float)
    ys = np.asarray(y, dtype=float)
    ok = ~(np.isnan(xs) | np.isnan(ys))
    xs, ys = xs[ok], ys[ok]
    if len(xs) < 3:
        return None
    b, a = np.polyfit(xs, ys, 1)
    orden = np.argsort(xs)
    xg = xs[orden]
    yg = a + b * xg
    n = len(xs)
    residuos = ys - (a + b * xs)
    s2 = float((residuos ** 2).sum() / max(n - 2, 1))
    sxx = float(((xs - xs.mean()) ** 2).sum()) or 1.0
    ee = np.sqrt(s2 * (1.0 / n + (xg - xs.mean()) ** 2 / sxx))
    return xg, yg, yg - 1.96 * ee, yg + 1.96 * ee


def dibujar(g):
    """Compila la pila de capas a una figura de Plotly."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    modo = g["tema"].get("modo", "claro")
    paleta = PALETA_CLARO if modo == "claro" else PALETA_OSCURO
    superficie, tinta = SUPERFICIE[modo], TINTA[modo]
    mapeo = g["mapeo"]
    datos = g["datos"]
    x_col, y_col = mapeo["x"], mapeo["y"]

    grupos = [(None, datos)]
    filas = cols = 1
    if g["facetas"]:
        valores = sorted(datos[g["facetas"]["por"]].dropna().unique(), key=str)
        cols = min(g["facetas"]["columnas"], max(1, len(valores)))
        filas = (len(valores) + cols - 1) // cols
        grupos = [(str(v), datos[datos[g["facetas"]["por"]] == v]) for v in valores]
        fig = make_subplots(rows=filas, cols=cols, subplot_titles=[str(v) for v, _ in grupos],
                            shared_yaxes=g["facetas"]["compartir_y"],
                            horizontal_spacing=0.06, vertical_spacing=0.10)
    else:
        fig = go.Figure()

    series_totales = len(_series(datos, mapeo))
    vistos = set()
    # Todo lo estimado (bandas, tendencias) comparte UNA sola entrada de leyenda.
    # Con cinco series, una entrada por serie tapaba el titulo del grafico.
    leyenda_estimado_puesta = False

    for indice_faceta, (_etiqueta_faceta, sub) in enumerate(grupos):
        fila = indice_faceta // cols + 1
        col = indice_faceta % cols + 1
        destino = {"row": fila, "col": col} if g["facetas"] else {}

        for i, (nombre_serie, marco) in enumerate(_series(sub, mapeo)):
            color = paleta[i % len(paleta)]
            mostrar = nombre_serie is not None and nombre_serie not in vistos
            if nombre_serie is not None:
                vistos.add(nombre_serie)
            etiqueta = nombre_serie or (y_col or "serie")

            # Las bandas van primero para quedar POR DEBAJO de las lineas.
            for capa in [c for c in g["capas"] if c["tipo"] in ("banda", "tendencia")]:
                if capa["tipo"] == "banda":
                    fig.add_trace(go.Scatter(
                        x=list(marco[x_col]) + list(marco[x_col])[::-1],
                        y=list(marco[capa["alto"]]) + list(marco[capa["bajo"]])[::-1],
                        fill="toself", fillcolor=_alfa(AMBAR, capa["opacidad"]),
                        line=dict(width=0), hoverinfo="skip",
                        name=capa["etiqueta"], legendgroup="estimado",
                        showlegend=not leyenda_estimado_puesta,
                    ), **destino)
                    leyenda_estimado_puesta = True
                elif capa["metodo"] == "lm":
                    ajuste = _tendencia_lm(_numerico(marco[x_col]), marco[y_col])
                    if ajuste is None:
                        continue
                    xg, yg, bajo, alto = ajuste
                    if capa["intervalo"]:
                        fig.add_trace(go.Scatter(
                            x=list(xg) + list(xg)[::-1], y=list(alto) + list(bajo)[::-1],
                            fill="toself", fillcolor=_alfa(AMBAR, 0.18), line=dict(width=0),
                            hoverinfo="skip", name="Intervalo de la tendencia",
                            legendgroup="estimado", showlegend=False,
                        ), **destino)
                    fig.add_trace(go.Scatter(
                        x=xg, y=yg, mode="lines", name="Tendencia (estimada)",
                        line=dict(color=AMBAR, width=capa["ancho"], dash="dash"),
                        legendgroup="estimado", showlegend=not leyenda_estimado_puesta,
                        hovertemplate=f"Tendencia de {etiqueta} (estimada): %{{y:.4g}}<extra></extra>",
                    ), **destino)
                    leyenda_estimado_puesta = True

            for capa in [c for c in g["capas"] if c["tipo"] not in ("banda", "tendencia", "referencia")]:
                comun = dict(name=etiqueta, legendgroup=etiqueta, showlegend=mostrar,
                             hovertemplate=f"<b>{etiqueta}</b><br>%{{x}}<br>%{{y:.4g}}<extra></extra>")
                pinta = AMBAR if capa.get("estimado") else color
                if capa["tipo"] == "linea":
                    fig.add_trace(go.Scatter(
                        x=marco[x_col], y=marco[y_col],
                        mode="lines+markers" if capa["marcadores"] else "lines",
                        line=dict(color=pinta, width=capa["ancho"],
                                  dash=capa["guiones"] or ("dash" if capa.get("estimado") else None)),
                        marker=dict(size=8, line=dict(width=2, color=superficie)), **comun,
                    ), **destino)
                elif capa["tipo"] == "puntos":
                    tam = marco[mapeo["tamano"]] if mapeo.get("tamano") in marco.columns else None
                    fig.add_trace(go.Scatter(
                        x=marco[x_col], y=marco[y_col], mode="markers",
                        marker=dict(color=pinta, opacity=capa["opacidad"],
                                    size=_escala_tamano(tam, capa["tamano"]),
                                    line=dict(width=2, color=superficie)),
                        text=marco[mapeo["texto"]] if mapeo.get("texto") in marco.columns else None,
                        **comun,
                    ), **destino)
                elif capa["tipo"] == "barras":
                    fig.add_trace(go.Bar(
                        x=marco[x_col], y=marco[y_col],
                        marker=dict(color=pinta, opacity=capa["opacidad"],
                                    line=dict(width=2, color=superficie)), **comun,
                    ), **destino)
                elif capa["tipo"] == "area":
                    fig.add_trace(go.Scatter(
                        x=marco[x_col], y=marco[y_col], mode="lines", fill="tozeroy",
                        fillcolor=_alfa(pinta, capa["opacidad"]),
                        line=dict(color=pinta, width=2), **comun,
                    ), **destino)

    for capa in [c for c in g["capas"] if c["tipo"] == "referencia"]:
        if capa["eje"] == "y":
            fig.add_hline(y=capa["valor"], line=dict(color=TINTA_SUAVE[modo], width=1, dash="dot"),
                          annotation_text=capa["etiqueta"], annotation_position="top left")
        else:
            fig.add_vline(x=capa["valor"], line=dict(color=TINTA_SUAVE[modo], width=1, dash="dot"),
                          annotation_text=capa["etiqueta"], annotation_position="top")

    hay_estimado = any(c.get("estimado") for c in g["capas"])
    nota = g["tema"].get("nota")
    if hay_estimado:
        aviso = "En ambar, lo estimado: no son datos observados."
        nota = f"{nota} · {aviso}" if nota else aviso

    hay_leyenda = g["tema"].get("leyenda", True) and (series_totales > 1 or hay_estimado)
    # El alto que hay que reservar abajo depende de si hay leyenda y de si hay
    # nota al pie. Calcularlo evita el choque en vez de esperar que no ocurra.
    abajo = 56 + (34 if hay_leyenda else 0) + (26 if nota else 0)

    fig.update_layout(
        title=dict(text=g["tema"].get("titulo") or "", font=dict(size=17, color=tinta),
                   x=0, xanchor="left", y=0.97, yanchor="top"),
        paper_bgcolor=superficie, plot_bgcolor=superficie,
        font=dict(family="Inter, system-ui, sans-serif", size=13, color=tinta),
        margin=dict(l=68, r=28, t=54 if g["tema"].get("titulo") else 24, b=abajo),
        hovermode="x unified" if any(c["tipo"] in ("linea", "area") for c in g["capas"]) else "closest",
        showlegend=hay_leyenda,
        legend=dict(orientation="h", yanchor="top", y=-0.14, x=0,
                    bgcolor="rgba(0,0,0,0)", font=dict(color=TINTA_SUAVE[modo], size=12),
                    itemsizing="constant"),
        barmode="group",
    )
    fig.update_xaxes(title_text=g["tema"].get("eje_x") or x_col, showgrid=False,
                     zeroline=False, linecolor=REJILLA[modo], ticks="outside",
                     tickcolor=REJILLA[modo], tickfont=dict(color=TINTA_SUAVE[modo]))
    fig.update_yaxes(title_text=g["tema"].get("eje_y") or (y_col or ""), gridcolor=REJILLA[modo],
                     zeroline=False, linecolor="rgba(0,0,0,0)", tickfont=dict(color=TINTA_SUAVE[modo]))

    for eje, ajuste in g["escalas"].items():
        cambios = {}
        if ajuste.get("tipo") == "log":
            cambios["type"] = "log"
        if ajuste.get("minimo") is not None or ajuste.get("maximo") is not None:
            cambios["range"] = [ajuste.get("minimo"), ajuste.get("maximo")]
        if ajuste.get("formato"):
            cambios["tickformat"] = ajuste["formato"]
        if cambios:
            (fig.update_xaxes if eje == "x" else fig.update_yaxes)(**cambios)

    if nota:
        fig.add_annotation(text=nota, xref="paper", yref="paper", x=0,
                           y=-0.30 if hay_leyenda else -0.20,
                           showarrow=False, font=dict(size=11, color=TINTA_SUAVE[modo]),
                           xanchor="left", yanchor="top")
    return fig


def _alfa(hexadecimal, alfa):
    h = hexadecimal.lstrip("#")
    r, v, a = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{v},{a},{alfa})"


def _numerico(serie):
    import pandas as pd

    if pd.api.types.is_numeric_dtype(serie):
        return serie.to_numpy(float)
    return pd.to_numeric(pd.to_datetime(serie, errors="coerce"), errors="coerce").to_numpy(float)


def _escala_tamano(serie, base):
    import numpy as np

    if serie is None:
        return base
    v = np.asarray(serie, dtype=float)
    lo, hi = np.nanmin(v), np.nanmax(v)
    if not np.isfinite(lo) or hi <= lo:
        return base
    return 8 + 22 * (v - lo) / (hi - lo)
'''))
