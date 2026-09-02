"""
Data lake del Atlas: escribir y leer capas con su procedencia pegada.

Cada capa se guarda como parquet (rápido, tipado, comprimido) junto a un
`_manifiesto.json` que registra qué se escribió, cuándo, cuántas filas y de
qué fuente. Sin manifiesto no hay auditoría posible, y el documento exige que
un banco o una autoridad puedan auditar el sistema.

Las geometrías se guardan en WKB dentro del parquet para no depender de que
esté instalado el motor de GeoPackage.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import from_wkb, to_wkb

from .config import Config, cargar

MANIFIESTO = "_manifiesto.json"


def _ruta(nombre: str, cfg: Config) -> Path:
    return cfg.lago / f"{nombre}.parquet"


def guardar(
    nombre: str,
    datos: pd.DataFrame | gpd.GeoDataFrame,
    fuente: str,
    nota: str = "",
    cfg: Config | None = None,
) -> Path:
    """Escribe una capa y anota su procedencia en el manifiesto."""
    cfg = cfg or cargar()
    p = _ruta(nombre, cfg)
    d = datos.copy()

    es_geo = isinstance(datos, gpd.GeoDataFrame) and datos.geometry is not None
    crs = None
    if es_geo:
        crs = str(datos.crs) if datos.crs else None
        wkb = to_wkb(d.geometry.values)
        d = pd.DataFrame(d.drop(columns=d.geometry.name))
        d["geometry"] = wkb

    # Las columnas `object` con listas/dicts (amenidades) van como JSON.
    for c in d.columns:
        if d[c].dtype == "object" and len(d) and isinstance(
            d[c].dropna().iloc[0] if d[c].notna().any() else None, (list, dict)
        ):
            d[c] = d[c].map(lambda v: json.dumps(v, ensure_ascii=False) if v is not None else None)

    d.to_parquet(p, index=False, compression="zstd")
    _anotar(nombre, len(d), fuente, nota, crs, cfg)
    return p


def leer(nombre: str, cfg: Config | None = None) -> pd.DataFrame | gpd.GeoDataFrame:
    """Lee una capa; si traía geometría vuelve como GeoDataFrame con su CRS."""
    cfg = cfg or cargar()
    p = _ruta(nombre, cfg)
    if not p.exists():
        raise FileNotFoundError(
            f"La capa '{nombre}' no está en el lago. Corre la Fase 0 primero: "
            "python -m atlas.pipelines.fase0"
        )
    d = pd.read_parquet(p)
    man = manifiesto(cfg).get(nombre, {})
    if "geometry" in d.columns and man.get("crs"):
        return gpd.GeoDataFrame(
            d.drop(columns="geometry"), geometry=from_wkb(d["geometry"]), crs=man["crs"]
        )
    return d


def existe(nombre: str, cfg: Config | None = None) -> bool:
    cfg = cfg or cargar()
    return _ruta(nombre, cfg).exists()


def manifiesto(cfg: Config | None = None) -> dict:
    cfg = cfg or cargar()
    p = cfg.lago / MANIFIESTO
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _anotar(nombre, filas, fuente, nota, crs, cfg: Config) -> None:
    m = manifiesto(cfg)
    m[nombre] = {
        "filas": int(filas),
        "fuente": fuente,
        "nota": nota,
        "crs": crs,
        "escrito": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (cfg.lago / MANIFIESTO).write_text(
        json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def resumen(cfg: Config | None = None) -> pd.DataFrame:
    """Tabla de qué hay en el lago. Es lo que se imprime al final de cada fase."""
    m = manifiesto(cfg)
    if not m:
        return pd.DataFrame(columns=["capa", "filas", "fuente", "escrito"])
    return pd.DataFrame(
        [
            {"capa": k, "filas": v["filas"], "fuente": v["fuente"], "escrito": v["escrito"]}
            for k, v in sorted(m.items())
        ]
    )
