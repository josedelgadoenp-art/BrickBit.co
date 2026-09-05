"""Nota metodologica generada del grafo.

El paso que casi nadie hace y que decide si un resultado se puede defender: dejar
escrito que se hizo, con que supuestos y con que advertencias. Abaco lo escribe
solo, porque ya sabe todo lo necesario — el registro trae la ayuda de cada
herramienta, y el IR trae los parametros con los que se corrio.

No es un nodo del lienzo a proposito: una nota metodologica habla del analisis
COMPLETO, y un nodo solo ve lo que le llega por sus puertos.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

from ..graph.compilador import Programa
from ..registry.base import FAMILIAS, obtener


def _valor_legible(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "si" if v else "no"
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v) if v else "—"
    if isinstance(v, dict):
        return ", ".join(f"{k}: {x}" for k, x in v.items()) if v else "—"
    return str(v)


def nota_metodologica(programa: Programa, *, autor: str | None = None,
                      incluir_supuestos: bool = True) -> str:
    """Markdown con lo que se hizo, en orden, con supuestos y advertencias."""
    hoy = _dt.date.today().isoformat()
    lineas: list[str] = [f"# Nota metodologica — {programa.titulo}", ""]
    lineas.append(f"*Generada por Ábaco el {hoy}"
                  + (f", para {autor}" if autor else "") + ".*")
    lineas.append("")
    lineas.append(f"- **Huella del análisis**: `{programa.huella_grafo[:16]}` "
                  "(identifica esta versión exacta del flujo)")
    lineas.append(f"- **Semilla de aleatoriedad**: `{programa.semilla}`")
    lineas.append(f"- **Pasos ejecutados**: {len(programa.instrucciones)}")
    if programa.podados:
        lineas.append(f"- **Pasos en el lienzo que no alimentan ningún resultado** "
                      f"(no se ejecutaron): {len(programa.podados)}")
    lineas.append("")
    lineas.append("## Qué se hizo, en orden")
    lineas.append("")

    supuestos: list[tuple[str, str]] = []
    advertencias: list[tuple[str, str]] = []
    fuentes: list[str] = []

    for i, ins in enumerate(programa.instrucciones, start=1):
        spec = obtener(ins.op)
        familia = FAMILIAS[spec.familia].titulo
        lineas.append(f"**{i}. {ins.etiqueta}** — {spec.titulo} · *{familia}*")
        lineas.append("")
        lineas.append(f"{spec.ayuda.que_hace}")
        params = ins.params.model_dump()
        visibles = {k: v for k, v in params.items()
                    if v is not None and v != [] and v != {} and v != ""}
        if visibles:
            lineas.append("")
            lineas.append("Configuración: " + "; ".join(
                f"*{k.replace('_', ' ')}* = {_valor_legible(v)}" for k, v in visibles.items()) + ".")
        if ins.notas:
            lineas.append("")
            lineas.append(f"> Nota del autor: {ins.notas}")
        lineas.append("")
        for s in spec.ayuda.supuestos:
            supuestos.append((ins.etiqueta, s))
        for a in spec.ayuda.advertencias:
            advertencias.append((ins.etiqueta, a))
        if spec.ayuda.referencia:
            fuentes.append(spec.ayuda.referencia)

    if incluir_supuestos and supuestos:
        lineas.append("## Supuestos que hay que sostener")
        lineas.append("")
        lineas.append("Cada método impone condiciones. Si alguna no se cumple, el resultado "
                      "sigue saliendo, pero deja de significar lo que parece.")
        lineas.append("")
        for etiqueta, s in supuestos:
            lineas.append(f"- **{etiqueta}**: {s}")
        lineas.append("")

    if advertencias:
        lineas.append("## Advertencias")
        lineas.append("")
        for etiqueta, a in advertencias:
            lineas.append(f"- **{etiqueta}**: {a}")
        lineas.append("")

    estimadas = _columnas_estimadas(programa)
    if estimadas:
        lineas.append("## Qué es dato y qué es estimación")
        lineas.append("")
        lineas.append("Las siguientes columnas **no son mediciones**: salieron de un modelo, un "
                      "pronóstico o un filtro. En la interfaz aparecen en ámbar. Al citarlas fuera "
                      "de Ábaco hay que decir que son estimaciones.")
        lineas.append("")
        for nodo, cols in estimadas:
            lineas.append(f"- **{nodo}**: {', '.join(cols)}")
        lineas.append("")

    if fuentes:
        lineas.append("## Referencias de los métodos")
        lineas.append("")
        for f in sorted(set(fuentes)):
            lineas.append(f"- {f}")
        lineas.append("")

    lineas.append("---")
    lineas.append("")
    lineas.append("El script de Python que produjo estos resultados se exporta desde la pestaña "
                  "**Código**. Es el mismo código que se ejecutó, no una reconstrucción.")
    return "\n".join(lineas)


def _columnas_estimadas(programa: Programa) -> list[tuple[str, list[str]]]:
    salida: list[tuple[str, list[str]]] = []
    for ins in programa.instrucciones:
        esquemas = programa.esquemas.get(ins.nodo_id, {})
        cols = sorted({c.nombre for e in esquemas.values() for c in e.columnas if c.es_estimado})
        if cols:
            salida.append((ins.etiqueta, cols))
    return salida
