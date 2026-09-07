"""El libro de especificaciones: cuántos modelos probaste antes de reportar uno.

El problema que resuelve es el fraude involuntario más extendido de la economía
aplicada. Alguien prueba veinte especificaciones —quita una variable, cambia la
muestra, mete un logaritmo— y publica la que «funcionó». Las otras diecinueve
no dejan rastro. Nadie miente; simplemente nadie cuenta. Y con veinte intentos,
encontrar un p-valor por debajo de 0.05 es lo esperable aunque no haya nada.

Abak es el único que PUEDE contarlo, porque cada ejecución pasa por aquí. Cada
modelo estimado deja una línea, y al reportar se puede decir la frase que
ninguna herramienta dice hoy: «estimaste catorce especificaciones para explicar
esta variable; el coeficiente que estás reportando es el más alto de todas».

Es la misma regla de la casa que pinta en ámbar lo estimado, un piso más
arriba: si un dato estimado no se presenta como un hecho, una especificación
elegida entre catorce tampoco se presenta como la única.

Referencia: Simonsohn, Simmons y Nelson, «Specification Curve Analysis»
(Nature Human Behaviour, 2020); Steegen et al., «Multiverse Analysis» (2016).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

# Un libro que crece sin tope acaba siendo un archivo de gigas que nadie lee.
# Se conservan las últimas N líneas: para juzgar si hubo búsqueda de resultados
# lo que importa es el historial reciente de ESTE análisis, no el de siempre.
TOPE_LINEAS = 5_000


def _significativa(p: float | None) -> bool:
    return p is not None and p < 0.05


def _mediana(valores: list[float]) -> float:
    """Con un número par de valores, el promedio de los dos centrales.

    Tomar el de arriba hacía que con dos especificaciones la «mediana» saliera
    igual al máximo, y en pantalla parecía que el valor reportado era el típico
    cuando era el extremo.
    """
    xs = sorted(valores)
    n = len(xs)
    if n % 2:
        return xs[n // 2]
    return (xs[n // 2 - 1] + xs[n // 2]) / 2


class LibroEspecificaciones:
    """Registro append-only de cada modelo estimado."""

    def __init__(self, ruta: str | Path) -> None:
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)

    # -- escritura -----------------------------------------------------------

    def anotar(self, *, ejecucion_id: str, nodo_id: str, etiqueta: str, op: str,
               resultado: str, artefacto_modelo: dict[str, Any],
               semilla: int | None = None) -> None:
        """Guarda una especificación estimada.

        `artefacto_modelo` es el mismo diccionario que ve la interfaz, así que
        el libro no puede desviarse de lo que se mostró en pantalla.
        """
        coeficientes = {}
        for fila in artefacto_modelo.get("coeficientes") or []:
            variable = str(fila.get("variable", ""))
            if not variable or variable == "const":
                continue
            coeficientes[variable] = {
                "coeficiente": fila.get("coeficiente"),
                "error_estandar": fila.get("error_estandar"),
                "p_valor": fila.get("p_valor"),
            }
        if not coeficientes:
            return

        diag = artefacto_modelo.get("diagnosticos") or {}
        linea = {
            "cuando": time.time(),
            "ejecucion_id": ejecucion_id,
            "nodo_id": nodo_id,
            "etiqueta": etiqueta,
            "op": op,
            "resultado": resultado,
            "semilla": semilla,
            "variables": sorted(coeficientes),
            "coeficientes": coeficientes,
            "n": diag.get("Observaciones"),
            "r2": diag.get("R²"),
        }
        with self.ruta.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")
        self._recortar()

    def _recortar(self) -> None:
        try:
            lineas = self.ruta.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        if len(lineas) <= TOPE_LINEAS:
            return
        self.ruta.write_text("\n".join(lineas[-TOPE_LINEAS:]) + "\n", encoding="utf-8")

    # -- lectura -------------------------------------------------------------

    def leer(self, resultado: str | None = None) -> list[dict[str, Any]]:
        if not self.ruta.exists():
            return []
        filas = []
        for linea in self.ruta.read_text(encoding="utf-8").splitlines():
            if not linea.strip():
                continue
            try:
                doc = json.loads(linea)
            except json.JSONDecodeError:
                continue  # una línea corrupta no invalida el libro entero
            if resultado is None or doc.get("resultado") == resultado:
                filas.append(doc)
        return filas

    def resumen(self, resultado: str, actual: str | None = None) -> dict[str, Any]:
        """La distribución de cada coeficiente entre TODAS las que probaste.

        `actual` es el id de nodo que se está mirando, para poder decir en qué
        lugar de su propia distribución cae el número que se va a reportar.
        """
        filas = self.leer(resultado)
        if not filas:
            return {"resultado": resultado, "n_especificaciones": 0, "variables": []}

        por_variable: dict[str, list[dict[str, Any]]] = {}
        for fila in filas:
            for variable, datos in (fila.get("coeficientes") or {}).items():
                if isinstance(datos.get("coeficiente"), (int, float)):
                    por_variable.setdefault(variable, []).append({**datos, "_fila": fila})

        variables = []
        for variable, entradas in sorted(por_variable.items()):
            valores = [e["coeficiente"] for e in entradas]
            signos = {1 if v > 0 else (-1 if v < 0 else 0) for v in valores}
            actual_valor = None
            if actual:
                for e in entradas:
                    if e["_fila"].get("nodo_id") == actual:
                        actual_valor = e["coeficiente"]
            variables.append({
                "variable": variable,
                "veces": len(entradas),
                "minimo": min(valores),
                "maximo": max(valores),
                "mediana": _mediana(valores),
                "veces_significativa": sum(_significativa(e.get("p_valor")) for e in entradas),
                "cambia_de_signo": len(signos - {0}) > 1,
                "actual": actual_valor,
                # ¿El número que se va a reportar es el extremo de todo lo que probaste?
                "actual_es_extremo": (
                    actual_valor is not None and len(valores) > 2
                    and (actual_valor == max(valores) or actual_valor == min(valores))),
            })

        return {
            "resultado": resultado,
            "n_especificaciones": len(filas),
            "desde": min(f["cuando"] for f in filas),
            "variables": variables,
        }

    def resultados_registrados(self) -> list[dict[str, Any]]:
        conteo: dict[str, int] = {}
        for fila in self.leer():
            conteo[fila.get("resultado", "?")] = conteo.get(fila.get("resultado", "?"), 0) + 1
        return [{"resultado": r, "veces": n}
                for r, n in sorted(conteo.items(), key=lambda kv: -kv[1])]


def libro_por_omision() -> LibroEspecificaciones:
    raiz = Path(os.environ.get("ABAK_INICIO", ".abak"))
    return LibroEspecificaciones(raiz / "especificaciones.jsonl")
