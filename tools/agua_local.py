#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agua_local.py — Disponibilidad de agua (sequía) por municipio, desde CONAGUA.

Dato real y público: el Monitor de Sequía de México (SMN/CONAGUA) publica cada
quincena el nivel de sequía POR MUNICIPIO (escala D0 a D4). A nivel colonia no
existe dato público nacional — no lo inventamos.

Como el gobierno bloquea IPs de nube (igual que DENUE/SESNSP), corre LOCAL:
  1) Descarga el CSV municipal del Monitor de Sequía:
     https://smn.conagua.gob.mx/es/climatologia/monitor-de-sequia/monitor-de-sequia-en-mexico
     (archivo tipo "MunicipiosSequia.csv": una fila por municipio y una columna
     por fecha de corte; el valor es D0..D4 o vacío = sin sequía).
  2) python tools/agua_local.py ruta/al/MunicipiosSequia.csv
  3) Sube data/agua.json con el sitio. El mapa y el analizador lo muestran solos.

Escala (US Drought Monitor adaptada por CONAGUA):
  sin dato/vacío = Sin sequía · D0 anormalmente seco · D1 moderada
  D2 severa · D3 extrema · D4 excepcional
"""
import csv, json, sys, unicodedata
from pathlib import Path

def norm(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip().lower()

# Zona BrickBit → (municipio del monitor, entidad). CDMX agrega sus alcaldías.
ZONA_MUN = {
    "Ciudad de México": ("*", "ciudad de mexico"),
    "Guadalajara": ("guadalajara", "jalisco"),
    "Monterrey": ("monterrey", "nuevo leon"),
    "Cancún": ("benito juarez", "quintana roo"),
    "Mérida": ("merida", "yucatan"),
    "Querétaro": ("queretaro", "queretaro"),
    "Tijuana": ("tijuana", "baja california"),
    "Puebla": ("puebla", "puebla"),
    "León": ("leon", "guanajuato"),
    "San Luis Potosí": ("san luis potosi", "san luis potosi"),
    "Aguascalientes": ("aguascalientes", "aguascalientes"),
    "La Paz": ("la paz", "baja california sur"),
    "Saltillo": ("saltillo", "coahuila"),
    "Chihuahua": ("chihuahua", "chihuahua"),
    "Culiacán": ("culiacan", "sinaloa"),
    "Hermosillo": ("hermosillo", "sonora"),
    "Durango": ("durango", "durango"),
    "Tepic": ("tepic", "nayarit"),
    "Colima": ("colima", "colima"),
    "Toluca": ("toluca", "mexico"),
    "Morelia": ("morelia", "michoacan"),
    "Cuernavaca": ("cuernavaca", "morelos"),
    "Pachuca": ("pachuca de soto", "hidalgo"),
    "Oaxaca": ("oaxaca de juarez", "oaxaca"),
    "Tuxtla Gutiérrez": ("tuxtla gutierrez", "chiapas"),
    "Villahermosa": ("centro", "tabasco"),
    "Campeche": ("campeche", "campeche"),
    "Veracruz": ("veracruz", "veracruz"),
    "Zacatecas": ("zacatecas", "zacatecas"),
    "Tlaxcala": ("tlaxcala", "tlaxcala"),
    "Reynosa": ("reynosa", "tamaulipas"),
    "Chilpancingo": ("chilpancingo de los bravo", "guerrero"),
}
NIVEL = {"": 0, "d0": 1, "d1": 2, "d2": 3, "d3": 4, "d4": 5}
ETIQ = ["Sin sequía", "D0 · anormalmente seco", "D1 · sequía moderada",
        "D2 · sequía severa", "D3 · sequía extrema", "D4 · sequía excepcional"]


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    src = Path(sys.argv[1])
    if not src.exists():
        print(f"No encuentro {src}"); sys.exit(1)

    rows = None
    for enc in ("utf-8-sig", "latin-1"):
        try:
            rows = list(csv.reader(src.open(encoding=enc)))
            if rows and len(rows[0]) > 3:
                break
        except UnicodeDecodeError:
            continue
    if not rows:
        print("No pude leer el CSV."); sys.exit(1)

    head = rows[0]
    hn = [norm(h) for h in head]
    try:
        i_mun = next(i for i, h in enumerate(hn) if "nombre_mun" in h or h == "municipio")
        i_ent = next(i for i, h in enumerate(hn) if "entidad" in h or h == "estado")
    except StopIteration:
        print("El CSV no trae columnas de municipio/entidad — usa el archivo municipal del Monitor."); sys.exit(1)
    i_fecha = len(head) - 1              # última columna = corte más reciente
    corte = head[i_fecha]

    # nivel por (municipio, entidad)
    monitor = {}
    for r in rows[1:]:
        if len(r) <= i_fecha: continue
        monitor[(norm(r[i_mun]), norm(r[i_ent]))] = NIVEL.get(norm(r[i_fecha]), 0)

    municipios = {f"{m}|{e}": n for (m, e), n in monitor.items()}
    zonas = {}
    for zona, (mun, ent) in ZONA_MUN.items():
        if mun == "*":   # CDMX: el peor nivel entre sus alcaldías
            niveles = [n for (m, e), n in monitor.items() if ent in e]
        else:
            niveles = [n for (m, e), n in monitor.items()
                       if m == mun and (ent in e or e in ent)]
            if not niveles:   # respaldo: coincidencia parcial del nombre
                niveles = [n for (m, e), n in monitor.items()
                           if mun in m and (ent in e or e in ent)]
        if niveles:
            n = max(niveles)
            zonas[zona] = {"nivel": n, "etiqueta": ETIQ[n]}

    if not zonas:
        print("Ningún municipio empató — revisa que sea el CSV municipal."); sys.exit(1)

    out = {
        "meta": {
            "fuente": "Monitor de Sequía de México (SMN/CONAGUA), corte municipal",
            "corte": corte,
            "escala": "0 sin sequía · 1 D0 · 2 D1 · 3 D2 · 4 D3 · 5 D4",
            "nota": ("Nivel de sequía OFICIAL por municipio (quincenal). Es contexto de "
                     "disponibilidad hídrica, no factibilidad de servicio: la dotación de "
                     "agua de un proyecto la dicta el organismo operador local."),
        },
        "zonas": zonas,
        "municipios": municipios,
    }
    dst = Path(__file__).resolve().parent.parent / "data" / "agua.json"
    dst.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"✅ {dst} — {len(zonas)} zonas, {len(municipios)} municipios, corte {corte}")


if __name__ == "__main__":
    main()
