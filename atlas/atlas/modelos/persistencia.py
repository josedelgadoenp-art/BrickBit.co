"""
Guardar el AVM entrenado y volver a usarlo para valuar un inmueble nuevo.

Sin esto, la Fase 2 evalúa y tira todo: cada valuación exigiría reentrenar tres
modelos y recalibrar el intervalo, que son minutos. La app de la Fase 4 necesita
responder en un segundo, así que el paquete entrenado se guarda entero.

QUÉ SE GUARDA, Y POR QUÉ TODO JUNTO. Un AVM no es un modelo: son seis piezas que
sólo significan algo juntas —el boosting, el hedónico regularizado, los pesos
del apilado, el modelo de dispersión, las correcciones conformes por segmento y
los cortes de tercil que definen esos segmentos—. Guardar sólo el predictor y
recalcular el intervalo con otros datos daría un número con una banda que no le
corresponde. Van en un mismo archivo para que sea imposible desparejarlos.

Y SE GUARDA LA HUELLA DE LOS DATOS. Cada paquete anota cuántos inmuebles lo
entrenaron y de qué fecha son. Un AVM entrenado con el inventario de hace ocho
meses sigue dando números convincentes mucho después de haber dejado de ser
cierto, y quien lo consulte tiene derecho a saber de cuándo es.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..config import Config, cargar

VERSION = 1


@dataclass
class Paquete:
    """Todo lo que hace falta para valuar, en una sola pieza."""

    columnas: list[str]                  # el orden exacto que espera el modelo
    boosting: Any
    lineal: tuple                        # (preparador, modelo, columnas del núcleo)
    apilado: Any
    dispersion: Any
    conforme_por_alpha: dict             # alpha -> Conformal
    cortes: np.ndarray | None
    nombre_segmentacion: str
    tipo_referencia: str | None
    operacion: str
    n_entrenamiento: int
    fecha_datos: str
    metricas: dict = field(default_factory=dict)
    version: int = VERSION

    @property
    def alphas(self) -> list[float]:
        return sorted(self.conforme_por_alpha)

    def antiguedad_dias(self) -> int:
        try:
            f = datetime.fromisoformat(self.fecha_datos)
        except ValueError:
            return -1
        if f.tzinfo is None:
            f = f.replace(tzinfo=timezone.utc)
        return int((datetime.now(timezone.utc) - f).days)


def ruta(cfg: Config | None = None, operacion: str = "venta") -> Path:
    cfg = cfg or cargar()
    d = cfg.ruta("artefactos")
    d.mkdir(parents=True, exist_ok=True)
    return d / f"avm_{operacion}.joblib"


def guardar(p: Paquete, cfg: Config | None = None) -> Path:
    import joblib

    destino = ruta(cfg, p.operacion)
    joblib.dump(p, destino, compress=3)
    return destino


def cargar_paquete(cfg: Config | None = None, operacion: str = "venta") -> Paquete | None:
    """Devuelve None si no hay paquete: la app debe poder decirlo, no reventar."""
    import joblib

    r = ruta(cfg, operacion)
    if not r.exists():
        return None
    try:
        p = joblib.load(r)
    except Exception:
        return None
    return p if getattr(p, "version", None) == VERSION else None


# ------------------------------------------------------------------ valuación
def fila_de_inmueble(
    lat: float,
    lng: float,
    atributos: dict,
    feats: pd.DataFrame,
    columnas: list[str],
    tipo_referencia: str | None,
    cfg: Config | None = None,
) -> pd.DataFrame:
    """
    Arma la fila de variables de un inmueble que no está en la base.

    Hereda las variables de la celda H3 donde cae —las mismas que la Fase 1
    calculó para toda la ciudad— y les pega los atributos que da el usuario. El
    orden de columnas se toma del paquete y no de lo que venga: un modelo de
    árboles no valida nombres, así que una columna corrida daría un número
    perfectamente plausible y perfectamente equivocado.
    """
    import h3

    cfg = cfg or cargar()
    res = int(cfg["modelado"]["h3"]["resolucion_malla"])
    celda = h3.latlng_to_cell(float(lat), float(lng), res)

    fila = feats.loc[feats["h3"].astype(str) == celda]
    if fila.empty:
        # Fuera de la malla: se toma la celda más cercana, igual que en el
        # ensamblado de la Fase 2, y quien llame debería avisarlo.
        from scipy.spatial import cKDTree

        from ..geo import _xy, puntos

        arbol = cKDTree(_xy(puntos(feats, cfg=cfg), cfg))
        p = _xy(puntos(pd.DataFrame([{"lat": lat, "lng": lng}]), cfg=cfg), cfg)
        _, i = arbol.query(p, k=1)
        fila = feats.iloc[[int(i[0])]]

    x = {c: np.nan for c in columnas}
    for c in columnas:
        if c in fila.columns:
            v = fila[c].iloc[0]
            x[c] = float(v) if pd.notna(v) else np.nan

    sup = float(atributos.get("superficie_construida_m2") or np.nan)
    terreno = atributos.get("superficie_terreno_m2")
    if not np.isfinite(sup) and terreno:
        sup = float(terreno)
    directos = {
        "superficie_construida_m2": sup,
        "superficie_terreno_m2": float(terreno) if terreno else np.nan,
        "ln_superficie": np.log(sup) if np.isfinite(sup) and sup > 0 else np.nan,
        "recamaras": atributos.get("recamaras"),
        "banos": atributos.get("banos"),
        "medios_banos": atributos.get("medios_banos"),
        "estacionamientos": atributos.get("estacionamientos"),
        "antiguedad_anios": atributos.get("antiguedad_anios"),
        "niveles": atributos.get("niveles"),
        "tiene_terreno": 1.0 if terreno else 0.0,
    }
    ban = atributos.get("banos")
    med = atributos.get("medios_banos")
    if ban is not None or med is not None:
        directos["banos_totales"] = float(ban or 0) + 0.5 * float(med or 0)
    for c, v in directos.items():
        if c in x and v is not None:
            x[c] = float(v) if v is not None and np.isfinite(float(v)) else np.nan

    tipo = str(atributos.get("tipo", "depto"))
    for c in columnas:
        if c.startswith("tipo_"):
            x[c] = 1.0 if c == f"tipo_{tipo}" else 0.0

    return pd.DataFrame([x], columns=columnas)


@dataclass
class Valuacion:
    precio_m2: float
    precio_total: float
    lo_m2: float
    hi_m2: float
    lo_total: float
    hi_total: float
    alpha: float
    segmento: str
    superficie_m2: float

    @property
    def ancho_pct(self) -> float:
        centro = np.sqrt(self.lo_m2 * self.hi_m2)
        return (self.hi_m2 - self.lo_m2) / (2 * centro) * 100.0


def valuar(p: Paquete, X: pd.DataFrame, superficie_m2: float,
           alpha: float = 0.05) -> Valuacion:
    """
    Punto e intervalo para un inmueble.

    El punto es la MEDIANA del precio por m², no la media: al deshacer el
    logaritmo, exp(ŷ) es la mediana, y convertirla en media exigiría un ajuste
    que supone errores log-normales homocedásticos. Para valuar, además, la
    mediana es la cifra correcta —"cuánto vale un inmueble así"— y no el valor
    esperado bajo un supuesto distribucional.
    """
    from . import conforme

    prep, lineal, cols_nucleo = p.lineal
    pred = p.apilado.predecir({
        "boosting": p.boosting.predict(X),
        "hedonico": lineal.predict(prep.transform(X[cols_nucleo])),
    })

    a = min(p.alphas, key=lambda x: abs(x - alpha)) if p.alphas else alpha
    c = p.conforme_por_alpha.get(a)
    tipo = next((col.replace("tipo_", "") for col in X.columns
                 if col.startswith("tipo_") and float(X[col].iloc[0]) == 1.0),
                p.tipo_referencia or "otro")
    seg = conforme.segmentar(p.nombre_segmentacion, pd.Series([tipo]),
                             pd.Series(np.exp(pred)), p.cortes)
    sig = p.dispersion.predict(X)
    lo, hi = conforme.aplicar_normalizado(pred, sig, c, seg)

    pm2, lom2, him2 = float(np.exp(pred[0])), float(np.exp(lo[0])), float(np.exp(hi[0]))
    s = float(superficie_m2)
    return Valuacion(
        precio_m2=pm2, precio_total=pm2 * s,
        lo_m2=lom2, hi_m2=him2, lo_total=lom2 * s, hi_total=him2 * s,
        alpha=a, segmento=str(seg.iloc[0]), superficie_m2=s,
    )
