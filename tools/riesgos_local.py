#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
riesgos_local.py — Capa de seguridad BrickBit desde el SESNSP (datos oficiales).

El gobierno de México bloquea las IPs de la nube (igual que INEGI/DENUE), así
que este script corre EN TU MÁQUINA, igual que denue_local.py:

  1) Descarga el CSV "Incidencia Delictiva Estatal" (nueva metodología) del
     SESNSP: https://www.gob.mx/sesnsp/acciones-y-programas/datos-abiertos-de-incidencia-delictiva
     (el archivo se llama parecido a "IDEFC_NM_ago25.csv").
  2) Corre:  python tools/riesgos_local.py ruta/al/IDEFC_NM_xxx.csv
  3) Sube el data/riesgos.json resultante con el resto del sitio (Netlify).

Qué calcula (últimos 12 meses con dato, por entidad federativa):
  · Homicidio doloso, robo a casa habitación, robo de vehículo y extorsión
  · Tasa por cada 100 mil habitantes (población: Censo INEGI 2020)
  · Percentil nacional (0 = la entidad más segura del país en ese delito)

Honestidad de datos: la incidencia es ESTATAL (carpetas de investigación
iniciadas; hay cifra negra) — el sitio lo etiqueta así y aclara que el riesgo
varía por colonia. Nada de esto se presenta como medición del punto exacto.
"""
import csv, json, sys, unicodedata
from pathlib import Path

# Población por entidad — Censo de Población y Vivienda 2020 (INEGI).
POB = {
    "aguascalientes": 1425607, "baja california": 3769020, "baja california sur": 798447,
    "campeche": 928363, "coahuila de zaragoza": 3146771, "colima": 731391,
    "chiapas": 5543828, "chihuahua": 3741869, "ciudad de mexico": 9209944,
    "durango": 1832650, "guanajuato": 6166934, "guerrero": 3540685,
    "hidalgo": 3082841, "jalisco": 8348151, "mexico": 16992418,
    "michoacan de ocampo": 4748846, "morelos": 1971520, "nayarit": 1235456,
    "nuevo leon": 5784442, "oaxaca": 4132148, "puebla": 6583278,
    "queretaro": 2368467, "quintana roo": 1857985, "san luis potosi": 2822255,
    "sinaloa": 3026943, "sonora": 2944840, "tabasco": 2402598,
    "tamaulipas": 3527735, "tlaxcala": 1342977, "veracruz de ignacio de la llave": 8062579,
    "yucatan": 2320898, "zacatecas": 1622138,
}

# Zona BrickBit (nombre EXACTO de data/estados.json) → entidad del SESNSP.
ZONA_ENTIDAD = {
    "Ciudad de México": "ciudad de mexico", "Guadalajara": "jalisco",
    "Monterrey": "nuevo leon", "Cancún": "quintana roo", "Mérida": "yucatan",
    "Querétaro": "queretaro", "Tijuana": "baja california", "Puebla": "puebla",
    "León": "guanajuato", "San Luis Potosí": "san luis potosi",
    "Aguascalientes": "aguascalientes", "La Paz": "baja california sur",
    "Saltillo": "coahuila de zaragoza", "Chihuahua": "chihuahua",
    "Culiacán": "sinaloa", "Hermosillo": "sonora", "Durango": "durango",
    "Tepic": "nayarit", "Colima": "colima", "Toluca": "mexico",
    "Morelia": "michoacan de ocampo", "Cuernavaca": "morelos",
    "Pachuca": "hidalgo", "Oaxaca": "oaxaca", "Tuxtla Gutiérrez": "chiapas",
    "Villahermosa": "tabasco", "Campeche": "campeche", "Veracruz": "veracruz de ignacio de la llave",
    "Zacatecas": "zacatecas", "Tlaxcala": "tlaxcala", "Reynosa": "tamaulipas",
    "Chilpancingo": "guerrero",
}

DELITOS = {  # subtipo SESNSP (normalizado) → clave corta del JSON
    "homicidio doloso": "homicidio",
    "robo a casa habitacion": "robo_casa",
    "robo de vehiculo automotor": "robo_vehiculo",
    "extorsion": "extorsion",
}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def norm(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip().lower()


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    src = Path(sys.argv[1])
    if not src.exists():
        print(f"No encuentro {src}"); sys.exit(1)

    # SESNSP publica en latin-1 o utf-8 según el corte; probar ambos.
    for enc in ("utf-8-sig", "latin-1"):
        try:
            rows = list(csv.DictReader(src.open(encoding=enc)))
            if rows and any("entidad" in norm(k) for k in rows[0]):
                break
        except UnicodeDecodeError:
            continue
    else:
        print("No pude leer el CSV (¿es el archivo estatal del SESNSP?)"); sys.exit(1)

    cols = {norm(k): k for k in rows[0]}
    c_ent, c_anio, c_sub = cols.get("entidad"), cols.get("ano") or cols.get("año"), cols.get("subtipo de delito")
    c_mes = {m: cols.get(m) for m in MESES}
    if not (c_ent and c_anio and c_sub):
        print("El CSV no trae Entidad/Año/Subtipo de delito — usa el archivo ESTATAL nueva metodología."); sys.exit(1)

    # serie mensual por (entidad, delito): {(ent, delito): {(año, mes_idx): suma}}
    serie = {}
    for r in rows:
        d = DELITOS.get(norm(r[c_sub]))
        if not d:
            continue
        ent = norm(r[c_ent])
        try:
            anio = int(float(r[c_anio]))
        except (TypeError, ValueError):
            continue
        for i, m in enumerate(MESES):
            raw = (r.get(c_mes[m]) or "").replace(",", "").strip()
            if raw == "":
                continue  # mes aún sin publicar
            try:
                v = int(float(raw))
            except ValueError:
                continue
            key = (ent, d)
            serie.setdefault(key, {})[(anio, i)] = serie.setdefault(key, {}).get((anio, i), 0) + v

    # últimos 12 meses con dato, por entidad y delito → tasa por 100 mil
    tasas, corte = {}, None
    for (ent, d), meses in serie.items():
        orden = sorted(meses)  # cronológico
        ult12 = orden[-12:]
        if len(ult12) < 12:
            continue
        total = sum(meses[k] for k in ult12)
        pob = POB.get(ent)
        if not pob:
            continue
        tasas.setdefault(ent, {})[d] = round(total / pob * 100000, 1)
        fin = ult12[-1]
        if corte is None or fin > corte:
            corte = fin

    if not tasas:
        print("No salió ninguna tasa — revisa que el CSV sea el estatal con meses."); sys.exit(1)

    # percentil nacional por delito (0 = la más segura)
    percentiles = {}
    for d in set(DELITOS.values()):
        vals = sorted(v[d] for v in tasas.values() if d in v)
        for ent, v in tasas.items():
            if d in v and len(vals) > 1:
                pct = round(100 * sum(1 for x in vals if x < v[d]) / (len(vals) - 1))
                percentiles.setdefault(ent, {})[d] = min(pct, 100)

    zonas = {}
    for zona, ent in ZONA_ENTIDAD.items():
        if ent in tasas:
            zonas[zona] = {"entidad": ent.title(), "tasas": tasas[ent],
                           "percentil": percentiles.get(ent, {})}

    out = {
        "meta": {
            "fuente": "SESNSP · Incidencia Delictiva Estatal (nueva metodología), carpetas de investigación",
            "poblacion": "Censo INEGI 2020",
            "corte": f"{corte[0]}-{corte[1] + 1:02d}" if corte else None,
            "nota": ("Tasas ESTATALES por 100 mil habitantes, últimos 12 meses publicados. "
                     "Hay cifra negra y el riesgo varía mucho por colonia: es contexto, no medición del punto exacto."),
        },
        "zonas": zonas,
    }
    dst = Path(__file__).resolve().parent.parent / "data" / "riesgos.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ {dst} — {len(zonas)} zonas, corte {out['meta']['corte']}")
    print("   Súbelo con el sitio y el mapa mostrará la capa de seguridad.")


if __name__ == "__main__":
    main()
