"""
FASE 3 — Tiempo y campo espacial.

    python -m pipelines.fase3
    python -m pipelines.fase3 --zona "Guadalajara"
    python -m pipelines.fase3 --informe

Cuatro piezas, y conviene saber de entrada cuál se apoya en qué:

  1. **Índice temporal** (SHF, 32 zonas × 22 años). Dato real de transacciones,
     resolución estatal, en términos nominales.
  2. **Difusión**: ¿el crecimiento se contagia entre zonas vecinas? Se contesta
     con validación hacia adelante, no con una correlación.
  3. **Superficie de precio** sobre la CDMX, por proceso gaussiano, con su
     incertidumbre y su gradiente ∇p en % por kilómetro.
  4. **Multiplicador espacial** (I − ρW)⁻¹ con el ρ que midió la Fase 2.

LO QUE ESTA FASE NO PUEDE HACER, Y POR QUÉ.

El documento pide un campo de CRECIMIENTO: cuánto va a subir cada celda. Eso
exige observar la misma celda en dos momentos, y hoy hay **una sola captura** de
listados. El índice SHF aporta la dimensión temporal pero a resolución estatal:
sirve para decir cuánto se movió la CDMX entera, no qué colonia se movió más.

Así que aquí se construyen las dos mitades que sí son medibles —el crecimiento
de la ciudad en el tiempo, y la estructura del precio en el espacio— y se declara
la que falta en vez de fabricarla multiplicando una por otra, que daría un mapa
convincente y sin ningún respaldo.

La condición para desbloquearla es concreta: **dos corridas del scraper
separadas en el tiempo**. Con capturas mensuales, en un año hay panel suficiente
para estimar crecimiento por celda y validarlo hacia adelante, igual que aquí se
valida el contagio entre zonas.
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atlas import lago                                      # noqa: E402
from atlas.campo import multiplicador, superficie           # noqa: E402
from atlas.config import cargar, fijar_semilla              # noqa: E402
from atlas.features import malla, pesos                     # noqa: E402
from atlas.geo import _xy, puntos                           # noqa: E402
from atlas.temporal import difusion, indice                 # noqa: E402


def _linea(t: str = "") -> None:
    print(t, flush=True)


def construir(cfg, zona: str = "Ciudad de México") -> dict:
    fijar_semilla(cfg)
    res: dict = {"zona": zona}

    # ------------------------------------------------------- 1. índice temporal
    _linea("· Índice temporal SHF…")
    panel = indice.cargar_panel(cfg)
    _linea(panel.texto())
    res["panel"] = panel
    res["resumen_zona"] = indice.resumen_zona(panel, zona)
    a0, a1 = panel.anios[0], panel.anios[-1]
    res["acumulado"] = indice.acumulado(panel, zona, a0, a1)
    _linea(f"    {zona}: ×{res['acumulado']:.2f} entre {a0} y {a1}")

    # ----------------------------------------------------------- 2. difusión
    _linea("· ¿El crecimiento se contagia entre zonas vecinas?…")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        w_zonas = difusion.pesos_zonas(panel.coords, k=4, cfg=cfg)
        res["agrupamiento"] = difusion.agrupamiento(panel, w_zonas)
        _linea(res["agrupamiento"].texto())
        res["contagio"] = difusion.contagio(panel, w_zonas)
        _linea(res["contagio"].texto())
        try:
            res["cointegracion"] = difusion.cointegracion(panel, zona)
        except Exception as e:
            res["cointegracion"] = None
            _linea(f"    ⚠ cointegración no evaluable: {type(e).__name__}: {e}")

    # ------------------------------------------------- 3. superficie de precio
    _linea("· Superficie de precio sobre la CDMX (proceso gaussiano)…")
    if not lago.existe("properties", cfg):
        res["superficie"] = None
        _linea("    ⚠ sin listados no hay superficie. Corre la Fase 0.")
    else:
        props = lago.leer("properties", cfg)
        props = props.loc[props["operacion"].eq("venta")].reset_index(drop=True)
        y = np.log(props["precio_m2_asking"].astype(float).to_numpy())
        xy = _xy(puntos(props, cfg=cfg), cfg)
        ok = np.isfinite(y) & np.isfinite(xy).all(axis=1)
        _linea(f"    ajustando con {int(ok.sum()):,} inmuebles de venta…")

        gp, centro, media = superficie.ajustar(xy[ok], y[ok], cfg)
        g = malla.malla(cfg=cfg)
        centros = malla.centros(g, cfg)
        xy_malla = _xy(centros, cfg)
        s = superficie.evaluar(gp, centro, media, xy_malla)
        _linea(s.texto())
        res["superficie"] = s
        res["malla"] = g

        _linea("· Frontera de precio (barato rodeado de caro)…")
        w_malla = pesos.knn(centros, 8, cfg)
        fr = superficie.frontera(s.valores, w_malla)
        n_fr = int(fr["es_frontera"].sum())
        _linea(f"    {n_fr:,} celdas en el frente ({n_fr / len(fr) * 100:.1f}% de la malla)")
        res["frontera"] = fr

        # --------------------------------------------- 4. multiplicador espacial
        _linea("· Multiplicador espacial (I − ρW)⁻¹…")
        rho = _rho_de_fase2(cfg)
        if rho is None:
            res["multiplicador"] = None
            _linea("    ⚠ falta el ρ de la Fase 2. Corre: python -m pipelines.fase2")
        else:
            m = multiplicador.calcular(w_malla, rho)
            _linea(m.texto())
            res["multiplicador"] = m

        salida = pd.DataFrame({
            "h3": g["h3"].to_numpy(),
            "lat": g["lat"].to_numpy(),
            "lng": g["lng"].to_numpy(),
            "ln_precio_m2": s.valores,
            "sigma": s.sigma,
            "pendiente_pct_km": s.pendiente_pct_km,
            "rumbo_grados": s.rumbo,
            "frontera": fr["es_frontera"].to_numpy(),
            "brecha_vecinos": fr["brecha"].to_numpy(),
        })
        if res.get("multiplicador") is not None:
            salida["efecto_propio"] = res["multiplicador"].propio
            salida["influencia"] = res["multiplicador"].influencia
        lago.guardar("campo_cdmx", salida,
                     fuente="Fase 3 · superficie GP, gradiente y multiplicador espacial",
                     nota=f"ρ={rho}; precio de OFERTA, no de cierre", cfg=cfg)
        res["salida"] = salida

    return res


def _rho_de_fase2(cfg) -> float | None:
    """
    El ρ estimado por el SDM de la Fase 2.

    Se vuelve a estimar aquí en vez de guardarse en un archivo aparte: un ρ
    escrito a mano se desincroniza del modelo en cuanto cambian los datos, y un
    multiplicador calculado con un ρ viejo es peor que no tenerlo.
    """
    from atlas.modelos import datos as mdatos
    from atlas.modelos import hedonico

    try:
        d = mdatos.ensamblar(cfg, operacion="venta")
        p = mdatos.particion(d.bloque, cfg)
        import geopandas as gpd
        from shapely.geometry import Point

        xy = d.coords[p["entrena"]]
        gdf = gpd.GeoDataFrame(
            {"i": np.arange(len(xy))},
            geometry=[Point(x, y) for x, y in xy], crs=cfg.crs_metrico,
        ).to_crs(cfg.crs_geografico)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            w, _ = hedonico.moran_del_precio(gdf, d.y[p["entrena"]], cfg,
                                             permutaciones=99, tipos=("knn",))
            r = hedonico.sdm(d.X[p["entrena"]], d.y[p["entrena"]], w)
        return None if r.degenerado else float(r.rho)
    except Exception:
        return None


# -------------------------------------------------------------------- informe
def informe(cfg, res: dict | None) -> None:
    _linea()
    _linea("=" * 66)
    _linea("INFORME DE LA FASE 3 — TIEMPO Y CAMPO ESPACIAL")
    _linea("=" * 66)
    if res is None:
        if lago.existe("campo_cdmx", cfg):
            s = lago.leer("campo_cdmx", cfg)
            _linea(f"\nÚltimo campo guardado: {len(s):,} celdas")
            _linea(f"  pendiente mediana {s['pendiente_pct_km'].median():.1f}%/km")
            _linea(f"  celdas en el frente: {int(s['frontera'].sum()):,}")
        else:
            _linea("Corre `python -m pipelines.fase3` para construir el campo.")
        _linea("=" * 66)
        return

    panel = res["panel"]
    z = res["zona"]
    _linea(f"\nÍNDICE TEMPORAL — {panel.fuente}")
    _linea(panel.texto())
    r = res["resumen_zona"].dropna()
    _linea(f"\n  {z}: ×{res['acumulado']:.2f} en {panel.anios[-1] - panel.anios[0]} años"
           f"  ({(res['acumulado'] ** (1 / (panel.anios[-1] - panel.anios[0])) - 1) * 100:.2f}% anual compuesto)")
    ult = r.tail(5)
    for anio, fila in ult.iterrows():
        _linea(f"    {int(anio)}   índice {fila['indice']:6.1f}   {fila['crec_%']:+5.2f}%")
    if not panel.real:
        _linea("  ⚠ NOMINAL. No está deflactado: parte de ese crecimiento es inflación,")
        _linea("    no plusvalía. Para la cifra real hace falta la serie del INPC.")

    _linea("\n¿EL CRECIMIENTO SE CONTAGIA ENTRE ZONAS?")
    _linea(res["agrupamiento"].texto())
    _linea("  (agrupamiento ≠ contagio: dos vecinos pueden crecer igual por un")
    _linea("   choque común, sin que uno empuje al otro. La prueba es predecir.)")
    _linea()
    _linea(res["contagio"].texto())
    if res.get("cointegracion") is not None:
        _linea(f"\nCOINTEGRACIÓN {z} ↔ agregado nacional")
        _linea(res["cointegracion"].texto())

    if res.get("superficie") is not None:
        _linea("\nSUPERFICIE DE PRECIO DE LA CDMX")
        _linea(res["superficie"].texto())
        fr = res["frontera"]
        _linea(f"\n  Frente de precio: {int(fr['es_frontera'].sum()):,} celdas baratas")
        _linea("  rodeadas de caras. Es un diferencial PRESENTE, no una plusvalía")
        _linea("  futura: que el mercado lo cierre depende de por qué está abierto,")
        _linea("  y esa razón puede ser una barrera, un uso de suelo o una")
        _linea("  diferencia real de calidad que estas variables no ven.")

    if res.get("multiplicador") is not None:
        _linea("\nMULTIPLICADOR ESPACIAL")
        m = res["multiplicador"]
        _linea(m.texto())
        _linea("  Las celdas de más influencia son donde una obra pública o un")
        _linea("  desarrollo mueven más ciudad. No es causal: describe cómo se")
        _linea("  propagaría un cambio SI el modelo de rezago fuera cierto.")
        disp = float(np.max(m.influencia) / np.median(m.influencia))
        if disp < 1.5:
            _linea(f"  ⚠ La influencia varía poco ({disp:.2f}× entre la máxima y la")
            _linea("    mediana) y eso es culpa del W, no del mercado: un grafo de k")
            _linea("    vecinos es casi regular por construcción —todos tienen k—, así")
            _linea("    que apenas hay diferencia de posición que capturar. Un W de")
            _linea("    banda de distancia sí distinguiría el centro denso de la")
            _linea("    periferia, pero ρ se estimó con KNN y mezclarlos daría un")
            _linea("    multiplicador que no corresponde al modelo que lo produjo.")

    _linea("\nLO QUE FALTA PARA EL CAMPO DE CRECIMIENTO")
    _linea("  Un crecimiento POR CELDA exige ver la misma celda en dos momentos,")
    _linea("  y hoy hay una sola captura de listados. El SHF aporta el tiempo pero")
    _linea("  a resolución estatal: dice cuánto se movió la CDMX, no qué colonia.")
    _linea("  No se fabrica multiplicando una cosa por la otra —daría un mapa")
    _linea("  convincente y sin respaldo—.")
    _linea("  Solución: correr el scraper cada mes. En un año hay panel para")
    _linea("  estimar crecimiento por celda y validarlo hacia adelante, igual que")
    _linea("  aquí se valida el contagio entre zonas.")
    _linea("=" * 66)


def main() -> int:
    ap = argparse.ArgumentParser(description="BrickBit Atlas · Fase 3")
    ap.add_argument("--zona", default="Ciudad de México")
    ap.add_argument("--informe", action="store_true")
    args = ap.parse_args()

    cfg = cargar()
    res = None
    if not args.informe:
        _linea(f"BrickBit Atlas · Fase 3 · semilla {cfg.semilla}")
        _linea()
        res = construir(cfg, args.zona)
    informe(cfg, res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
