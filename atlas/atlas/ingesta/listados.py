"""
Ingesta de listados → tabla `properties`.

ESTADO REAL AL ESCRIBIR ESTO: BrickBit no conserva listados individuales.
`data/mercado.json` trae 0 registros, y el scraper autorizado de Century 21
(`tools/c21-scraper.mjs`) sí produce exactamente el vector que hace falta
—precio, m² construidos y de terreno, recámaras, baños, estacionamientos,
lat/lng, colonia, municipio, tipo, operación— pero su salida se sube al KV del
Worker y el archivo local nunca se guarda.

Por eso este módulo lee `c21_out/listados.json` si existe. No inventa datos ni
genera sintéticos: sin listados, el AVM no se entrena y el pipeline lo dice.

Para conseguirlos:
    node tools/c21-scraper.mjs todo     # en tu máquina; deja c21_out/listados.json

El scraping de C21 está autorizado por convenio (ver cabecera del scraper).
Cualquier otra fuente debe respetar robots.txt y términos de servicio, y
registrar procedencia y fecha — que es justo lo que guarda el esquema.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..config import Config, cargar
from ..esquema import Reporte, deduplicar, normalizar

# Mapa del formato del scraper C21 → esquema canónico.
MAPA_C21 = {
    "precio": "precio_asking",
    "moneda": "moneda",
    "tipo": "tipo",
    "operacion": "operacion",
    "m2_construccion": "superficie_construida_m2",
    "m2_terreno": "superficie_terreno_m2",
    "recamaras": "recamaras",
    "banos": "banos",
    "estacionamientos": "estacionamientos",
    "lat": "lat",
    "lng": "lng",
    "colonia": "colonia",
    "municipio": "alcaldia",
}


def hay_listados(cfg: Config | None = None) -> bool:
    cfg = cfg or cargar()
    return cfg.ruta("listados_c21").exists()


def cargar_c21(cfg: Config | None = None) -> tuple[pd.DataFrame, Reporte]:
    """
    Lee la salida del scraper y la lleva al esquema. Devuelve (properties, reporte).
    Si el archivo no está, devuelve un DataFrame vacío CON el esquema completo:
    así el resto del pipeline puede seguir corriendo y reportar la ausencia,
    en vez de reventar.
    """
    cfg = cfg or cargar()
    ruta = cfg.ruta("listados_c21")
    if not ruta.exists():
        vacio, rep = normalizar(pd.DataFrame(columns=list(MAPA_C21)), cfg)
        return vacio, rep

    crudo = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if isinstance(crudo, dict):
        crudo = crudo.get("listados") or crudo.get("items") or []
    df = pd.DataFrame(crudo)
    if df.empty:
        vacio, rep = normalizar(pd.DataFrame(columns=list(MAPA_C21)), cfg)
        return vacio, rep

    d = df.rename(columns={k: v for k, v in MAPA_C21.items() if k in df.columns})
    d["source"] = "century21"
    # El scraper no fecha cada registro; la fecha del archivo es la mejor
    # aproximación disponible y se declara como tal.
    d["fecha_captura"] = pd.Timestamp(ruta.stat().st_mtime, unit="s")

    limpio, rep = normalizar(d, cfg)
    limpio, n_dup = deduplicar(limpio, cfg)
    rep.duplicados = n_dup
    rep.aceptados = len(limpio)
    return limpio, rep
