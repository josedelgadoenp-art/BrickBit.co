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

CÓMO SE VARÍA LA PARTICIÓN, Y POR QUÉ NO CON LA SEMILLA. La primera versión de
este experimento cambiaba `cfg.semilla` y corría de nuevo. No funcionó, y las
tres filas salieron IDÉNTICAS hasta el tercer decimal. El motivo está en
`datos.particion`: baraja las etiquetas sólo para desempatar y después las
ordena de mayor a menor tamaño, porque repartir primero los bloques grandes es
lo que hace que las fracciones salgan parejas (y no hacerlo costó una vez un
60/20/20 que salió 76/10/14). Con bloques de tamaños distintos ese orden es el
mismo para cualquier semilla, y el reparto greedy que sigue es determinista.

O sea: la partición de la Fase 2 es deliberadamente única. Así que aquí se
rodea en vez de tocarla. Los bloques se parten en K pliegues del mismo tamaño;
en la repetición i, el pliegue i es PRUEBA, el siguiente es CALIBRACIÓN y el
resto entrena. Eso da K particiones 60/20/20 genuinamente distintas, cada
bloque pasa por prueba exactamente una vez, y el equilibrio se conserva porque
`GroupKFold` reparte por tamaño.

LO QUE NO HACE. No decide por ti qué hacer con el resultado. Si confirma que
estorban, quitarlos es una opción y arreglarlos es otra: el modelo los usa
mucho (`comp15_ln_precio_m2` sale alto en SHAP), y la sospecha razonable es que
en prueba esa variable se degrada porque los vecinos del propio bloque no están
entre las fuentes —una covariable que significa algo distinto al entrenar y al
evaluar—. Eso se arregla, no se amputa. Pero primero hay que saber si es real.

    python -m experimentos.contraste_comparables            # 5 particiones
    python -m experimentos.contraste_comparables -n 8
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atlas.config import cargar  # noqa: E402
from atlas.modelos import datos  # noqa: E402
from pipelines import fase2  # noqa: E402


def particiones_por_pliegue(bloque: pd.Series, k: int) -> list[dict]:
    """
    K particiones 60/20/20 en las que cada bloque es prueba exactamente una vez.

    No se usa `datos.particion` con semillas distintas porque ese reparto es
    determinista (ver el encabezado). `GroupKFold` agrupa por bloque y equilibra
    por tamaño, que es la misma preocupación que motivó el orden de mayor a
    menor en la partición original.
    """
    from sklearn.model_selection import GroupKFold

    g = pd.Series(bloque).astype(str).to_numpy()
    k = int(min(k, pd.Series(g).nunique()))
    if k < 3:
        raise ValueError(f"Hacen falta al menos 3 bloques; hay {k}.")

    pliegues = [fuera for _, fuera in
                GroupKFold(n_splits=k).split(np.zeros(len(g)), groups=g)]
    salida = []
    for i in range(k):
        prueba = pliegues[i]
        calibra = pliegues[(i + 1) % k]
        m_pr = np.zeros(len(g), dtype=bool); m_pr[prueba] = True
        m_ca = np.zeros(len(g), dtype=bool); m_ca[calibra] = True
        p = {"prueba": m_pr, "calibra": m_ca, "entrena": ~(m_pr | m_ca)}
        if all(v.sum() for v in p.values()):
            salida.append(p)
    return salida


def main() -> int:
    ap = argparse.ArgumentParser(description="Contraste de comparables sobre N particiones")
    ap.add_argument("-n", "--particiones", type=int, default=5)
    ap.add_argument("--operacion", default="venta", choices=["venta", "renta"])
    args = ap.parse_args()

    cfg = cargar()
    d = datos.ensamblar(cfg, operacion=args.operacion)
    ps = particiones_por_pliegue(d.bloque, max(3, int(args.particiones)))
    print(f"Contraste de comparables sobre {len(ps)} particiones "
          f"({d.bloque.nunique()} bloques, cada uno es prueba una vez)\n")
    print(f"{'#':>3}{'prueba':>8}{'con':>9}{'sin':>9}{'efecto':>10}"
          f"{'R² con':>9}{'R² sin':>9}{'cobert.':>9}{'ancho':>8}")

    filas = []
    for i, p in enumerate(ps, 1):
        try:
            r = fase2.construir(cfg, args.operacion, None, ligero=True, particion=p)
        except Exception as e:  # noqa: BLE001 — una partición mala no tumba el experimento
            print(f"{i:>3}  ✗ {type(e).__name__}: {e}")
            continue
        con, sin = r["punto"]["boosting"], r["punto"]["sin_comparables"]
        efecto = (con.mdape_pct - sin.mdape_pct) / sin.mdape_pct * 100
        iv = r["intervalo"]
        filas.append((efecto, con, sin, iv))
        print(f"{i:>3}{int(p['prueba'].sum()):>8,}{con.mdape_pct:>8.1f}%"
              f"{sin.mdape_pct:>8.1f}%{efecto:>+9.1f}%"
              f"{con.r2_log:>9.3f}{sin.r2_log:>9.3f}"
              f"{iv.cobertura * 100:>8.1f}%{iv.ancho_mediano_pct:>7.0f}%")

    if len(filas) < 3:
        print("\nMenos de 3 particiones válidas: no alcanza para concluir nada.")
        return 1

    ef = np.array([f[0] for f in filas])
    estorban = int((ef > 0).sum())
    print(f"\n   {'—' * 66}")
    print(f"   efecto medio {ef.mean():+.1f}%  ·  mediano {np.median(ef):+.1f}%  ·  "
          f"rango {ef.min():+.1f}% a {ef.max():+.1f}%")
    print(f"   estorban en {estorban} de {len(ef)} particiones")

    # El criterio se fija ANTES de ver el número, y se dice cuál es: el signo
    # tiene que ser el mismo en TODAS y el efecto medio pasar de 3 puntos. Con
    # un número tan chico de particiones, exigir menos sería volver a leerle
    # significado al ruido.
    if estorban == len(ef) and ef.mean() > 3:
        print("\n   → CONSISTENTE: estorban en todas las particiones.")
        print("     Antes de quitarlos conviene entender por qué se degradan en")
        print("     prueba: el modelo los usa mucho y la señal de fondo es real.")
    elif estorban == 0 and ef.mean() < -3:
        print("\n   → CONSISTENTE: ayudan en todas las particiones.")
    else:
        print("\n   → NO CONCLUYENTE: el signo depende de la partición, así que")
        print("     el efecto —si existe— es menor que el ruido de esta muestra.")
        print("     Con este tamaño no da para más, y no se decide inventando")
        print("     una diferencia que el dato no sostiene.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
