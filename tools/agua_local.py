#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agua_local.py — Disponibilidad de agua (sequía) por municipio, desde CONAGUA.

Dato real y público: el Monitor de Sequía de México (SMN/CONAGUA) publica cada
quincena el nivel de sequía POR MUNICIPIO (escala D0 a D4). A nivel colonia no
existe dato público nacional — no lo inventamos.

Como el gobierno bloquea IPs de nube (igual que DENUE/SESNSP), corre LOCAL:
  1) Descarga "MunicipiosSequia.xlsx" del Monitor de Sequía:
     https://smn.conagua.gob.mx/es/climatologia/monitor-de-sequia/monitor-de-sequia-en-mexico
  2) python tools/agua_local.py ruta/al/MunicipiosSequia.xlsx
     (también acepta .csv si algún día lo publican en ese formato)
  3) Sube data/agua.json con el sitio. El mapa y el analizador lo muestran solos.

El archivo trae una fila por municipio y una columna por corte quincenal desde
2003; se toma SIEMPRE la última columna (el corte más reciente). Las celdas
vacías significan "sin sequía" y en Excel simplemente no existen: por eso se
leen por letra de columna y no por posición.

Escala (US Drought Monitor adaptada por CONAGUA):
  vacío = Sin sequía · D0 anormalmente seco · D1 moderada
  D2 severa · D3 extrema · D4 excepcional
"""
import csv, json, sys, unicodedata, zipfile, datetime
import xml.etree.ElementTree as ET
from pathlib import Path

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


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


def col_letra(ref):
    """'AV12' → 'AV' (letra de columna de una referencia de celda)."""
    return ref.rstrip("0123456789")


def fecha_serial(v):
    """Número de serie de Excel → 'AAAA-MM-DD' (si ya es texto, lo devuelve)."""
    try:
        d = datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(v)))
        return d.isoformat()
    except (TypeError, ValueError):
        return str(v)


def leer_xlsx(path):
    """Lee la hoja de municipios sin dependencias externas.
    Devuelve (filas, corte) donde filas = [{'mun':…, 'ent':…, 'nivel':…}]."""
    z = zipfile.ZipFile(path)
    try:
        shared = [
            "".join(t.text or "" for t in si.iter(NS + "t"))
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(NS + "si")
        ]
    except KeyError:
        shared = []

    # hoja de municipios (la primera, o la que se llame MUNICIPIOS)
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    nombres = [s.get("name", "") for s in wb.iter(NS + "sheet")]
    idx = next((i for i, n in enumerate(nombres) if "municipio" in norm(n)), 0)
    hoja = ET.fromstring(z.read(f"xl/worksheets/sheet{idx + 1}.xml"))

    def val(c):
        v = c.find(NS + "v")
        if v is None:
            inline = c.find(NS + "is")
            return "".join(x.text or "" for x in inline.iter(NS + "t")) if inline is not None else ""
        return shared[int(v.text)] if c.get("t") == "s" else (v.text or "")

    filas_xml = list(hoja.iter(NS + "row"))
    if not filas_xml:
        raise ValueError("La hoja está vacía.")

    encabezado = [(col_letra(c.get("r", "")), val(c)) for c in filas_xml[0].iter(NS + "c")]
    cols = {v: k for k, v in ((k, norm(v)) for k, v in encabezado)}  # nombre normalizado → letra
    c_mun = cols.get("nombre_mun") or cols.get("municipio")
    c_ent = cols.get("entidad") or cols.get("estado")
    if not (c_mun and c_ent):
        raise ValueError("No encuentro las columnas NOMBRE_MUN / ENTIDAD.")
    c_ultima, v_ultima = encabezado[-1]        # última columna = corte más reciente

    filas = []
    for r in filas_xml[1:]:
        celdas = {col_letra(c.get("r", "")): val(c) for c in r.iter(NS + "c")}
        mun, ent = celdas.get(c_mun, ""), celdas.get(c_ent, "")
        if not mun:
            continue
        # celda ausente = sin sequía (el Excel omite las vacías)
        filas.append({"mun": norm(mun), "ent": norm(ent),
                      "nivel": NIVEL.get(norm(celdas.get(c_ultima, "")), 0)})
    return filas, fecha_serial(v_ultima)


def leer_csv(path):
    rows = None
    for enc in ("utf-8-sig", "latin-1"):
        try:
            rows = list(csv.reader(path.open(encoding=enc)))
            if rows and len(rows[0]) > 3:
                break
        except UnicodeDecodeError:
            continue
    if not rows:
        raise ValueError("No pude leer el CSV.")
    hn = [norm(h) for h in rows[0]]
    i_mun = next((i for i, h in enumerate(hn) if "nombre_mun" in h or h == "municipio"), None)
    i_ent = next((i for i, h in enumerate(hn) if "entidad" in h or h == "estado"), None)
    if i_mun is None or i_ent is None:
        raise ValueError("No encuentro las columnas de municipio/entidad.")
    i_last = len(rows[0]) - 1
    filas = [{"mun": norm(r[i_mun]), "ent": norm(r[i_ent]),
              "nivel": NIVEL.get(norm(r[i_last]), 0)}
             for r in rows[1:] if len(r) > i_last and r[i_mun]]
    return filas, fecha_serial(rows[0][i_last])


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    src = Path(sys.argv[1])
    if not src.exists():
        print(f"No encuentro {src}"); sys.exit(1)

    try:
        filas, corte = (leer_xlsx(src) if src.suffix.lower() in (".xlsx", ".xlsm")
                        else leer_csv(src))
    except Exception as e:
        print(f"No pude leer el archivo: {e}")
        print("Usa el archivo MUNICIPAL del Monitor de Sequía (MunicipiosSequia.xlsx).")
        sys.exit(1)

    monitor = {(f["mun"], f["ent"]): f["nivel"] for f in filas}
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
        print("Ningún municipio empató — revisa que sea el archivo municipal."); sys.exit(1)

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
    dst.parent.mkdir(exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    faltan = [z for z in ZONA_MUN if z not in zonas]
    print(f"✅ {dst}")
    print(f"   {len(zonas)}/32 zonas · {len(municipios)} municipios · corte {corte}")
    if faltan:
        print(f"   Sin empate (se omiten): {', '.join(faltan)}")
    print("   Súbelo con el sitio y el mapa mostrará la capa de agua.")


if __name__ == "__main__":
    main()
