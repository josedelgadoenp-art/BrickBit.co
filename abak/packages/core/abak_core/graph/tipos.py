"""Sistema de tipos de los puertos.

Los puertos de un nodo tienen tipo, y los tipos forman una jerarquía pequeña.
La verificación de tipos es lo que atrapa la mayor parte de los errores del
usuario antes de gastar un segundo de cómputo: conectar una tabla cruda a un
VAR, o un modelo a un puerto que espera pesos espaciales.

La jerarquía es deliberadamente plana. Un sistema de tipos que necesita
diagramas para explicarse es un sistema de tipos que el usuario no va a poder
razonar cuando la interfaz le diga "esto no se conecta con esto".
"""

from __future__ import annotations

# tipo -> supertipo inmediato. `cualquiera` es la raíz.
JERARQUIA: dict[str, str | None] = {
    "cualquiera": None,
    # --- datos tabulares -------------------------------------------------
    "tabla": "cualquiera",      # DataFrame de pandas, sin más compromisos
    "serie": "tabla",           # DataFrame con índice temporal (DatetimeIndex/PeriodIndex)
    "panel": "tabla",           # DataFrame con MultiIndex (entidad, tiempo)
    "geotabla": "tabla",        # DataFrame con geometría o lat/lng por fila
    # --- objetos de análisis ---------------------------------------------
    "modelo": "cualquiera",     # resultados de una estimación ya ajustada
    "pesos": "cualquiera",      # matriz de pesos espaciales W (libpysal)
    "mio": "cualquiera",        # sistema insumo-producto resuelto
    # --- visualización ----------------------------------------------------
    "capa": "cualquiera",       # una capa de la gramática de gráficos
    "figura": "cualquiera",     # figura de Plotly lista para dibujar
    # --- escalares --------------------------------------------------------
    "escalar": "cualquiera",    # número, texto o booleano suelto
}

# Cómo se le explica cada tipo a alguien que no es ingeniero. Aparece en el
# tooltip del puerto y en el mensaje de error cuando una conexión no procede.
DESCRIPCION: dict[str, str] = {
    "cualquiera": "Cualquier cosa",
    "tabla": "Una tabla de datos (filas y columnas)",
    "serie": "Una tabla con fecha: cada fila es un periodo en orden",
    "panel": "Una tabla de panel: varias entidades observadas en varios periodos",
    "geotabla": "Una tabla con ubicación: cada fila tiene coordenadas o geometría",
    "modelo": "Un modelo ya estimado, con sus coeficientes y diagnósticos",
    "pesos": "Una matriz de pesos espaciales (quién es vecino de quién)",
    "mio": "Un sistema insumo-producto resuelto",
    "capa": "Una capa de gráfico, para apilar sobre un lienzo",
    "figura": "Una gráfica lista para verse",
    "escalar": "Un número o un texto suelto",
}

# Color por tipo, para pintar los puertos en el lienzo. Paleta mate v2 de la
# casa: nada de colores brillosos.
COLOR: dict[str, str] = {
    "cualquiera": "#8a8178",
    "tabla": "#6fa287",
    "serie": "#55997e",
    "panel": "#24664a",
    "geotabla": "#9aac6b",
    "modelo": "#c07a66",
    "pesos": "#cf928b",
    "mio": "#b7c489",
    "capa": "#8fa8bd",
    "figura": "#7f93a8",
    "escalar": "#a99b8c",
}


class TipoDesconocido(KeyError):
    pass


def linaje(tipo: str) -> list[str]:
    """`serie` -> ['serie', 'tabla', 'cualquiera']."""
    if tipo not in JERARQUIA:
        raise TipoDesconocido(tipo)
    cadena, actual = [], tipo
    while actual is not None:
        cadena.append(actual)
        actual = JERARQUIA[actual]
    return cadena


def acepta(destino: str, origen: str) -> bool:
    """¿Un puerto que pide `destino` acepta un valor de tipo `origen`?

    La regla es la subsunción de siempre: una `serie` sirve donde piden una
    `tabla`, porque una serie *es* una tabla. Al revés no: el nodo que pide
    una `serie` necesita el índice temporal, y una tabla cruda no lo trae.
    """
    if destino == "cualquiera":
        return True
    return destino in linaje(origen)


def explicar_incompatibilidad(destino: str, origen: str) -> str:
    """Mensaje para el usuario cuando una conexión no procede.

    Cuando el problema es sólo que falta una promoción (tabla → serie), se dice
    qué nodo la hace, que es la pregunta siguiente del usuario.
    """
    promocion = {
        "serie": "Definir serie temporal",
        "panel": "Definir panel",
        "geotabla": "Definir ubicación",
    }
    base = (
        f"Esta conexión entrega «{DESCRIPCION.get(origen, origen).lower()}» "
        f"y el destino necesita «{DESCRIPCION.get(destino, destino).lower()}»."
    )
    if origen == "tabla" and destino in promocion:
        return f"{base} Agrega antes un nodo «{promocion[destino]}»."
    return base
