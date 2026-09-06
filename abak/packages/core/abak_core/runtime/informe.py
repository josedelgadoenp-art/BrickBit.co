"""Informe en PDF: el análisis completo, listo para entregar.

Se arma a partir de los MISMOS artefactos que ve la interfaz, no de una segunda
pasada por los datos. Un informe que recalcula es un informe que puede
contradecir a la pantalla.

Dos cosas no se negocian aquí, igual que en el resto del sistema:

  · lo estimado se marca. En pantalla es ámbar; en papel, ámbar oscuro **más**
    el sufijo «est.», porque el color solo no basta para quien imprime en
    blanco y negro o no distingue ese tono.
  · las figuras se pintan tal como se vieron. Si el usuario eligió modo oscuro,
    en el PDF sale oscura: recolorear en silencio sería enseñar otra cosa.

Las figuras necesitan Chrome (vía kaleido) para volverse imagen. Es una
dependencia pesada y opcional: si no está, el informe **se genera igual** con
las tablas y la metodología, y dice en su lugar por qué falta la figura. Que
una dependencia opcional tumbe el entregable completo sería el peor canje.
"""

from __future__ import annotations

import datetime as _dt
import io
import os
from pathlib import Path
from typing import Any

# Paleta para PAPEL, no para pantalla. El ámbar de la interfaz (#F5C277) sobre
# blanco da un contraste de ~1.5:1 y sería ilegible; aquí se usa uno oscuro para
# el texto y el claro sólo como relleno de marca.
TINTA = (26, 21, 18)
TINTA_SUAVE = (110, 100, 92)
BOSQUE = (36, 102, 74)
AMBAR_TEXTO = (138, 93, 10)
AMBAR_RELLENO = (252, 240, 218)
CREMA = (251, 247, 241)
BORDE = (222, 214, 204)
TERRACOTA = (168, 74, 52)

FUENTES_CANDIDATAS = {
    "regular": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ],
    "bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ],
    "mono": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "C:/Windows/Fonts/consola.ttf",
    ],
}

ANCHO_UTIL = 180.0   # A4 (210 mm) menos los márgenes


class ErrorInforme(Exception):
    pass


def _buscar_fuente(clase: str) -> str | None:
    for ruta in FUENTES_CANDIDATAS[clase]:
        if os.path.exists(ruta):
            return ruta
    return None


class _Informe:
    """Envoltura de FPDF con encabezado, pie y el estilo de la casa."""

    def __init__(self, titulo: str, huella: str) -> None:
        from fpdf import FPDF

        self.titulo = titulo
        self.huella = huella
        self.unicode = False

        class _Pdf(FPDF):
            def header(interno) -> None:  # noqa: N805
                if interno.page_no() == 1:
                    return
                interno.set_font(self.familia, "", 8)
                interno.set_text_color(*TINTA_SUAVE)
                interno.cell(0, 6, self._t(titulo), align="L")
                interno.set_x(-60)
                interno.cell(50, 6, self._t(f"Abak · {huella[:12]}"), align="R")
                interno.ln(8)

            def footer(interno) -> None:  # noqa: N805
                interno.set_y(-14)
                interno.set_font(self.familia, "", 8)
                interno.set_text_color(*TINTA_SUAVE)
                interno.cell(0, 6, self._t(f"Página {interno.page_no()}"), align="C")

        self.familia = "Helvetica"
        self.familia_mono = "Courier"

        regular, bold, mono = (_buscar_fuente("regular"), _buscar_fuente("bold"),
                               _buscar_fuente("mono"))
        self.pdf = _Pdf(orientation="P", unit="mm", format="A4")
        if regular:
            # Con una TTF Unicode salen bien los acentos, el guión largo y el «·».
            self.pdf.add_font("Abak", "", regular)
            self.pdf.add_font("Abak", "B", bold or regular)
            self.familia = "Abak"
            self.unicode = True
        if mono:
            self.pdf.add_font("AbakMono", "", mono)
            self.familia_mono = "AbakMono"

        self.pdf.set_auto_page_break(auto=True, margin=18)
        self.pdf.set_margins(15, 15, 15)
        self.pdf.set_title(titulo)
        self.pdf.set_creator("Abak")

    # -- texto ---------------------------------------------------------------

    def _t(self, texto: Any) -> str:
        """Sin fuente Unicode, hay que degradar en vez de tronar."""
        s = str(texto if texto is not None else "")
        if self.unicode:
            return s
        reemplazos = {"—": "-", "–": "-", "·": "*", "“": '"', "”": '"', "‘": "'",
                      "’": "'", "…": "...", "²": "2", "³": "3", "≥": ">=", "≤": "<=",
                      "→": "->", "±": "+/-", "α": "alfa", "β": "beta", "ρ": "rho",
                      "λ": "lambda", "χ": "chi", "€": "EUR"}
        for viejo, nuevo in reemplazos.items():
            s = s.replace(viejo, nuevo)
        return s.encode("latin-1", "replace").decode("latin-1")

    def titulo_seccion(self, texto: str, nivel: int = 1) -> None:
        self.pdf.ln(4 if nivel > 1 else 6)
        self.pdf.set_font(self.familia, "B", 14 if nivel == 1 else 11)
        self.pdf.set_text_color(*(BOSQUE if nivel == 1 else TINTA))
        self.pdf.multi_cell(0, 7, self._t(texto))
        self.pdf.ln(1)

    def parrafo(self, texto: str, tam: int = 9.5, color: tuple[int, int, int] = TINTA) -> None:
        self.pdf.set_font(self.familia, "", tam)
        self.pdf.set_text_color(*color)
        self.pdf.multi_cell(0, 4.6, self._t(texto))
        self.pdf.ln(1)

    def viñetas(self, elementos: list[str], color: tuple[int, int, int] = TINTA) -> None:
        self.pdf.set_font(self.familia, "", 9)
        self.pdf.set_text_color(*color)
        for elemento in elementos:
            x = self.pdf.get_x()
            self.pdf.cell(4, 4.4, self._t("·"))
            self.pdf.set_x(x + 4)
            self.pdf.multi_cell(ANCHO_UTIL - 4, 4.4, self._t(elemento))
        self.pdf.ln(1)

    def aviso(self, texto: str) -> None:
        """Recuadro ámbar: es como se marca lo estimado y lo que hay que cuidar."""
        self.pdf.set_fill_color(*AMBAR_RELLENO)
        self.pdf.set_draw_color(*AMBAR_RELLENO)
        self.pdf.set_font(self.familia, "", 8.5)
        self.pdf.set_text_color(*AMBAR_TEXTO)
        self.pdf.multi_cell(0, 4.4, self._t(texto), fill=True, border=0,
                            padding=(2, 3, 2, 3))
        self.pdf.ln(2)

    # -- tablas --------------------------------------------------------------

    #: Con menos de esto por columna, el texto se recorta tanto que deja de
    #: leerse. Es preferible mostrar menos columnas y decirlo.
    ANCHO_MINIMO_COLUMNA = 15.0

    def tabla(self, columnas: list[dict], filas: list[list], tope: int = 40,
              n_total: int | None = None) -> None:
        if not columnas:
            return
        cabian = int(ANCHO_UTIL // self.ANCHO_MINIMO_COLUMNA)
        omitidas = max(0, len(columnas) - cabian)
        if omitidas:
            columnas = columnas[:cabian]
            filas = [fila[:cabian] for fila in filas]
        anchos = self._anchos(columnas, filas[:tope])
        self.pdf.set_font(self.familia, "B", 7.5)
        self.pdf.set_fill_color(*CREMA)
        self.pdf.set_draw_color(*BORDE)
        self.pdf.set_text_color(*TINTA_SUAVE)
        alto_y = self.pdf.get_y()
        for col, ancho in zip(columnas, anchos):
            estimada = bool(col.get("estimada"))
            self.pdf.set_text_color(*(AMBAR_TEXTO if estimada else TINTA_SUAVE))
            etiqueta = col["nombre"] + (" est." if estimada else "")
            self.pdf.cell(ancho, 6, self._t(self._recortar(etiqueta, ancho, 7.5)),
                          border="B", fill=True)
        self.pdf.ln(6)
        _ = alto_y

        self.pdf.set_font(self.familia, "", 7.5)
        for fila in filas[:tope]:
            if self.pdf.get_y() > 262:
                self.pdf.add_page()
            for valor, col, ancho in zip(fila, columnas, anchos):
                estimada = bool(col.get("estimada"))
                self.pdf.set_text_color(*(AMBAR_TEXTO if estimada else TINTA))
                texto = _formatear(valor)
                alineacion = "R" if isinstance(valor, (int, float)) else "L"
                self.pdf.cell(ancho, 5, self._t(self._recortar(texto, ancho, 7.5)),
                              border="B", align=alineacion)
            self.pdf.ln(5)

        total = n_total if n_total is not None else len(filas)
        avisos = []
        if total > tope:
            avisos.append(f"las primeras {tope} de {total:,} filas")
        if omitidas:
            avisos.append(f"las primeras {cabian} de {len(columnas) + omitidas} columnas")
        if avisos:
            self.parrafo("Se muestran " + " y ".join(avisos) +
                         ". La tabla completa va en el archivo exportado.",
                         tam=8, color=TINTA_SUAVE)
        self.pdf.ln(2)

    def _anchos(self, columnas: list[dict], filas: list[list]) -> list[float]:
        """Ancho por columna proporcional a su contenido, con mínimo y máximo."""
        pesos = []
        for i, col in enumerate(columnas):
            largo = len(str(col["nombre"])) + 2
            for fila in filas[:20]:
                if i < len(fila):
                    largo = max(largo, len(_formatear(fila[i])))
            pesos.append(min(max(largo, 6), 28))
        total = sum(pesos) or 1
        # Se reserva un margen para que las celdas no se toquen: sin él, un
        # número pegado al de al lado se lee como un número distinto.
        util = ANCHO_UTIL - 1.2 * len(columnas)
        return [max(self.ANCHO_MINIMO_COLUMNA, util * p / total) + 1.2 for p in pesos]

    def _recortar(self, texto: str, ancho: float, tam: float) -> str:
        # Se descuenta el margen entre celdas antes de calcular cuánto cabe.
        maximo = max(3, int((ancho - 1.4) / (tam * 0.19)))
        return texto if len(texto) <= maximo else texto[: maximo - 1] + "…"

    # -- figuras -------------------------------------------------------------

    def figura(self, figura_json: dict, titulo: str | None = None) -> None:
        png, error = _figura_a_png(figura_json)
        if png is None:
            self.aviso(
                f"No se pudo incluir la gráfica «{titulo or 'sin título'}» en el PDF. {error} "
                "Las tablas y la metodología de este informe no se ven afectadas.")
            return
        if self.pdf.get_y() > 180:
            self.pdf.add_page()
        self.pdf.image(io.BytesIO(png), w=ANCHO_UTIL)
        self.pdf.ln(3)

    def codigo(self, texto: str, tope_lineas: int = 900) -> None:
        self.pdf.set_font(self.familia_mono, "", 6.8)
        self.pdf.set_text_color(*TINTA)
        lineas = texto.splitlines()
        for linea in lineas[:tope_lineas]:
            if self.pdf.get_y() > 268:
                self.pdf.add_page()
            self.pdf.cell(0, 3.2, self._t(linea[:118]))
            self.pdf.ln(3.2)
        if len(lineas) > tope_lineas:
            self.parrafo(f"[…] {len(lineas) - tope_lineas} líneas más. "
                         "El archivo completo va en el paquete exportado.",
                         tam=8, color=TINTA_SUAVE)

    def salida(self) -> bytes:
        return bytes(self.pdf.output())


def _formatear(valor: Any) -> str:
    if valor is None:
        return "—"
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    if isinstance(valor, float):
        if valor != valor:  # NaN
            return "—"
        if abs(valor) >= 1e6 or (valor != 0 and abs(valor) < 1e-4):
            return f"{valor:.3e}"
        return f"{valor:,.4f}".rstrip("0").rstrip(".") or "0"
    if isinstance(valor, int):
        return f"{valor:,}"
    return str(valor)


def _figura_a_png(figura_json: dict) -> tuple[bytes | None, str]:
    """Plotly -> PNG. Devuelve (None, motivo) si no se puede, sin lanzar.

    Requiere Chrome a través de kaleido. En un contenedor sin navegador esto
    falla, y es exactamente por eso que el informe tiene que seguir saliendo.
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None, "Falta plotly en este servidor."
    try:
        figura = go.Figure(data=figura_json.get("data", []),
                           layout=figura_json.get("layout", {}))
        return figura.to_image(format="png", width=1400, height=800, scale=2), ""
    except Exception as exc:
        detalle = str(exc).strip().splitlines()
        motivo = detalle[0] if detalle else type(exc).__name__
        if "chrome" in str(exc).lower():
            motivo = ("Convertir una gráfica a imagen necesita Chrome en el servidor. "
                      "Instálalo, o apunta la variable BROWSER_PATH a un Chromium existente.")
        return None, motivo


# ---------------------------------------------------------------------------
# El informe
# ---------------------------------------------------------------------------


def informe_pdf(
    *,
    titulo: str,
    huella: str,
    semilla: int,
    nodos: dict[str, dict],
    orden: list[str] | None = None,
    metodologia: str | None = None,
    codigo: str | None = None,
    autor: str | None = None,
    solo_nodo: str | None = None,
) -> bytes:
    """Arma el PDF a partir de los artefactos de una ejecución.

    `nodos` es el mismo diccionario que guarda la ejecución: {id: {etiqueta,
    estado, ms, artefactos}}. No se recalcula nada.
    """
    informe = _Informe(titulo, huella)
    pdf = informe.pdf
    ids = [n for n in (orden or list(nodos)) if n in nodos]
    if solo_nodo:
        ids = [n for n in ids if n == solo_nodo]
        if not ids:
            raise ErrorInforme(f"La ejecución no tiene resultados del bloque «{solo_nodo}».")

    # --- portada ------------------------------------------------------------
    pdf.add_page()
    pdf.ln(28)
    pdf.set_font(informe.familia, "B", 24)
    pdf.set_text_color(*TINTA)
    pdf.multi_cell(0, 11, informe._t(titulo))
    pdf.ln(4)
    pdf.set_font(informe.familia, "", 11)
    pdf.set_text_color(*TINTA_SUAVE)
    pdf.multi_cell(0, 6, informe._t(
        "Informe generado por Abak" + (f" para {autor}" if autor else "")))
    pdf.ln(10)

    pdf.set_draw_color(*BORDE)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(6)

    hechos = [
        ("Fecha", _dt.date.today().isoformat()),
        ("Huella del análisis", huella[:24]),
        ("Semilla de aleatoriedad", str(semilla)),
        ("Pasos con resultado", str(len(ids))),
    ]
    pdf.set_font(informe.familia, "", 10)
    for etiqueta, valor in hechos:
        pdf.set_text_color(*TINTA_SUAVE)
        pdf.cell(58, 6.5, informe._t(etiqueta))
        pdf.set_text_color(*TINTA)
        pdf.cell(0, 6.5, informe._t(valor))
        pdf.ln(6.5)

    pdf.ln(8)
    informe.parrafo(
        "La huella identifica esta versión exacta del análisis. Con la misma huella, la misma "
        "semilla y los mismos datos, los resultados se repiten. El código que los produjo se "
        "exporta desde Abak y es el mismo que se ejecutó, no una reconstrucción.",
        tam=9, color=TINTA_SUAVE)

    estimadas_totales = _columnas_estimadas(nodos, ids)
    if estimadas_totales:
        pdf.ln(4)
        informe.aviso(
            "Este informe contiene datos estimados, marcados en ámbar y con el sufijo «est.». "
            "No son mediciones: salieron de un modelo, un pronóstico o un filtro. Al citarlos "
            "fuera de aquí hay que decirlo. Columnas afectadas: "
            + ", ".join(sorted(estimadas_totales)[:18])
            + ("…" if len(estimadas_totales) > 18 else "") + ".")

    # --- resultados ---------------------------------------------------------
    pdf.add_page()
    informe.titulo_seccion("Resultados")

    for i, nodo_id in enumerate(ids, start=1):
        datos = nodos[nodo_id]
        artefactos = datos.get("artefactos") or {}
        error = datos.get("error")
        if not artefactos and not error:
            continue

        informe.titulo_seccion(f"{i}. {datos.get('etiqueta') or nodo_id}", nivel=2)
        if datos.get("ms") is not None:
            informe.parrafo(f"Tiempo de cómputo: {datos['ms']} ms", tam=8, color=TINTA_SUAVE)

        if error:
            pdf.set_text_color(*TERRACOTA)
            informe.parrafo(f"Este paso falló: {error.get('titulo', '')}", tam=9.5, color=TERRACOTA)
            informe.parrafo(error.get("detalle", ""), tam=9, color=TINTA_SUAVE)
            continue

        for puerto, artefacto in artefactos.items():
            _seccion_artefacto(informe, artefacto, puerto)

    # --- metodología --------------------------------------------------------
    if metodologia:
        pdf.add_page()
        _markdown(informe, metodologia)

    # --- apéndice de código -------------------------------------------------
    if codigo:
        pdf.add_page()
        informe.titulo_seccion("Apéndice: el código que se ejecutó")
        informe.parrafo(
            "Este no es un código equivalente escrito para el informe: es el mismo programa que "
            "produjo los resultados de arriba. Corre en cualquier máquina con Python y las "
            "bibliotecas que importa.", tam=9, color=TINTA_SUAVE)
        pdf.ln(2)
        informe.codigo(codigo)

    return informe.salida()


def _seccion_artefacto(informe: _Informe, artefacto: dict, puerto: str) -> None:
    tipo = artefacto.get("tipo")
    titulo = artefacto.get("titulo") or puerto

    if tipo == "tabla":
        informe.parrafo(titulo, tam=9.5)
        informe.tabla(artefacto.get("columnas", []), artefacto.get("filas", []),
                      n_total=artefacto.get("n_filas"))

    elif tipo == "modelo":
        informe.parrafo(titulo, tam=9.5)
        columnas = [
            {"nombre": "Variable", "estimada": False},
            {"nombre": "Coeficiente", "estimada": True},
            {"nombre": "Error est.", "estimada": True},
            {"nombre": "Estadístico", "estimada": True},
            {"nombre": "p", "estimada": True},
            {"nombre": "IC 95%", "estimada": True},
        ]
        filas = []
        for c in artefacto.get("coeficientes", []):
            ic = ("—" if c.get("ic_bajo") is None
                  else f"[{_formatear(c['ic_bajo'])}, {_formatear(c['ic_alto'])}]")
            filas.append([c.get("variable"), c.get("coeficiente"), c.get("error_estandar"),
                          c.get("estadistico"), c.get("p_valor"), ic])
        informe.tabla(columnas, filas, tope=60)
        diagnosticos = artefacto.get("diagnosticos") or {}
        if diagnosticos:
            informe.parrafo(
                " · ".join(f"{k}: {_formatear(v)}" for k, v in diagnosticos.items()),
                tam=8.5, color=TINTA_SUAVE)
        informe.parrafo(
            "*** significativo al 1%, ** al 5%, * al 10%. Que un coeficiente sea significativo "
            "no lo vuelve grande: hay que mirar también su tamaño en las unidades del problema.",
            tam=8, color=TINTA_SUAVE)

    elif tipo == "figura":
        informe.parrafo(titulo, tam=9.5)
        informe.figura(artefacto.get("figura", {}), titulo)

    elif tipo == "detalle":
        informe.parrafo(titulo, tam=9.5)
        informe.viñetas([f"{k.replace('_', ' ')}: {_formatear(v)}"
                         for k, v in (artefacto.get("datos") or {}).items()])

    elif tipo == "escalar":
        informe.parrafo(f"{titulo}: {_formatear(artefacto.get('valor'))}", tam=9.5)


def _markdown(informe: _Informe, texto: str) -> None:
    """Render mínimo del Markdown que genera la nota metodológica."""
    for linea in texto.split("\n"):
        limpia = linea.rstrip()
        if not limpia:
            informe.pdf.ln(2)
        elif limpia.startswith("# "):
            informe.titulo_seccion(limpia[2:])
        elif limpia.startswith("## "):
            informe.titulo_seccion(limpia[3:], nivel=2)
        elif limpia.startswith("- "):
            informe.viñetas([_sin_marcas(limpia[2:])])
        elif limpia.startswith("> "):
            informe.parrafo(_sin_marcas(limpia[2:]), tam=9, color=TINTA_SUAVE)
        elif limpia.startswith("---"):
            informe.pdf.ln(2)
        else:
            informe.parrafo(_sin_marcas(limpia))


def _sin_marcas(texto: str) -> str:
    return texto.replace("**", "").replace("`", "").replace("*", "")


def _columnas_estimadas(nodos: dict[str, dict], ids: list[str]) -> set[str]:
    estimadas: set[str] = set()
    for nodo_id in ids:
        for artefacto in (nodos[nodo_id].get("artefactos") or {}).values():
            for columna in (artefacto.get("columnas") or []):
                if columna.get("estimada"):
                    estimadas.add(str(columna.get("nombre")))
    return estimadas
