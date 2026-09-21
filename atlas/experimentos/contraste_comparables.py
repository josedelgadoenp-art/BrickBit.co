"""
¿Los comparables ayudan o estorban? Decidirlo con reparticiones, no con una.

POR QUÉ EXISTE ESTE ARCHIVO. El contraste "con comparables contra sin
comparables" se midió tres veces sobre casi los mismos datos y dio tres cosas
distintas:

    corrida 1    −7.3%   (ayudaban)
    corrida 2    +6.6%   (estorbaban)
    corrida 3   +10.0%   (estorbaban más)

Con 355 inmuebles de prueba repartidos en 6 bloques, una diferencia de dos
puntos en el error mediano cabe holgadamente dentro del ruido de QUÉ bloques
tocaron ser prueba. Leer una sola partición y concluir es exactamente el error
que este experimento evita: la primera lectura produjo la afirmación de que los
comparables eran "el hueco grande", y no estaba respaldada.

QUÉ HACE. Corre la Fase 2 completa sobre N particiones distintas —cambia la
semilla, que reparte los bloques de otra manera— y reporta la distribución del
contraste en vez de un número. Si el signo es estable en N reparticiones,
entonces sí es del modelo; si baila, era de la partición.

LO QUE NO HACE. No decide por ti qué hacer con el resultado. Si confirma que
estorban, quitarlos es una opción y arreglarlos es otra: el modelo los usa
mucho (comp15_ln_precio_m2 sale alto en SHAP), y la sospecha razonable es que
en prueba esa variable se degrada porque los vecinos del propio bloque no están
entre las fuentes —una covariable que significa algo distinto al entrenar y al
evaluar—. Eso se arregla, no se amputa. Pero primero hay que saber si es real.

    python -m experimentos.contraste_comparables            # 5 reparticiones
    python -m experimentos.contraste_comparables -n 10
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atlas.config import cargar  # noqa: E402
from pipelines import fase2  # noqa: E402

# Semillas fijas: el experimento tiene que dar lo mismo si se repite. Son
# arbitrarias a propósito —no se eligieron mirando el resultado—.
SEMILLAS = (20260828, 17, 991, 4242, 65537, 123457, 8191, 31337, 5, 777)


def main() -> int:
    ap = argparse.ArgumentParser(description="Contraste de comparables sobre N particiones")
    ap.add_argument("-n", "--reparticiones", type=int, default=5)
    ap.add_argument("--operacion", default="venta", choices=["venta", "renta"])
    args = ap.parse_args()

    n = max(2, min(int(args.reparticiones), len(SEMILLAS)))
    print(f"Contraste de comparables sobre {n} reparticiones\n")
    print(f"{'semilla':>9}{'con':>9}{'sin':>9}{'efecto':>10}"
          f"{'R² con':>9}{'R² sin':>9}{'cobert.':>9}{'ancho':>8}")

    filas = []
    for s in SEMILLAS[:n]:
        cfg = cargar()          # config fresca: la semilla se muta en sitio
        try:
            r = fase2.construir(cfg, args.operacion, None, semilla=s, ligero=True)
        except Exception as e:  # noqa: BLE001 — una partición mala no tumba el experimento
            print(f"{s:>9}  ✗ {type(e).__name__}: {e}")
            continue
        con = r["punto"]["boosting"]
        sin = r["punto"]["sin_comparables"]
        efecto = (con.mdape_pct - sin.mdape_pct) / sin.mdape_pct * 100
        iv = r["intervalo"]
        filas.append((s, con.mdape_pct, sin.mdape_pct, efecto,
                      con.r2_log, sin.r2_log, iv.cobertura, iv.ancho_mediano_pct))
        print(f"{s:>9}{con.mdape_pct:>8.1f}%{sin.mdape_pct:>8.1f}%{efecto:>+9.1f}%"
              f"{con.r2_log:>9.3f}{sin.r2_log:>9.3f}"
              f"{iv.cobertura * 100:>8.1f}%{iv.ancho_mediano_pct:>7.0f}%")

    if len(filas) < 2:
        print("\nNo hubo suficientes reparticiones válidas para concluir nada.")
        return 1

    ef = np.array([f[3] for f in filas])
    estorban = int((ef > 0).sum())
    print(f"\n{'':9}{'—' * 62}")
    print(f"  efecto medio {ef.mean():+.1f}%  ·  mediano {np.median(ef):+.1f}%  ·  "
          f"rango {ef.min():+.1f}% a {ef.max():+.1f}%")
    print(f"  estorban en {estorban} de {len(ef)} reparticiones")

    # El criterio se fija ANTES de ver el número, y se dice cuál es.
    if estorban == len(ef) and ef.mean() > 3:
        print("\n  → CONSISTENTE: estorban en todas y el efecto medio es grande.")
        print("    Vale la pena arreglar la variable (por qué se degrada en")
        print("    prueba) antes que quitarla: el modelo la usa mucho.")
    elif estorban == 0 and ef.mean() < -3:
        print("\n  → CONSISTENTE: ayudan en todas. La corrida que dijo lo")
        print("    contrario era ruido de partición.")
    else:
        print("\n  → NO CONCLUYENTE: el signo depende de la partición, así que")
        print("    el efecto -si existe- es menor que el ruido de esta muestra.")
        print("    Con 355 inmuebles de prueba no da para más; no se decide")
        print("    inventando una diferencia que el dato no sostiene.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
