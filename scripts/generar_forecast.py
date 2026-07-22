# -*- coding: utf-8 -*-
"""
BrickBit · Genera data/forecast.json con el modelo v2 (ensamble + espacial).

Usa el MISMO modelo y las MISMAS bandas que valida scripts/backtest_shf.py:
así lo que el sitio muestra y lo que el backtest mide son una sola cosa.

Horizontes 1 y 3: validados (walk-forward). 5 y 10: extrapolación del modelo
(tasa anual compuesta) con bandas ensanchadas ~ proporcional al horizonte;
el producto ya los marca como "no validados".

Uso:  python scripts/generar_forecast.py     → reescribe data/forecast.json
"""
import datetime
import json
import os

import backtest_shf as bt   # modelo, bandas y datos compartidos

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = 2026                     # año de origen del pronóstico publicado


def residuos(h):
    out = []
    for tp in range(2011, T - h):
        for z in bt.ZS:
            if str(tp + h) in bt.S[z] and str(tp) in bt.S[z]:
                ga = bt.tasa_modelo(z, tp, h)
                if ga is not None:
                    out.append((bt.S[z][str(tp + h)] / bt.S[z][str(tp)] - 1) - ((1 + ga) ** h - 1))
    return out


def main():
    import numpy as np
    bandas = {}
    for h in (1, 3):
        r = residuos(h)
        k = bt.KBANDA[h]
        bandas[h] = (float(np.quantile(r, 0.05)) * k, float(np.quantile(r, 0.95)) * k)
    # extrapolación 5/10: banda de h=3 escalada por h/3 (conservador)
    for h in (5, 10):
        lo3, hi3 = bandas[3]
        bandas[h] = (lo3 * h / 3.0, hi3 * h / 3.0)

    zonas = {}
    for z in bt.ZS:
        zonas[z] = {}
        for h in (1, 3, 5, 10):
            ga = bt.tasa_modelo(z, T, h if h in (1, 3) else 3)
            if ga is None:
                continue
            f = (1 + ga) ** h
            lo, hi = bandas[h]
            zonas[z][str(h)] = {"f": round(f, 4),
                                "lo": round(max(f + lo, 0.5), 4),
                                "hi": round(f + hi, 4),
                                "g1": round(ga, 4)}
    out = {
        "meta": {
            "modelo": "v2 ensamble: 50% (momentum+tendencia+reversión) + 50% contagio espacial (1/distancia)",
            "origen": T,
            "validacion": "walk-forward SHF 2011-2025 sin fuga; ver scripts/backtest_shf.py y data/backtest_shf.json",
            "horizontes_validados": [1, 3],
            "horizontes_extrapolados": [5, 10],
            "calibracion_ic": "bandas = cuantiles 5-95 de residuos walk-forward × KBANDA (cobertura empírica ~90%)",
            "generado": datetime.date.today().isoformat(),
        },
        "zonas": zonas,
    }
    ruta = os.path.join(_DIR, "data", "forecast.json")
    json.dump(out, open(ruta, "w"), ensure_ascii=False, indent=1)
    print(f"✓ {ruta} · {len(zonas)} zonas · origen {T}")
    ej = zonas.get("Ciudad de México", {})
    print("  CDMX:", json.dumps(ej, ensure_ascii=False)[:220])


if __name__ == "__main__":
    main()
