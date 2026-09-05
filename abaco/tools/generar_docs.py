"""Genera docs/nodos.md a partir del registro.

La documentación de las herramientas no se escribe: se deriva. Así no puede
quedar desactualizada, que es lo que le pasa a toda documentación escrita a
mano en cuanto alguien agrega un nodo con prisa.

    python tools/generar_docs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "packages" / "core"))

from abaco_core.registry import FAMILIAS, cargar_todos, todos  # noqa: E402

NOMBRE_SISTEMA = {"stata": "Stata", "r": "R", "spss": "SPSS", "eviews": "EViews", "python": "Python"}


def main() -> None:
    cargar_todos()
    l: list[str] = []
    l.append("# Herramientas de Ábaco")
    l.append("")
    l.append("**Este archivo se genera solo.** Sale del registro (`abaco_core/nodes/`), así que")
    l.append("no puede quedar desactualizado. Para regenerarlo: `python tools/generar_docs.py`.")
    l.append("")

    familias = sorted(FAMILIAS.values(), key=lambda f: f.orden)
    total = sum(1 for _ in todos())
    l.append(f"{total} herramientas en {len(familias)} familias.")
    l.append("")
    l.append("| Familia | Herramientas | Para qué |")
    l.append("|---|---:|---|")
    for f in familias:
        l.append(f"| [{f.titulo}](#{f.id}) | {sum(1 for _ in todos(f.id))} | {f.descripcion} |")
    l.append("")

    for f in familias:
        herramientas = sorted(todos(f.id), key=lambda c: c.titulo)
        if not herramientas:
            continue
        l.append(f'<a id="{f.id}"></a>')
        l.append("")
        l.append(f"## {f.titulo}")
        l.append("")
        l.append(f"{f.descripcion}")
        l.append("")
        for cls in herramientas:
            a = cls.ayuda
            l.append(f"### {cls.titulo}")
            l.append("")
            l.append(f"`{cls.op}` · v{cls.version}")
            l.append("")
            l.append(f"**Qué hace.** {a.que_hace}")
            l.append("")
            l.append(f"**Cuándo usarlo.** {a.cuando_usarlo}")
            l.append("")
            l.append(f"**Cómo se lee el resultado.** {a.interpretacion}")
            l.append("")
            if a.supuestos:
                l.append("**Supuestos que impone:**")
                l.append("")
                for s in a.supuestos:
                    l.append(f"- {s}")
                l.append("")
            if a.advertencias:
                l.append("**Ten cuidado con:**")
                l.append("")
                for x in a.advertencias:
                    l.append(f"- {x}")
                l.append("")
            if cls.entradas or cls.salidas:
                l.append("| | Puerto | Tipo |")
                l.append("|---|---|---|")
                for p in cls.entradas:
                    req = "" if p.requerido else " *(opcional)*"
                    l.append(f"| entra | {p.titulo or p.nombre}{req} | {p.ayuda_tipo} |")
                for p in cls.salidas:
                    l.append(f"| sale | {p.titulo or p.nombre} | {p.ayuda_tipo} |")
                l.append("")
            props = cls.esquema_params().get("properties", {})
            if props:
                l.append("| Parámetro | Por omisión |")
                l.append("|---|---|")
                for clave, campo in props.items():
                    omision = campo.get("default", "—")
                    l.append(f"| `{clave}` | `{omision}` |")
                l.append("")
            if a.equivalente:
                pares = " · ".join(
                    f"**{NOMBRE_SISTEMA.get(k, k)}**: `{v}`" for k, v in a.equivalente.items())
                l.append(f"Si vienes de otro sistema — {pares}")
                l.append("")
            if a.referencia:
                l.append(f"Para leer más: {a.referencia}")
                l.append("")

    destino = RAIZ / "docs" / "nodos.md"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(l), encoding="utf-8")
    print(f"{destino.relative_to(RAIZ)}: {total} herramientas, {len(l)} líneas")


if __name__ == "__main__":
    main()
