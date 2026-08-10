#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cp_index.py — Índice de códigos postales → coordenada, para /financial/gmm.

El buscador "hospitales GNP a X km de mi código postal" necesita convertir un
CP de cinco dígitos en un punto. Este script construye ese índice.

Formato de salida (data/cp_centroides.txt): una sola línea, registros fijos de
16 caracteres, ordenados por CP ascendente. Cada registro es

    CCCCC LLLLL GGGGGG
    │     │     └─ |longitud| × 1000, 6 dígitos con ceros a la izquierda
    │     └─────── latitud   × 1000, 5 dígitos con ceros a la izquierda
    └───────────── código postal, 5 dígitos

La longitud siempre es oeste (negativa) en México, así que se guarda el valor
absoluto y el navegador le antepone el signo. Ancho fijo = la página no tiene
que parsear separadores: corta de 16 en 16 y arma un Map. Un JSON con 30 mil
llaves pesaría cuatro veces más y tardaría en parsearse.

FUENTES, EN ORDEN DE PREFERENCIA
  1) Un CSV de SEPOMEX con coordenadas (cobertura nacional). SEPOMEX no publica
     lat/lng en su catálogo oficial; los CSV que sí las traen son derivados
     comunitarios. Pásalo con --sepomex ruta.csv y detectamos las columnas.
     Igual que riesgos_local.py y macro_local.py, esto se corre EN LOCAL: las
     dependencias de gobierno bloquean IPs de nube.
  2) data/cdmx_codigos_postales.json — 1,182 polígonos de CP de la CDMX que ya
     viven en este repo. Se usa su centroide. Es exacto y auditable, pero sólo
     cubre la Ciudad de México.

Se pueden combinar: el CSV nacional manda, los polígonos rellenan lo que falte.

  python3 tools/cp_index.py                          # sólo CDMX (lo que hay en repo)
  python3 tools/cp_index.py --sepomex ~/cp_mx.csv    # cobertura nacional

HONESTIDAD DE DATOS
El centroide de un CP NO es una dirección: es el centro de una zona que puede
medir varios kilómetros. La página lo dice y marca en ámbar toda distancia
calculada a partir de él. Este índice sirve para "¿qué hospitales me quedan
cerca?", nunca para "¿a cuántos metros estoy?".
"""
import argparse, csv, json, math, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "data" / "cp_centroides.txt"
POLIGONOS_CDMX = RAIZ / "data" / "cdmx_codigos_postales.json"
HOSPITALES = RAIZ / "data" / "gnp_hospitales.json"

# Caja de México con holgura. Todo lo que caiga fuera se descarta: más vale un
# CP ausente (la página lo dice) que un CP que manda al usuario al mar.
LAT_MIN, LAT_MAX = 14.0, 33.0
LNG_MIN, LNG_MAX = -119.0, -86.0


def dentro_de_mexico(lat, lng):
    return LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX


def centroides_cdmx():
    """Centroide de cada polígono de CP de la CDMX que ya está en el repo."""
    if not POLIGONOS_CDMX.exists():
        print(f"  · {POLIGONOS_CDMX.name} no está; me lo salto")
        return {}
    try:
        from shapely.geometry import shape
    except ImportError:
        print("  · falta shapely (pip install shapely); me salto los polígonos")
        return {}

    gj = json.loads(POLIGONOS_CDMX.read_text(encoding="utf-8"))
    puntos = {}
    for f in gj.get("features", []):
        cp = str(f.get("properties", {}).get("cp", "")).strip()
        if not (cp.isdigit() and len(cp) == 5):
            continue
        try:
            g = shape(f["geometry"])
            # representative_point() siempre cae DENTRO del polígono; el
            # centroide de una forma de herradura puede caer fuera de ella.
            p = g.representative_point()
        except Exception:
            continue
        if dentro_de_mexico(p.y, p.x):
            puntos[cp] = (p.y, p.x)
    print(f"  · {len(puntos):,} CP de la CDMX desde polígonos del repo")
    return puntos


def centroides_hospitales():
    """
    Los propios hospitales de la red traen su CP en el domicilio y su
    coordenada ya derivada de ese CP (o de su colonia, que cae dentro del CP).
    Son pocos, pero dan cobertura NACIONAL justo donde importa: si alguien
    teclea el CP de la zona de su hospital, resuelve aunque no haya CSV.
    Se prefiere el registro con precisión de CP sobre el de colonia.
    """
    if not HOSPITALES.exists():
        return {}
    import re
    d = json.loads(HOSPITALES.read_text(encoding="utf-8"))
    puntos, calidad = {}, {}
    for h in d.get("hospitales", []):
        # El CP es el penúltimo campo del domicilio: "…, CALLE 1, COLONIA, 20020, CIUDAD"
        m = re.findall(r"\b(\d{5})\b", h.get("d", ""))
        if not m:
            continue
        cp = m[-1]
        lat, lng = h.get("lat"), h.get("lng")
        if lat is None or lng is None or not dentro_de_mexico(lat, lng):
            continue
        rango = 2 if h.get("pr") == "cp" else 1
        if rango >= calidad.get(cp, 0):
            puntos[cp], calidad[cp] = (lat, lng), rango
    print(f"  · {len(puntos):,} CP desde los domicilios de la red hospitalaria")
    return puntos


def _col(campos, *candidatos):
    """Encuentra una columna por nombre aproximado, sin importar acentos ni caso."""
    norm = {c.strip().lower().replace("ó", "o").replace("í", "i").replace("á", "a"): c
            for c in campos}
    for cand in candidatos:
        for k, original in norm.items():
            if k == cand or k.startswith(cand):
                return original
    return None


def centroides_csv(ruta):
    """Promedia lat/lng por CP a partir de un CSV comunitario de SEPOMEX."""
    p = Path(ruta)
    if not p.exists():
        sys.exit(f"No encuentro {p}")

    acum = {}
    with p.open(encoding="utf-8-sig", newline="") as fh:
        muestra = fh.read(8192)
        fh.seek(0)
        try:
            dialecto = csv.Sniffer().sniff(muestra, delimiters=",;|\t")
        except csv.Error:
            dialecto = csv.excel
        r = csv.DictReader(fh, dialect=dialecto)
        if not r.fieldnames:
            sys.exit("El CSV no trae encabezados.")
        c_cp = _col(r.fieldnames, "d_codigo", "codigo_postal", "codigopostal", "cp", "zip")
        c_la = _col(r.fieldnames, "lat", "latitud", "y")
        c_ln = _col(r.fieldnames, "lon", "lng", "longitud", "x")
        if not (c_cp and c_la and c_ln):
            sys.exit(f"El CSV necesita columnas de CP, latitud y longitud. "
                     f"Encontré: {r.fieldnames}")
        print(f"  · columnas: CP={c_cp}  lat={c_la}  lng={c_ln}")

        for fila in r:
            cp = str(fila.get(c_cp, "")).strip().zfill(5)
            if not (cp.isdigit() and len(cp) == 5):
                continue
            try:
                lat = float(str(fila[c_la]).replace(",", "."))
                lng = float(str(fila[c_ln]).replace(",", "."))
            except (TypeError, ValueError):
                continue
            if lng > 0:          # algunos CSV guardan la longitud sin signo
                lng = -lng
            if not dentro_de_mexico(lat, lng):
                continue
            s = acum.setdefault(cp, [0.0, 0.0, 0])
            s[0] += lat
            s[1] += lng
            s[2] += 1

    puntos = {cp: (sla / n, sln / n) for cp, (sla, sln, n) in acum.items()}
    print(f"  · {len(puntos):,} CP desde {p.name}")
    return puntos


def escribir(puntos):
    if not puntos:
        sys.exit("No se generó ningún punto: no escribo un índice vacío.")

    trozos = []
    for cp in sorted(puntos):
        lat, lng = puntos[cp]
        la = int(round(lat * 1000))
        ln = int(round(abs(lng) * 1000))
        if not (0 <= la <= 99999 and 0 <= ln <= 999999):
            continue
        trozos.append(f"{cp}{la:05d}{ln:06d}")

    blob = "".join(trozos)
    assert len(blob) % 16 == 0, "el blob debe ser múltiplo de 16"
    SALIDA.write_text(blob, encoding="ascii")

    kb = len(blob) / 1024
    print(f"\n✓ {SALIDA.relative_to(RAIZ)} — {len(trozos):,} códigos postales, {kb:,.0f} KB")
    print(f"  rango: {trozos[0][:5]} … {trozos[-1][:5]}")
    return trozos


def verificar(trozos):
    """Relee el archivo como lo hará el navegador y revisa que todo cuadre."""
    blob = SALIDA.read_text(encoding="ascii")
    assert len(blob) % 16 == 0
    previo = ""
    for i in range(0, len(blob), 16):
        reg = blob[i:i + 16]
        assert reg.isdigit(), f"registro no numérico en {i}: {reg!r}"
        cp = reg[:5]
        lat = int(reg[5:10]) / 1000
        lng = -int(reg[10:16]) / 1000
        assert cp > previo, f"CP fuera de orden en {i}: {cp} después de {previo}"
        assert dentro_de_mexico(lat, lng), f"{cp} cae fuera de México: {lat},{lng}"
        previo = cp
    print(f"✓ verificado: {len(blob)//16:,} registros, orden ascendente, todos dentro de México")


def main():
    ap = argparse.ArgumentParser(description="Construye el índice de CP para /financial/gmm")
    ap.add_argument("--sepomex", metavar="CSV",
                    help="CSV de SEPOMEX con coordenadas (cobertura nacional)")
    args = ap.parse_args()

    print("Construyendo índice de códigos postales…")
    puntos = centroides_hospitales()
    # Los polígonos de la CDMX son más precisos que el pin de un hospital.
    puntos.update(centroides_cdmx())
    if args.sepomex:
        # El CSV nacional tiene prioridad sobre el polígono cuando hay ambos.
        puntos.update(centroides_csv(args.sepomex))
    else:
        print("  · sin --sepomex: el índice sólo cubrirá la CDMX")

    verificar(escribir(puntos))


if __name__ == "__main__":
    main()
