"""Genera los conjuntos de ejemplo que trae Abaco.

Honestidad de datos (principio de la casa): lo que viene de una fuente real se
anota como tal; lo simulado se anota como simulado, columna por columna, en
FUENTES.md. Ningun dato simulado se presenta como hecho.
"""
from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np
import pandas as pd

RAIZ = Path("/home/user/BrickBit.co")
SAL = RAIZ / "abaco/packages/core/abaco_core/data/ejemplos"
SAL.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(20260905)

# --------------------------------------------------------------------------
# 1. Corte transversal de las 32 entidades (base real: data/estados.json, SHF)
# --------------------------------------------------------------------------
crudo = json.loads((RAIZ / "data/estados.json").read_text(encoding="utf-8"))
filas = []
for e in crudo["estados"]:
    filas.append({
        "entidad": e["nombre"],
        "lat": e["lat"],
        "lng": e["lng"],
        "precio_m2": e.get("precio_m2"),
        "plusvalia_pct": e.get("plusvalia"),
        "yield_pct": e.get("yield"),
        "dias_en_mercado": e.get("dom"),
        "ciclo": e.get("ciclo"),
        "valor_mediano_vivienda": e.get("valor_mediano_vivienda_shf"),
    })
est = pd.DataFrame(filas).sort_values("entidad").reset_index(drop=True)
n = len(est)

# Covariables socioeconomicas: SIMULADAS, correlacionadas con el precio real
# para que los ejemplos econometricos den resultados con sentido.
base = np.log(est["precio_m2"].astype(float).fillna(est["precio_m2"].median()))
z = (base - base.mean()) / base.std(ddof=0)
est["ingreso_hogar_mensual"] = np.round(11000 * np.exp(0.42 * z + rng.normal(0, .10, n)), -2)
est["escolaridad_anios"] = np.round(9.6 + 1.35 * z + rng.normal(0, .35, n), 1)
est["densidad_hab_km2"] = np.round(np.exp(4.6 + 1.05 * z + rng.normal(0, .55, n)), 1)
est["poblacion_miles"] = np.round(np.exp(7.4 + .35 * rng.normal(0, 1, n)) , 0)
est["empleo_formal_pct"] = np.round(np.clip(38 + 9.5 * z + rng.normal(0, 3.2, n), 12, 78), 1)
est["credito_hipotecario_pc"] = np.round(np.clip(2.1 + .9 * z + rng.normal(0, .35, n), .2, None), 2)
est.to_csv(SAL / "mexico_estados.csv", index=False)

# --------------------------------------------------------------------------
# 2. Macro trimestral 2005T1-2025T4 (SIMULADA, calibrada a ordenes de magnitud reales)
# --------------------------------------------------------------------------
per = pd.period_range("2005Q1", "2025Q4", freq="Q")
T = len(per)
t = np.arange(T)
ciclo = 2.8 * np.sin(2 * math.pi * t / 34) + 1.3 * np.sin(2 * math.pi * t / 11)
choque = np.zeros(T); choque[(per.year == 2009)] = -5.5; choque[(per.year == 2020) & (per.quarter == 2)] = -17.0
choque[(per.year == 2020) & (per.quarter == 3)] = -8.0; choque[(per.year == 2021)] = 3.0
pib = 100 * np.exp(np.cumsum(0.0055 + 0.0016 * rng.standard_normal(T)) ) + ciclo + np.cumsum(choque) / 8
infl = np.clip(3.9 + 0.55 * ciclo + np.where(per.year >= 2022, 2.6, 0) * np.exp(-(t - 68)**2 / 90) + rng.normal(0, .55, T), .8, 9.5)
tasa = np.clip(0.62 * infl + 1.9 + 0.25 * rng.standard_normal(T), 3.0, 11.5)
fx = 11.2 * np.exp(np.cumsum(0.0075 + 0.021 * rng.standard_normal(T)))
desempleo = np.clip(3.9 - 0.22 * ciclo - np.cumsum(choque) / 120 + rng.normal(0, .22, T), 2.6, 6.4)
macro = pd.DataFrame({
    "fecha": per.to_timestamp(how="start").normalize(),
    "trimestre": per.astype(str),
    "pib_indice": np.round(pib, 2),
    "inflacion_anual": np.round(infl, 2),
    "tasa_objetivo": np.round(tasa, 2),
    "tipo_cambio": np.round(fx, 3),
    "desempleo": np.round(desempleo, 2),
})
macro["consumo_indice"] = np.round(0.72 * macro.pib_indice + 24 + rng.normal(0, 1.1, T), 2)
macro["inversion_indice"] = np.round(1.35 * macro.pib_indice - 34 + rng.normal(0, 3.4, T), 2)
macro.to_csv(SAL / "mexico_macro_trimestral.csv", index=False)

# --------------------------------------------------------------------------
# 3. Panel estatal anual 2010-2024 (SIMULADO)
# --------------------------------------------------------------------------
anios = list(range(2010, 2025))
regs = []
efecto_fijo = dict(zip(est.entidad, rng.normal(0, .28, n)))
for _, e in est.iterrows():
    ef = efecto_fijo[e.entidad]
    nivel = math.log(max(e.ingreso_hogar_mensual, 1)) + ef
    for a in anios:
        ch = -0.085 if a == 2020 else (0.03 if a == 2021 else 0.0)
        tend = 0.021 * (a - 2010)
        lpib = nivel + tend + ch + rng.normal(0, .035)
        inv = 0.19 * math.exp(lpib) * math.exp(rng.normal(0, .16))
        cre = 0.31 * math.exp(lpib) * math.exp(rng.normal(0, .22))
        regs.append({
            "entidad": e.entidad, "anio": a,
            "pib_per_capita": round(math.exp(lpib) * 9.4, 1),
            "inversion_pc": round(inv * 9.4, 1),
            "credito_pc": round(cre * 9.4, 1),
            "empleo_formal_pct": round(min(max(e.empleo_formal_pct + 0.42 * (a - 2010) + rng.normal(0, 1.1), 10), 82), 2),
            "salario_real": round(280 * math.exp(0.4 * (lpib - 9)) * (1 + 0.012 * (a - 2010)) + rng.normal(0, 6), 2),
        })
panel = pd.DataFrame(regs)
panel.to_csv(SAL / "panel_estados_anual.csv", index=False)

# --------------------------------------------------------------------------
# 4. Matriz insumo-producto, 12 sectores (SIMULADA, estructura tipo INEGI)
# --------------------------------------------------------------------------
sectores = ["Agropecuario","Mineria","Energia","Manufactura alimentos","Manufactura metalica",
            "Manufactura otras","Construccion","Comercio","Transporte","Informacion y medios",
            "Servicios financieros","Servicios diversos"]
k = len(sectores)
A = rng.uniform(0.008, 0.075, (k, k))
np.fill_diagonal(A, rng.uniform(0.09, 0.24, k))
A[:, 6] *= 1.9   # la construccion compra mucho a los demas
A[3, 0] += 0.16  # alimentos compra al agro
A[4, 1] += 0.12  # metalica compra a mineria
A = A / np.maximum(A.sum(axis=0), 1e-9) * rng.uniform(0.34, 0.63, k)  # suma de insumos < 1
vbp = np.round(rng.uniform(180, 2400, k) * 1000, 0)
Z = A * vbp
dem = vbp - Z.sum(axis=1)
mio = pd.DataFrame(np.round(Z, 1), index=sectores, columns=sectores)
mio.insert(0, "sector", sectores)
mio["demanda_final"] = np.round(dem, 1)
mio["produccion_total"] = np.round(vbp, 1)
mio["empleo_miles"] = np.round(vbp / rng.uniform(420, 1900, k), 2)
mio["remuneraciones"] = np.round(vbp * rng.uniform(0.16, 0.42, k), 1)
mio.to_csv(SAL / "mexico_insumo_producto.csv", index=False)

# --------------------------------------------------------------------------
# 5. Microdatos de hogares (SIMULADOS, forma tipo ENIGH)
# --------------------------------------------------------------------------
m = 2400
ing = np.exp(rng.normal(9.35, .62, m))
edad = np.clip(rng.normal(41, 12, m), 20, 78).round(0)
esc = np.clip(rng.normal(10.6, 3.6, m), 0, 22).round(0)
tam = np.clip(rng.poisson(3.4, m), 1, 11)
urbano = rng.binomial(1, .78, m)
idx = (-6.4 + 0.52 * np.log(ing) + 0.061 * esc + 0.031 * edad - 0.0004 * edad**2
       - 0.085 * tam + 0.36 * urbano + rng.logistic(0, 1, m))
hog = pd.DataFrame({
    "id_hogar": np.arange(1, m + 1),
    "ingreso_mensual": np.round(ing, 0),
    "edad_jefe": edad, "escolaridad_anios": esc, "tamano_hogar": tam,
    "urbano": urbano,
    "tiene_credito_hipotecario": (idx > 0).astype(int),
    "gasto_vivienda": np.round(ing * np.clip(rng.normal(.24, .08, m), .04, .62), 0),
    "entidad": rng.choice(est.entidad.tolist(), m),
})
hog.to_csv(SAL / "hogares_vivienda.csv", index=False)

for f in sorted(SAL.glob("*.csv")):
    d = pd.read_csv(f)
    print(f"{f.name:34s} {d.shape[0]:5d} x {d.shape[1]:2d}  {f.stat().st_size/1024:6.1f} KB")
