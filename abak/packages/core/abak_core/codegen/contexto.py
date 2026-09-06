"""Contexto de emision: la unica forma que tiene un nodo de tocar el mundo.

Aqui vive la regla mas importante del sistema:

    NUNCA se construye codigo con f-strings.

Un nodo arma **nodos AST**. Los parametros del usuario entran al arbol como
`ast.Constant`, es decir como *datos*, no como texto que se vuelve a parsear.
Eso elimina por construccion la inyeccion de codigo: una columna que se llame
`x); import os; os.system("rm -rf /"); (` acaba siendo una cadena literal con
ese contenido exacto, y pandas se queja de que no existe esa columna. Que es
justo lo que debe pasar.

Escribir AST a mano para sesenta nodos seria insoportable, asi que hay un
mecanismo de **plantillas con huecos**: la plantilla es codigo fuente escrito
por nosotros (conjunto cerrado, revisado, versionado) y los huecos se rellenan
sustituyendo nodos AST, no texto. Los huecos van en MAYUSCULAS:

    ctx.plantilla("SALIDA = sm.OLS(Y, X).fit(cov_type=COV)",
                  SALIDA=ctx.salida("modelo"), Y=..., COV=ctx.lit("HC1"))

Lo que se parsea siempre es la plantilla nuestra; lo que viene del usuario
siempre es una hoja del arbol.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any

from ..registry.base import AYUDANTES, Ayudante


@dataclass
class Import:
    modulo: str
    alias: str | None = None
    desde: str | None = None

    def clave(self) -> tuple[str, str | None, str | None]:
        return (self.modulo, self.alias, self.desde)

    def como_ast(self) -> ast.stmt:
        if self.desde:
            return ast.ImportFrom(
                module=self.desde,
                names=[ast.alias(name=self.modulo, asname=self.alias)],
                level=0,
            )
        return ast.Import(names=[ast.alias(name=self.modulo, asname=self.alias)])

    @property
    def nombre_local(self) -> str:
        return self.alias or (self.modulo if self.desde else self.modulo.split(".")[0])


@dataclass
class BloqueCodigo:
    """Lo que devuelve `emit()`: sentencias mas lo que necesitan para correr."""

    cuerpo: list[ast.stmt] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)
    ayudantes: list[str] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)


class ErrorEmision(Exception):
    """Error del desarrollador del nodo, no del usuario."""


class _Sustituir(ast.NodeTransformer):
    def __init__(self, huecos: dict[str, ast.AST]):
        self.huecos = huecos
        self.usados: set[str] = set()

    def visit_Name(self, nodo: ast.Name) -> Any:
        if nodo.id not in self.huecos:
            return nodo
        self.usados.add(nodo.id)
        reemplazo = self.huecos[nodo.id]
        nuevo = ast.copy_location(_clonar(reemplazo), nodo)
        # Un hueco puede aparecer como destino de asignacion; hay que ajustar
        # el contexto o `compile()` lo rechaza.
        if isinstance(nodo.ctx, (ast.Store, ast.Del)) and hasattr(nuevo, "ctx"):
            nuevo.ctx = nodo.ctx  # type: ignore[attr-defined]
        return ast.fix_missing_locations(nuevo)


def _clonar(nodo: ast.AST) -> ast.AST:
    """Copia profunda: el mismo hueco puede usarse dos veces en una plantilla."""
    return ast.parse(ast.unparse(nodo), mode="eval").body if isinstance(nodo, ast.expr) else nodo


class ContextoEmision:
    """Se le entrega a `EspecNodo.emit()`. Acumula imports y ayudantes usados."""

    def __init__(
        self,
        *,
        nodo_id: str,
        etiqueta: str,
        params: Any,
        entradas: dict[str, str],
        salidas: dict[str, str],
        esquemas: dict[str, Any] | None = None,
        proyeccion: set[str] | None = None,
    ) -> None:
        self.nodo_id = nodo_id
        self.etiqueta = etiqueta
        self.params = params
        self._entradas = entradas
        self._salidas = salidas
        self.esquemas = esquemas or {}
        #: Columnas que el grafo entero necesita, o None si no se puede podar.
        self.proyeccion = proyeccion
        self.bloque = BloqueCodigo()

    # -- entradas y salidas ---------------------------------------------------

    def entrada(self, puerto: str) -> ast.Name:
        """Variable de la que viene el valor conectado a ese puerto."""
        if puerto not in self._entradas:
            raise ErrorEmision(f"{self.nodo_id}: el puerto de entrada {puerto!r} no esta conectado")
        return ast.Name(id=self._entradas[puerto], ctx=ast.Load())

    def entradas_multiples(self, puerto: str) -> list[ast.Name]:
        """Para puertos `multiple=True` (asi se apilan las capas de un grafico)."""
        crudo = self._entradas.get(puerto, "")
        if not crudo:
            return []
        return [ast.Name(id=v, ctx=ast.Load()) for v in crudo.split("\x00")]

    def tiene_entrada(self, puerto: str) -> bool:
        return bool(self._entradas.get(puerto))

    def salida(self, puerto: str) -> ast.Name:
        if puerto not in self._salidas:
            raise ErrorEmision(f"{self.nodo_id}: el puerto de salida {puerto!r} no existe")
        return ast.Name(id=self._salidas[puerto], ctx=ast.Store())

    def ref_salida(self, puerto: str) -> ast.Name:
        """La misma variable de salida, pero para leerla.

        Hace falta cuando un nodo escribe su salida en dos pasos: primero copia
        y luego modifica columnas sobre la copia.
        """
        return ast.Name(id=self._salidas[puerto], ctx=ast.Load())

    def nombre_salida(self, puerto: str) -> str:
        return self._salidas[puerto]

    def columnas_a_leer(self, disponibles: list[str]) -> list[str] | None:
        """De las columnas del archivo, cuáles hacen falta de verdad.

        Devuelve `None` cuando hay que leerlas todas: o porque algún nodo del
        grafo puede tocar columnas que no nombró, o porque no se ahorra nada.
        """
        if self.proyeccion is None or not disponibles:
            return None
        usadas = [c for c in disponibles if c in self.proyeccion]
        if not usadas or len(usadas) == len(disponibles):
            return None
        return usadas

    def esquema(self, puerto: str = "datos") -> Any:
        from ..graph.spec import Esquema

        return self.esquemas.get(puerto) or Esquema()

    def temporal(self, sufijo: str) -> ast.Name:
        """Variable auxiliar del bloque, visible en el script exportado.

        El nombre lo determina el sufijo, no un contador: pedir dos veces el
        mismo sufijo devuelve la misma variable, que es justo lo que hace falta
        para escribirla en una linea y leerla en otra.
        """
        base = self._salidas.get(next(iter(self._salidas), ""), self.nodo_id)
        return ast.Name(id=f"_{base}_{sufijo}", ctx=ast.Load())

    # -- parametros -----------------------------------------------------------

    def p(self, nombre: str) -> Any:
        return getattr(self.params, nombre)

    def lit(self, valor: Any) -> ast.expr:
        """Valor de Python -> literal AST. Es la frontera dato/codigo."""
        try:
            return ast.parse(repr(valor), mode="eval").body
        except SyntaxError as exc:  # pragma: no cover - defensivo
            raise ErrorEmision(f"{self.nodo_id}: no se puede literalizar {valor!r}") from exc

    def lista(self, elementos: list[ast.expr]) -> ast.expr:
        """Varias expresiones AST en una lista literal. Lo usan los puertos multiples."""
        return ast.List(elts=list(elementos), ctx=ast.Load())

    def plit(self, nombre: str) -> ast.expr:
        """Atajo de `lit(p(nombre))`, que es lo que se hace el 90% de las veces."""
        return self.lit(self.p(nombre))

    # -- dependencias ---------------------------------------------------------

    def importar(self, modulo: str, alias: str | None = None, desde: str | None = None) -> ast.Name:
        imp = Import(modulo=modulo, alias=alias, desde=desde)
        if imp.clave() not in {i.clave() for i in self.bloque.imports}:
            self.bloque.imports.append(imp)
        return ast.Name(id=imp.nombre_local, ctx=ast.Load())

    def usar_ayudante(self, nombre: str) -> ast.Name:
        if nombre not in AYUDANTES:
            raise ErrorEmision(f"{self.nodo_id}: no existe el ayudante {nombre!r}")
        if nombre not in self.bloque.ayudantes:
            self.bloque.ayudantes.append(nombre)
        return ast.Name(id=nombre, ctx=ast.Load())

    def nota(self, texto: str) -> None:
        """Comentario en espanol que precede al bloque en el script exportado."""
        self.bloque.notas.append(texto)

    # -- construccion de codigo ----------------------------------------------

    def plantilla(self, fuente: str, **huecos: ast.AST) -> list[ast.stmt]:
        """Parsea una plantilla nuestra y sustituye los huecos por nodos AST."""
        try:
            arbol = ast.parse(fuente.strip())
        except SyntaxError as exc:
            raise ErrorEmision(f"{self.nodo_id}: plantilla invalida: {fuente!r}") from exc
        sustituidor = _Sustituir(huecos)
        arbol = sustituidor.visit(arbol)
        sobrantes = set(huecos) - sustituidor.usados
        if sobrantes:
            raise ErrorEmision(
                f"{self.nodo_id}: la plantilla no usa los huecos {sorted(sobrantes)}"
            )
        ast.fix_missing_locations(arbol)
        return arbol.body

    def emitir(self, fuente: str, **huecos: ast.AST) -> None:
        """`plantilla()` + agregar al cuerpo. Es la forma normal de escribir un nodo."""
        self.bloque.cuerpo.extend(self.plantilla(fuente, **huecos))

    def fin(self) -> BloqueCodigo:
        return self.bloque


# ---------------------------------------------------------------------------
# Resolucion de ayudantes en orden de dependencia
# ---------------------------------------------------------------------------


def resolver_ayudantes(pedidos: list[str]) -> list[Ayudante]:
    """Cierre transitivo de los ayudantes usados, en orden topologico.

    Se emiten solo los que el grafo realmente usa: un analisis que no toca
    econometria espacial no arrastra el constructor de matrices de pesos.
    """
    orden: list[str] = []
    visitando: set[str] = set()

    def visitar(nombre: str) -> None:
        if nombre in orden:
            return
        if nombre in visitando:
            raise ErrorEmision(f"Ciclo entre ayudantes en {nombre!r}")
        if nombre not in AYUDANTES:
            raise ErrorEmision(f"No existe el ayudante {nombre!r}")
        visitando.add(nombre)
        for dep in AYUDANTES[nombre].depende_de:
            visitar(dep)
        visitando.discard(nombre)
        orden.append(nombre)

    for nombre in pedidos:
        visitar(nombre)
    return [AYUDANTES[n] for n in orden]
