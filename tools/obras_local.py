#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
obras_local.py — Capa de OBRA PÚBLICA por entidad, desde CompraNet (SHCP).

Dato real y oficial: CompraNet publica en datos abiertos TODOS los contratos
de la contratación pública federal, con importe, entidad federativa y tipo.
Como el gobierno bloquea IPs de nube (igual que DENUE/SESNSP/CONAGUA), este
script corre EN TU MÁQUINA, mismo patrón que riesgos_local.py y agua_local.py:

  1) Descarga el archivo de contratos del año en curso desde el portal de
     datos abiertos de CompraNet:
       https://compranet.hacienda.gob.mx  →  sección "Datos abiertos"
     (el archivo se llama parecido a "Contratos2026.csv" o "Contratos2026.xlsx").
  2) Corre:  python tools/obras_local.py ruta/al/Contratos2026.csv
     Acepta VARIOS archivos (años distintos) y los suma:
       python tools/obras_local.py Contratos2025.csv Contratos2026.csv
     Si es .xlsx se intenta leer sin dependencias; si el Excel es demasiado
     pesado, conviértelo a CSV desde Excel y reintenta.
  3) Sube el data/obras.json resultante con el resto del sitio (Netlify).
     El mapa muestra la capa solo cuando el archivo existe.

Qué calcula (solo contratos cuyo tipo de contratación contiene "obra"):
  · Por entidad federativa: número de contratos de obra pública, monto total
    y el top 5 de contratos por importe (título, dependencia, monto, inicio).

Honestidad de datos: CompraNet registra la contratación pública FEDERAL; la
obra estatal/municipal que se contrata fuera de CompraNet NO aparece. Es una
señal de inversión pública en la entidad, no un catálogo exhaustivo — el
sitio lo etiqueta así.

Los encabezados de CompraNet cambian entre años, por eso las columnas se
localizan por nombre normalizado (sin acentos, minúsculas) que CONTENGA:
  tipo de contratación → "tipo"+"contrat" · entidad → "entidad federativa"
  (respaldo "entidad") · importe → "importe" o "monto" (la primera numérica)
  · título → "titulo" · dependencia → "siglas"/"institucion"/"dependencia"
  · fecha de inicio → "inicio" o "firma".
"""
import csv, json, re, sys, unicodedata, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# Zona BrickBit (nombre EXACTO de data/estados.json) → entidad federativa.
# (Mismo mapeo de 32 zonas que riesgos_local.py.)
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
CANON = sorted(set(ZONA_ENTIDAD.values()))
# Nombres alternos que CompraNet ha usado según el año.
ALIAS = {"distrito federal": "ciudad de mexico", "cdmx": "ciudad de mexico",
         "estado de mexico": "mexico", "edomex": "mexico"}


def norm(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip().lower()


def canon_ent(e):
    """Entidad normalizada del archivo → nombre canónico (o None)."""
    e = ALIAS.get(e, e)
    if e in ZONA_ENTIDAD.values():
        return e
    # respaldo por prefijo: "coahuila" → "coahuila de zaragoza", etc.
    cands = [c for c in CANON if c.startswith(e) or e.startswith(c)]
    return min(cands, key=lambda c: abs(len(c) - len(e))) if cands else None


def num(v):
    """'$1,234,567.89 ' → 1234567.89; basura → None (se salta, no se inventa)."""
    s = str(v or "").strip().replace("$", "").replace(",", "").replace(" ", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def leer_csv(path):
    """Devuelve (encabezados, filas como dicts). CompraNet alterna codificación."""
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with path.open(encoding=enc, newline="") as f:
                rows = list(csv.DictReader(f))
            if rows and len(rows[0]) > 3:
                return list(rows[0].keys()), rows
        except UnicodeDecodeError:
            continue
    raise ValueError("no pude leer el CSV (¿es el archivo de contratos de CompraNet?)")


def leer_xlsx(path):
    """Primera hoja del .xlsx sin dependencias externas (patrón agua_local.py)."""
    z = zipfile.ZipFile(path)
    try:
        shared = ["".join(t.text or "" for t in si.iter(NS + "t"))
                  for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(NS + "si")]
    except KeyError:
        shared = []
    hoja = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))

    def col_letra(ref):
        return ref.rstrip("0123456789")

    def val(c):
        v = c.find(NS + "v")
        if v is None:
            inline = c.find(NS + "is")
            return "".join(x.text or "" for x in inline.iter(NS + "t")) if inline is not None else ""
        return shared[int(v.text)] if c.get("t") == "s" else (v.text or "")

    filas_xml = list(hoja.iter(NS + "row"))
    if not filas_xml:
        raise ValueError("la hoja está vacía")
    encabezado = {col_letra(c.get("r", "")): val(c) for c in filas_xml[0].iter(NS + "c")}
    rows = []
    for r in filas_xml[1:]:
        celdas = {col_letra(c.get("r", "")): val(c) for c in r.iter(NS + "c")}
        rows.append({h: celdas.get(letra, "") for letra, h in encabezado.items()})
    return list(encabezado.values()), rows


def detectar_columnas(headers, rows):
    """Encabezados reales de CompraNet cambian entre años → buscar por contenido."""
    hn = [(norm(h), h) for h in headers if h]

    def busca(cond):
        return next((h for n, h in hn if cond(n)), None)

    c_tipo = busca(lambda n: "tipo" in n and "contrat" in n)
    c_ent = busca(lambda n: "entidad federativa" in n) or busca(lambda n: "entidad" in n)
    c_tit = busca(lambda n: "titulo" in n and "contrat" in n) or busca(lambda n: "titulo" in n)
    c_dep = (busca(lambda n: "siglas" in n) or busca(lambda n: "institucion" in n)
             or busca(lambda n: "dependencia" in n))
    c_ini = busca(lambda n: "inicio" in n) or busca(lambda n: "firma" in n)

    # importe: entre las columnas "importe"/"monto", la primera que sea numérica
    c_imp = None
    for n, h in hn:
        if "importe" in n or "monto" in n:
            muestra = [num(r.get(h)) for r in rows[:80] if str(r.get(h) or "").strip()]
            if muestra and sum(1 for x in muestra if x is not None) >= len(muestra) / 2:
                c_imp = h
                break
    return c_tipo, c_ent, c_imp, c_tit, c_dep, c_ini


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)

    agg = {}          # entidad canónica → {"n":…, "monto_total":…, "top":[…]}
    anios = set()     # años vistos (fechas de inicio o nombre de archivo)
    total_filas = 0

    for arg in sys.argv[1:]:
        src = Path(arg)
        if not src.exists():
            print(f"No encuentro {src}"); sys.exit(1)
        try:
            if src.suffix.lower() in (".xlsx", ".xlsm"):
                headers, rows = leer_xlsx(src)
            else:
                headers, rows = leer_csv(src)
        except Exception as e:
            print(f"No pude leer {src.name}: {e}")
            print("Si es un Excel muy pesado, convierte a CSV desde Excel y reintenta.")
            sys.exit(1)

        c_tipo, c_ent, c_imp, c_tit, c_dep, c_ini = detectar_columnas(headers, rows)
        if not (c_tipo and c_ent):
            print(f"{src.name}: no encuentro las columnas de tipo de contratación / "
                  "entidad federativa — usa el archivo de CONTRATOS de CompraNet.")
            sys.exit(1)
        print(f"→ {src.name}: {len(rows)} filas · tipo=[{c_tipo}] entidad=[{c_ent}] "
              f"importe=[{c_imp}] titulo=[{c_tit}] dependencia=[{c_dep}] inicio=[{c_ini}]")
        anios.update(int(a) for a in re.findall(r"(?:19|20)\d{2}", src.name))

        for r in rows:
            if "obra" not in norm(r.get(c_tipo)):
                continue          # solo obra pública
            ent = canon_ent(norm(r.get(c_ent)))
            if not ent:
                continue          # "extranjero", vacíos, etc.
            total_filas += 1
            a = agg.setdefault(ent, {"n": 0, "monto_total": 0.0, "top": []})
            a["n"] += 1
            monto = num(r.get(c_imp)) if c_imp else None
            inicio = str(r.get(c_ini) or "").strip()[:10] if c_ini else ""
            anios.update(int(x) for x in re.findall(r"(?:19|20)\d{2}", inicio))
            if monto is None:
                continue          # importe basura: no suma, no se inventa
            a["monto_total"] += monto
            a["top"].append({
                "titulo": str(r.get(c_tit) or "").strip()[:110] if c_tit else "",
                "dependencia": str(r.get(c_dep) or "").strip() if c_dep else "",
                "monto": round(monto, 2),
                "inicio": inicio,
            })
            a["top"].sort(key=lambda t: -t["monto"])
            del a["top"][5:]      # top 5 por importe

    if not agg:
        print("Ningún contrato de obra empató — revisa que sea el archivo de "
              "contratos de CompraNet (columna de tipo de contratación con 'Obra')."); sys.exit(1)

    for a in agg.values():
        a["monto_total"] = round(a["monto_total"], 2)

    corte = (f"{min(anios)}–{max(anios)}" if len(anios) > 1
             else str(next(iter(anios))) if anios else None)

    zonas = {}
    for zona, ent in ZONA_ENTIDAD.items():
        if ent in agg:
            zonas[zona] = {"entidad": ent.title(), **agg[ent]}

    out = {
        "meta": {
            "fuente": "CompraNet (SHCP) · contratos de obra pública",
            "corte": corte,
            "nota": ("Contratación pública FEDERAL registrada en CompraNet; la obra "
                     "estatal/municipal fuera de CompraNet no aparece. Es señal de "
                     "inversión pública, no catálogo exhaustivo."),
        },
        "estados": agg,
        "zonas": zonas,
    }
    dst = Path(__file__).resolve().parent.parent / "data" / "obras.json"
    dst.parent.mkdir(exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    monto_nac = sum(a["monto_total"] for a in agg.values())
    print(f"✅ {dst}")
    print(f"   {len(agg)}/32 entidades · {total_filas} contratos de obra · "
          f"monto nacional ${monto_nac:,.0f} MXN · corte {corte}")
    print("   Súbelo con el sitio y el mapa mostrará la capa de obra pública.")


if __name__ == "__main__":
    main()
