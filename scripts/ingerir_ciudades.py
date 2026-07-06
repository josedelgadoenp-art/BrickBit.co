# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
 BrickBit · INGESTA MASIVA DE CIUDADES → escala Calle · Establecimiento
═══════════════════════════════════════════════════════════════════════════════
 Descarga el DENUE de cada entidad UNA sola vez y procesa TODAS sus ciudades
 objetivo (capitales estatales + metrópolis clave), generando por ciudad:

   data/establecimientos_<sufijo>.csv.gz · data/calles_<sufijo>.json
   data/sismografo_<sufijo>.json

 La app las detecta sola y aparecen en el selector de la escala calle.

 Uso:
     python scripts/ingerir_ciudades.py                 # todas las entidades
     python scripts/ingerir_ciudades.py 09 15 19        # solo algunas
     python scripts/ingerir_ciudades.py --zip-dir /ruta # zips ya descargados

 Reanudable: las ciudades cuyos archivos ya existen se saltan.
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse
import gc
import io
import os
import sys
import urllib.request
import zipfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ingerir_denue as ing                                  # noqa: E402

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://www.inegi.org.mx/contenidos/masiva/denue/denue_{ee}_csv.zip"
URL_PARTE = ("https://www.inegi.org.mx/contenidos/masiva/denue/"
             "denue_{ee}_{p}_csv.zip")
COLS = ["municipio", "entidad", "codigo_act", "nombre_act", "per_ocu",
        "tipo_vial", "nom_vial", "latitud", "longitud", "nom_estab",
        "fecha_alta"]

# Ciudades objetivo por entidad: capitales + metrópolis clave.
# (nombre oficial del municipio en el DENUE, sufijo de archivo único)
CIUDADES_OBJETIVO = {
    "01": [("Aguascalientes", "aguascalientes")],
    "02": [("Tijuana", "tijuana"), ("Mexicali", "mexicali"),
           ("Ensenada", "ensenada")],
    "03": [("La Paz", "la_paz"), ("Los Cabos", "los_cabos")],
    "04": [("Campeche", "campeche"), ("Carmen", "ciudad_del_carmen")],
    "05": [("Saltillo", "saltillo"), ("Torreón", "torreon")],
    "06": [("Colima", "colima"), ("Manzanillo", "manzanillo")],
    "07": [("Tuxtla Gutiérrez", "tuxtla_gutierrez"),
           ("Tapachula", "tapachula")],
    "08": [("Chihuahua", "chihuahua"), ("Juárez", "ciudad_juarez")],
    "09": [("Azcapotzalco", "azcapotzalco"), ("Cuauhtémoc", "cuauhtemoc"),
           ("Benito Juárez", "benito_juarez_cdmx"),
           ("Miguel Hidalgo", "miguel_hidalgo"), ("Coyoacán", "coyoacan"),
           ("Iztapalapa", "iztapalapa"),
           ("Gustavo A. Madero", "gustavo_a_madero"),
           ("Álvaro Obregón", "alvaro_obregon"), ("Tlalpan", "tlalpan")],
    "10": [("Durango", "durango")],
    "11": [("León", "leon"), ("Celaya", "celaya"), ("Irapuato", "irapuato"),
           ("Guanajuato", "guanajuato"),
           ("San Miguel de Allende", "san_miguel_de_allende")],
    "12": [("Acapulco de Juárez", "acapulco"),
           ("Chilpancingo de los Bravo", "chilpancingo")],
    "13": [("Pachuca de Soto", "pachuca")],
    "14": [("Guadalajara", "guadalajara"), ("Zapopan", "zapopan"),
           ("San Pedro Tlaquepaque", "tlaquepaque"),
           ("Puerto Vallarta", "puerto_vallarta")],
    "15": [("Toluca", "toluca"), ("Naucalpan de Juárez", "naucalpan"),
           ("Ecatepec de Morelos", "ecatepec"),
           ("Tlalnepantla de Baz", "tlalnepantla"),
           ("Huixquilucan", "huixquilucan")],
    "16": [("Morelia", "morelia"), ("Uruapan", "uruapan")],
    "17": [("Cuernavaca", "cuernavaca")],
    "18": [("Tepic", "tepic"), ("Bahía de Banderas", "bahia_de_banderas")],
    "19": [("Monterrey", "monterrey"),
           ("San Pedro Garza García", "san_pedro_garza_garcia"),
           ("Guadalupe", "guadalupe_nl"), ("Apodaca", "apodaca"),
           ("San Nicolás de los Garza", "san_nicolas")],
    "20": [("Oaxaca de Juárez", "oaxaca")],
    "21": [("Puebla", "puebla")],
    "22": [("Querétaro", "queretaro"),
           ("San Juan del Río", "san_juan_del_rio")],
    "23": [("Benito Juárez", "benito_juarez"),
           ("Solidaridad", "playa_del_carmen"), ("Tulum", "tulum"),
           ("Othón P. Blanco", "chetumal")],
    "24": [("San Luis Potosí", "san_luis_potosi")],
    "25": [("Culiacán", "culiacan"), ("Mazatlán", "mazatlan"),
           ("Ahome", "los_mochis")],
    "26": [("Hermosillo", "hermosillo"), ("Cajeme", "ciudad_obregon"),
           ("Nogales", "nogales")],
    "27": [("Centro", "villahermosa")],
    "28": [("Reynosa", "reynosa"), ("Tampico", "tampico"),
           ("Victoria", "ciudad_victoria"), ("Nuevo Laredo", "nuevo_laredo"),
           ("Matamoros", "matamoros")],
    "29": [("Tlaxcala", "tlaxcala")],
    "30": [("Veracruz", "veracruz"), ("Xalapa", "xalapa"),
           ("Coatzacoalcos", "coatzacoalcos"),
           ("Boca del Río", "boca_del_rio")],
    "31": [("Mérida", "merida"), ("Valladolid", "valladolid")],
    "32": [("Zacatecas", "zacatecas"), ("Guadalupe", "guadalupe_zac")],
}


def _leer_zip(datos: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        nombre = max((n for n in z.namelist() if n.lower().endswith(".csv")),
                     key=lambda n: z.getinfo(n).file_size)
        with z.open(nombre) as f:
            return pd.read_csv(f, encoding="latin-1", low_memory=False,
                               usecols=lambda c: c.strip().lower() in COLS)


def descargar_entidad(ee: str, zip_dir: str = None) -> pd.DataFrame:
    """DENUE completo de una entidad (usa zip local si existe; entidades
    grandes particionadas en _1, _2… se concatenan solas)."""
    local = os.path.join(zip_dir or "", f"denue_{ee}_csv.zip")
    if zip_dir and os.path.exists(local):
        with open(local, "rb") as f:
            return _leer_zip(f.read())
    try:
        with urllib.request.urlopen(URL.format(ee=ee), timeout=600) as r:
            return _leer_zip(r.read())
    except zipfile.BadZipFile:
        partes = []
        for p in range(1, 9):
            try:
                with urllib.request.urlopen(URL_PARTE.format(ee=ee, p=p),
                                            timeout=600) as r:
                    partes.append(_leer_zip(r.read()))
            except (zipfile.BadZipFile, urllib.error.HTTPError):
                break
        if not partes:
            raise
        return pd.concat(partes, ignore_index=True)


def ciudad_lista(sufijo: str) -> bool:
    return all(os.path.exists(os.path.join(_DIR, "data", f))
               for f in (f"calles_{sufijo}.json",
                         f"establecimientos_{sufijo}.csv.gz"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("entidades", nargs="*",
                    default=list(CIUDADES_OBJETIVO.keys()))
    ap.add_argument("--zip-dir", default=None,
                    help="carpeta con denue_EE_csv.zip ya descargados")
    ap.add_argument("--salida", default=os.path.join(_DIR, "data"))
    args = ap.parse_args()

    hechas, fallidas = [], []
    for ee in [e.zfill(2) for e in args.entidades]:
        objetivo = [c for c in CIUDADES_OBJETIVO.get(ee, [])
                    if not ciudad_lista(c[1])]
        if not objetivo:
            print(f"[{ee}] ✓ todas sus ciudades ya están; salto")
            continue
        try:
            print(f"[{ee}] ⇣ descargando entidad "
                  f"({len(objetivo)} ciudades)…", flush=True)
            df = descargar_entidad(ee, args.zip_dir)
        except Exception as e:                    # noqa: BLE001
            print(f"[{ee}] ✗ descarga: {e}")
            fallidas += [s for _, s in objetivo]
            continue
        disponibles = {ing.sin_acentos(m): m
                       for m in df["municipio"].dropna().unique()}
        for muni, suf in objetivo:
            clave = ing.sin_acentos(muni)
            if clave not in disponibles:
                print(f"  ✗ {muni}: no está en el DENUE de {ee}. "
                      f"Cercanos: {[m for k, m in disponibles.items() if clave.split()[0] in k][:4]}")
                fallidas.append(suf)
                continue
            try:
                ing.procesar(df, disponibles[clave], args.salida, suf)
                hechas.append(suf)
            except SystemExit:
                fallidas.append(suf)
            except Exception as e:                # noqa: BLE001
                print(f"  ✗ {muni}: {e}")
                fallidas.append(suf)
        del df
        gc.collect()

    print(f"\n✅ {len(hechas)} ciudades ingeridas"
          + (f" · ✗ fallidas: {fallidas}" if fallidas else ""))
    print("Reinicia la app: aparecen solas en el selector de la escala calle.")


if __name__ == "__main__":
    main()
