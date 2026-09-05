"""Emision: del IR a un modulo de Python.

El resultado de emitir es UN arbol por bloque. De ahi salen las dos cosas que
hace Abaco, y salen del mismo objeto:

    compile(arbol)      -> lo que se ejecuta
    ast.unparse(arbol)  -> lo que se exporta

No hay una segunda ruta. La divergencia entre "lo que corrio" y "el codigo que
te ensenamos" no esta mitigada: es imposible de representar.

El texto se ensambla bloque por bloque en vez de desparramar un unico
`ast.unparse` porque el AST de Python no guarda comentarios, y los comentarios
en espanol sobre cada paso son justamente lo que vuelve legible el script para
alguien que no programa.
"""

from __future__ import annotations

import ast
import datetime as _dt
from dataclasses import dataclass, field

from ..graph.compilador import Instruccion, Programa
from ..registry.base import obtener
from .contexto import BloqueCodigo, ContextoEmision, Import, resolver_ayudantes

VERSION_ABACO = "0.1.0"

ANCHO = 78


@dataclass
class BloqueEmitido:
    instruccion: Instruccion
    arbol: ast.Module
    notas: list[str] = field(default_factory=list)


@dataclass
class Emision:
    preludio: ast.Module
    bloques: list[BloqueEmitido]
    epilogo: ast.Module
    imports: list[Import]
    ayudantes: list[str]
    programa: Programa


def emitir(programa: Programa) -> Emision:
    """Recorre el IR y pide a cada nodo su bloque de codigo."""
    bloques: list[BloqueEmitido] = []
    imports: list[Import] = []
    ayudantes: list[str] = []
    claves_import: set[tuple[str, str | None, str | None]] = set()

    for ins in programa.instrucciones:
        spec = obtener(ins.op)
        ctx = ContextoEmision(
            nodo_id=ins.nodo_id, etiqueta=ins.etiqueta, params=ins.params,
            entradas=ins.entradas, salidas=ins.salidas, esquemas=ins.esquemas_entrada,
        )
        bloque: BloqueCodigo = spec().emit(ctx) or ctx.fin()
        for imp in bloque.imports:
            if imp.clave() not in claves_import:
                claves_import.add(imp.clave())
                imports.append(imp)
        for ayu in bloque.ayudantes:
            if ayu not in ayudantes:
                ayudantes.append(ayu)
        arbol = ast.Module(body=bloque.cuerpo, type_ignores=[])
        ast.fix_missing_locations(arbol)
        notas = list(bloque.notas)
        if ins.notas:
            notas.append(ins.notas)
        bloques.append(BloqueEmitido(instruccion=ins, arbol=arbol, notas=notas))

    resueltos = resolver_ayudantes(ayudantes)
    for ayu in resueltos:
        for modulo, alias in ayu.imports:
            imp = Import(modulo=modulo, alias=alias)
            if imp.clave() not in claves_import:
                claves_import.add(imp.clave())
                imports.append(imp)

    ayudantes_ast = [stmt for a in resueltos for stmt in a.como_ast()]
    preludio = _preludio(programa, imports, ayudantes_ast)
    epilogo = _epilogo(programa)
    return Emision(preludio=preludio, bloques=bloques, epilogo=epilogo,
                   imports=imports, ayudantes=[a.nombre for a in resueltos], programa=programa)


def _preludio(programa: Programa, imports: list[Import], ayudantes: list[ast.stmt]) -> ast.Module:
    cuerpo: list[ast.stmt] = []
    for imp in _ordenar_imports(imports):
        cuerpo.append(imp.como_ast())

    if any(obtener(i.op).necesita_datos for i in programa.instrucciones):
        # Una sola definicion que significa lo mismo al ejecutar y al exportar:
        # el worker pone ABACO_DATOS, y quien descomprime el .zip encuentra
        # `datos/` al lado del script. Sin ramas, sin dos versiones del codigo.
        cuerpo.extend(ast.parse(
            "import os\n"
            "from pathlib import Path\n"
            "RUTA_DATOS = Path(os.environ.get('ABACO_DATOS', 'datos'))\n"
        ).body)
    if programa.semilla is not None:
        cuerpo.extend(
            ast.parse(
                "import random as _random\n"
                "_random.seed(SEMILLA)\n"
                "try:\n"
                "    import numpy as _np_semilla\n"
                "    _np_semilla.random.seed(SEMILLA)\n"
                "except ImportError:\n"
                "    pass\n".replace("SEMILLA", str(programa.semilla))
            ).body
        )
    cuerpo.extend(ayudantes)
    modulo = ast.Module(body=cuerpo, type_ignores=[])
    ast.fix_missing_locations(modulo)
    return modulo


def _ordenar_imports(imports: list[Import]) -> list[Import]:
    import sys

    estandar = set(getattr(sys, "stdlib_module_names", set()))

    def llave(i: Import) -> tuple[int, str, str]:
        raiz = (i.desde or i.modulo).split(".")[0]
        grupo = 0 if raiz in estandar else 1
        return (grupo, i.desde or i.modulo, i.alias or "")

    return sorted(imports, key=llave)


def _epilogo(programa: Programa) -> ast.Module:
    """Lo unico que separa ejecutar de exportar, y esta del lado inocuo.

    Al ejecutar, los resultados se cosechan leyendo el espacio de nombres, sin
    tocar el programa. Al exportar, hace falta que el script *ensene* algo
    cuando alguien lo corre en su maquina, asi que se agregan `print` y `show`.
    Ninguna de estas sentencias altera el analisis.
    """
    cuerpo: list[ast.stmt] = []
    for ins in programa.instrucciones:
        spec = obtener(ins.op)
        for puerto in spec.salidas:
            var = ins.salidas.get(puerto.nombre)
            if not var:
                continue
            if puerto.tipo == "modelo":
                cuerpo.extend(ast.parse(f"print({var}.summary())").body)
            elif puerto.tipo == "figura":
                cuerpo.extend(ast.parse(f"{var}.show()").body)
            elif spec.terminal and puerto.tipo in ("tabla", "serie", "panel", "geotabla"):
                cuerpo.extend(ast.parse(f"print({var}.head(20).to_string())").body)
    modulo = ast.Module(body=cuerpo, type_ignores=[])
    ast.fix_missing_locations(modulo)
    return modulo


# ---------------------------------------------------------------------------
# Render a texto: el shadow code que el usuario exporta
# ---------------------------------------------------------------------------


#: Las comillas triples cerrarian el docstring del encabezado.
_COMILLAS_TRIPLES = '"' * 3
_COMILLAS_SUAVES = "'" * 3


def _seguro(texto: str) -> str:
    """Texto del usuario listo para meterse en un comentario o en el docstring.

    Es la UNICA frontera por la que texto libre del usuario llega al archivo
    generado: la etiqueta que le puso a un bloque, su nota sobre un paso, el
    titulo del analisis. Todo eso acaba en comentarios.

    Dos cosas hay que neutralizar. Un salto de linea cerraria el comentario y
    lo que siguiera pasaria a ser CODIGO. Unas comillas triples cerrarian el
    docstring del encabezado, con el mismo resultado. `textwrap` colapsa los
    saltos por omision, pero un valor por omision no es una garantia.
    """
    return " ".join(str(texto).split()).replace(_COMILLAS_TRIPLES, _COMILLAS_SUAVES)


def _regla(texto: str = "", char: str = "─") -> str:
    if not texto:
        return "# " + char * (ANCHO - 2)
    prefijo = f"# {char}{char} {_seguro(texto)[:ANCHO - 8]} "
    return prefijo + char * max(3, ANCHO - len(prefijo))


def _envolver(texto: str, prefijo: str = "# ") -> list[str]:
    """Texto libre -> lineas de comentario, sin posibilidad de salirse."""
    import textwrap

    lineas = textwrap.wrap(_seguro(texto), width=ANCHO, initial_indent=prefijo,
                           subsequent_indent=prefijo) or [prefijo.rstrip()]
    return [linea if linea.lstrip().startswith("#") else f"{prefijo}{linea}" for linea in lineas]


def a_texto(emision: Emision, *, con_epilogo: bool = True, autor: str | None = None) -> str:
    """El script `.py` autonomo. Sin `import abaco` por ningun lado."""
    p = emision.programa
    hoy = _dt.date.today().isoformat()
    titulo = _seguro(p.titulo)
    lineas: list[str] = [_COMILLAS_TRIPLES]
    lineas.append(titulo)
    lineas.append("=" * len(titulo))
    lineas.append("")
    lineas.append("Script generado por Abaco. Es el mismo codigo que se ejecuto en el")
    lineas.append("lienzo: no es una reconstruccion ni un equivalente aproximado.")
    lineas.append("")
    lineas.append(f"Fecha        : {hoy}")
    if autor:
        lineas.append(f"Autor        : {_seguro(autor)}")
    lineas.append(f"Abaco        : v{VERSION_ABACO}")
    lineas.append(f"Huella grafo : {p.huella_grafo[:16]}")
    lineas.append(f"Semilla      : {p.semilla}")
    lineas.append("")
    lineas.append("Para reproducirlo hace falta Python y las bibliotecas que se importan")
    lineas.append("abajo. Abaco no es una de ellas.")
    lineas.append(_COMILLAS_TRIPLES)
    lineas.append("")

    if emision.preludio.body:
        lineas.append(_regla("Preparacion"))
        lineas.append(ast.unparse(emision.preludio))
        lineas.append("")

    for i, bloque in enumerate(emision.bloques, start=1):
        ins = bloque.instruccion
        lineas.append("")
        lineas.append(_regla(f"{i}. {ins.etiqueta}"))
        for nota in bloque.notas:
            lineas.extend(_envolver(nota))
        if not bloque.arbol.body:
            lineas.append("# (este paso no genera codigo)")
            continue
        lineas.append(ast.unparse(bloque.arbol))

    if con_epilogo and emision.epilogo.body:
        lineas.append("")
        lineas.append(_regla("Resultados"))
        lineas.extend(_envolver(
            "Al ejecutar dentro de Abaco los resultados se leen del espacio de "
            "nombres; aqui se imprimen para que el script tambien sirva solo."))
        lineas.append(ast.unparse(emision.epilogo))

    lineas.append("")
    return "\n".join(lineas)
