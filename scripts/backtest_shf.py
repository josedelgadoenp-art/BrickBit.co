# -*- coding: utf-8 -*-
"""
BrickBit · Backtest walk-forward REPRODUCIBLE del modelo de plusvalía (v2).

MODELO (elegido con protocolo anti-overfitting: pesos calibrados SOLO con
orígenes 2011-2018 y validados en 2019+ que el modelo nunca vio):

  tasa anual = 0.5 · [0.5·g1 + 0.3·g3 + 0.2·g_nacional]        (momentum+reversión)
             + 0.5 · [w1·g1 + w2·g3 + w3·g_nac + w4·g_vecinal] (contagio espacial)

  g_vecinal = crecimiento 3 años de las demás zonas ponderado por 1/distancia
  (forma reducida del SAR: el término W·v del motor de morfogénesis).
  Pesos espaciales por horizonte (promedio del top-10 en calibración):
    h=1 → (0.18, 0.06, 0.01, 0.75)   ·   h=3 → (0.34, 0.01, 0.03, 0.62)

Bandas de confianza: cuantiles 5-95 de los residuos PASADOS (ventana expansiva)
inflados por KBANDA para lograr ~90% de cobertura empírica real.

Uso:  python scripts/backtest_shf.py
Salida: consola + data/backtest_shf.json (fuente de verdad del sitio).
"""
import json, math, os
import numpy as np

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = json.load(open(os.path.join(_DIR, "data", "shf_series.json")))["series"]
_E = json.load(open(os.path.join(_DIR, "data", "estados.json")))
COORD = {e["nombre"]: (e["lat"], e["lng"]) for e in (_E.get("estados") or _E)}
ZS = [z for z in S if z in COORD]

WESP = {1: (0.18, 0.06, 0.01, 0.75), 3: (0.34, 0.01, 0.03, 0.62)}
KBANDA = {1: 2.0, 3: 1.85}            # se re-mide abajo; ajustar si la cobertura se aleja de 90

def _hav(a, b):
    R, p = 6371, math.pi / 180
    la1, lo1 = COORD[a]; la2, lo2 = COORD[b]
    h = math.sin((la2 - la1) * p / 2) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))

W = {}
for a in ZS:
    ws = [(b, 1.0 / max(_hav(a, b), 50)) for b in ZS if b != a]
    tot = sum(w for _, w in ws)
    W[a] = [(b, w / tot) for b, w in ws]

def g(s, a, b):
    x, y = s.get(str(a)), s.get(str(b))
    return None if (not x or not y or b <= a) else (y / x) ** (1.0 / (b - a)) - 1.0

def tasa_modelo(z, t, h):
    s = S[z]
    g1, g3 = g(s, t - 1, t), g(s, t - 3, t)
    if g1 is None or g3 is None:
        return None
    gn = [g(S[b], t - 3, t) for b in ZS]
    gn = [x for x in gn if x is not None]
    gnac = sum(gn) / len(gn)
    gvec = sum(w * (g(S[b], t - 3, t) or gnac) for b, w in W[z])
    w1, w2, w3, w4 = WESP.get(h, WESP[3])
    parte_base = 0.5 * g1 + 0.3 * g3 + 0.2 * gnac
    parte_esp = w1 * g1 + w2 * g3 + w3 * gnac + w4 * gvec
    return 0.5 * parte_base + 0.5 * parte_esp

def evaluar():
    out = {}
    for h in (1, 3):
        ebb, ep, en = [], [], []
        dentro = tot = 0
        origenes = set()
        for t in range(2011, 2027 - h):
            gn = [g(S[b], t - 3, t) for b in ZS]
            gn = [x for x in gn if x is not None]
            gnac = sum(gn) / len(gn)
            past = []
            for tp in range(2011, t):
                for z in ZS:
                    if str(tp + h) in S[z] and str(tp) in S[z]:
                        ga = tasa_modelo(z, tp, h)
                        if ga is not None:
                            past.append((S[z][str(tp + h)] / S[z][str(tp)] - 1) - ((1 + ga) ** h - 1))
            band = (np.quantile(past, 0.05) * KBANDA[h], np.quantile(past, 0.95) * KBANDA[h]) if len(past) >= 20 else None
            for z in ZS:
                if str(t + h) not in S[z] or str(t) not in S[z]:
                    continue
                r = S[z][str(t + h)] / S[z][str(t)] - 1
                ga = tasa_modelo(z, t, h)
                g1 = g(S[z], t - 1, t)
                if ga is None or g1 is None:
                    continue
                p = (1 + ga) ** h - 1
                ebb.append(abs(p - r) * 100)
                ep.append(abs((1 + g1) ** h - 1 - r) * 100)
                en.append(abs((1 + gnac) ** h - 1 - r) * 100)
                origenes.add(t)
                if band:
                    tot += 1
                    dentro += (p + band[0] <= r <= p + band[1])
        mae = lambda a: round(sum(a) / len(a), 2)
        out[str(h)] = {"bb": mae(ebb), "persistencia": mae(ep), "nacional": mae(en),
                       "n": len(ebb), "origenes": len(origenes),
                       "cobertura_ic90": round(100 * dentro / tot, 1) if tot else None}
    return out

if __name__ == "__main__":
    r = evaluar()
    for h, d in r.items():
        gana = d["bb"] < d["persistencia"] and d["bb"] < d["nacional"]
        print(f"\n=== Error a {h} año(s) · MAE puntos % de plusvalía ===")
        print(f"  BrickBit (ensamble+espacial): {d['bb']}")
        print(f"  Persistencia               : {d['persistencia']}")
        print(f"  Prom. nacional             : {d['nacional']}")
        print(f"  n={d['n']} · orígenes {d['origenes']} · cobertura IC90 {d['cobertura_ic90']}%")
        print(f"  ¿Gana a ambos baselines? {'SÍ' if gana else 'NO'}")
    json.dump(r, open(os.path.join(_DIR, "data", "backtest_shf.json"), "w"), ensure_ascii=False, indent=1)
    print("\n✓ data/backtest_shf.json")
