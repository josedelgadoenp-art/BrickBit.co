"""
Esquema canónico `properties` (§5 del prompt maestro), validación y dedup.

Todo listado, venga de donde venga, entra por aquí. Dos razones:
  1. Que el resto del sistema no sepa ni le importe de qué portal salió.
  2. Que la procedencia y la fecha de captura queden pegadas a cada registro.
     Sin eso no se puede auditar nada, y el documento exige auditabilidad.

NOTA DE HONESTIDAD: `precio_asking` es precio de OFERTA. No es de cierre y no
se convierte en uno. El campo se llama `asking` justamente para que nadie lo
confunda río abajo.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Config, cargar

# Columnas del esquema, con su tipo destino. El orden es el del documento.
ESQUEMA: dict[str, str] = {
    "id": "string",
    "source": "string",
    "fecha_captura": "datetime64[ns]",
    "lat": "float64",
    "lng": "float64",
    "precio_asking": "float64",
    "moneda": "string",
    "precio_m2_asking": "float64",
    "tipo": "string",              # depto | casa | terreno | otro
    "operacion": "string",         # venta | renta
    "superficie_construida_m2": "float64",
    "superficie_terreno_m2": "float64",
    "recamaras": "float64",
    "banos": "float64",
    "medios_banos": "float64",
    "estacionamientos": "float64",
    "antiguedad_anios": "float64",
    "niveles": "float64",
    "amenidades": "object",        # lista/dict; se serializa a JSON en parquet
    "alcaldia": "string",
    "colonia": "string",
    "cp": "string",
    "ageb": "string",
    "uso_suelo_seduvi": "string",
    "niveles_permitidos": "float64",
}

OBLIGATORIAS = ["id", "source", "fecha_captura", "lat", "lng", "precio_asking", "operacion"]

TIPOS_VALIDOS = {"depto", "casa", "terreno", "otro"}
OPERACIONES_VALIDAS = {"venta", "renta"}


@dataclass
class Reporte:
    """Qué entró, qué se cayó y por qué. Se imprime al final de cada ingesta."""

    recibidos: int = 0
    sin_geo: int = 0
    fuera_de_caja: int = 0
    sin_precio: int = 0
    sin_superficie: int = 0
    precio_m2_absurdo: int = 0
    duplicados: int = 0
    aceptados: int = 0

    def texto(self) -> str:
        p = [
            f"  recibidos            {self.recibidos:>8,}",
            f"  · sin coordenadas    {self.sin_geo:>8,}",
            f"  · fuera de la CDMX   {self.fuera_de_caja:>8,}",
            f"  · sin precio         {self.sin_precio:>8,}",
            f"  · sin superficie     {self.sin_superficie:>8,}",
            f"  · precio/m² absurdo  {self.precio_m2_absurdo:>8,}",
            f"  · duplicados         {self.duplicados:>8,}",
            f"  ACEPTADOS            {self.aceptados:>8,}",
        ]
        return "\n".join(p)


# ------------------------------------------------------------------ helpers
def _sin_acentos(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn"
    )


def normalizar_texto(s) -> str:
    """Minúsculas, sin acentos, sin puntuación, espacios colapsados."""
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    t = _sin_acentos(str(s)).lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def normalizar_tipo(v) -> str:
    t = normalizar_texto(v)
    if not t:
        return "otro"
    if any(k in t for k in ("depa", "depto", "departament", "condo", "loft", "penthouse")):
        return "depto"
    if any(k in t for k in ("casa", "residencia", "chalet", "duplex", "townhouse")):
        return "casa"
    if any(k in t for k in ("terreno", "lote", "predio", "suelo")):
        return "terreno"
    return "otro"


def normalizar_operacion(v) -> str:
    t = normalizar_texto(v)
    if "renta" in t or "arrenda" in t or "alquiler" in t:
        return "renta"
    if "venta" in t or "vender" in t or "compra" in t:
        return "venta"
    return "venta"  # el inventario de venta domina; se declara el supuesto


def geohash(lat: float, lng: float, precision: int = 8) -> str:
    """
    Geohash clásico. Se usa como llave gruesa de dedup: con precisión 8 la
    celda mide ~38×19 m, así que dos anuncios del mismo edificio caen juntos
    aunque sus coordenadas difieran un poco entre portales.
    """
    B32 = "0123456789bcdefghjkmnpqrstuvwxyz"
    lat_i, lng_i = (-90.0, 90.0), (-180.0, 180.0)
    bits, bit, ch, out = [16, 8, 4, 2, 1], 0, 0, []
    par = True
    while len(out) < precision:
        if par:
            medio = (lng_i[0] + lng_i[1]) / 2
            if lng > medio:
                ch |= bits[bit]
                lng_i = (medio, lng_i[1])
            else:
                lng_i = (lng_i[0], medio)
        else:
            medio = (lat_i[0] + lat_i[1]) / 2
            if lat > medio:
                ch |= bits[bit]
                lat_i = (medio, lat_i[1])
            else:
                lat_i = (lat_i[0], medio)
        par = not par
        if bit < 4:
            bit += 1
        else:
            out.append(B32[ch])
            bit = ch = 0
    return "".join(out)


def id_estable(source: str, lat: float, lng: float, precio: float, sup: float) -> str:
    """
    Identificador reproducible. No usa la fecha ni el id del portal a propósito:
    así el mismo inmueble capturado dos veces produce el mismo id y el dedup
    tiene algo firme de dónde agarrarse.
    """
    crudo = f"{source}|{lat:.6f}|{lng:.6f}|{round(float(precio or 0))}|{round(float(sup or 0))}"
    return hashlib.sha1(crudo.encode()).hexdigest()[:16]


# ---------------------------------------------------------------- validación
def normalizar(df: pd.DataFrame, cfg: Config | None = None) -> tuple[pd.DataFrame, Reporte]:
    """
    Lleva un DataFrame cualquiera al esquema canónico, descartando lo que no
    sirve y contando cada descarte. Devuelve (limpio, reporte).
    """
    cfg = cfg or cargar()
    rep = Reporte(recibidos=len(df))
    d = df.copy()

    # columnas faltantes → nulas, para que el esquema siempre esté completo
    for col in ESQUEMA:
        if col not in d.columns:
            d[col] = pd.NA

    d["lat"] = pd.to_numeric(d["lat"], errors="coerce")
    d["lng"] = pd.to_numeric(d["lng"], errors="coerce")
    sin_geo = d["lat"].isna() | d["lng"].isna()
    rep.sin_geo = int(sin_geo.sum())
    d = d.loc[~sin_geo]

    caja = cfg.caja
    dentro = d["lat"].between(caja.lat_min, caja.lat_max) & d["lng"].between(
        caja.lng_min, caja.lng_max
    )
    rep.fuera_de_caja = int((~dentro).sum())
    d = d.loc[dentro]

    d["precio_asking"] = pd.to_numeric(d["precio_asking"], errors="coerce")
    sin_precio = d["precio_asking"].isna() | (d["precio_asking"] <= 0)
    rep.sin_precio = int(sin_precio.sum())
    d = d.loc[~sin_precio]

    for c in (
        "superficie_construida_m2", "superficie_terreno_m2", "recamaras", "banos",
        "medios_banos", "estacionamientos", "antiguedad_anios", "niveles",
        "niveles_permitidos",
    ):
        d[c] = pd.to_numeric(d[c], errors="coerce")

    d["tipo"] = d["tipo"].map(normalizar_tipo)
    d["operacion"] = d["operacion"].map(normalizar_operacion)
    d["moneda"] = d["moneda"].fillna("MXN").astype("string").str.upper()

    # Superficie de referencia: construida, y para terrenos la del terreno.
    sup = d["superficie_construida_m2"].where(
        d["superficie_construida_m2"].notna() & (d["superficie_construida_m2"] > 0),
        d["superficie_terreno_m2"],
    )
    ing = cfg["ingesta"]
    sup_ok = sup.between(ing["min_superficie_m2"], ing["max_superficie_m2"])
    rep.sin_superficie = int((~sup_ok).sum())
    d = d.loc[sup_ok]
    sup = sup.loc[d.index]

    d["precio_m2_asking"] = d["precio_asking"] / sup

    # El filtro de precio/m² sólo aplica a VENTA: una renta de $250/m² al mes
    # es normal y caería por debajo del piso pensado para venta.
    es_venta = d["operacion"].eq("venta")
    absurdo = es_venta & ~d["precio_m2_asking"].between(
        ing["min_precio_m2"], ing["max_precio_m2"]
    )
    rep.precio_m2_absurdo = int(absurdo.sum())
    d = d.loc[~absurdo]
    sup = sup.loc[d.index]      # realinear: d acaba de encoger otra vez

    d["fecha_captura"] = pd.to_datetime(d["fecha_captura"], errors="coerce")
    d["fecha_captura"] = d["fecha_captura"].fillna(pd.Timestamp.now('UTC').tz_localize(None))
    d["source"] = d["source"].fillna("desconocida").astype("string")

    faltan_id = d["id"].isna()
    if faltan_id.any():
        d.loc[faltan_id, "id"] = [
            id_estable(s, la, lo, p, su)
            for s, la, lo, p, su in zip(
                d.loc[faltan_id, "source"], d.loc[faltan_id, "lat"],
                d.loc[faltan_id, "lng"], d.loc[faltan_id, "precio_asking"],
                sup.loc[faltan_id],
            )
        ]

    d = d[list(ESQUEMA)]
    for col, tipo in ESQUEMA.items():
        if tipo.startswith("datetime"):
            continue
        if tipo == "object":
            continue
        try:
            d[col] = d[col].astype(tipo)
        except (TypeError, ValueError):
            pass  # una columna rebelde no debe tumbar la ingesta entera

    rep.aceptados = len(d)
    return d.reset_index(drop=True), rep


def deduplicar(df: pd.DataFrame, cfg: Config | None = None) -> tuple[pd.DataFrame, int]:
    """
    Quita republicaciones del mismo inmueble.

    Llave: geohash + tipo + operación + superficie y precio redondeados a su
    tolerancia. Dos anuncios del mismo depto en portales distintos rara vez
    coinciden al peso, pero sí caen en el mismo cubo. Se conserva el registro
    MÁS RECIENTE de cada grupo, que es el precio vigente.
    """
    cfg = cfg or cargar()
    if df.empty:
        return df, 0
    dd = cfg["dedup"]
    p = int(dd["precision_geohash"])
    tol_s = float(dd["tolerancia_superficie"])
    tol_p = float(dd["tolerancia_precio"])

    d = df.copy()
    gh = [geohash(la, lo, p) for la, lo in zip(d["lat"], d["lng"])]
    sup = d["superficie_construida_m2"].fillna(d["superficie_terreno_m2"]).fillna(0)
    # Redondeo logarítmico: agrupa por diferencia RELATIVA, no absoluta.
    cubo_s = np.floor(np.log1p(sup) / max(tol_s, 1e-9)).astype("int64")
    cubo_p = np.floor(np.log1p(d["precio_asking"].fillna(0)) / max(tol_p, 1e-9)).astype("int64")

    d["_llave"] = (
        pd.Series(gh, index=d.index).astype(str) + "|"
        + d["tipo"].astype(str) + "|" + d["operacion"].astype(str) + "|"
        + cubo_s.astype(str) + "|" + cubo_p.astype(str)
    )
    antes = len(d)
    d = (
        d.sort_values("fecha_captura")
        .drop_duplicates("_llave", keep="last")
        .drop(columns="_llave")
        .reset_index(drop=True)
    )
    return d, antes - len(d)
