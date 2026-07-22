# -*- coding: utf-8 -*-
"""
BrickBit · Backtest walk-forward REPRODUCIBLE sobre el índice SHF real.

Mide el error de pronóstico de plusvalía SIN fuga de información: en cada año
de origen del pasado, ajusta el modelo SOLO con datos hasta ese año, proyecta
a 1 y 3 años, y compara contra lo que de verdad ocurrió (índice SHF observado).

Modelo BrickBit (momentum + tendencia + reversión, transparente y auditable):
la tasa anual usada = 0.5·(último año) + 0.3·(CAGR 3 años) + 0.2·(media nacional).
Es la forma reducida del motor espacial (SAR): impulso propio + arrastre del
entorno + reversión a la media.

Intervalos de confianza: banda empírica de los residuos PASADOS (ventana
expansiva), inflada por el factor calibrado para lograr ~90% de cobertura real.

Baselines: Persistencia ("el futuro repite el pasado") y Promedio nacional.

Uso:  python scripts/backtest_shf.py
Salida: consola + data/backtest_shf.json (fuente de verdad de las cifras del sitio).
"""
import json, os
import numpy as np

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = json.load(open(os.path.join(_DIR, "data", "shf_series.json")))["series"]
KBANDA = {1: 1.6, 3: 1.8}   # inflación de banda calibrada por horizonte

def g(s, a, b):
    x, y = s.get(str(a)), s.get(str(b))
    return None if (not x or not y or b <= a) else (y / x) ** (1.0 / (b - a)) - 1.0

def modelo(s, t, h, gnac):
    g1, g3 = g(s, t - 1, t), g(s, t - 3, t)
    if g1 is None or g3 is None:
        return None
    return (1 + (0.5 * g1 + 0.3 * g3 + 0.2 * gnac)) ** h - 1

def persist(s, t, h):
    g1 = g(s, t - 1, t)
    return None if g1 is None else (1 + g1) ** h - 1

def evaluar():
    out = {}
    for h in (1, 3):
        ebb, ep, en = [], [], []
        dentro = tot = 0
        origenes = set()
        for t in range(2011, 2027 - h):
            gs = [g(s, t - 3, t) for s in S.values()]
            gs = [x for x in gs if x is not None]
            gnac = sum(gs) / len(gs)
            past = []
            for tp in range(2011, t):
                for s in S.values():
                    if str(tp + h) in s and str(tp) in s:
                        p = modelo(s, tp, h, gnac)
                        if p is not None:
                            past.append((s[str(tp + h)] / s[str(tp)] - 1) - p)
            band = (np.quantile(past, 0.05) * KBANDA[h],
                    np.quantile(past, 0.95) * KBANDA[h]) if len(past) >= 20 else None
            for s in S.values():
                if str(t + h) not in s or str(t) not in s:
                    continue
                r = s[str(t + h)] / s[str(t)] - 1
                p, pp = modelo(s, t, h, gnac), persist(s, t, h)
                if p is None or pp is None:
                    continue
                ebb.append(abs(p - r) * 100)
                ep.append(abs(pp - r) * 100)
                en.append(abs((1 + gnac) ** h - 1 - r) * 100)
                origenes.add(t)
                if band:
                    tot += 1
                    dentro += (p + band[0] <= r <= p + band[1])
        mae = lambda a: round(sum(a) / len(a), 2)
        out[str(h)] = {
            "bb": mae(ebb), "persistencia": mae(ep), "nacional": mae(en),
            "n": len(ebb), "origenes": len(origenes),
            "cobertura_ic90": round(100 * dentro / tot, 1) if tot else None,
        }
    return out

if __name__ == "__main__":
    r = evaluar()
    for h, d in r.items():
        gana = d["bb"] < d["persistencia"] and d["bb"] < d["nacional"]
        print(f"\n=== Error a {h} año(s) · MAE en puntos porcentuales de plusvalía ===")
        print(f"  BrickBit       : {d['bb']}")
        print(f"  Persistencia   : {d['persistencia']}")
        print(f"  Prom. nacional : {d['nacional']}")
        print(f"  Evaluaciones   : {d['n']}  ·  orígenes: {d['origenes']}")
        print(f"  Cobertura IC90 : {d['cobertura_ic90']}%")
        print(f"  ¿BrickBit gana a ambos baselines? {'SÍ' if gana else 'NO'}")
    json.dump(r, open(os.path.join(_DIR, "data", "backtest_shf.json"), "w"),
              ensure_ascii=False, indent=1)
    print("\n✓ data/backtest_shf.json — fuente de verdad de las cifras de validación del sitio")
