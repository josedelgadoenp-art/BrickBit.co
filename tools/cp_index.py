#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cp_index.py — Índice de códigos postales → coordenada, para /financial/gmm.

El buscador "hospitales GNP a X km de mi código postal" necesita convertir un
CP de cinco dígitos en un punto. Este script construye ese índice.

FORMATO DE SALIDA (data/cp_centroides.txt)
Una sola línea, registros fijos de 17 caracteres, ordenados por CP ascendente:

    CCCCC LLLLL GGGGGG P
    │     │     │      └─ precisión: 0 = punto del propio CP, 1 = centro del municipio
    │     │     └──────── |longitud| × 1000, 6 dígitos con ceros a la izquierda
    │     └────────────── latitud   × 1000, 5 dígitos con ceros a la izquierda
    └──────────────────── código postal, 5 dígitos

La longitud siempre es oeste en México, así que se guarda el valor absoluto y
el navegador le antepone el signo. Ancho fijo = la página corta de 17 en 17 y
arma un Map, sin parsear separadores. Un JSON con 30 mil llaves pesaría cuatro
veces más y tardaría en parsearse.

FUENTES (se combinan; la más precisa gana)
  1) data/cdmx_codigos_postales.json — 1,182 polígonos de CP de la CDMX que ya
     viven en el repo. Centroide exacto del propio CP.            → precisión 0
  2) data/gnp_hospitales.json — los hospitales traen su CP en el domicilio y
     su coordenada ya derivada de él.                             → precisión 0
  3) Catálogo Nacional de SEPOMEX (--sepomex CPdescarga.xls o un CSV).
     Da CP → municipio para todo el país. OJO: el catálogo oficial NO trae
     coordenadas, así que el punto sale del centro del municipio usando los
     polígonos de data/mexico_municipios.json.                    → precisión 1

  python3 tools/cp_index.py                              # sólo lo que hay en el repo
  python3 tools/cp_index.py --sepomex ~/CPdescarga.xls   # cobertura nacional

El .xls de SEPOMEX pesa 70 MB y NO se guarda en el repo: se descarga de
https://www.correosdemexico.gob.mx/SSLServicios/ConsultaCP/Descarga.aspx
y se corre en local, igual que riesgos_local.py o macro_local.py.

HONESTIDAD DE DATOS
Un centroide municipal NO es una dirección, y en municipios grandes puede
quedar a varios kilómetros del CP real. Por eso cada registro guarda su
precisión y la página lo dice en pantalla: los CP con precisión municipal se
anuncian como aproximados. Este índice sirve para "¿qué hospitales me quedan
cerca?", nunca para "¿a cuántos metros estoy?".
"""
import argparse, csv, json, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "data" / "cp_centroides.txt"
POLIGONOS_CDMX = RAIZ / "data" / "cdmx_codigos_postales.json"
HOSPITALES = RAIZ / "data" / "gnp_hospitales.json"
MUNICIPIOS = RAIZ / "data" / "mexico_municipios.json"

# Caja de México con holgura. Lo que caiga fuera se descarta: más vale un CP
# ausente (la página lo dice) que un CP que mande al usuario al mar.
LAT_MIN, LAT_MAX = 14.0, 33.0
LNG_MIN, LNG_MAX = -119.0, -86.0

EXACTO, MUNICIPAL = 0, 1


def dentro_de_mexico(lat, lng):
    return LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX


def _punto_interior(geom):
    """Punto garantizado DENTRO del polígono (el centroide de una herradura no lo está)."""
    from shapely.geometry import shape
    p = shape(geom).representative_point()
    return (p.y, p.x)


# ---------------------------------------------------------------- fuentes ---
def centroides_cdmx():
    if not POLIGONOS_CDMX.exists():
        return {}
    gj = json.loads(POLIGONOS_CDMX.read_text(encoding="utf-8"))
    puntos = {}
    for f in gj.get("features", []):
        cp = str(f.get("properties", {}).get("cp", "")).strip()
        if not (cp.isdigit() and len(cp) == 5):
            continue
        try:
            lat, lng = _punto_interior(f["geometry"])
        except Exception:
            continue
        if dentro_de_mexico(lat, lng):
            puntos[cp] = (lat, lng)
    print(f"  · {len(puntos):,} CP de la CDMX (polígono del propio CP)")
    return puntos


def centroides_hospitales():
    if not HOSPITALES.exists():
        return {}
    import re
    d = json.loads(HOSPITALES.read_text(encoding="utf-8"))
    puntos, calidad = {}, {}
    for h in d.get("hospitales", []):
        m = re.findall(r"\b(\d{5})\b", h.get("d", ""))
        if not m:
            continue
        cp = m[-1]
        lat, lng = h.get("lat"), h.get("lng")
        if lat is None or lng is None or not dentro_de_mexico(lat, lng):
            continue
        rango = 2 if h.get("pr") == "cp" else 1   # el pin de CP manda sobre el de colonia
        if rango >= calidad.get(cp, 0):
            puntos[cp], calidad[cp] = (lat, lng), rango
    print(f"  · {len(puntos):,} CP desde los domicilios de la red hospitalaria")
    return puntos


def _centros_municipales():
    """(clave_estado, clave_municipio) → punto interior del municipio."""
    if not MUNICIPIOS.exists():
        sys.exit(f"Falta {MUNICIPIOS}, que es de donde salen los centros municipales.")
    gj = json.loads(MUNICIPIOS.read_text(encoding="utf-8"))
    centros = {}
    for f in gj.get("features", []):
        p = f.get("properties", {})
        try:
            clave = (int(p["state_code"]), int(p["mun_code"]))
            lat, lng = _punto_interior(f["geometry"])
        except Exception:
            continue
        if dentro_de_mexico(lat, lng):
            centros[clave] = (lat, lng)
    print(f"  · {len(centros):,} municipios con centro calculado")
    return centros


def _filas_sepomex(ruta):
    """Devuelve (cp, clave_estado, clave_municipio) del catálogo, sea .xls o CSV."""
    p = Path(ruta)
    if not p.exists():
        sys.exit(f"No encuentro {p}")

    if p.suffix.lower() in (".xls", ".xlsx"):
        try:
            import xlrd
        except ImportError:
            sys.exit("Para leer el .xls de SEPOMEX hace falta xlrd:  pip install xlrd")
        wb = xlrd.open_workbook(str(p), on_demand=True)
        for nombre in wb.sheet_names():
            if nombre.lower().startswith("nota"):
                continue
            s = wb.sheet_by_name(nombre)
            if s.nrows < 2:
                continue
            enc = [str(c.value).strip().lower() for c in s.row(0)]
            try:
                i_cp, i_e, i_m = enc.index("d_codigo"), enc.index("c_estado"), enc.index("c_mnpio")
            except ValueError:
                print(f"    ⚠ hoja «{nombre}» sin las columnas esperadas; me la salto")
                continue
            for r in range(1, s.nrows):
                fila = s.row(r)
                yield (str(fila[i_cp].value).strip(), fila[i_e].value, fila[i_m].value)
            wb.unload_sheet(nombre)          # 70 MB: no cabe todo en memoria a la vez
        return

    with p.open(encoding="utf-8-sig", newline="") as fh:
        muestra = fh.read(8192); fh.seek(0)
        try:
            dial = csv.Sniffer().sniff(muestra, delimiters=",;|\t")
        except csv.Error:
            dial = csv.excel
        r = csv.DictReader(fh, dialect=dial)
        cols = {c.strip().lower(): c for c in (r.fieldnames or [])}
        need = ("d_codigo", "c_estado", "c_mnpio")
        if not all(n in cols for n in need):
            sys.exit(f"El CSV necesita las columnas {need}. Trae: {r.fieldnames}")
        for fila in r:
            yield (fila[cols["d_codigo"]], fila[cols["c_estado"]], fila[cols["c_mnpio"]])


def centroides_sepomex(ruta):
    centros = _centros_municipales()
    puntos, sin_municipio, vistos = {}, set(), set()
    for cp_raw, ce, cm in _filas_sepomex(ruta):
        cp = str(cp_raw).split(".")[0].strip().zfill(5)
        if not (cp.isdigit() and len(cp) == 5):
            continue
        vistos.add(cp)
        if cp in puntos:
            continue
        try:
            clave = (int(float(ce)), int(float(cm)))
        except (TypeError, ValueError):
            continue
        pt = centros.get(clave)
        if pt:
            puntos[cp] = pt
        else:
            sin_municipio.add(clave)
    print(f"  · {len(vistos):,} CP en el catálogo SEPOMEX; "
          f"{len(puntos):,} ubicados al centro de su municipio")
    if sin_municipio:
        print(f"    ⚠ {len(sin_municipio)} municipios del catálogo no están en "
              f"mexico_municipios.json ({len(vistos)-len(puntos):,} CP sin ubicar)")
    return puntos


# ---------------------------------------------------------------- salida ---
def escribir(exactos, municipales):
    puntos = {cp: (p, MUNICIPAL) for cp, p in municipales.items()}
    puntos.update({cp: (p, EXACTO) for cp, p in exactos.items()})   # lo exacto manda
    if not puntos:
        sys.exit("No se generó ningún punto: no escribo un índice vacío.")

    trozos = []
    for cp in sorted(puntos):
        (lat, lng), prec = puntos[cp]
        la, ln = int(round(lat * 1000)), int(round(abs(lng) * 1000))
        if not (0 <= la <= 99999 and 0 <= ln <= 999999):
            continue
        trozos.append(f"{cp}{la:05d}{ln:06d}{prec}")

    blob = "".join(trozos)
    assert len(blob) % 17 == 0, "el blob debe ser múltiplo de 17"
    SALIDA.write_text(blob, encoding="ascii")

    n_ex = sum(1 for t in trozos if t[16] == "0")
    print(f"\n✓ {SALIDA.relative_to(RAIZ)} — {len(trozos):,} códigos postales, "
          f"{len(blob)/1024:,.0f} KB")
    print(f"  {n_ex:,} con punto del propio CP · {len(trozos)-n_ex:,} al centro de su municipio")
    print(f"  rango: {trozos[0][:5]} … {trozos[-1][:5]}")
    return trozos


def verificar():
    """Relee el archivo como lo hará el navegador y revisa que todo cuadre."""
    blob = SALIDA.read_text(encoding="ascii")
    assert len(blob) % 17 == 0, "longitud no múltiplo de 17"
    previo = ""
    for i in range(0, len(blob), 17):
        reg = blob[i:i + 17]
        assert reg.isdigit(), f"registro no numérico en {i}: {reg!r}"
        cp, lat, lng, prec = reg[:5], int(reg[5:10]) / 1000, -int(reg[10:16]) / 1000, reg[16]
        assert cp > previo, f"CP fuera de orden en {i}: {cp} tras {previo}"
        assert dentro_de_mexico(lat, lng), f"{cp} cae fuera de México: {lat},{lng}"
        assert prec in "01", f"precisión inválida en {cp}: {prec}"
        previo = cp
    print(f"✓ verificado: {len(blob)//17:,} registros, orden ascendente, "
          f"precisión válida y todo dentro de México")


def main():
    ap = argparse.ArgumentParser(description="Construye el índice de CP para /financial/gmm")
    ap.add_argument("--sepomex", metavar="ARCHIVO",
                    help="Catálogo Nacional de SEPOMEX (.xls) o un CSV equivalente")
    args = ap.parse_args()

    try:
        import shapely  # noqa: F401
    except ImportError:
        sys.exit("Hace falta shapely:  pip install shapely")

    print("Construyendo índice de códigos postales…")
    municipales = centroides_sepomex(args.sepomex) if args.sepomex else {}
    if not args.sepomex:
        print("  · sin --sepomex: sólo se indexa lo que ya está en el repo")

    exactos = centroides_hospitales()
    exactos.update(centroides_cdmx())     # el polígono del CP gana sobre el pin del hospital

    escribir(exactos, municipales)
    verificar()


if __name__ == "__main__":
    main()
