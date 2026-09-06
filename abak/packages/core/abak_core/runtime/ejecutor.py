"""Ejecutor: corre el programa bloque por bloque sobre un espacio de nombres.

El worker no ejecuta el programa de un golpe. Lo recorre nodo por nodo, sobre
un unico espacio de nombres compartido, por cuatro razones concretas:

  1. progreso real por nodo en el lienzo, no una barra que finge;
  2. cache: se salta el bloque pero se reponen sus variables, asi que el resto
     del programa no nota la diferencia;
  3. errores localizados: el `try` envuelve un bloque, y el bloque es un nodo;
  4. cancelar entre bloques, sin matar el proceso.

Lo que se compila son los MISMOS objetos AST que `ast.unparse` convierte en el
archivo exportado.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ..codegen.emisor import Emision, emitir
from ..graph.compilador import Programa
from ..registry.base import obtener
from .cache import Cache, CacheMemoria
from .errores import ErrorTraducido, traducir


@dataclass
class ResultadoNodo:
    nodo_id: str
    op: str
    etiqueta: str
    estado: str                      # "listo" | "cacheado" | "error" | "omitido"
    ms: int = 0
    artefactos: dict[str, Any] = field(default_factory=dict)
    error: ErrorTraducido | None = None


@dataclass
class ResultadoEjecucion:
    ok: bool
    nodos: list[ResultadoNodo] = field(default_factory=list)
    bitacora: list[str] = field(default_factory=list)
    ms_total: int = 0
    script: str = ""

    def por_nodo(self) -> dict[str, ResultadoNodo]:
        return {r.nodo_id: r for r in self.nodos}


Progreso = Callable[[str, str, dict[str, Any]], None]


class Ejecutor:
    def __init__(self, cache: Cache | None = None, progreso: Progreso | None = None,
                 cancelado: Callable[[], bool] | None = None) -> None:
        self.cache = cache or CacheMemoria()
        self.progreso = progreso or (lambda *_a, **_k: None)
        self.cancelado = cancelado or (lambda: False)

    def ejecutar(self, programa: Programa, emision: Emision | None = None) -> ResultadoEjecucion:
        if programa.hay_errores:
            errores = [d for d in programa.diagnosticos if d.severidad == "error"]
            return ResultadoEjecucion(
                ok=False,
                bitacora=[f"[compilacion] {d.codigo}: {d.mensaje}" for d in errores],
            )

        emision = emision or emitir(programa)
        inicio_total = time.perf_counter()
        resultado = ResultadoEjecucion(ok=True)
        espacio: dict[str, Any] = {"__name__": "__abak__", "__builtins__": __builtins__}

        try:
            exec(compile(emision.preludio, "<abak:preludio>", "exec"), espacio)
        except Exception as exc:
            tr = traducir(exc)
            resultado.ok = False
            resultado.bitacora.append(f"[preludio] {tr.excepcion}")
            resultado.bitacora.append(tr.traceback)
            return resultado

        padres = _mapa_padres(programa)
        fallidos: set[str] = set()
        for bloque in emision.bloques:
            ins = bloque.instruccion
            if self.cancelado():
                resultado.bitacora.append("[cancelado] la ejecucion se detuvo a peticion del usuario")
                resultado.ok = False
                break

            if padres.get(ins.nodo_id, set()) & fallidos:
                resultado.nodos.append(ResultadoNodo(
                    nodo_id=ins.nodo_id, op=ins.op, etiqueta=ins.etiqueta, estado="omitido"))
                fallidos.add(ins.nodo_id)
                self.progreso(ins.nodo_id, "omitido", {})
                continue

            spec = obtener(ins.op)
            self.progreso(ins.nodo_id, "corriendo", {"etiqueta": ins.etiqueta})
            inicio = time.perf_counter()

            if spec.cacheable and self.cache.tiene(ins.huella):
                espacio.update(self.cache.leer(ins.huella))
                artefactos = self._resumir(spec, ins, espacio, resultado)
                r = ResultadoNodo(nodo_id=ins.nodo_id, op=ins.op, etiqueta=ins.etiqueta,
                                  estado="cacheado", ms=0, artefactos=artefactos)
                resultado.nodos.append(r)
                self.progreso(ins.nodo_id, "cacheado", {})
                continue

            try:
                exec(compile(bloque.arbol, f"<abak:{ins.nodo_id}>", "exec"), espacio)
            except Exception as exc:
                tr = traducir(exc, ins.nodo_id)
                resultado.ok = False
                fallidos.add(ins.nodo_id)
                resultado.nodos.append(ResultadoNodo(
                    nodo_id=ins.nodo_id, op=ins.op, etiqueta=ins.etiqueta, estado="error",
                    ms=int((time.perf_counter() - inicio) * 1000), error=tr))
                resultado.bitacora.append(f"[{ins.etiqueta}] {tr.excepcion}")
                resultado.bitacora.append(tr.traceback)
                self.progreso(ins.nodo_id, "error", {"titulo": tr.titulo, "detalle": tr.detalle})
                continue

            # Cosecha de nombres: el programa no sabe que lo estan observando.
            valores = {var: espacio.get(var) for var in ins.salidas.values()}
            if spec.cacheable:
                self.cache.escribir(ins.huella, valores)
            artefactos = self._resumir(spec, ins, espacio, resultado)
            ms = int((time.perf_counter() - inicio) * 1000)
            resultado.nodos.append(ResultadoNodo(
                nodo_id=ins.nodo_id, op=ins.op, etiqueta=ins.etiqueta,
                estado="listo", ms=ms, artefactos=artefactos))
            resultado.bitacora.append(f"[{ins.etiqueta}] listo en {ms} ms")
            self.progreso(ins.nodo_id, "listo", {"ms": ms})

        resultado.ms_total = int((time.perf_counter() - inicio_total) * 1000)
        return resultado

    def _resumir(self, spec: Any, ins: Any, espacio: dict[str, Any],
                 resultado: ResultadoEjecucion) -> dict[str, Any]:
        """Resumen para la interfaz. Un fallo aqui no invalida el analisis."""
        salidas = {puerto: espacio.get(var) for puerto, var in ins.salidas.items()}
        try:
            return spec().resumir(salidas, ins.params)
        except Exception as exc:
            resultado.bitacora.append(f"[{ins.etiqueta}] no se pudo resumir el resultado: {exc}")
            return {}


def _mapa_padres(programa: Programa) -> dict[str, set[str]]:
    """nodo -> nodos de los que depende, deducido de los nombres de variable.

    Se deduce del IR y no del grafo a proposito: si un nodo falla, lo que hay
    que omitir es exactamente lo que iba a leer sus variables.
    """
    dueno: dict[str, str] = {}
    for ins in programa.instrucciones:
        for var in ins.salidas.values():
            dueno[var] = ins.nodo_id
    padres: dict[str, set[str]] = {}
    for ins in programa.instrucciones:
        vistos: set[str] = set()
        for crudo in ins.entradas.values():
            for var in crudo.split("\x00"):
                if (p := dueno.get(var)) is not None:
                    vistos.add(p)
        padres[ins.nodo_id] = vistos
    return padres
