# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
 BrickBit · BACKTESTING DEL MOTOR — ¿el SAR predijo el pasado?
═══════════════════════════════════════════════════════════════════════════════
 Valida el Motor de Morfogénesis contra la historia real: corre el SAR desde
 un año pasado y compara la proyección contra los precios observados. El
 resultado calibra ρ (la virulencia real del contagio) por entidad.

 Entrada esperada: un CSV con el Índice SHF de precios de vivienda por
 entidad federativa (Sociedad Hipotecaria Federal, público en
 https://www.gob.mx/shf → estadísticas → índice SHF, o vía datos.gob.mx):

     data/indice_shf.csv   con columnas: estado, año, indice

 Uso:
     python scripts/backtesting.py                # usa data/indice_shf.csv
     python scripts/backtesting.py mi_indice.csv

 Salida:
   · data/backtest_resultados.csv  (estado, rho_optimo, error_pct)
   · resumen en consola: MAPE global y ρ calibrado por estado.
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys

import numpy as np
import pandas as pd

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _DIR)


def backtest(ruta_csv: str) -> None:
    import app   # reutiliza el motor y la contigüidad real

    hist = pd.read_csv(ruta_csv)
    años = sorted(hist["año"].unique())
    if len(años) < 4:
        print("Se necesitan ≥4 años de historia para calibrar.")
        sys.exit(1)
    base, fin = años[0], años[-1]
    horizonte = fin - base
    print(f"📅 Backtest {base} → {fin} ({horizonte} años)")

    df_e = app.datos_estatales()
    pivote = hist.pivot(index="estado", columns="año", values="indice") \
        .reindex(df_e["estado"])
    v_real_0 = pivote[base].to_numpy(dtype=float)
    v_real_f = pivote[fin].to_numpy(dtype=float)
    crecimiento_real = v_real_f / v_real_0 - 1

    pi, pj, g = app.vecindad_estados()
    potencial = df_e["potencial"].to_numpy(dtype=float)
    g_propio = df_e["plusvalia"].to_numpy(dtype=float) / 100.0 * 0.55

    mejores = None
    for rho in np.arange(0.0, 1.55, 0.05):
        v = v_real_0.copy()
        pot = potencial.copy()
        for _ in range(horizonte):
            vn = (v - v.min()) / (np.ptp(v) + 1e-9)
            derrame = np.bincount(pi, weights=vn[pj], minlength=v.size) / g
            v = v * (1 + g_propio + rho * 0.10 * derrame * pot)
        error = np.abs(v / v_real_0 - 1 - crecimiento_real) \
            / (np.abs(crecimiento_real) + 1e-9)
        mape = float(np.nanmean(error) * 100)
        if mejores is None or mape < mejores[1]:
            mejores = (rho, mape, v)
        print(f"  ρ={rho:.2f} → MAPE {mape:.1f}%")

    rho_opt, mape_opt, v_pred = mejores
    print(f"\n✅ ρ óptimo global = {rho_opt:.2f} (MAPE {mape_opt:.1f}%)")

    error_edo = np.abs(v_pred / v_real_0 - 1 - crecimiento_real) * 100
    salida = pd.DataFrame({"estado": df_e["estado"],
                           "crecimiento_real_pct": crecimiento_real * 100,
                           "crecimiento_predicho_pct":
                           (v_pred / v_real_0 - 1) * 100,
                           "error_pp": error_edo})
    ruta_out = os.path.join(_DIR, "data", "backtest_resultados.csv")
    salida.round(1).to_csv(ruta_out, index=False)
    print(f"✓ {ruta_out}")
    print("\nTop aciertos:")
    print(salida.nsmallest(5, "error_pp").to_string(index=False))


def validar_contagio_denue(sufijo: str = "azcapotzalco") -> None:
    """
    VALIDACIÓN CON DATOS REALES — sin necesidad del índice SHF. Usa el propio
    DENUE (columna `anio` = fecha_alta) para poner a prueba la premisa central
    del motor: ¿la actividad económica se CONTAGIA espacialmente?

    Prueba out-of-sample temporal: ¿la vitalidad de una zona y de sus VECINAS
    ANTES de un corte predice dónde ABREN negocios DESPUÉS? Si el coeficiente
    del vecindario es alto, el término espacial del SAR (ρ·W·v) está
    empíricamente justificado.
    """
    import gzip
    ruta = os.path.join(_DIR, "data", f"establecimientos_{sufijo}.csv.gz")
    if not os.path.exists(ruta):
        print(f"✗ No existe {ruta}. Genera los datos con "
              f"ingerir_denue.py primero.")
        return
    with gzip.open(ruta, "rt", encoding="utf-8") as f:
        d = pd.read_csv(f)
    if "anio" not in d.columns:
        print("✗ El export no tiene columna 'anio'. Reejecuta ingerir_denue.py.")
        return
    d = d.dropna(subset=["lat", "lng", "anio"])

    # rejilla ~300 m
    gy = np.round((d["lat"] - d["lat"].min()) / 0.0027).astype(int)
    gx = np.round((d["lng"] - d["lng"].min()) / 0.0027).astype(int)
    d = d.assign(celda=gy * 10000 + gx)
    corte = d["anio"].quantile(0.6)
    viejo = d[d["anio"] <= corte].groupby("celda").size()
    nuevo = d[d["anio"] > corte].groupby("celda").size()
    cel = pd.DataFrame({"viejo": viejo, "nuevo": nuevo}).fillna(0)

    idx = cel.index.values
    gyv, gxv, vv = idx // 10000, idx % 10000, cel["viejo"].values
    vecino = np.array([vv[(np.abs(gyv - gyv[i]) <= 1)
                          & (np.abs(gxv - gxv[i]) <= 1)].sum() - vv[i]
                       for i in range(len(idx))])
    r_prop = float(np.corrcoef(cel["viejo"], cel["nuevo"])[0, 1])
    r_vec = float(np.corrcoef(vecino, cel["nuevo"])[0, 1])

    print(f"\n🔬 VALIDACIÓN DE CONTAGIO ESPACIAL — DENUE real ({sufijo})")
    print(f"   {len(cel)} celdas · corte temporal en {corte:.0f}")
    print(f"   vitalidad PROPIA (pre-corte) → aperturas post-corte : r = {r_prop:.3f}")
    print(f"   vitalidad de VECINAS (pre-corte) → aperturas post    : r = {r_vec:.3f}")
    veredicto = ("✅ el término espacial del SAR está EMPÍRICAMENTE justificado"
                 if r_vec > 0.25 else "⚠️ señal espacial débil en esta zona")
    print(f"   {veredicto}")
    # persiste el resultado para que la app lo muestre
    salida = os.path.join(_DIR, "data", f"validacion_{sufijo}.json")
    import json
    with open(salida, "w", encoding="utf-8") as f:
        json.dump({"r_propio": round(r_prop, 3), "r_vecinas": round(r_vec, 3),
                   "celdas": int(len(cel)), "corte": int(corte)}, f)
    print(f"   ✓ {salida}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "denue":
        validar_contagio_denue(sys.argv[2] if len(sys.argv) > 2
                               else "azcapotzalco")
        sys.exit(0)
    ruta = sys.argv[1] if len(sys.argv) > 1 \
        else os.path.join(_DIR, "data", "indice_shf.csv")
    if not os.path.exists(ruta):
        print(f"✗ No existe {ruta}. Descarga el Índice SHF por entidad "
              "(https://transparencia.shf.gob.mx) y guárdalo con columnas: "
              "estado, año, indice.\n"
              "   Alternativa REAL sin SHF: python scripts/backtesting.py denue")
        sys.exit(1)
    backtest(ruta)
