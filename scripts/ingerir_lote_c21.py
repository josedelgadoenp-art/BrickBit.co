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
  2) Descarga el DENUE de cada ESTADO necesario UNA sola vez (a denue_cache/;
     sin ese caché, un lote de 150 ciudades re-descargaría lo mismo decenas de
     veces). El ZIP no se extrae —se lee por dentro— y se borra al terminar el
     estado, así que el disco solo carga un estado a la vez.
  3) Corre scripts/ingerir_denue.py por cada municipio faltante (los que ya
     tienen data/calles_*.json se saltan) leyendo ese ZIP.
  4) Resume: ingeridos, saltados y fallidos. Después: revisa `git status`,
     agrega los data/ nuevos, commit y push — Streamlit Cloud se actualiza solo.

Peso esperado: ~1.15 MB por ciudad, medido sobre las 83 ya ingeridas (242 KB
de calles + 665 KB de establecimientos + 247 KB del sismógrafo). Llegar a 200
ciudades suma ~135 MB a data/, que pasa de 99 MB a ~235 MB.
"""
import argparse, errno, glob, json, os, shutil, subprocess, sys, time, unicodedata, zipfile
import urllib.error, urllib.request

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = "https://brickbit-api.jose-delgado-enp.workers.dev"
CACHE = os.path.join(_DIR, "denue_cache")
# Piso de disco libre. Como ya no se extrae nada, lo unico que baja es el ZIP
# del estado (decenas de MB), asi que con 1 GB de holgura sobra.
MIN_LIBRE_GB = 1.0
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
    """Réplica EXACTA del sufijo que usa ingerir_denue.py para nombrar sus
    archivos: sin acentos, minúsculas y solo los espacios pasan a "_".

    Tiene que ser idéntica, no parecida. Si aquí se normalizara además la
    puntuación, "Gral. Escobedo" daría "gral_escobedo" mientras el ingeridor
    escribe "calles_gral._escobedo.json": el lote no reconocería el archivo
    recién creado y reportaría como fallido un municipio que sí se ingirió
    (y en la siguiente corrida lo volvería a descargar).
    """
    return norm(municipio).replace(" ", "_")


# C21 → nombre con el que el DENUE sí encuentra el municipio, para los casos
# que ninguna regla automática puede resolver sin adivinar.
# San Pedro Mixtepec: C21 le agrega el distrito ("Juquila"); el DENUE actual lo
# lista a secas (verificado en la corrida real: la sugerencia del propio
# archivo fue 'San Pedro Mixtepec', sin número de distrito).
ALIAS_C21 = {
    "san pedro mixtepec juquila": ["San Pedro Mixtepec"],
    # El municipio General Trías (Chihuahua) se llamó Santa Isabel hasta que se
    # renombró en honor al general; INEGI ha usado ambos según el corte. La
    # corrida real no encontró "General Trias" ni "Gral. Trias" en el DENUE
    # estatal, así que se prueba también el nombre viejo — el que exista gana.
    "general trias": ["General Trias", "Santa Isabel"],
}


def candidatos(municipio):
    """Nombres con los que vale la pena buscar el municipio en el DENUE.

    Century 21 nombra algunas plazas con el municipio Y la marca turística:
    "Solidaridad / Riviera Maya" (el municipio es Solidaridad) y
    "Cancún/Benito Juárez" (el municipio es Benito Juárez). Como la parte
    oficial unas veces va antes y otras después de la diagonal, se prueban las
    dos y el DENUE decide cuál existe. De paso esto evita el otro problema de
    la diagonal: "calles_cancun/benito_juarez.json" no es una ruta válida.
    """
    alias = ALIAS_C21.get(norm(municipio))
    if alias:
        return alias
    if "/" not in municipio:
        return [municipio]
    partes = [p.strip() for p in municipio.split("/") if p.strip()]
    return partes or [municipio.replace("/", " ").strip()]


# Windows: cuando la salida del hijo se captura por tubería, Python usa la
# codificación del sistema (cp1252) y revienta con UnicodeEncodeError al
# imprimir una flecha o una palomita. PYTHONIOENCODING lo obliga a UTF-8 en el
# hijo y aquí se decodifica igual; errors="replace" para que un carácter raro
# nunca tumbe una ingesta que sí funcionó.
TEXTO_UTF8 = {
    "text": True,
    "encoding": "utf-8",
    "errors": "replace",
    "env": {**os.environ, "PYTHONIOENCODING": "utf-8"},
}

# Cloudflare (que es quien recibe las peticiones al Worker antes que el código)
# responde 403 a los User-Agent obviamente automatizados, y el de Python lo es:
# "Python-urllib/3.14". El navegador sí pasa, por eso el mapa carga el
# inventario mientras el script no. Con cabeceras de navegador pasa igual.
NAVEGADOR = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-MX,es;q=0.9",
    "Referer": "https://brickbit.co/",
}


def jget(url, intentos=3):
    ultimo = None
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers=NAVEGADOR)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            ultimo = e
            if e.code in (403, 404):
                break            # no lo arregla reintentar
        except Exception as e:    # timeouts, DNS, cortes de red
            ultimo = e
        if i < intentos - 1:
            time.sleep(2 ** i)
    raise ultimo


def clave_estado(texto):
    ne = norm(texto)
    if ne in ESTADO_CLAVE:
        return ESTADO_CLAVE[ne]
    for k, v in ESTADO_CLAVE.items():
        if k in ne or ne in k:
            return v
    return None


def borrar(*rutas):
    for r in rutas:
        try:
            os.remove(r)
        except OSError:
            pass


def libre_gb():
    return shutil.disk_usage(_DIR).free / 2**30


def csv_estado(ee):
    """Descarga el DENUE del estado `ee` y devuelve la ruta del ZIP.

    NO se extrae: ingerir_denue.py lee el CSV desde dentro del ZIP. Extraerlo
    costaba más de un GB por estado grande, y duplicado mientras el ZIP seguía
    ahí. Así el pico de disco es solo el ZIP —decenas de MB—, y el llamador lo
    borra al terminar ese estado.
    """
    os.makedirs(CACHE, exist_ok=True)
    borrar(os.path.join(CACHE, f"denue_{ee}.csv"))   # sobras de versiones previas
    ruta_zip = os.path.join(CACHE, f"denue_{ee}_csv.zip")
    # Hasta 2 vueltas completas: si la descarga llega cortada (pasa con los
    # estados grandes en conexiones flojas), se borra y se intenta UNA vez más
    # en la misma corrida en vez de rendirse en silencio.
    for vuelta in range(2):
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
                except OSError as e:
                    if getattr(e, "errno", None) == errno.ENOSPC:
                        borrar(ruta_zip)          # el parcial no sirve y estorba
                        raise
                    print(f"      no respondió: {e}")
                except Exception as e:
                    print(f"      no respondió: {e}")
            else:
                return None
        try:                                        # solo validar que sirva
            with zipfile.ZipFile(ruta_zip) as z:
                if not any(n.lower().endswith(".csv") for n in z.namelist()):
                    print(f"      el ZIP del estado {ee} no trae ningún CSV")
                    return None
            return ruta_zip
        except zipfile.BadZipFile:
            borrar(ruta_zip)
            if vuelta == 0:
                print(f"      la descarga del estado {ee} llegó corrupta o "
                      "incompleta; reintentando…")
    print(f"      la descarga del estado {ee} volvió a llegar corrupta. "
          "Reintenta la corrida más tarde (suele ser la conexión).")
    return None


def main():
    ap = argparse.ArgumentParser(description="Lote DENUE → escala calle, guiado por el inventario C21")
    ap.add_argument("--max", type=int, default=200,
                    help="tope TOTAL de ciudades en la escala calle (existentes + nuevas)")
    ap.add_argument("--min-inv", type=int, default=5,
                    help="mínimo de propiedades C21 para que un municipio califique")
    ap.add_argument("--solo-listar", action="store_true",
                    help="muestra el plan sin ingerir nada")
    ap.add_argument("--conservar-cache", action="store_true",
                    help="no borrar los CSV del DENUE al terminar cada estado "
                         "(ocupa varios GB; solo si vas a reprocesar)")
    ap.add_argument("--zonas-json", default=None,
                    help="ruta a un archivo con la respuesta de _zonas guardada "
                         "desde el navegador (evita la llamada al Worker)")
    args = ap.parse_args()

    existentes = {os.path.basename(p)[len("calles_"):-len(".json")]
                  for p in glob.glob(os.path.join(_DIR, "data", "calles_*.json"))}
    print(f"Escala calle actual: {len(existentes)} ciudades.")

    URL_ZONAS = BACKEND + "/api/listados?zona=_zonas"
    if args.zonas_json:
        print(f"Leyendo el inventario C21 de {args.zonas_json}…")
        with open(args.zonas_json, encoding="utf-8") as f:
            reg = json.load(f)
    else:
        print("Consultando el inventario C21 vivo…")
        try:
            reg = jget(URL_ZONAS)
        except Exception as e:
            codigo = getattr(e, "code", None)
            print(f"\n✗ No pude consultar el inventario: {e}")
            if codigo == 403:
                print("  Un 403 aquí casi siempre es Cloudflare filtrando peticiones")
                print("  automatizadas, no un problema del Worker: desde el navegador la")
                print("  misma URL responde bien.")
            print("\n  Salida de emergencia (funciona siempre):")
            print(f"   1. Abre esta URL en tu navegador:\n      {URL_ZONAS}")
            print("   2. Guarda la página como  zonas.json  (Ctrl+S) en esta carpeta.")
            print("   3. Vuelve a correr agregando:  --zonas-json zonas.json")
            sys.exit(1)
    if not isinstance(reg, list):
        print("El registro _zonas no respondió como lista. ¿Worker arriba?"); sys.exit(1)

    objetivos = []
    for m in sorted(reg, key=lambda x: -(x.get("n") or 0)):
        nombre = m.get("nombre") or ""
        if "," not in nombre or (m.get("n") or 0) < args.min_inv:
            continue
        municipio, estado = [p.strip() for p in nombre.split(",", 1)]
        cands = candidatos(municipio)
        sufs = [sufijo(c) for c in cands]
        if any(s in existentes for s in sufs):
            continue
        ee = clave_estado(estado)
        if not ee:
            print(f"  ? entidad no reconocida: {estado} ({nombre}) — se salta")
            continue
        if any(o["suf"] in sufs for o in objetivos):   # homónimos entre estados
            print(f"  ! homónimo detectado ({municipio}): se conserva el de más inventario")
            continue
        objetivos.append({"municipio": municipio, "estado": estado, "cands": cands,
                          "ee": ee, "suf": sufs[0], "n": m.get("n", 0)})

    cupo = max(0, args.max - len(existentes))
    objetivos = objetivos[:cupo]
    print(f"Plan: {len(objetivos)} municipios nuevos (cupo {cupo}, mínimo "
          f"{args.min_inv} propiedades C21).")
    # Medido sobre las 83 ciudades ya ingeridas: 242 KB de calles + 665 KB de
    # establecimientos + 247 KB del sismógrafo ≈ 1.15 MB por ciudad.
    print(f"Peso estimado: ~{len(objetivos) * 1.15:.0f} MB nuevos en data/ "
          f"(~1.15 MB por ciudad: calles + establecimientos + sismógrafo).")
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
        print(f"\n== Estado {ee} · {len(del_estado)} municipios · "
              f"{libre_gb():.1f} GB libres ==")
        if libre_gb() < MIN_LIBRE_GB:
            print(f"  ✗ Menos de {MIN_LIBRE_GB} GB libres: se detiene aquí para no dejar")
            print("    archivos a medias. Libera espacio y vuelve a correr el mismo")
            print("    comando; retoma en las ciudades que falten.")
            break
        try:
            csv = csv_estado(ee)
        except OSError as e:
            if getattr(e, "errno", None) != errno.ENOSPC:
                raise
            print("  ✗ Se acabó el espacio en disco a media descarga.")
            print(f"    Borra la carpeta {CACHE} y vuelve a correr el mismo comando:")
            print("    lo ya ingerido se conserva y retoma donde quedó.")
            break
        if not csv:
            print(f"  ✗ no se pudo obtener el DENUE del estado {ee}; se saltan sus municipios")
            fallidos += [o["municipio"] for o in del_estado]
            continue
        for o in del_estado:
            print(f"  → {o['municipio']} ({o['n']} props C21)")
        # Una sola llamada por estado: el DENUE estatal se lee UNA vez para
        # todos sus municipios. Antes se lanzaba un proceso por municipio, y
        # cada uno volvía a parsear el archivo completo — en un estado con 10
        # ciudades eso son 10 lecturas del mismo CSV y 10 picos de memoria.
        # Las candidatas de un nombre con diagonal van todas: la que no exista
        # en el DENUE simplemente no produce archivo.
        munis = [c for o in del_estado for c in o["cands"]]
        r = subprocess.run([sys.executable, ingeridor, "--estado", ee,
                            "--municipios", "|".join(munis), "--csv", csv],
                           capture_output=True, **TEXTO_UTF8)
        salida = (r.stdout or "") + (r.stderr or "")
        for linea in salida.splitlines():
            if linea.lstrip().startswith(("(", "✓", "✗")):
                print(f"    {linea.strip()}")
        antes = len(ok)
        for o in del_estado:
            hecho = next((c for c in o["cands"] if os.path.exists(
                os.path.join(_DIR, "data", f"calles_{sufijo(c)}.json"))), None)
            (ok.append(hecho) if hecho else fallidos.append(o["municipio"]))
        if len(ok) == antes and del_estado:
            # Ningún municipio del estado salió: el problema es del estado
            # (memoria, archivo corrupto…), no de los nombres. Mostrar el final
            # de la salida del hijo, que es donde vive el error real.
            print("    — Ningún municipio de este estado se ingirió. Últimas "
                  "líneas del proceso:")
            for linea in salida.strip().splitlines()[-6:]:
                print(f"      | {linea.strip()[:110]}")
        if not args.conservar_cache:
            borrar(csv)      # el ZIP de este estado ya no se necesita

    print("\n================= RESUMEN =================")
    print(f"  Ingeridos: {len(ok)}  ·  Fallidos: {len(fallidos)}")
    if fallidos:
        print("  Fallidos:", ", ".join(fallidos[:20]) + ("…" if len(fallidos) > 20 else ""))
    print(f"  Escala calle ahora: ~{len(existentes) + len(ok)} ciudades.")
    print("\nSiguiente paso: git add data/ && git commit -m 'Escala calle: lote C21' && git push")
    print("(Streamlit Cloud se redespliega solo. El caché denue_cache/ puede borrarse cuando quieras.)")


if __name__ == "__main__":
    main()
