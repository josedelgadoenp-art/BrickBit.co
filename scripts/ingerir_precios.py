# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
 BrickBit · MUESTREO CONTROLADO DE PRECIOS DE PORTALES INMOBILIARIOS
═══════════════════════════════════════════════════════════════════════════════
 Obtiene una MUESTRA PEQUEÑA de precios de oferta (venta, MXN/m²) en zonas
 importantes, desde varios portales, con comportamiento deliberadamente
 respetuoso:

   · consulta y respeta robots.txt antes de tocar cada portal
   · User-Agent identificado (no se hace pasar por navegador)
   · máximo PAGINAS_MAX páginas por zona y PAUSA_SEG segundos entre peticiones
   · solo unas decenas de anuncios por zona — calibración, no clonado del portal

 Salida: data/precios_zonas.csv
   zona, lat, lng, portal, precio_m2_mediano, n_muestras, fecha

 La app la detecta sola y CALIBRA el precio sintético de las escalas CP y
 calle contra estos anclajes reales.

 ⚠ AVISO IMPORTANTE (léelo):
   Los términos de servicio de la mayoría de los portales restringen el
   scraping. Este script está diseñado para un muestreo mínimo de datos
   públicamente visibles con fines de calibración interna. Para un producto
   comercial de asesoría, lo correcto es licenciar los datos (Inmuebles24/
   Navent, Lamudi y Propiedades.com ofrecen data services) o usar datos
   propios de BrickBit. No aumentes los límites de este script.

 Uso:
     python scripts/ingerir_precios.py            # todas las zonas, ambos portales
     python scripts/ingerir_precios.py --portal lamudi
 Requiere red con acceso a los portales (agrega los dominios a la política
 de red del entorno, o ejecútalo desde tu máquina).
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.robotparser
from datetime import date
from statistics import median

import pandas as pd

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(_DIR, "data", "precios_zonas.csv")

UA = "BrickBitResearch/1.0 (calibracion-interna; contacto@brickbit.co)"
PAUSA_SEG = 4          # pausa entre peticiones — NO bajar
PAGINAS_MAX = 2        # páginas por zona/portal — NO subir
MUESTRAS_MAX = 40      # anuncios por zona/portal

# Zonas de calibración (nombre, lat, lng, slug de búsqueda aproximado)
ZONAS = [
    ("Polanco · CDMX", 19.433, -99.190, "polanco"),
    ("Condesa · CDMX", 19.412, -99.172, "condesa"),
    ("Del Valle · CDMX", 19.386, -99.170, "del-valle"),
    ("Santa Fe · CDMX", 19.359, -99.259, "santa-fe"),
    ("Coyoacán · CDMX", 19.350, -99.162, "coyoacan"),
    ("Azcapotzalco · CDMX", 19.482, -99.186, "azcapotzalco"),
    ("San Pedro GG · NL", 25.657, -100.402, "san-pedro-garza-garcia"),
    ("Monterrey Centro · NL", 25.669, -100.310, "monterrey"),
    ("Providencia · GDL", 20.699, -103.374, "guadalajara"),
    ("Zapopan · JAL", 20.711, -103.411, "zapopan"),
    ("Mérida Norte · YUC", 21.019, -89.618, "merida"),
    ("Cancún · QR", 21.161, -86.851, "cancun"),
    ("Querétaro · QRO", 20.588, -100.389, "queretaro"),
    ("Puebla Angelópolis · PUE", 19.027, -98.230, "puebla"),
    ("Tijuana · BC", 32.514, -117.038, "tijuana"),
]

PORTALES = {
    # patrón de búsqueda de VENTA de departamentos/casas por zona
    "lamudi": "https://www.lamudi.com.mx/{slug}/for-sale/?page={p}",
    "propiedades": "https://propiedades.com/{slug}/venta?pagina={p}",
    "inmuebles24": "https://www.inmuebles24.com/inmuebles-en-venta-en-{slug}.html",
    "casasyterrenos": "https://www.casasyterrenos.com/buscar?q={slug}&tipo=venta&pagina={p}",
}

# precios plausibles MXN/m² para descartar basura de parseo
M2_MIN, M2_MAX = 3000, 220000


def robots_permite(url: str) -> bool:
    """Consulta robots.txt del portal y respeta su decisión."""
    from urllib.parse import urlparse
    base = urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.set_url(f"{base.scheme}://{base.netloc}/robots.txt")
        rp.read()
        return rp.can_fetch(UA, url)
    except Exception:                     # noqa: BLE001 — si no responde, no tocamos
        return False


def descargar(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", errors="ignore")


def extraer_precios_m2(html: str) -> list[float]:
    """
    Extractor doble:
      1) JSON-LD (schema.org) con offers.price + floorSize → precio/m² exacto.
      2) Regex de respaldo: pares precio MXN + superficie m² cercanos.
    """
    precios = []
    # 1 · JSON-LD
    for bloque in re.findall(
            r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>',
            html, re.S):
        try:
            data = json.loads(bloque)
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            for nodo in ([it] + it.get("itemListElement", [])
                         if isinstance(it, dict) else []):
                if not isinstance(nodo, dict):
                    continue
                nodo = nodo.get("item", nodo)
                try:
                    precio = float(str(nodo["offers"]["price"])
                                   .replace(",", ""))
                    m2 = float(re.sub(r"[^\d.]", "",
                                      str(nodo["floorSize"]["value"])))
                    if m2 > 15 and M2_MIN < precio / m2 < M2_MAX:
                        precios.append(precio / m2)
                except (KeyError, TypeError, ValueError, ZeroDivisionError):
                    continue
    if precios:
        return precios
    # 2 · regex de respaldo: "$4,500,000 ... 120 m²" en la misma tarjeta
    tarjetas = re.findall(
        r'\$\s?([\d,]{6,12})(?:\s?MXN)?.{0,300}?(\d{2,4})\s?m',
        html, re.S)
    for p_txt, m2_txt in tarjetas[:MUESTRAS_MAX]:
        try:
            precio, m2 = float(p_txt.replace(",", "")), float(m2_txt)
            if m2 > 15 and M2_MIN < precio / m2 < M2_MAX:
                precios.append(precio / m2)
        except (ValueError, ZeroDivisionError):
            continue
    return precios


def muestrear(portales: list[str]) -> pd.DataFrame:
    filas = []
    for nombre, lat, lng, slug in ZONAS:
        for portal in portales:
            plantilla = PORTALES[portal]
            muestras = []
            for p in range(1, PAGINAS_MAX + 1):
                url = plantilla.format(slug=slug, p=p)
                if p == 1 and not robots_permite(url):
                    print(f"  🤖 {portal}: robots.txt no permite {slug}; "
                          "respetado, salto")
                    break
                try:
                    html = descargar(url)
                except Exception as e:            # noqa: BLE001
                    print(f"  ✗ {portal}/{slug} p{p}: {e}")
                    break
                nuevos = extraer_precios_m2(html)
                muestras += nuevos
                print(f"  · {portal}/{slug} p{p}: {len(nuevos)} precios")
                time.sleep(PAUSA_SEG)
                if len(muestras) >= MUESTRAS_MAX:
                    break
            if muestras:
                muestras = muestras[:MUESTRAS_MAX]
                filas.append({"zona": nombre, "lat": lat, "lng": lng,
                              "portal": portal,
                              "precio_m2_mediano": round(median(muestras)),
                              "n_muestras": len(muestras),
                              "fecha": date.today().isoformat()})
    return pd.DataFrame(filas)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--portal", choices=list(PORTALES), default=None,
                    help="limitar a un portal")
    args = ap.parse_args()
    portales = [args.portal] if args.portal else list(PORTALES)

    print(f"🕊 Muestreo controlado: {len(ZONAS)} zonas × {portales} "
          f"(máx {PAGINAS_MAX} páginas/zona, pausa {PAUSA_SEG}s)")
    df = muestrear(portales)
    if df.empty:
        print("\n✗ Sin datos. Causas típicas: red bloqueada (agrega los "
              "dominios a la política de red o corre local), robots.txt "
              "restrictivo, o marcado HTML distinto (ajustar extractor).")
        sys.exit(1)
    # combina con corridas anteriores (histórico de calibración)
    if os.path.exists(SALIDA):
        df = pd.concat([pd.read_csv(SALIDA), df], ignore_index=True) \
            .drop_duplicates(["zona", "portal", "fecha"], keep="last")
    df.to_csv(SALIDA, index=False)
    print(f"\n✅ {SALIDA}: {len(df)} filas · "
          f"{df['zona'].nunique()} zonas · {df['portal'].nunique()} portales")
    print("La app calibrará los precios de las escalas CP y calle sola.")


if __name__ == "__main__":
    main()
