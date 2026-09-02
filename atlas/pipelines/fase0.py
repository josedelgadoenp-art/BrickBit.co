"""
FASE 0 — Andamiaje + datos.

Construye el data lake del Atlas a partir de lo que ya existe en el repo, y
opcionalmente descarga OSM. Es idempotente: se puede correr las veces que sea.

    python -m atlas.pipelines.fase0            # sólo lo local (sin red)
    python -m atlas.pipelines.fase0 --osm      # además baja OSM (en tu máquina)
    python -m atlas.pipelines.fase0 --informe  # sólo imprime el estado del lago

Al terminar imprime el informe de la fase: qué capas hay, con cuántas filas, y
—sobre todo— qué falta. El documento pide declarar los supuestos y no inventar
datos; el informe es donde eso se cumple.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permite `python -m atlas.pipelines.fase0` y `python atlas/pipelines/fase0.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atlas.config import cargar, fijar_semilla          # noqa: E402
from atlas.ingesta import base_geo, denue, listados     # noqa: E402
from atlas import lago                                   # noqa: E402


def _linea(t: str = "") -> None:
    print(t, flush=True)


def ingerir_local(cfg) -> dict[str, int]:
    """Capas que no necesitan red. Devuelve {capa: filas}."""
    hecho: dict[str, int] = {}

    _linea("· Códigos postales de la CDMX…")
    cp = base_geo.cargar_cp(cfg)
    lago.guardar("cp", cp, fuente="data/cdmx_codigos_postales.json (repo)",
                 nota="Polígonos de CP; unidad territorial más fina sin AGEB.", cfg=cfg)
    hecho["cp"] = len(cp)
    _linea(f"    {len(cp):,} polígonos")

    _linea("· Red vial…")
    calles = base_geo.cargar_calles(cfg)
    lago.guardar("calles", calles, fuente="data/calles_*.json (repo)",
                 nota="Ejes viales por alcaldía; base de las isócronas de la Fase 1.", cfg=cfg)
    hecho["calles"] = len(calles)
    _linea(f"    {len(calles):,} ejes")

    _linea("· Establecimientos DENUE…")
    try:
        est = denue.cargar_denue(cfg)
        lago.guardar("denue", est, fuente="INEGI DENUE vía scripts/ingerir_denue.py",
                     nota="Densidad comercial y de servicios georreferenciada.", cfg=cfg)
        hecho["denue"] = len(est)
        _linea(f"    {len(est):,} establecimientos")
    except FileNotFoundError as e:
        _linea(f"    ⚠ {e}")

    _linea("· Listados (materia prima del AVM)…")
    props, rep = listados.cargar_c21(cfg)
    lago.guardar("properties", props, fuente="Century 21 (convenio) vía tools/c21-scraper.mjs",
                 nota="Precios de OFERTA (asking). No son precios de cierre.", cfg=cfg)
    hecho["properties"] = len(props)
    _linea(rep.texto())
    return hecho


def ingerir_osm(cfg) -> int:
    _linea("· OpenStreetMap (Overpass)…")
    from atlas.ingesta import osm

    g = osm.descargar(cfg=cfg)
    lago.guardar("osm_poi", g, fuente="OpenStreetMap vía Overpass API",
                 nota="Parques, plazas, transporte, salud, educación, mercados.", cfg=cfg)
    for cat, n in g["categoria"].value_counts().items():
        _linea(f"    {cat:12s} {n:>7,}")
    return len(g)


def informe(cfg) -> None:
    _linea()
    _linea("=" * 66)
    _linea("INFORME DE LA FASE 0")
    _linea("=" * 66)

    res = lago.resumen(cfg)
    if res.empty:
        _linea("El lago está vacío.")
        return
    _linea("\nCAPAS EN EL LAGO")
    for _, r in res.iterrows():
        _linea(f"  {r['capa']:<12} {r['filas']:>9,}  {r['fuente']}")

    _linea("\nCOBERTURA POR ALCALDÍA")
    cob = base_geo.cobertura(cfg)
    for _, r in cob.iterrows():
        marca = lambda b: "sí " if b else "NO "   # noqa: E731
        _linea(f"  {r['alcaldia']:<24} DENUE {marca(r['denue'])}  calles {marca(r['calles'])}")
    sin_denue = cob.loc[~cob["denue"], "alcaldia"].tolist()

    _linea("\nLO QUE FALTA — y por qué importa")
    n_props = int(res.loc[res["capa"] == "properties", "filas"].sum()) if "properties" in set(res["capa"]) else 0
    if n_props == 0:
        _linea("  ✗ LISTADOS: 0 registros. Es el bloqueo principal.")
        _linea("    Sin precios individuales no hay AVM, ni SHAP, ni intervalo")
        _linea("    conforme, ni campo de crecimiento anclado a precios. Todo el")
        _linea("    resto del sistema es andamio hasta que existan.")
        _linea("    Solución: node tools/c21-scraper.mjs todo   (deja c21_out/listados.json)")
    else:
        _linea(f"  ✓ LISTADOS: {n_props:,} inmuebles.")
    if sin_denue:
        _linea(f"  ⚠ DENUE incompleto en {len(sin_denue)} alcaldías: {', '.join(sin_denue[:5])}"
               + ("…" if len(sin_denue) > 5 else ""))
        _linea("    Solución: python scripts/ingerir_denue.py  (en tu máquina)")
    if not lago.existe("osm_poi", cfg):
        _linea("  ⚠ OSM sin descargar: faltan parques, plazas y transporte,")
        _linea("    que son los motores explícitos del valor (§5 del documento).")
        _linea("    Solución: python -m atlas.pipelines.fase0 --osm  (en tu máquina)")

    _linea("\nSUPUESTOS DECLARADOS")
    _linea("  · Precio de OFERTA, no de cierre. No se aplica ningún descuento")
    _linea("    asking→cierre porque no hay transacciones con que calibrarlo.")
    _linea("  · CRS métrico EPSG:6372 para toda distancia y área.")
    _linea(f"  · Semilla fija {cfg.semilla}: dos corridas dan lo mismo.")
    _linea("=" * 66)


def main() -> int:
    ap = argparse.ArgumentParser(description="BrickBit Atlas · Fase 0")
    ap.add_argument("--osm", action="store_true", help="Descargar OSM (requiere red no bloqueada)")
    ap.add_argument("--informe", action="store_true", help="Sólo imprimir el estado del lago")
    args = ap.parse_args()

    cfg = cargar()
    fijar_semilla(cfg)

    if not args.informe:
        _linea(f"BrickBit Atlas · Fase 0 · semilla {cfg.semilla}")
        _linea(f"lago: {cfg.lago}")
        _linea()
        ingerir_local(cfg)
        if args.osm:
            try:
                ingerir_osm(cfg)
            except RuntimeError as e:
                _linea(f"    ⚠ {e}")

    informe(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
