#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ingerir_lote_c21.py — Lleva la escala CALLE del Motor de Morfogénesis a todas
las ciudades donde Century 21 tiene inventario, en UN solo comando.

Corre EN TU MÁQUINA (INEGI bloquea IPs de nube; desde tu PC descarga bien):

    python scripts/ingerir_lote_c21.py                # objetivo: ~200 ciudades
    python scripts/ingerir_lote_c21.py --max 150      # o el tope que quieras
    python scripts/ingerir_lote_c21.py --min-inv 10   # solo munis con >=10 props

Qué hace:
  1) Pregunta al Worker de BrickBit qué municipios tienen inventario C21 vivo
     (registro _zonas + índice) y los ordena por número de propiedades.
  2) Descarga el DENUE de cada ESTADO necesario UNA sola vez (caché en
     denue_cache/ — los ZIP estatales pesan cientos de MB; sin caché, un lote
     de 150 ciudades re-descargaría lo mismo decenas de veces).
  3) Corre scripts/ingerir_denue.py por cada municipio faltante (los que ya
     tienen data/calles_*.json se saltan) usando el CSV cacheado.
  4) Resume: ingeridos, saltados y fallidos. Después: revisa `git status`,
     agrega los data/ nuevos, commit y push — Streamlit Cloud se actualiza solo.

Peso esperado: ~250 KB por ciudad (~40 MB por 150 ciudades nuevas).
"""
import argparse, glob, io, json, os, re, subprocess, sys, unicodedata, urllib.request, zipfile

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = "https://brickbit-api.jose-delgado-enp.workers.dev"
CACHE = os.path.join(_DIR, "denue_cache")
PATRONES_URL = [
    "https://www.inegi.org.mx/contenidos/masiva/denue/denue_{ee}_csv.zip",
    "https://www.inegi.org.mx/contenidos/masiva/denue/denue_{ee}_shp_csv.zip",
]

# Entidad (texto del inventario C21) → clave INEGI de 2 dígitos.
ESTADO_CLAVE = {
    "aguascalientes": "01", "baja california": "02", "baja california sur": "03",
    "campeche": "04", "coahuila": "05", "colima": "06", "chiapas": "07",
    "chihuahua": "08", "ciudad de mexico": "09", "cdmx": "09",
    "distrito federal": "09", "durango": "10", "guanajuato": "11",
    "guerrero": "12", "hidalgo": "13", "jalisco": "14",
    "estado de mexico": "15", "mexico": "15", "michoacan": "16", "morelos": "17",
    "nayarit": "18", "nuevo leon": "19", "oaxaca": "20", "puebla": "21",
    "queretaro": "22", "quintana roo": "23", "san luis potosi": "24",
    "sinaloa": "25", "sonora": "26", "tabasco": "27", "tamaulipas": "28",
    "tlaxcala": "29", "veracruz": "30", "yucatan": "31", "zacatecas": "32",
}


def norm(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip().lower()


def sufijo(municipio):
    """Réplica del sufijo de archivo que usa ingerir_denue.py."""
    return re.sub(r"[^a-z0-9]+", "_", norm(municipio)).strip("_")


def jget(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def clave_estado(texto):
    ne = norm(texto)
    if ne in ESTADO_CLAVE:
        return ESTADO_CLAVE[ne]
    for k, v in ESTADO_CLAVE.items():
        if k in ne or ne in k:
            return v
    return None


def csv_estado(ee):
    """Descarga (una vez) el DENUE del estado `ee` y devuelve la ruta del CSV."""
    os.makedirs(CACHE, exist_ok=True)
    ruta_csv = os.path.join(CACHE, f"denue_{ee}.csv")
    if os.path.exists(ruta_csv) and os.path.getsize(ruta_csv) > 1_000_000:
        return ruta_csv
    ruta_zip = os.path.join(CACHE, f"denue_{ee}_csv.zip")
    if not (os.path.exists(ruta_zip) and os.path.getsize(ruta_zip) > 1_000_000):
        for patron in PATRONES_URL:
            url = patron.format(ee=ee)
            try:
                print(f"    Descargando DENUE estado {ee} … ({url})")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=600) as r, open(ruta_zip, "wb") as f:
                    while True:
                        b = r.read(1 << 20)
                        if not b:
                            break
                        f.write(b)
                break
            except Exception as e:
                print(f"      no respondió: {e}")
        else:
            return None
    try:
        with zipfile.ZipFile(ruta_zip) as z:
            candidatos = [n for n in z.namelist() if n.lower().endswith(".csv")]
            if not candidatos:
                return None
            mayor = max(candidatos, key=lambda n: z.getinfo(n).file_size)
            with z.open(mayor) as src, open(ruta_csv, "wb") as dst:
                while True:
                    b = src.read(1 << 20)
                    if not b:
                        break
                    dst.write(b)
        return ruta_csv
    except zipfile.BadZipFile:
        os.remove(ruta_zip)
        return None


def main():
    ap = argparse.ArgumentParser(description="Lote DENUE → escala calle, guiado por el inventario C21")
    ap.add_argument("--max", type=int, default=200,
                    help="tope TOTAL de ciudades en la escala calle (existentes + nuevas)")
    ap.add_argument("--min-inv", type=int, default=5,
                    help="mínimo de propiedades C21 para que un municipio califique")
    ap.add_argument("--solo-listar", action="store_true",
                    help="muestra el plan sin ingerir nada")
    args = ap.parse_args()

    existentes = {os.path.basename(p)[len("calles_"):-len(".json")]
                  for p in glob.glob(os.path.join(_DIR, "data", "calles_*.json"))}
    print(f"Escala calle actual: {len(existentes)} ciudades.")

    print("Consultando el inventario C21 vivo…")
    reg = jget(BACKEND + "/api/listados?zona=_zonas")           # municipios
    if not isinstance(reg, list):
        print("El registro _zonas no respondió como lista. ¿Worker arriba?"); sys.exit(1)

    objetivos = []
    for m in sorted(reg, key=lambda x: -(x.get("n") or 0)):
        nombre = m.get("nombre") or ""
        if "," not in nombre or (m.get("n") or 0) < args.min_inv:
            continue
        municipio, estado = [p.strip() for p in nombre.split(",", 1)]
        suf = sufijo(municipio)
        if suf in existentes:
            continue
        ee = clave_estado(estado)
        if not ee:
            print(f"  ? entidad no reconocida: {estado} ({nombre}) — se salta")
            continue
        if any(o["suf"] == suf for o in objetivos):   # homónimos entre estados
            print(f"  ! homónimo detectado ({municipio}): se conserva el de más inventario")
            continue
        objetivos.append({"municipio": municipio, "estado": estado,
                          "ee": ee, "suf": suf, "n": m.get("n", 0)})

    cupo = max(0, args.max - len(existentes))
    objetivos = objetivos[:cupo]
    print(f"Plan: {len(objetivos)} municipios nuevos (cupo {cupo}, mínimo "
          f"{args.min_inv} propiedades C21).")
    for o in objetivos[:15]:
        print(f"  · {o['municipio']}, {o['estado']} ({o['n']} props)")
    if len(objetivos) > 15:
        print(f"  … y {len(objetivos) - 15} más")
    if args.solo_listar or not objetivos:
        return

    ingeridor = os.path.join(_DIR, "scripts", "ingerir_denue.py")
    ok, fallidos = [], []
    estados_orden = sorted({o["ee"] for o in objetivos})
    for ee in estados_orden:   # estado por estado: un download, N municipios
        del_estado = [o for o in objetivos if o["ee"] == ee]
        print(f"\n== Estado {ee} · {len(del_estado)} municipios ==")
        csv = csv_estado(ee)
        if not csv:
            print(f"  ✗ no se pudo obtener el DENUE del estado {ee}; se saltan sus municipios")
            fallidos += [o["municipio"] for o in del_estado]
            continue
        for o in del_estado:
            print(f"  → {o['municipio']} ({o['n']} props C21)")
            r = subprocess.run([sys.executable, ingeridor, "--estado", ee,
                                "--municipio", o["municipio"], "--csv", csv],
                               capture_output=True, text=True)
            if r.returncode == 0 and os.path.exists(
                    os.path.join(_DIR, "data", f"calles_{o['suf']}.json")):
                ok.append(o["municipio"])
            else:
                fallidos.append(o["municipio"])
                cola = (r.stderr or r.stdout or "").strip().splitlines()
                print(f"    ✗ falló: {cola[-1] if cola else 'sin detalle'}")

    print("\n================= RESUMEN =================")
    print(f"  Ingeridos: {len(ok)}  ·  Fallidos: {len(fallidos)}")
    if fallidos:
        print("  Fallidos:", ", ".join(fallidos[:20]) + ("…" if len(fallidos) > 20 else ""))
    print(f"  Escala calle ahora: ~{len(existentes) + len(ok)} ciudades.")
    print("\nSiguiente paso: git add data/ && git commit -m 'Escala calle: lote C21' && git push")
    print("(Streamlit Cloud se redespliega solo. El caché denue_cache/ puede borrarse cuando quieras.)")


if __name__ == "__main__":
    main()
