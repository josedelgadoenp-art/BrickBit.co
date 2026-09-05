"""
Diagnóstico de la partición por bloques.

    python diagnostico.py        (desde la carpeta atlas/)

No modela nada. Responde tres preguntas, en orden, cuando la Fase 2 reparte los
datos de una forma que no cuadra con lo que pide `config.yaml`:

  1. ¿Python está cargando el archivo que creemos? Imprime la ruta real del
     módulo y su fecha. Si esa ruta no es la del repo, hay otra copia
     ensombreciendo la buena y ningún `git pull` va a arreglarlo.
  2. ¿Cómo son los bloques de verdad? Imprime sus tamaños. La partición no
     puede repartir bien lo que no se deja repartir: si un bloque solo vale más
     que un cupo entero, ninguna heurística lo salva.
  3. ¿Qué reparto sale, y qué reparto saldría con otras fracciones? Así se ve
     si conviene mover `fracciones` en `config.yaml`.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from atlas.config import cargar                    # noqa: E402
from atlas.modelos import datos                    # noqa: E402


def main() -> int:
    cfg = cargar()

    print("=" * 62)
    print("1 · QUÉ ARCHIVO ESTÁ CARGANDO PYTHON")
    print("=" * 62)
    ruta = Path(datos.__file__).resolve()
    print(f"  módulo   {ruta}")
    print(f"  fecha    {datetime.fromtimestamp(ruta.stat().st_mtime, timezone.utc):%Y-%m-%d %H:%M} UTC")
    fuente = ruta.read_text(encoding="utf-8")
    tiene_texto = "sorted(orden" in fuente
    print(f"  el ARCHIVO trae el arreglo:   {'SÍ' if tiene_texto else 'NO'}")

    # Leer el .py no basta: Python puede estar ejecutando bytecode viejo de
    # __pycache__ aunque el texto ya esté actualizado. Lo que importa es qué
    # trae la FUNCIÓN cargada en memoria, y eso se lee del código compilado.
    import inspect

    try:
        compilado = inspect.getsource(datos.particion)
        tiene_memoria = "sorted(orden" in compilado
    except OSError:
        tiene_memoria = None
    consts = datos.particion.__code__.co_consts
    nombres = datos.particion.__code__.co_names
    usa_sorted = "sorted" in nombres or any(
        isinstance(c, str) and "sorted" in c for c in consts if isinstance(c, str)
    )
    print(f"  la FUNCIÓN cargada lo usa:    {'SÍ' if usa_sorted else 'NO — bytecode viejo en __pycache__'}")
    if tiene_texto and not usa_sorted:
        print()
        print("  >>> El archivo está bien pero Python ejecuta una versión vieja.")
        print("  >>> Borra la caché y vuelve a correr:")
        print("  >>>   for /d /r . %d in (__pycache__) do @if exist \"%d\" rd /s /q \"%d\"")

    print()
    print("=" * 62)
    print("2 · CÓMO SON LOS BLOQUES")
    print("=" * 62)
    d = datos.ensamblar(cfg, operacion="venta")
    tam = d.bloque.value_counts()
    n = int(tam.sum())
    print(f"  {n:,} inmuebles en {len(tam)} bloques")
    print(f"  el mayor tiene {int(tam.iloc[0]):,} ({tam.iloc[0] / n * 100:.1f}% del total)")
    print(f"  los 5 mayores suman {int(tam.head(5).sum()):,} ({tam.head(5).sum() / n * 100:.1f}%)")
    print("  tamaños: " + ", ".join(str(int(x)) for x in tam.values))

    print()
    print("=" * 62)
    print("3 · QUÉ REPARTO SALE")
    print("=" * 62)
    for f in [(0.60, 0.20, 0.20), (0.50, 0.30, 0.20), (0.45, 0.35, 0.20)]:
        try:
            p = datos.particion(d.bloque, cfg, fracciones=f)
        except ValueError as e:
            print(f"  pedido {f}: no se pudo ({e})")
            continue
        real = tuple(round(p[k].sum() / n * 100, 1) for k in ("entrena", "calibra", "prueba"))
        filas = tuple(int(p[k].sum()) for k in ("entrena", "calibra", "prueba"))
        marca = "  ← el de config.yaml" if f == (0.60, 0.20, 0.20) else ""
        print(f"  pedido {int(f[0]*100)}/{int(f[1]*100)}/{int(f[2]*100)}"
              f"  →  sale {real[0]}/{real[1]}/{real[2]}"
              f"   ({filas[0]:,} / {filas[1]:,} / {filas[2]:,}){marca}")

    print()
    print("=" * 62)
    print("4 · EL MISMO REPARTO, CALCULADO AQUÍ MISMO")
    print("=" * 62)
    print("  Si esto da 60/20/20 y el punto 3 no, la función importada es vieja.")
    cupos = [0.60 * n, 0.20 * n, 0.20 * n]
    orden = sorted(tam.index.to_list(), key=lambda b: -int(tam[b]))
    acum, cuenta = [0.0, 0.0, 0.0], [0, 0, 0]
    for b in orden:
        deficit = [(acum[i] - cupos[i]) / cupos[i] for i in range(3)]
        i = int(np.argmin(deficit))
        acum[i] += float(tam[b])
        cuenta[i] += 1
    print(f"  orden (5 mayores): {[int(tam[b]) for b in orden[:5]]}")
    print(f"  reparto  {acum[0] / n * 100:.1f}/{acum[1] / n * 100:.1f}/{acum[2] / n * 100:.1f}"
          f"   ({int(acum[0]):,} / {int(acum[1]):,} / {int(acum[2]):,})"
          f"   bloques {cuenta[0]}/{cuenta[1]}/{cuenta[2]}")

    print()
    print("  Pega esta salida completa en el chat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
