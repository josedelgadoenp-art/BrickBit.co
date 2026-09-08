"""Las figuras que Abak dibuja sin que se las pidan.

Un modelo estimado tiene una lectura visual obvia —los coeficientes con su
intervalo, el ajuste contra lo observado, los residuos, la banda del
pronostico— y hasta ahora habia que armarla a mano, capa por capa. La gente no
la armaba: en la verificacion completa de los seis ejemplos se dibujaba **una**
grafica en total. No es que no las quisieran; es que el camino para tenerlas era
mas largo que el camino para no tenerlas.

Estas funciones son PRESENTACION, igual que la tabla de coeficientes: se
construyen en `resumir()` a partir de los mismos objetos que el script deja en
memoria, no cambian ni una linea de lo que se ejecuta. Por eso viajan tambien
en el paquete exportado como `figuras.py`: quien corra el script fuera de Abak
puede volver a dibujar exactamente lo mismo llamandolas con sus objetos.

Reglas de la casa que aqui se respetan sin excepcion:

  · El ambar #F5C277 marca lo ESTIMADO y nada mas. Un pronostico va en ambar; la
    serie observada, no. Nunca es color decorativo.
  · Nunca hay dos ejes Y (ver `viz/gramatica.py`).
  · El fondo es transparente: la figura toma el color del panel donde cae, y se
    ve igual en el lienzo oscuro y en el PDF claro.
"""

from __future__ import annotations

from typing import Any

# Los mismos colores de la gramatica. Se repiten aqui a proposito y no se
# importan: este modulo tiene que poder copiarse solo al paquete exportado.
PALETA = ["#25A87F", "#DC6A2B", "#4293DE", "#9C8F10", "#D85DA4", "#5FA92F", "#8E6BD8"]
AMBAR = "#F5C277"          # RESERVADO: marca lo estimado.
TINTA = "#8f8880"          # ejes y rotulos: neutro, legible en claro y en oscuro
REJILLA = "rgba(143,136,128,.20)"
ALTO = 380


def marco(fig: Any, *, titulo: str | None = None, eje_x: str | None = None,
          eje_y: str | None = None, nota: str | None = None, alto: int = ALTO) -> Any:
    """El vestido comun de toda figura automatica."""
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=13, color=TINTA)) if titulo else None,
        height=alto,
        margin=dict(l=58, r=22, t=44 if titulo else 18, b=78 if nota else 42),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Geist, ui-sans-serif, system-ui, sans-serif", size=11, color=TINTA),
        hoverlabel=dict(font_size=11),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, font=dict(size=10)),
        showlegend=fig.layout.showlegend if fig.layout.showlegend is not None else False,
    )
    fig.update_xaxes(title_text=eje_x, gridcolor=REJILLA, zeroline=False,
                     linecolor=REJILLA, ticks="outside", tickcolor=REJILLA)
    fig.update_yaxes(title_text=eje_y, gridcolor=REJILLA, zeroline=False,
                     linecolor=REJILLA, ticks="outside", tickcolor=REJILLA)
    if nota:
        # Anclada en pixeles bajo el area de dibujo, no en fraccion del alto.
        # Con `y=-0.19` la nota se montaba encima de los rotulos del eje en
        # cuanto la figura era baja, y estas figuras cambian de alto solas.
        fig.add_annotation(text=nota, xref="paper", yref="paper", x=0, y=0,
                           yanchor="top", yshift=-58, showarrow=False, xanchor="left",
                           font=dict(size=10, color=TINTA), opacity=0.85)
    return fig


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

def fig_coeficientes(res: Any, *, titulo: str = "Coeficientes con su intervalo al 95%") -> Any:
    """El bosque de coeficientes: punto, bigote y la linea del cero.

    Es la lectura que la tabla no da de un vistazo: que tan lejos del cero esta
    cada efecto Y que tan ancha es su incertidumbre. Un coeficiente grande con
    un intervalo que cruza el cero se ve grande en la tabla y se ve exactamente
    igual de incierto aqui.
    """
    import numpy as np
    import plotly.graph_objects as go

    try:
        params = res.params
        ic = res.conf_int()
    except Exception:
        return None
    nombres = [str(n) for n in getattr(params, "index", range(len(params)))]
    valores = np.asarray(params, dtype=float)
    ic = np.asarray(ic, dtype=float)
    if ic.ndim != 2 or ic.shape[0] != len(valores):
        return None

    # Coeficientes crudos NO son comparables entre si: un ingreso en pesos da
    # 0.48 y una escolaridad en anios da 1,105, y en un eje compartido el
    # primero se ve pegado al cero aunque mueva mas el resultado. Se escalan por
    # la desviacion estandar de cada variable —el efecto de moverla una
    # desviacion— que es la comparacion que la gente quiere hacer al mirar esto.
    # Los coeficientes en sus unidades siguen intactos en la tabla de arriba.
    escala = np.ones(len(valores))
    comparable = False
    try:
        exog = np.asarray(res.model.exog, dtype=float)
        if exog.shape[1] == len(valores):
            desviaciones = exog.std(axis=0, ddof=1)
            constante = np.array([n.lower() in ("const", "intercept", "intercepto")
                                  for n in nombres])
            if np.all(desviaciones[~constante] > 0):
                escala = np.where(constante, 1.0, desviaciones)
                comparable = True
    except Exception:
        comparable = False
    if comparable:
        valores = valores * escala
        ic = ic * escala[:, None]

    # La constante no es un efecto: comparte eje con los demas y aplasta la
    # escala. Se deja fuera salvo que sea lo unico que hay.
    orden = [i for i, n in enumerate(nombres) if n.lower() not in ("const", "intercept", "intercepto")]
    if not orden:
        orden = list(range(len(nombres)))

    y = [nombres[i] for i in orden][::-1]
    v = [valores[i] for i in orden][::-1]
    bajo = [ic[i][0] for i in orden][::-1]
    alto = [ic[i][1] for i in orden][::-1]
    cruza = [b <= 0 <= a for b, a in zip(bajo, alto)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=v, y=y, mode="markers",
        marker=dict(size=9, color=[TINTA if c else PALETA[0] for c in cruza],
                    line=dict(width=0)),
        error_x=dict(type="data", symmetric=False,
                     array=[a - x for a, x in zip(alto, v)],
                     arrayminus=[x - b for b, x in zip(bajo, v)],
                     color=TINTA, thickness=1.2, width=5),
        hovertemplate="%{y}<br>%{x:.4f}<extra></extra>", showlegend=False))
    fig.add_vline(x=0, line=dict(color=TINTA, width=1, dash="dot"))
    return marco(
        fig, titulo=titulo,
        eje_x=("Cambio en la variable explicada si esta sube una desviación estándar"
               if comparable else "Efecto sobre la variable explicada"),
        nota=("Escalado por la desviación estándar de cada variable para poder compararlas; "
              "los coeficientes en sus unidades están en la tabla. Los grises cruzan el cero."
              if comparable else
              "Los grises cruzan el cero: con estos datos no se distingue de «ningún efecto». "
              "Ojo: las variables están en unidades distintas y comparten eje."),
        alto=max(250, 110 + 34 * len(y)))


def fig_ajuste(df: Any, *, titulo: str = "Qué tan bien ajusta") -> Any:
    """Observado contra ajustado, y los residuos contra el ajustado.

    Dos paneles porque contestan dos preguntas distintas: si el modelo acierta
    (izquierda, la diagonal es el acierto perfecto) y si se equivoca de manera
    sistematica (derecha, un embudo o una curva delatan lo que el R2 esconde).
    """
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    if df is None or not {"observado", "ajustado", "residuo"} <= set(getattr(df, "columns", [])):
        return None
    obs = np.asarray(df["observado"], dtype=float)
    aju = np.asarray(df["ajustado"], dtype=float)
    resid = np.asarray(df["residuo"], dtype=float)
    ok = ~(np.isnan(obs) | np.isnan(aju))
    if ok.sum() < 3:
        return None
    obs, aju, resid = obs[ok], aju[ok], resid[ok]

    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.12,
                        subplot_titles=("Observado vs. ajustado", "Residuos vs. ajustado"))
    fig.add_trace(go.Scatter(x=aju, y=obs, mode="markers",
                             marker=dict(size=6, color=PALETA[0], opacity=0.75),
                             hovertemplate="ajustado %{x:.4g}<br>observado %{y:.4g}<extra></extra>",
                             showlegend=False), row=1, col=1)
    lim = [float(min(aju.min(), obs.min())), float(max(aju.max(), obs.max()))]
    fig.add_trace(go.Scatter(x=lim, y=lim, mode="lines",
                             line=dict(color=TINTA, width=1, dash="dot"),
                             hoverinfo="skip", showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=aju, y=resid, mode="markers",
                             marker=dict(size=6, color=PALETA[1], opacity=0.75),
                             hovertemplate="ajustado %{x:.4g}<br>residuo %{y:.4g}<extra></extra>",
                             showlegend=False), row=1, col=2)
    fig.add_hline(y=0, line=dict(color=TINTA, width=1, dash="dot"), row=1, col=2)
    for anotacion in fig.layout.annotations:
        anotacion.font.size = 11
        anotacion.font.color = TINTA
    marco(fig, titulo=titulo,
          nota="Si los residuos abren un embudo o dibujan una curva, el modelo se equivoca de forma "
               "sistemática y el R² no lo dice.")
    fig.update_xaxes(title_text="Ajustado", gridcolor=REJILLA, linecolor=REJILLA, row=1, col=1)
    fig.update_xaxes(title_text="Ajustado", gridcolor=REJILLA, linecolor=REJILLA, row=1, col=2)
    fig.update_yaxes(title_text="Observado", gridcolor=REJILLA, linecolor=REJILLA, row=1, col=1)
    fig.update_yaxes(title_text="Residuo", gridcolor=REJILLA, linecolor=REJILLA, row=1, col=2)
    return fig


# ---------------------------------------------------------------------------
# Series de tiempo y proyecciones
# ---------------------------------------------------------------------------

def fig_pronostico(historico: Any, pronostico: Any, *, nombre: str = "serie",
                   titulo: str = "Pronóstico con su banda al 95%") -> Any:
    """El abanico: lo observado en color, lo pronosticado en ambar, con banda.

    La banda no es adorno. Un pronostico puntual sin banda es una opinion
    disfrazada de numero, y a los seis trimestres suele ser mas ancha que el
    movimiento que pretende anunciar. Aqui se ve.
    """
    import numpy as np
    import plotly.graph_objects as go

    if pronostico is None or "pronostico" not in getattr(pronostico, "columns", []):
        return None
    x_p = list(pronostico.index)
    y_p = np.asarray(pronostico["pronostico"], dtype=float)
    baja = pronostico["banda_baja"] if "banda_baja" in pronostico.columns else None
    alta = pronostico["banda_alta"] if "banda_alta" in pronostico.columns else None

    fig = go.Figure()
    if historico is not None and len(historico):
        fig.add_trace(go.Scatter(x=list(historico.index),
                                 y=np.asarray(historico, dtype=float),
                                 mode="lines", name="Observado",
                                 line=dict(color=PALETA[0], width=2),
                                 hovertemplate="%{x}<br>%{y:.4g}<extra>observado</extra>"))
    if baja is not None and alta is not None:
        fig.add_trace(go.Scatter(
            x=x_p + x_p[::-1],
            y=list(np.asarray(alta, dtype=float)) + list(np.asarray(baja, dtype=float))[::-1],
            fill="toself", fillcolor="rgba(245,194,119,.18)", line=dict(width=0),
            name="Banda 95%", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x_p, y=y_p, mode="lines+markers", name="Pronóstico (est.)",
                             line=dict(color=AMBAR, width=2, dash="dash"),
                             marker=dict(size=5, color=AMBAR),
                             hovertemplate="%{x}<br>%{y:.4g}<extra>pronóstico</extra>"))
    fig.update_layout(showlegend=True)
    return marco(fig, titulo=titulo, eje_y=nombre,
                 nota="En ámbar, lo estimado. La banda al 95% suele ser más ancha que el movimiento "
                      "que el pronóstico anuncia: esa es la información.")


def fig_lineas(df: Any, *, titulo: str | None = None, eje_y: str | None = None,
               nota: str | None = None, estimadas: list[str] | None = None) -> Any:
    """Varias columnas contra el indice. Sirve para indices, IRF y acumulados."""
    import numpy as np
    import plotly.graph_objects as go

    if df is None or not len(getattr(df, "columns", [])):
        return None
    estimadas = estimadas or []
    fig = go.Figure()
    for i, col in enumerate(df.columns):
        serie = df[col]
        try:
            y = np.asarray(serie, dtype=float)
        except Exception:
            continue
        es_est = str(col) in estimadas
        fig.add_trace(go.Scatter(
            x=list(df.index), y=y, mode="lines",
            name=f"{col} (est.)" if es_est else str(col),
            line=dict(color=AMBAR if es_est else PALETA[i % len(PALETA)],
                      width=2, dash="dash" if es_est else "solid"),
            hovertemplate="%{x}<br>%{y:.4g}<extra>" + str(col) + "</extra>"))
    if not fig.data:
        return None
    fig.update_layout(showlegend=len(fig.data) > 1)
    return marco(fig, titulo=titulo, eje_y=eje_y, nota=nota)


# ---------------------------------------------------------------------------
# Barras, dispersion y distribuciones
# ---------------------------------------------------------------------------

def fig_barras(etiquetas: Any, valores: Any, *, titulo: str | None = None,
               eje_x: str | None = None, nota: str | None = None,
               estimado: bool = False, tope: int = 20) -> Any:
    """Barras horizontales ordenadas. Importancias, multiplicadores, rankings."""
    import numpy as np
    import plotly.graph_objects as go

    try:
        v = np.asarray(list(valores), dtype=float)
    except Exception:
        return None
    e = [str(x) for x in etiquetas]
    if not len(v) or len(v) != len(e):
        return None
    orden = np.argsort(np.abs(v))[-tope:]
    e = [e[i] for i in orden]
    v = [float(v[i]) for i in orden]

    fig = go.Figure(go.Bar(
        x=v, y=e, orientation="h",
        marker=dict(color=AMBAR if estimado else PALETA[0]),
        hovertemplate="%{y}<br>%{x:.4g}<extra></extra>"))
    return marco(fig, titulo=titulo, eje_x=eje_x, nota=nota,
                 alto=max(240, 90 + 26 * len(e)))


def fig_dispersion(x: Any, y: Any, *, nombre_x: str = "x", nombre_y: str = "y",
                   etiquetas: Any = None, titulo: str | None = None,
                   linea_45: bool = False, nota: str | None = None) -> Any:
    """Nube de puntos con su recta de tendencia."""
    import numpy as np
    import plotly.graph_objects as go

    xs = np.asarray(x, dtype=float)
    ys = np.asarray(y, dtype=float)
    ok = ~(np.isnan(xs) | np.isnan(ys))
    xs, ys = xs[ok], ys[ok]
    if len(xs) < 3:
        return None
    texto = None
    if etiquetas is not None:
        etiquetas = [str(t) for t in etiquetas]
        texto = [etiquetas[i] for i, v in enumerate(ok) if v] if len(etiquetas) == len(ok) else None

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers", text=texto,
        marker=dict(size=7, color=PALETA[0], opacity=0.8),
        hovertemplate=(("%{text}<br>" if texto else "")
                       + nombre_x + " %{x:.4g}<br>" + nombre_y + " %{y:.4g}<extra></extra>"),
        showlegend=False))
    b, a = np.polyfit(xs, ys, 1)
    xg = np.linspace(xs.min(), xs.max(), 60)
    fig.add_trace(go.Scatter(x=xg, y=a + b * xg, mode="lines",
                             line=dict(color=PALETA[1], width=1.6),
                             hoverinfo="skip", showlegend=False))
    if linea_45:
        lim = [float(min(xs.min(), ys.min())), float(max(xs.max(), ys.max()))]
        fig.add_trace(go.Scatter(x=lim, y=lim, mode="lines",
                                 line=dict(color=TINTA, width=1, dash="dot"),
                                 hoverinfo="skip", showlegend=False))
    return marco(fig, titulo=titulo, eje_x=nombre_x, eje_y=nombre_y, nota=nota)


def fig_distribuciones(df: Any, columnas: list[str], *,
                       titulo: str = "Cómo se reparte cada variable") -> Any:
    """Un histograma por variable, en la misma pantalla.

    Es lo primero que hay que mirar y lo ultimo que se mira: una media de 15,000
    puede venir de una campana o de dos grupos que no se parecen en nada, y la
    tabla de descriptivos no distingue esos dos mundos.
    """
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    cols = [c for c in columnas if c in getattr(df, "columns", [])][:6]
    if not cols:
        return None
    n = len(cols)
    filas = 1 if n <= 3 else 2
    columnas_g = n if n <= 3 else (n + 1) // 2
    fig = make_subplots(rows=filas, cols=columnas_g, subplot_titles=cols,
                        horizontal_spacing=0.09, vertical_spacing=0.22)
    for i, col in enumerate(cols):
        try:
            v = np.asarray(df[col], dtype=float)
        except Exception:
            continue
        v = v[~np.isnan(v)]
        if not len(v):
            continue
        fig.add_trace(go.Histogram(x=v, nbinsx=24, marker=dict(color=PALETA[i % len(PALETA)]),
                                   hovertemplate="%{x}<br>%{y} casos<extra></extra>",
                                   showlegend=False),
                      row=1 + i // columnas_g, col=1 + i % columnas_g)
    if not fig.data:
        return None
    for anotacion in fig.layout.annotations:
        anotacion.font.size = 11
        anotacion.font.color = TINTA
    marco(fig, titulo=titulo, alto=300 if filas == 1 else 460,
          nota="Dos grupos distintos y una campana pueden tener la misma media. Aquí se distinguen.")
    fig.update_xaxes(gridcolor=REJILLA, linecolor=REJILLA)
    fig.update_yaxes(gridcolor=REJILLA, linecolor=REJILLA)
    return fig


def fig_cajas(tabla: Any, *, titulo: str = "Rango y mediana de cada variable",
              tope: int = 6) -> Any:
    """Cajas armadas con los cuantiles que la tabla de descriptivos ya calculo.

    No se vuelve a tocar el dato: `go.Box` admite los cinco numeros hechos, y
    esos son justo los que la tabla trae.

    Un panel por variable, con su PROPIO eje. Se intento con un solo eje y salio
    inservible: un precio por m2 de 8,300 a 40,500 y una escolaridad de 6.8 a
    13.6 en la misma escala dejan la segunda aplastada contra el suelo, y el
    grafico dice «la escolaridad no varia», que es falso. Compartir eje entre
    magnitudes distintas no es un problema de estetica.
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    necesarias = {"variable", "minimo", "p25", "mediana", "p75", "maximo"}
    if tabla is None or not necesarias <= set(getattr(tabla, "columns", [])):
        return None
    filas = [f for _, f in tabla.iterrows()][:tope]
    if not filas:
        return None

    fig = make_subplots(rows=1, cols=len(filas), horizontal_spacing=0.06,
                        subplot_titles=[str(f["variable"]) for f in filas])
    dibujadas = 0
    for i, fila in enumerate(filas):
        try:
            fig.add_trace(go.Box(
                x=[str(fila["variable"])],
                q1=[float(fila["p25"])], median=[float(fila["mediana"])],
                q3=[float(fila["p75"])], lowerfence=[float(fila["minimo"])],
                upperfence=[float(fila["maximo"])],
                marker=dict(color=PALETA[i % len(PALETA)]),
                line=dict(width=1.4), showlegend=False), row=1, col=i + 1)
            dibujadas += 1
        except Exception:
            continue
    if not dibujadas:
        return None
    for anotacion in fig.layout.annotations:
        anotacion.font.size = 10
        anotacion.font.color = TINTA
    marco(fig, titulo=titulo, alto=320,
          nota="Cada panel tiene su propia escala: son magnitudes distintas y compartir eje "
               "aplastaría a la más pequeña hasta hacerla parecer constante.")
    fig.update_xaxes(showticklabels=False, gridcolor=REJILLA, linecolor=REJILLA)
    fig.update_yaxes(gridcolor=REJILLA, linecolor=REJILLA)
    return fig


def fig_calor_correlacion(tabla: Any, *, titulo: str = "Correlaciones") -> Any:
    """Mapa de calor a partir de la tabla larga variable_1 / variable_2.

    Escala divergente y centrada en cero, que es la unica honesta para una
    correlacion: el color tiene que decir el SIGNO antes que la intensidad.
    """
    import plotly.graph_objects as go

    cols = set(getattr(tabla, "columns", []))
    if tabla is None or not {"variable_1", "variable_2", "correlacion"} <= cols:
        return None
    nombres = sorted(set(tabla["variable_1"]) | set(tabla["variable_2"]), key=str)
    indice = {n: i for i, n in enumerate(nombres)}
    matriz = [[None] * len(nombres) for _ in nombres]
    for i in range(len(nombres)):
        matriz[i][i] = 1.0
    for _, f in tabla.iterrows():
        try:
            a, b, r = indice[f["variable_1"]], indice[f["variable_2"]], float(f["correlacion"])
        except Exception:
            continue
        matriz[a][b] = r
        matriz[b][a] = r
    fig = go.Figure(go.Heatmap(
        z=matriz, x=nombres, y=nombres, zmin=-1, zmax=1,
        colorscale=[[0, "#bf5b52"], [0.5, "rgba(143,136,128,.18)"], [1, "#24664a"]],
        colorbar=dict(thickness=10, outlinewidth=0, tickfont=dict(size=10)),
        hovertemplate="%{y} · %{x}<br>r = %{z:.3f}<extra></extra>"))
    return marco(fig, titulo=titulo, alto=max(300, 90 + 34 * len(nombres)),
                 nota="Correlación no es causalidad, y una correlación alta entre dos explicativas "
                      "es el aviso temprano de colinealidad.")


def fig_impulso_respuesta(irf: Any, *, titulo: str = "Impulso-respuesta",
                          tope: int = 9) -> Any:
    """Una rejilla de respuestas: fila = quien responde, columna = quien choca.

    La tabla larga de un VAR con cuatro variables trae 192 renglones y es
    ilegible. La rejilla es como se lee un VAR en cualquier articulo: lo que
    importa es si la banda cruza el cero, y eso se ve o no se ve.
    """
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    cols = set(getattr(irf, "columns", []))
    if irf is None or not {"periodo", "choque_en", "respuesta_de", "efecto"} <= cols:
        return None
    choques = sorted(set(irf["choque_en"]), key=str)
    respuestas = sorted(set(irf["respuesta_de"]), key=str)
    if len(choques) * len(respuestas) > tope:
        # Con mas de nueve paneles no se ve nada; se deja la tabla.
        choques, respuestas = choques[:3], respuestas[:3]
    fig = make_subplots(rows=len(respuestas), cols=len(choques),
                        shared_xaxes=True, horizontal_spacing=0.07, vertical_spacing=0.12,
                        subplot_titles=[f"choque en {c}" for c in choques] * 1
                        if len(respuestas) else None)
    hay_banda = {"banda_baja", "banda_alta"} <= cols
    for i, r in enumerate(respuestas):
        for j, c in enumerate(choques):
            t = irf[(irf["choque_en"] == c) & (irf["respuesta_de"] == r)].sort_values("periodo")
            if not len(t):
                continue
            x = list(t["periodo"])
            if hay_banda:
                fig.add_trace(go.Scatter(
                    x=x + x[::-1],
                    y=list(np.asarray(t["banda_alta"], dtype=float))
                      + list(np.asarray(t["banda_baja"], dtype=float))[::-1],
                    fill="toself", fillcolor="rgba(245,194,119,.16)", line=dict(width=0),
                    hoverinfo="skip", showlegend=False), row=i + 1, col=j + 1)
            fig.add_trace(go.Scatter(
                x=x, y=np.asarray(t["efecto"], dtype=float), mode="lines",
                line=dict(color=AMBAR, width=1.8),
                hovertemplate="periodo %{x}<br>%{y:.4g}<extra>" + f"{c} → {r}" + "</extra>",
                showlegend=False), row=i + 1, col=j + 1)
            fig.add_hline(y=0, line=dict(color=TINTA, width=1, dash="dot"), row=i + 1, col=j + 1)
            if j == 0:
                fig.update_yaxes(title_text=str(r), title_font=dict(size=10), row=i + 1, col=1)
    if not fig.data:
        return None
    for anotacion in fig.layout.annotations:
        anotacion.font.size = 10
        anotacion.font.color = TINTA
    marco(fig, titulo=titulo, alto=max(300, 170 * len(respuestas)),
          nota="Todo lo dibujado es estimación (ámbar). Si la banda cruza el cero en un periodo, "
               "ahí el efecto no se distingue de cero.")
    fig.update_xaxes(gridcolor=REJILLA, linecolor=REJILLA)
    fig.update_yaxes(gridcolor=REJILLA, linecolor=REJILLA)
    return fig


def fig_proyeccion(art: dict, *, resaltar: int | None = None) -> Any:
    """El abanico completo de escenarios, en una sola figura estatica.

    En pantalla la proyeccion se mueve con un deslizador; en un PDF no hay
    deslizador, y omitirla seria dejar fuera justo el resultado principal. Aqui
    se dibujan TODAS las curvas a la vez, con su banda en la del medio: se
    pierde el gesto, no la informacion.
    """
    import plotly.graph_objects as go

    x = (art.get("x") or {}).get("valores") or []
    series = art.get("series") or []
    control = art.get("control")
    if not x or not series:
        return None
    medio = len(series) // 2 if resaltar is None else max(0, min(resaltar, len(series) - 1))

    fig = go.Figure()
    s = series[medio]
    if s.get("alto") and s.get("bajo"):
        fig.add_trace(go.Scatter(
            x=list(x) + list(x)[::-1], y=list(s["alto"]) + list(s["bajo"])[::-1],
            fill="toself", fillcolor="rgba(245,194,119,.15)", line=dict(width=0),
            hoverinfo="skip", showlegend=False))
    for k, serie in enumerate(series):
        destacada = k == medio
        nombre = (f"{control['nombre']} = {serie['escenario']:,.4g}"
                  if control and serie.get("escenario") is not None else "proyección")
        fig.add_trace(go.Scatter(
            x=x, y=serie["y"], mode="lines", name=nombre,
            line=dict(color=AMBAR, width=2.4 if destacada else 1.2,
                      dash="solid" if destacada else "dot"),
            opacity=1.0 if destacada else 0.55,
            hovertemplate="%{x:.4g}<br>%{y:.4g}<extra>" + nombre + "</extra>"))
    fig.update_layout(showlegend=bool(control))
    return marco(fig, titulo=art.get("titulo"),
                 eje_x=(art.get("x") or {}).get("nombre"), eje_y=art.get("respuesta"),
                 nota=art.get("nota") or "Todo lo dibujado es estimación del modelo.")
