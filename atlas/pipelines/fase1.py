"""
FASE 1 — Variables geoespaciales.

Construye la malla H3 de la CDMX, le cuelga las variables de amenidad y
accesibilidad, elige la matriz de pesos W con un criterio explícito, y corre
el diagnóstico espacial (I de Moran global + LISA) que el documento exige
ANTES de modelar.

    python -m pipelines.fase1
    python -m pipelines.fase1 --permutaciones 999
    python -m pipelines.fase1 --informe

POR QUÉ SE CORRE SOBRE LA MALLA Y NO SOBRE LOS INMUEBLES
Porque todavía no hay inmuebles (ver Fase 0). Pero las variables no dependen
de tener precios: la distancia de un punto al metro es la misma haya o no un
anuncio ahí. Al construirlas sobre la malla se consigue el sustrato de la
"tela" y, cuando lleguen los listados, EL MISMO código se aplica sobre ellos
—las funciones toman cualquier GeoDataFrame de puntos—.

El diagnóstico de Moran se corre sobre la densidad de empleo DENUE, que es la
variable con contenido económico que sí existe hoy. No es el precio, y se dice
así: mide si la estructura espacial de la actividad económica es real, que es
el supuesto sobre el que descansa todo el aparato espacial.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atlas import lago                                    # noqa: E402
from atlas.config import cargar, fijar_semilla            # noqa: E402
from atlas.features import amenidades, malla, pesos       # noqa: E402


def _linea(t: str = "") -> None:
    print(t, flush=True)


def construir(cfg, permutaciones: int = 199) -> dict:
    fijar_semilla(cfg)
    res = {}

    _linea("· Malla H3 de la CDMX…")
    g = malla.malla(cfg=cfg)
    if g.empty:
        raise RuntimeError(
            "La malla salió vacía. ¿Corriste la Fase 0? Hace falta la capa `cp`."
        )
    g["bloque"] = malla.bloques(g, cfg)
    pts = malla.centros(g, cfg)
    _linea(f"    {len(g):,} celdas · resolución {cfg['modelado']['h3']['resolucion_malla']}"
           f" · {g['bloque'].nunique():,} bloques de validación")
    res["celdas"] = len(g)

    _linea("· Variables desde DENUE…")
    denue = lago.leer("denue", cfg)
    fd = amenidades.desde_denue(pts, denue, cfg)
    _linea(f"    {fd.shape[1]} variables desde {len(denue):,} establecimientos")

    _linea("· Variables desde OSM…")
    osm = lago.leer("osm_poi", cfg) if lago.existe("osm_poi", cfg) else None
    fo = amenidades.desde_osm(pts, osm, cfg)
    if osm is None:
        _linea(f"    {fo.shape[1]} variables con AUSENCIA DECLARADA (OSM sin descargar)")
    else:
        _linea(f"    {fo.shape[1]} variables desde {len(osm):,} puntos de interés")

    feats = pd.concat([g[["h3", "lat", "lng", "bloque"]], fd, fo], axis=1)

    # ---- diagnóstico espacial sobre la densidad de empleo DENUE ----
    _linea("· Eligiendo W y midiendo la I de Moran…")
    y = feats["acc_denue"].to_numpy()
    if not np.isfinite(y).any() or np.nanstd(y) == 0:
        raise RuntimeError("La densidad DENUE no varía; no hay nada que diagnosticar.")
    w, eleccion = pesos.elegir(pts, y, cfg, permutaciones=permutaciones)
    _linea(f"    {eleccion.texto()}")
    res["w"] = eleccion

    # ---- rezagos espaciales: W·X sobre las variables continuas ----
    _linea("· Rezagos espaciales W·X…")
    continuas = [
        c for c in feats.columns
        if c.startswith(("acc_", "n_")) and feats[c].dtype.kind in "if"
    ]
    rez = pd.DataFrame(
        {f"W_{c}": pesos.rezago(w, feats[c]) for c in continuas}, index=feats.index
    )
    _linea(f"    {rez.shape[1]} rezagos")

    _linea("· LISA (clústeres locales)…")
    cl = pesos.lisa(w, y, permutaciones=permutaciones)
    cl.index = feats.index
    conteo = cl.loc[cl["lisa_sig"], "lisa_cuadrante"].value_counts().to_dict()
    _linea("    " + " · ".join(f"{k}: {v:,}" for k, v in sorted(conteo.items())) or "    sin clústeres")
    res["lisa"] = conteo

    matriz = pd.concat([feats, rez, cl], axis=1)
    lago.guardar(
        "features_malla", matriz,
        fuente="Atlas Fase 1 (malla H3 + DENUE + OSM)",
        nota=(f"W={eleccion.tipo}({eleccion.parametro}); I de Moran="
              f"{eleccion.moran_I:.4f} p={eleccion.moran_p:.4g} sobre acc_denue"),
        cfg=cfg,
    )
    lago.guardar(
        "w_candidatos", eleccion.candidatos,
        fuente="Atlas Fase 1 (selección de W)",
        nota="I de Moran de cada definición de vecindad probada.", cfg=cfg,
    )
    res["variables"] = matriz.shape[1]
    res["matriz"] = matriz
    return res


def informe(cfg, res: dict | None = None) -> None:
    _linea()
    _linea("=" * 66)
    _linea("INFORME DE LA FASE 1")
    _linea("=" * 66)

    if not lago.existe("features_malla", cfg):
        _linea("Sin matriz de variables. Corre: python -m pipelines.fase1")
        return
    m = lago.leer("features_malla", cfg)
    man = lago.manifiesto(cfg)["features_malla"]

    _linea(f"\nMATRIZ  {len(m):,} celdas × {m.shape[1]} columnas")
    _linea(f"  {man['nota']}")

    if res and "w" in res:
        _linea("\nSELECCIÓN DE W  (criterio: máxima I de Moran)")
        t = res["w"].candidatos.dropna(subset=["I"]).sort_values("I", ascending=False)
        for _, r in t.iterrows():
            marca = "←" if (r["tipo"] == res["w"].tipo and r["parametro"] == res["w"].parametro) else " "
            _linea(f"  {marca} {r['tipo']:<6} {str(r['parametro']):>6}   I={r['I']:.4f}  p={r['p']:.4g}")

    _linea("\nDIAGNÓSTICO ESPACIAL")
    I = float(man["nota"].split("Moran=")[1].split()[0]) if "Moran=" in man["nota"] else float("nan")
    if np.isfinite(I):
        if I > 0.3:
            _linea(f"  I = {I:.4f} — estructura espacial FUERTE.")
        elif I > 0.1:
            _linea(f"  I = {I:.4f} — estructura espacial clara.")
        else:
            _linea(f"  I = {I:.4f} — estructura espacial débil.")
        _linea("  Un I positivo y significativo confirma que un modelo sin")
        _linea("  componente espacial estaría mal especificado. Justifica el SDM")
        _linea("  y los rezagos W·X de la Fase 2.")

    if "lisa_cuadrante" in m.columns:
        sig = m.loc[m["lisa_sig"]]
        _linea(f"\nCLÚSTERES LISA  ({len(sig):,} celdas significativas al 5%)")
        for q, n in sig["lisa_cuadrante"].value_counts().items():
            etiqueta = {
                "AA": "alto-alto  · núcleo consolidado",
                "BB": "bajo-bajo  · zona homogénea",
                "BA": "bajo-alto  · FRENTE DE ONDA, donde hay recorrido",
                "AB": "alto-bajo  · caro aislado",
            }.get(q, q)
            _linea(f"  {q}  {n:>6,}   {etiqueta}")

    faltan = [c for c in m.columns if c.startswith("dist_") and m[c].isna().all()]
    if faltan:
        _linea(f"\nVARIABLES SIN FUENTE  ({len(faltan)})")
        _linea("  " + ", ".join(c.replace("dist_", "").replace("_m", "") for c in faltan[:10]))
        _linea("  Están en NaN a propósito: no hay dato, no valen cero.")
        _linea("  Solución: python -m pipelines.fase0 --osm   (en tu máquina)")

    _linea("\nLO QUE ESTO NO ES")
    _linea("  El diagnóstico se corre sobre densidad de empleo DENUE, no sobre")
    _linea("  precios. Mide que la estructura espacial de la actividad económica")
    _linea("  es real, que es el supuesto del que cuelga todo el aparato")
    _linea("  espacial. El Moran del PRECIO se mide en la Fase 2.")
    # No afirmar que faltan listados sin haber mirado: en cuanto la Fase 0
    # ingiere el scraper, el lago sí los tiene y la frase quedaría mintiendo.
    n_props = lago.filas("properties", cfg) if lago.existe("properties", cfg) else 0
    if n_props:
        _linea(f"  Ya hay {n_props:,} listados en el lago: la Fase 2 puede arrancar.")
    else:
        _linea("  Todavía no hay listados; sin ellos la Fase 2 no puede empezar.")
        _linea("  Solución: node tools/c21-scraper.mjs todo  →  python -m pipelines.fase0")
    _linea("=" * 66)


def main() -> int:
    ap = argparse.ArgumentParser(description="BrickBit Atlas · Fase 1")
    ap.add_argument("--permutaciones", type=int, default=199,
                    help="Permutaciones para Moran/LISA (más = p-valor más fino)")
    ap.add_argument("--informe", action="store_true")
    args = ap.parse_args()

    cfg = cargar()
    res = None
    if not args.informe:
        _linea(f"BrickBit Atlas · Fase 1 · semilla {cfg.semilla}")
        _linea()
        res = construir(cfg, args.permutaciones)
    informe(cfg, res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
