"""Llena la caché de fuentes desde una computadora con conexión doméstica.

Banxico e INEGI rechazan las peticiones que vienen de IPs de centros de datos.
Este script existe para ese caso, que es el normal en producción: se corre en
una laptop, descarga lo que el análisis necesita, y deja los archivos en la
caché que después usan tanto el servidor como el script exportado.

    export BANXICO_TOKEN=...
    export INEGI_TOKEN=...
    python tools/traer_datos.py analisis.json            # lo que pide un grafo
    python tools/traer_datos.py --banxico SF43718,SP1    # series sueltas
    python tools/traer_datos.py analisis.json --destino ./datos/fuentes

Con `--destino` apuntando a la carpeta `datos/fuentes/` de un paquete exportado,
el `.zip` queda autocontenido y `python analisis.py` corre sin red.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "packages" / "core"))

from abak_core import GrafoSpec, compilar  # noqa: E402
from abak_core.nodes.fuentes.http import dir_fuentes  # noqa: E402
from abak_core.registry import cargar_todos, obtener  # noqa: E402


def _peticiones_del_grafo(ruta: Path) -> list[tuple[str, dict]]:
    """Qué fuentes necesita este análisis, leídas del propio grafo."""
    documento = json.loads(ruta.read_text(encoding="utf-8"))
    grafo = GrafoSpec.model_validate(documento.get("grafo", documento))
    programa = compilar(grafo)
    peticiones = []
    for instruccion in programa.instrucciones:
        if instruccion.op.startswith("fuentes."):
            peticiones.append((instruccion.op, instruccion.params.model_dump()))
    return peticiones


def _traer(op: str, params: dict, destino: Path, forzar: bool) -> str:
    """Ejecuta la misma función que usaría el análisis. Una sola ruta de código."""
    from abak_core.nodes.fuentes import banxico as _bx  # noqa: F401  (registra ayudantes)
    from abak_core.nodes.fuentes import inegi as _in  # noqa: F401
    from abak_core.registry import AYUDANTES

    espacio: dict = {}
    from abak_core.codegen.contexto import resolver_ayudantes

    necesarios = {
        "fuentes.banxico": ["traer_banxico"],
        "fuentes.inegi": ["traer_inegi"],
        "fuentes.denue": ["traer_denue"],
    }[op]
    for ayudante in resolver_ayudantes(necesarios):
        for modulo, alias in ayudante.imports:
            espacio[alias or modulo.split(".")[0]] = __import__(modulo)
        exec(ayudante.fuente, espacio)
    espacio.setdefault("pd", __import__("pandas"))

    destino.mkdir(parents=True, exist_ok=True)
    if op == "fuentes.banxico":
        marco = espacio["traer_banxico"](
            params["series"], destino, inicio=params.get("inicio"),
            fin=params.get("fin"), forzar_red=forzar)
        etiqueta = ", ".join(params["series"])
    elif op == "fuentes.inegi":
        marco = espacio["traer_inegi"](
            params["indicadores"], destino, area=params.get("area", "0700"),
            banco=params.get("banco", "BIE"), forzar_red=forzar)
        etiqueta = ", ".join(params["indicadores"])
    else:
        marco = espacio["traer_denue"](
            params.get("condicion", "todos"), params["latitud"], params["longitud"],
            params["metros"], destino, forzar_red=forzar)
        etiqueta = f"{params.get('condicion')} @ {params['latitud']},{params['longitud']}"
    return f"{op}  {etiqueta}  →  {len(marco):,} filas"


def main() -> int:
    cargar_todos()
    ap = argparse.ArgumentParser(description="Llena la caché de fuentes oficiales de Abak.")
    ap.add_argument("grafo", nargs="?", type=Path,
                    help="Archivo .json de un análisis. Se descarga lo que ese análisis pide.")
    ap.add_argument("--banxico", help="Claves de series del SIE separadas por coma")
    ap.add_argument("--inegi", help="Claves de indicadores separadas por coma")
    ap.add_argument("--area", default="0700", help="Clave geográfica de INEGI (0700 = nacional)")
    ap.add_argument("--banco", default="BIE", choices=["BIE", "BISE"])
    ap.add_argument("--destino", type=Path, default=None,
                    help="Dónde escribir la caché (por omisión, la de esta instalación)")
    ap.add_argument("--forzar", action="store_true",
                    help="Vuelve a descargar aunque ya esté en caché")
    args = ap.parse_args()

    destino = args.destino or dir_fuentes()
    peticiones: list[tuple[str, dict]] = []

    if args.grafo:
        peticiones += _peticiones_del_grafo(args.grafo)
    if args.banxico:
        peticiones.append(("fuentes.banxico",
                           {"series": [s.strip() for s in args.banxico.split(",") if s.strip()],
                            "inicio": None, "fin": None}))
    if args.inegi:
        peticiones.append(("fuentes.inegi",
                           {"indicadores": [s.strip() for s in args.inegi.split(",") if s.strip()],
                            "area": args.area, "banco": args.banco}))

    if not peticiones:
        ap.error("Indica un archivo de análisis, o --banxico / --inegi.")

    faltan = []
    if any(op == "fuentes.banxico" for op, _ in peticiones) and not os.environ.get("BANXICO_TOKEN"):
        faltan.append("BANXICO_TOKEN")
    if any(op in ("fuentes.inegi", "fuentes.denue") for op, _ in peticiones) \
            and not os.environ.get("INEGI_TOKEN"):
        faltan.append("INEGI_TOKEN")
    if faltan:
        print(f"Faltan estas variables de entorno: {', '.join(faltan)}", file=sys.stderr)
        print("Los tokens son gratuitos y se piden en el sitio de cada institución.", file=sys.stderr)
        return 2

    print(f"Caché: {destino}")
    fallos = 0
    for op, params in peticiones:
        try:
            print("  ✓", _traer(op, params, destino, args.forzar))
        except Exception as exc:
            fallos += 1
            print(f"  ✗ {op}: {exc}", file=sys.stderr)

    if fallos:
        print(f"\n{fallos} de {len(peticiones)} peticiones fallaron.", file=sys.stderr)
        return 1
    print(f"\n{len(peticiones)} fuentes en caché. El servidor ya no necesita red para este análisis.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
