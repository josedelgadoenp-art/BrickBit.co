#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
obras_local.py — Capa de OBRA PÚBLICA por entidad, desde CompraNet (SHCP).

Dato real y oficial: CompraNet publica en datos abiertos los contratos de la
contratación pública federal, con importe, tipo de contratación y fechas.
Como el gobierno bloquea IPs de nube (igual que DENUE/SESNSP/CONAGUA), este
script corre EN TU MÁQUINA, mismo patrón que riesgos_local.py y agua_local.py:

  1) Descarga el archivo de contratos desde datos abiertos de CompraNet:
       https://canvas-compranet.buengobierno.gob.mx  (plataforma nueva)
       https://www.datos.gob.mx/dataset/contratos_expedientes_sistema_historico_compranet
  2) Corre:  python tools/obras_local.py ruta/al/archivo.csv
     Acepta VARIOS archivos y los suma:
       python tools/obras_local.py contratos2025.csv contratos2026.csv
     Opción --desde AAAA para fijar el año inicial de la ventana (por defecto,
     los últimos 5 años con dato en el archivo).
  3) Sube el data/obras.json resultante con el resto del sitio (Netlify).
     El mapa muestra la capa solo cuando el archivo existe.

Qué calcula (solo contratos cuyo tipo de contratación contiene "obra"):
  · Por entidad federativa: número de contratos, monto total en pesos y el
    top 5 de contratos por importe (título, dependencia, monto, inicio).

DE DÓNDE SALE LA ENTIDAD — y por qué el script a veces se niega a escribir:
  A) Archivos con columna de ENTIDAD FEDERATIVA (o de unidad compradora)
     explícita → se usa tal cual. Este es el archivo que hay que conseguir.
  B) Respaldo: el export histórico (codigo_contrato, proveedor,
     titulo_contrato, descripcion_contrato, tipo_contratacion, importe,
     fecha_inicio…) NO trae columna de entidad. Algunos contratos describen la
     ubicación como lista de etiquetas —"México, Morelos, Cuautla, Avalúo…"—
     y de ahí se puede leer el estado por coincidencia exacta.

     MEDIDO contra el export real (2.36 M de filas, 265 mil de obra): solo el
     7.3% sigue ese formato. El resto es prosa libre sin lugar. Un ranking por
     estado construido sobre el 7% no mide inversión pública: mide qué
     dependencias escriben la ubicación. Por eso, si la cobertura queda por
     debajo de MIN_COBERTURA, el script imprime el diagnóstico y NO escribe
     data/obras.json. Preferimos no tener la capa a tenerla mintiendo.

  En ningún caso se reparten los contratos sin estado entre las entidades ni
  se estima su ubicación: se excluyen y se reporta cuántos fueron.

Honestidad de datos: CompraNet registra la contratación pública FEDERAL; la
obra estatal/municipal contratada fuera de la plataforma NO aparece. Es una
señal de inversión pública en la entidad, no un catálogo exhaustivo — el
sitio lo etiqueta así, junto con el rango de años del archivo.

Los encabezados de CompraNet cambian entre años, por eso las columnas se
localizan por nombre normalizado (sin acentos, minúsculas) que CONTENGA:
  tipo de contratación → "tipo"+"contrat" · entidad → "entidad federativa"
  · importe → "importe" o "monto" (la primera numérica) · título → "titulo"
  · dependencia → "siglas"/"institucion"/"dependencia" · fecha → "inicio"
  · descripción → "descripcion" · moneda → "moneda".
"""
import csv, json, re, sys, unicodedata, zipfile
from collections import Counter
from itertools import chain
from pathlib import Path
import xml.etree.ElementTree as ET

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

# Token EXACTO que puede aparecer en la lista de etiquetas → entidad canónica.
# Solo coincidencia exacta: "puebla" sí, "pueblan" no, "san pedro" tampoco.
ENT_TOKEN = {
    "aguascalientes": "aguascalientes",
    "baja california": "baja california", "baja california norte": "baja california",
    "baja california sur": "baja california sur",
    "campeche": "campeche",
    "coahuila": "coahuila de zaragoza", "coahuila de zaragoza": "coahuila de zaragoza",
    "colima": "colima", "chiapas": "chiapas", "chihuahua": "chihuahua",
    "ciudad de mexico": "ciudad de mexico", "distrito federal": "ciudad de mexico",
    "cdmx": "ciudad de mexico",
    "durango": "durango", "guanajuato": "guanajuato", "guerrero": "guerrero",
    "hidalgo": "hidalgo", "jalisco": "jalisco",
    "mexico": "mexico", "estado de mexico": "mexico", "edomex": "mexico",
    "michoacan": "michoacan de ocampo", "michoacan de ocampo": "michoacan de ocampo",
    "morelos": "morelos", "nayarit": "nayarit", "nuevo leon": "nuevo leon",
    "oaxaca": "oaxaca", "puebla": "puebla",
    "queretaro": "queretaro", "queretaro de arteaga": "queretaro",
    "quintana roo": "quintana roo", "san luis potosi": "san luis potosi",
    "sinaloa": "sinaloa", "sonora": "sonora", "tabasco": "tabasco",
    "tamaulipas": "tamaulipas", "tlaxcala": "tlaxcala",
    "veracruz": "veracruz de ignacio de la llave",
    "veracruz de ignacio de la llave": "veracruz de ignacio de la llave",
    "veracruz llave": "veracruz de ignacio de la llave",
    "yucatan": "yucatan", "zacatecas": "zacatecas",
}
# Cobertura mínima para publicar: si menos de este porcentaje de los contratos
# de obra tiene estado identificable, el archivo NO se escribe (ver main()).
MIN_COBERTURA = 0.60


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


def ent_de_etiquetas(texto):
    """Entidad leída de la descripción, o None.

    Algunos contratos traen la descripción como lista de etiquetas que empieza
    por país, estado y municipio ("México, Morelos, Cuautla, Avalúo, Nuevo…").
    Cuando existe, el estado se lee por coincidencia EXACTA de un token con los
    32 nombres y sus alias; el token 0 se ignora si es "mexico" (el país), para
    no confundirlo con el Estado de México.

    OJO — medido contra el export real: solo ~7 de cada 100 contratos de obra
    siguen ese formato; el resto es prosa libre ("Repotenciación de la Línea de
    Distribución del Circuito Lmx-4012…"), sin lugar. Por eso este camino es
    un RESPALDO y main() aborta si la cobertura es baja: atribuir el 7% y
    presentarlo como el mapa de la obra pública del país sería mentir.
    """
    partes = [p.strip() for p in str(texto or "").split(",")]
    if not partes:
        return None
    inicio = 1 if norm(partes[0]) == "mexico" else 0
    for i in range(inicio, len(partes)):
        ent = ENT_TOKEN.get(norm(partes[i]))
        if ent:
            return ent
    return None


def num(v):
    """'$1,234,567.89 ' → 1234567.89; basura → None (se salta, no se inventa)."""
    s = str(v or "").strip().replace("$", "").replace(",", "").replace(" ", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def abrir_csv(path):
    """(encabezados, iterador de filas) SIN cargar el archivo en memoria.

    Los export de CompraNet llegan a pesar cientos de MB: leerlos con
    list(DictReader) tumba máquinas de 8 GB, así que se recorren en streaming.
    Solo se guardan en RAM las primeras filas, para detectar qué columna trae
    el importe.
    """
    for enc in ("utf-8-sig", "latin-1"):
        try:
            f = path.open(encoding=enc, newline="")
            rd = csv.DictReader(f)
            if rd.fieldnames and len(rd.fieldnames) > 3:
                muestra = [r for _, r in zip(range(80), rd)]
                return list(rd.fieldnames), chain(muestra, rd), muestra, f
            f.close()
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


def detectar_columnas(headers, muestra):
    """Encabezados reales de CompraNet cambian entre años → buscar por contenido."""
    hn = [(norm(h), h) for h in headers if h]

    def busca(cond):
        return next((h for n, h in hn if cond(n)), None)

    col = {
        "tipo": busca(lambda n: "tipo" in n and "contrat" in n),
        "ctype": busca(lambda n: n in ("contract_type", "tipo de contrato")),
        "ent": busca(lambda n: "entidad federativa" in n) or busca(
            lambda n: "entidad" in n and "compradora" not in n),
        "desc": busca(lambda n: "descripcion" in n),
        "tit": busca(lambda n: "titulo" in n and "contrat" in n) or busca(lambda n: "titulo" in n),
        "dep": (busca(lambda n: "siglas" in n) or busca(lambda n: "institucion" in n)
                or busca(lambda n: "dependencia" in n) or busca(lambda n: "proveedor" in n)),
        "ini": busca(lambda n: "inicio" in n) or busca(lambda n: "firma" in n),
        "mon": busca(lambda n: n == "moneda"),
    }
    # importe: entre las columnas "importe"/"monto", la primera que sea numérica
    col["imp"] = None
    for n, h in hn:
        if "importe" in n or "monto" in n:
            vals = [num(r.get(h)) for r in muestra[:80] if str(r.get(h) or "").strip()]
            if vals and sum(1 for x in vals if x is not None) >= len(vals) / 2:
                col["imp"] = h
                break
    return col


def main():
    argv = sys.argv[1:]
    desde_fijo = None
    if "--desde" in argv:
        i = argv.index("--desde")
        try:
            desde_fijo = int(argv[i + 1])
        except (IndexError, ValueError):
            print("--desde necesita un año, p. ej. --desde 2018"); sys.exit(1)
        del argv[i:i + 2]
    archivos = [a for a in argv if not a.startswith("--")]
    if not archivos:
        print(__doc__); sys.exit(1)

    # agg[entidad][año] = {"n":…, "monto":…, "top":[…], "muni":Counter()}
    agg, dx = {}, Counter()
    ejemplos_sin_ent, origenes = [], set()

    for arg in archivos:
        src = Path(arg)
        if not src.exists():
            print(f"No encuentro {src}"); sys.exit(1)
        fh = None
        try:
            if src.suffix.lower() in (".xlsx", ".xlsm"):
                headers, rows = leer_xlsx(src)
                muestra = rows[:80]
            else:
                headers, rows, muestra, fh = abrir_csv(src)
        except Exception as e:
            print(f"No pude leer {src.name}: {e}")
            print("Si es un Excel muy pesado, conviértelo a CSV desde Excel y reintenta.")
            sys.exit(1)

        col = detectar_columnas(headers, muestra)
        if not col["tipo"] and not col["ctype"]:
            print(f"{src.name}: no encuentro la columna de tipo de contratación.")
            print("Columnas del archivo:", ", ".join(str(h) for h in headers))
            sys.exit(1)
        if not col["ent"] and not col["desc"]:
            print(f"{src.name}: sin columna de entidad federativa ni de descripción, "
                  "no hay de dónde sacar el estado.")
            print("Columnas del archivo:", ", ".join(str(h) for h in headers))
            sys.exit(1)
        origen = "columna de entidad" if col["ent"] else "etiquetas de la descripción"
        origenes.add(origen)
        print(f"→ {src.name}: tipo=[{col['tipo'] or col['ctype']}] importe=[{col['imp']}] "
              f"título=[{col['tit']}] inicio=[{col['ini']}] · estado leído de: {origen}")

        for r in rows:
            dx["filas"] += 1
            tipo = norm(r.get(col["tipo"])) if col["tipo"] else ""
            ctype = norm(r.get(col["ctype"])) if col["ctype"] else ""
            if "obra" not in tipo and "obra" not in ctype:
                continue                       # solo obra pública
            dx["obra"] += 1

            if col["ent"]:
                ent = canon_ent(norm(r.get(col["ent"])))
            else:
                ent = ent_de_etiquetas(r.get(col["desc"]))
            if not ent:
                dx["sin_entidad"] += 1
                if len(ejemplos_sin_ent) < 3:
                    d = str(r.get(col["desc"]) or r.get(col["tit"]) or "").strip()
                    if d:
                        ejemplos_sin_ent.append(d[:90])
                continue                       # no se adivina: se reporta y se excluye

            inicio = str(r.get(col["ini"]) or "").strip()[:10] if col["ini"] else ""
            m = re.search(r"(?:19|20)\d{2}", inicio)
            anio = int(m.group()) if m else 0
            a = agg.setdefault(ent, {}).setdefault(anio, {"n": 0, "monto": 0.0, "top": []})
            a["n"] += 1

            moneda = norm(r.get(col["mon"])) if col["mon"] else ""
            if moneda and moneda not in ("mxn", "pesos", "mn", "peso mexicano"):
                dx["moneda_extranjera"] += 1
                continue                       # no se convierte: no suma al monto
            monto = num(r.get(col["imp"])) if col["imp"] else None
            if monto is None:
                dx["sin_importe"] += 1
                continue                       # importe basura: no suma, no se inventa
            a["monto"] += monto
            a["top"].append({
                "titulo": str(r.get(col["tit"]) or "").strip()[:110] if col["tit"] else "",
                "dependencia": str(r.get(col["dep"]) or "").strip()[:70] if col["dep"] else "",
                "monto": round(monto, 2),
                "inicio": inicio,
            })
            a["top"].sort(key=lambda t: -t["monto"])
            del a["top"][5:]
        if fh:
            fh.close()

    if not agg:
        print("Ningún contrato de obra empató — revisa que sea el archivo de contratos "
              "de CompraNet (columna de tipo de contratación con 'Obra').")
        sys.exit(1)

    # ---- Corte de honestidad -------------------------------------------------
    # Una capa que dice "obra pública por estado" tiene que estar construida
    # sobre CASI TODA la obra, no sobre los contratos que por casualidad
    # mencionan su estado. Si la cobertura es baja, el ranking mide qué
    # dependencia redacta mejor sus descripciones, no dónde se invierte: se
    # imprime el diagnóstico y NO se escribe el archivo.
    cobertura = (dx["obra"] - dx["sin_entidad"]) / max(dx["obra"], 1)
    if cobertura < MIN_COBERTURA:
        print(f"\n✗ NO se escribió data/obras.json.")
        print(f"  Solo {cobertura * 100:.1f}% de los {dx['obra']:,} contratos de obra trae "
              f"un estado identificable (mínimo exigido: {MIN_COBERTURA * 100:.0f}%).")
        print("  Con esa cobertura, el ranking por entidad no mide inversión pública:")
        print("  mide qué dependencias escriben la ubicación en la descripción.")
        for e in ejemplos_sin_ent:
            print(f"    · sin lugar: {e}")
        print("\n  Este export no sirve para la capa por estado. Busca en datos abiertos")
        print("  de CompraNet el archivo de CONTRATOS que incluya 'entidad federativa'")
        print("  o 'unidad compradora' (o el catálogo de unidades compradoras, que trae")
        print("  el estado de cada clave y permite el cruce).")
        sys.exit(2)

    anios = sorted({a for por in agg.values() for a in por if a})
    if not anios:
        print("Ningún contrato trae fecha legible; no puedo fijar la ventana de años.")
        sys.exit(1)
    desde = desde_fijo if desde_fijo is not None else max(anios[-1] - 4, anios[0])
    hasta = anios[-1]

    # colapsar la ventana elegida
    estados, por_anio_nac = {}, Counter()
    for ent, por in agg.items():
        n = monto = 0
        top = []
        for anio, a in por.items():
            if not (desde <= anio <= hasta):
                continue
            n += a["n"]; monto += a["monto"]; top += a["top"]
            por_anio_nac[anio] += a["n"]
        if not n:
            continue
        top.sort(key=lambda t: -t["monto"])
        estados[ent] = {"n": n, "monto_total": round(monto, 2), "top": top[:5]}

    if not estados:
        print(f"No quedaron contratos en la ventana {desde}–{hasta}. "
              "Usa --desde con un año más antiguo.")
        sys.exit(1)

    zonas = {zona: {"entidad": ent.title(), **estados[ent]}
             for zona, ent in ZONA_ENTIDAD.items() if ent in estados}

    out = {
        "meta": {
            "fuente": "CompraNet (SHCP) · contratos de obra pública",
            "corte": f"{desde}–{hasta}" if desde != hasta else str(hasta),
            "rango_archivo": f"{anios[0]}–{anios[-1]}",
            "atribucion": (" y ".join(sorted(origenes)) +
                           "; los contratos sin estado reconocible quedan fuera"),
            "sin_entidad": dx["sin_entidad"],
            "cobertura": round(cobertura, 3),
            "nota": ("Contratación pública FEDERAL registrada en CompraNet; la obra "
                     "estatal/municipal fuera de CompraNet no aparece. Es señal de "
                     "inversión pública, no catálogo exhaustivo."),
        },
        "estados": estados,
        "zonas": zonas,
    }
    dst = Path(__file__).resolve().parent.parent / "data" / "obras.json"
    dst.parent.mkdir(exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    n_win = sum(e["n"] for e in estados.values())
    monto_nac = sum(e["monto_total"] for e in estados.values())
    print(f"\n✅ {dst}")
    print(f"   Filas leídas: {dx['filas']:,} · de obra pública: {dx['obra']:,}")
    if dx["sin_entidad"]:
        pct = 100 * dx["sin_entidad"] / max(dx["obra"], 1)
        print(f"   Sin estado reconocible: {dx['sin_entidad']:,} ({pct:.1f}%) — excluidos, no repartidos")
        for e in ejemplos_sin_ent:
            print(f"     · ejemplo: {e}")
    if dx["sin_importe"]:
        print(f"   Sin importe legible: {dx['sin_importe']:,} (cuentan como contrato, no suman monto)")
    if dx["moneda_extranjera"]:
        print(f"   En moneda extranjera: {dx['moneda_extranjera']:,} (no se convierten)")
    print(f"   Años en el archivo: {anios[0]}–{anios[-1]} · ventana usada: {desde}–{hasta} "
          f"(cámbiala con --desde AAAA)")
    print(f"   {len(estados)}/32 entidades · {n_win:,} contratos · ${monto_nac:,.0f} MXN")
    top_ent = sorted(estados.items(), key=lambda kv: -kv[1]["monto_total"])[:8]
    for ent, e in top_ent:
        print(f"     {ent.title():<28} {e['n']:>6,} contratos   ${e['monto_total']/1e6:>12,.0f} mdp")
    print("   Súbelo con el sitio y el mapa mostrará la capa de obra pública.")


if __name__ == "__main__":
    main()
