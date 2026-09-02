"""
Carga de configuración del Atlas.

Un solo punto de verdad: `cargar()` devuelve la config ya resuelta, con las
rutas convertidas a absolutas contra la raíz del repo. Nadie más lee el YAML.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# atlas/atlas/config.py → atlas/ → raíz del repo
RAIZ = Path(__file__).resolve().parent.parent.parent
CONFIG = RAIZ / "atlas" / "config.yaml"


@dataclass(frozen=True)
class Caja:
    """Caja envolvente en grados. Sirve para descartar puntos fuera de la CDMX."""

    lat_min: float
    lat_max: float
    lng_min: float
    lng_max: float

    def contiene(self, lat: float, lng: float) -> bool:
        try:
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            return False
        # NaN falla todas las comparaciones, así que queda fuera solo.
        return (self.lat_min <= lat <= self.lat_max) and (self.lng_min <= lng <= self.lng_max)


class Config:
    """Vista de sólo lectura sobre config.yaml, con rutas ya resueltas."""

    def __init__(self, crudo: dict[str, Any]):
        self._d = crudo

    # -- acceso genérico ----------------------------------------------------
    def __getitem__(self, clave: str) -> Any:
        return self._d[clave]

    def get(self, clave: str, defecto: Any = None) -> Any:
        return self._d.get(clave, defecto)

    # -- accesos con nombre, que es lo que se usa en el resto del código ----
    @property
    def semilla(self) -> int:
        return int(self._d["proyecto"]["semilla"])

    @property
    def crs_geografico(self) -> str:
        return self._d["crs"]["geografico"]

    @property
    def crs_metrico(self) -> str:
        return self._d["crs"]["metrico"]

    @property
    def caja(self) -> Caja:
        e = self._d["extension"]
        return Caja(e["lat_min"], e["lat_max"], e["lng_min"], e["lng_max"])

    @property
    def alcaldias(self) -> list[dict[str, str]]:
        return list(self._d["alcaldias"])

    def ruta(self, clave: str) -> Path:
        """Ruta absoluta de una entrada de `rutas`. Falla si la clave no existe."""
        rel = self._d["rutas"][clave]
        return (RAIZ / rel).resolve()

    @property
    def lago(self) -> Path:
        p = self.ruta("lago")
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def artefactos(self) -> Path:
        p = self.ruta("artefactos")
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache(maxsize=1)
def cargar(ruta: str | Path | None = None) -> Config:
    """Lee config.yaml una sola vez por proceso."""
    p = Path(ruta) if ruta else CONFIG
    if not p.exists():
        raise FileNotFoundError(
            f"No encuentro {p}. El Atlas no arranca sin su configuración: "
            "todos los parámetros viven ahí a propósito."
        )
    with p.open(encoding="utf-8") as fh:
        return Config(yaml.safe_load(fh))


def fijar_semilla(cfg: Config | None = None) -> int:
    """
    Fija las semillas de random y numpy. Se llama al inicio de cada pipeline:
    sin esto, dos corridas del mismo código dan números distintos y el
    'reproducible' del documento sería mentira.
    """
    cfg = cfg or cargar()
    s = cfg.semilla
    random.seed(s)
    try:
        import numpy as np

        np.random.seed(s)
    except ImportError:  # numpy siempre está, pero no se asume
        pass
    return s
