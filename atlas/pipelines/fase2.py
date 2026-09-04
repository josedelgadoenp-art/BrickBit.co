"""
FASE 2 — AVM e incertidumbre calibrada.

    python -m pipelines.fase2
    python -m pipelines.fase2 --operacion renta
    python -m pipelines.fase2 --alpha 0.10        # intervalos al 90%
    python -m pipelines.fase2 --informe

Encadena lo que las fases anteriores dejaron listo:

  1. Junta los listados con la malla de la Fase 1 y parte los datos POR BLOQUE
     ESPACIAL, no al azar. Sin eso todo lo que sigue mide de más.
  2. Mide la I de Moran del PRECIO —la medición que la Fase 1 no podía hacer— y
     con ella justifica (o no) el modelo espacial.
  3. Ajusta tres modelos: hedónico OLS legible, Durbin espacial y boosting.
  4. Los combina por apilado, con pesos aprendidos fuera de muestra.
  5. Convierte la predicción en un INTERVALO con cobertura garantizada. Se
     calibran DOS formas —CQR y normalizado— con la misma garantía y distinto
     ancho, y se reportan las dos: con muestras chicas el normalizado suele
     ganar, porque no tiene que estimar los cuantiles 2.5% y 97.5% directamente.
  6. Explica el modelo con SHAP.

LO QUE ESTE PIPELINE NO HACE, Y CONVIENE SABERLO DE ENTRADA.
Todo sale de precios de OFERTA. No hay precios de cierre en México a los que un
particular pueda acceder, así que el sistema estima *a qué precio se ofrece* un
inmueble como el que se le describa, no a cuánto se vende. El descuento
oferta→cierre existe, es positivo, y `config.yaml` lo deja en `null` a propósito.
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atlas import lago                                          # noqa: E402
from atlas.config import cargar, fijar_semilla                  # noqa: E402
from atlas.geo import puntos                                    # noqa: E402
from atlas.modelos import (apilado, arboles, conforme, datos,   # noqa: E402
                           evaluacion, hedonico, importancia)


def _linea(t: str = "") -> None:
    print(t, flush=True)


def construir(cfg, operacion: str = "venta", alpha: float | None = None) -> dict:
    fijar_semilla(cfg)
    alpha = float(cfg["modelado"]["alpha"] if alpha is None else alpha)
    semilla = int(cfg.semilla)
    res: dict = {"operacion": operacion, "alpha": alpha}

    # ---------------------------------------------------------------- datos
    _linea("· Ensamblando listados + malla…")
    d = datos.ensamblar(cfg, operacion=operacion)
    _linea(f"    {len(d):,} inmuebles en {operacion} · {d.X.shape[1]} variables "
           f"· {d.bloque.nunique():,} bloques espaciales")
    if d.n_sin_celda:
        _linea(f"    {d.n_sin_celda:,} cayeron fuera de la malla y tomaron la celda más cercana")
    res["datos"] = d

    _linea("· Partiendo por bloque espacial (sin fuga entre vecinos)…")
    n_bloques = int(d.bloque.nunique())
    if n_bloques < 30:
        _linea(f"    ⚠ sólo {n_bloques} bloques: la partición es gruesa y las métricas")
        _linea("      traen bastante ruido de muestreo. No invalida el resultado,")
        _linea("      pero sí desaconseja leer diferencias pequeñas entre modelos.")
    p = datos.particion(d.bloque, cfg)
    for k in ("entrena", "calibra", "prueba"):
        _linea(f"    {k:<9} {int(p[k].sum()):>6,} inmuebles · {d.bloque[p[k]].nunique():>4,} bloques")
    res["particion"] = {k: int(v.sum()) for k, v in p.items()}

    Xtr, ytr = d.X[p["entrena"]], d.y[p["entrena"]]
    Xca, yca = d.X[p["calibra"]], d.y[p["calibra"]]
    Xte, yte = d.X[p["prueba"]], d.y[p["prueba"]]

    # ------------------------------------------------- Moran del PRECIO
    _linea("· I de Moran del precio…")
    props_tr = _gdf_de(d, p["entrena"], cfg)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, eleccion = hedonico.moran_del_precio(props_tr, ytr, cfg, permutaciones=999)
            # Para el SDM se pide un W de sólo KNN: una banda de distancia deja
            # islas y sobre ellas la verosimilitud del modelo de rezago no
            # converge a nada útil (se comprobó: rho=-0.93, pseudo R2=0.002).
            w_tr, _ = hedonico.moran_del_precio(props_tr, ytr, cfg, permutaciones=99,
                                                tipos=("knn",))
        _linea(f"    {eleccion.texto()}")
        res["moran_precio"] = eleccion
    except Exception as e:
        w_tr, res["moran_precio"] = None, None
        _linea(f"    ⚠ no se pudo medir: {type(e).__name__}: {e}")

    # ------------------------------------------------------------ hedónico
    _linea("· Hedónico semi-log (OLS, errores robustos)…")
    ols = hedonico.ols(Xtr, ytr)
    _linea(f"    R²={ols.r2:.4f} (ajustado {ols.r2_ajustado:.4f}) sobre {ols.n:,} inmuebles")
    res["ols"] = ols

    _linea("· Durbin espacial (SDM)…")
    if w_tr is None:
        res["sdm"] = None
        _linea("    ⚠ sin W no hay SDM.")
    else:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res["sdm"] = hedonico.sdm(Xtr, ytr, w_tr)
            _linea(res["sdm"].texto())
        except Exception as e:
            res["sdm"] = None
            _linea(f"    ⚠ no convergió: {type(e).__name__}: {e}")

    # ------------------------------------------------------------ boosting
    _linea("· Boosting: media y cuantiles…")
    m_media = arboles.media(Xtr, ytr, semilla)
    m_lo, m_hi = arboles.banda(Xtr, ytr, alpha, semilla)
    _linea(f"    3 modelos sobre {Xtr.shape[1]} variables ({arboles.BASE['max_iter']} iteraciones)")

    # ------------------------------------------------ apilado fuera de muestra
    _linea("· Apilado (pesos aprendidos fuera de muestra por bloque)…")
    fuera_boost = arboles.fuera_de_muestra_por_bloque(Xtr, ytr, d.bloque[p["entrena"]], semilla)
    fuera_ols = _lineal_fuera_de_muestra(Xtr, ytr, d.bloque[p["entrena"]])
    ap = apilado.ajustar({"boosting": fuera_boost, "hedonico": fuera_ols}, ytr.to_numpy())
    _linea(ap.texto())
    res["apilado"] = ap

    # Modelo de dispersión: cuánto suele fallar la predicción en cada punto.
    # Se ajusta sobre residuales FUERA DE MUESTRA; con residuales de
    # entrenamiento aprendería que el sistema es más preciso de lo que es.
    _linea("· Modelo de dispersión (para el intervalo adaptativo)…")
    fuera_apilado = ap.predecir({"boosting": fuera_boost, "hedonico": fuera_ols})
    m_sigma = arboles.dispersion(Xtr, ytr, fuera_apilado, semilla)
    # γ se elige sobre las predicciones FUERA DE MUESTRA del entrenamiento, que
    # el conjunto de calibración no ha tocado. Todos los γ dan intervalos
    # válidos —la garantía no depende de σ̂—, así que elegir por ancho no
    # compromete la cobertura, sólo mejora la eficiencia.
    sigma_fuera = arboles.dispersion_fuera_de_muestra(
        Xtr, ytr, fuera_apilado, d.bloque[p["entrena"]], semilla)
    gamma = conforme.elegir_estabilizador(
        ytr.to_numpy(), fuera_apilado, sigma_fuera, m_sigma.escala, alpha)
    m_sigma.gamma = gamma
    _linea(f"    estabilizador γ = {gamma:g} × la mediana de |residual|")

    def predecir(X: pd.DataFrame) -> np.ndarray:
        return ap.predecir({
            "boosting": m_media.predict(X),
            "hedonico": _lineal_predict(Xtr, ytr, d.bloque[p["entrena"]], X),
        })

    # ------------------------------------------------------- conformalización
    _linea("· Calibrando el intervalo (CQR + Mondrian)…")
    # El segmento se arma con el precio PREDICHO, nunca con el observado: en el
    # momento de valuar un inmueble el precio real es justamente lo que no se
    # sabe, y un grupo que dependiera de él no se podría asignar en producción.
    pred_ca = predecir(Xca)
    nombre_seg, seg_ca, cortes = conforme.elegir_segmentacion(
        _tipo_de(d, p["calibra"]), np.exp(pred_ca), alpha
    )
    _linea(f"    segmentación: {nombre_seg}  ({seg_ca.nunique()} grupos)")
    minimo = conforme.minimo_por_grupo(alpha)

    # Dos formas de intervalo, las dos con la MISMA garantía de cobertura.
    # Difieren sólo en el score de disconformidad, y por tanto en el ancho.
    c_cqr = conforme.calibrar(yca.to_numpy(), m_lo.predict(Xca), m_hi.predict(Xca),
                              alpha, grupos_cal=seg_ca, minimo_por_grupo=minimo)
    sigma_ca = m_sigma.predict(Xca)
    c_norm = conforme.calibrar_normalizado(yca.to_numpy(), pred_ca, sigma_ca,
                                           alpha, grupos_cal=seg_ca, minimo_por_grupo=minimo)
    _linea("    [normalizado]")
    _linea(c_norm.texto())
    res["conformal"] = c_norm
    res["conformal_cqr"] = c_cqr
    res["segmentacion"] = nombre_seg

    # -------------------------------------------------------------- evaluación
    _linea("· Evaluando en el conjunto de prueba (bloques nunca vistos)…")
    pred_te = predecir(Xte)
    res["punto"] = {
        "apilado": evaluacion.punto(yte.to_numpy(), pred_te),
        "boosting": evaluacion.punto(yte.to_numpy(), m_media.predict(Xte)),
        "hedonico": evaluacion.punto(yte.to_numpy(), _lineal_predict(Xtr, ytr, d.bloque[p["entrena"]], Xte)),
    }
    seg_te = conforme.segmentar(nombre_seg, _tipo_de(d, p["prueba"]), np.exp(pred_te), cortes)
    sigma_te = m_sigma.predict(Xte)

    lo, hi = conforme.aplicar_normalizado(pred_te, sigma_te, c_norm, seg_te)
    res["intervalo"] = evaluacion.intervalo(yte.to_numpy(), lo, hi, alpha, grupos=seg_te)
    lo_q, hi_q = conforme.aplicar(m_lo.predict(Xte), m_hi.predict(Xte), c_cqr, seg_te)
    res["intervalo_cqr"] = evaluacion.intervalo(yte.to_numpy(), lo_q, hi_q, alpha, grupos=seg_te)
    # Contraste: el mismo intervalo SIN conformalizar, para poder decir cuánto
    # aportó la calibración en vez de afirmarlo.
    res["intervalo_crudo"] = evaluacion.intervalo(
        yte.to_numpy(), m_lo.predict(Xte), m_hi.predict(Xte), alpha
    )

    # Con el score normalizado, cambiar el nivel de confianza NO exige reentrenar
    # nada: es otro cuantil de los mismos scores. Con CQR harían falta dos
    # modelos de cuantil nuevos por cada nivel.
    niveles = []
    for a in (0.50, 0.20, 0.10, 0.05):
        ca = conforme.calibrar_normalizado(
            yca.to_numpy(), pred_ca, sigma_ca, a, grupos_cal=seg_ca,
            minimo_por_grupo=conforme.minimo_por_grupo(a))
        l, h = conforme.aplicar_normalizado(pred_te, sigma_te, ca, seg_te)
        niveles.append((a, evaluacion.intervalo(yte.to_numpy(), l, h, a)))
    res["niveles"] = niveles

    # ----------------------------------------------------------- explicabilidad
    _linea("· Explicabilidad…")
    res["importancia"] = importancia.calcular(m_media, Xtr, ytr, semilla)
    _linea(f"    método: {res['importancia'].metodo}")

    # ------------------------------------------------------------- persistencia
    salida = pd.DataFrame({
        "y_log": yte.to_numpy(),
        "pred_log": pred_te,
        "lo_log": lo,
        "hi_log": hi,
        "segmento": seg_te.to_numpy(),
        "superficie_m2": d.superficie[p["prueba"]].to_numpy(),
        "bloque": d.bloque[p["prueba"]].to_numpy(),
    })
    lago.guardar(f"avm_prueba_{operacion}", salida,
                 fuente="Fase 2 · predicción e intervalo en el conjunto de prueba",
                 nota=f"CQR+Mondrian, alpha={alpha}", cfg=cfg)
    res["salida"] = salida
    return res


# ----------------------------------------------------------------- auxiliares
def _gdf_de(d: datos.Datos, mascara: np.ndarray, cfg):
    """GeoDataFrame de puntos del subconjunto, para construir W."""
    import geopandas as gpd
    from shapely.geometry import Point

    xy = d.coords[mascara]
    return gpd.GeoDataFrame(
        {"i": np.arange(len(xy))},
        geometry=[Point(x, y) for x, y in xy],
        crs=cfg.crs_metrico,
    ).to_crs(cfg.crs_geografico)


def _tipo_de(d: datos.Datos, mascara: np.ndarray) -> pd.Series:
    """
    Reconstruye el tipo desde las indicadoras, para segmentar Mondrian.

    La fila sin ninguna indicadora encendida es la CATEGORÍA DE REFERENCIA, la
    que se dejó fuera del diseño — no "otro". La primera versión la etiquetaba
    como "otro" a secas, y en los datos reales la referencia resultó ser `casa`:
    las 144 casas de la calibración aparecían en el informe como "otro" y el
    segmento `casa` no existía. Un intervalo aplicado al grupo equivocado.
    Se detectó porque en la salida real había depto, otro y terreno, y ninguna
    casa: en un inventario inmobiliario eso es imposible.
    """
    cols = [c for c in d.X.columns if c.startswith("tipo_")]
    sub = d.X.loc[mascara, cols]
    referencia = d.tipo_referencia or "otro"
    if not cols:
        return pd.Series([referencia] * len(sub))
    nombres = np.array([c.replace("tipo_", "") for c in cols])
    t = nombres[sub.to_numpy().argmax(axis=1)].astype(object)
    t[sub.to_numpy().sum(axis=1) == 0] = referencia
    return pd.Series(t.astype(str))


_CACHE_LINEAL: dict = {}


def _lineal_predict(Xtr: pd.DataFrame, ytr: pd.Series, btr: pd.Series,
                    X: pd.DataFrame) -> np.ndarray:
    """
    Predicción del hedónico REGULARIZADO. Se guarda el ajuste en caché porque el
    pipeline lo pide varias veces con el mismo entrenamiento.

    Es cresta y no mínimos cuadrados por una razón medida: con OLS, el hedónico
    pasaba de R²=0.456 dentro de muestra a R²=0.002 fuera. Dos variables casi
    idénticas se repartían coeficientes enormes de signo opuesto que se
    cancelaban en los datos de entrenamiento y no transferían a ningún otro
    barrio. La penalización reparte ese peso en vez de concentrarlo.
    """
    clave = (id(Xtr), Xtr.shape)
    if clave not in _CACHE_LINEAL:
        _CACHE_LINEAL[clave] = hedonico.ridge_por_bloque(Xtr, ytr, btr)
    prep, m, cols = _CACHE_LINEAL[clave]
    return m.predict(prep.transform(X[cols]))


def _lineal_fuera_de_muestra(X: pd.DataFrame, y: pd.Series, bloque: pd.Series) -> np.ndarray:
    """Predicciones del hedónico fuera de muestra, con los mismos bloques."""
    from sklearn.model_selection import GroupKFold

    g = bloque.to_numpy()
    k = int(min(5, pd.Series(g).nunique()))
    fuera = np.full(len(y), np.nan)
    for tr, va in GroupKFold(n_splits=k).split(X, y, groups=g):
        prep, m, cols = hedonico.ridge_por_bloque(
            X.iloc[tr], y.iloc[tr], bloque.iloc[tr])
        fuera[va] = m.predict(prep.transform(X.iloc[va][cols]))
    return fuera


# -------------------------------------------------------------------- informe
def informe(cfg, res: dict | None) -> None:
    _linea()
    _linea("=" * 66)
    _linea("INFORME DE LA FASE 2 — AVM E INCERTIDUMBRE")
    _linea("=" * 66)
    if res is None:
        # Sin correr el modelo se puede releer la última evaluación guardada:
        # sirve para consultar el resultado sin volver a entrenar.
        capa = "avm_prueba_venta"
        if not lago.existe(capa, cfg):
            _linea("Corre `python -m pipelines.fase2` para generar el modelo.")
            _linea("=" * 66)
            return
        s = lago.leer(capa, cfg)
        alpha = float(cfg["modelado"]["alpha"])
        _linea(f"\nÚltima evaluación guardada · {len(s):,} inmuebles de prueba")
        _linea(evaluacion.punto(s["y_log"].to_numpy(), s["pred_log"].to_numpy()).texto())
        _linea("\nINTERVALO CONFORME")
        _linea(evaluacion.intervalo(s["y_log"].to_numpy(), s["lo_log"].to_numpy(),
                                    s["hi_log"].to_numpy(), alpha,
                                    grupos=s["segmento"]).texto())
        _linea("=" * 66)
        return

    d = res["datos"]
    _linea(f"\nDATOS  {len(d):,} inmuebles en {res['operacion']} · {d.X.shape[1]} variables")
    pa = res["particion"]
    _linea(f"  entrena {pa['entrena']:,} · calibra {pa['calibra']:,} · prueba {pa['prueba']:,}"
           "   (partición por bloque H3 res-6)")
    if d.descartadas.get("sin_dato"):
        n = len(d.descartadas["sin_dato"])
        _linea(f"  {n} variables sin ningún dato quedaron fuera (OSM sin descargar)")

    if res.get("moran_precio") is not None:
        e = res["moran_precio"]
        _linea(f"\nESTRUCTURA ESPACIAL DEL PRECIO")
        _linea(f"  I de Moran = {e.moran_I:.4f} (p={e.moran_p:.3g}) con {e.tipo}({e.parametro})")
        if e.moran_I > 0.3:
            _linea("  El precio está espacialmente autocorrelacionado: un modelo sin")
            _linea("  componente espacial estaría mal especificado.")
        else:
            _linea("  Autocorrelación débil. El aparato espacial aporta menos de lo")
            _linea("  que se esperaba, y conviene decirlo antes de apoyarse en él.")

    _linea("\nHEDÓNICO  (los 10 coeficientes de mayor magnitud, en desviaciones estándar)")
    _linea(res["ols"].texto())
    if res.get("sdm"):
        _linea("\nDURBIN ESPACIAL")
        _linea(res["sdm"].texto())

    _linea("\nAPILADO")
    _linea(res["apilado"].texto())

    _linea("\nERROR EN EL CONJUNTO DE PRUEBA  (bloques que ningún modelo vio)")
    for nombre, m in res["punto"].items():
        _linea(f"  {nombre}")
        _linea(m.texto())

    _linea("\nINTERVALO CONFORME  (normalizado + Mondrian)")
    _linea(res["intervalo"].texto())

    cqr, crudo = res["intervalo_cqr"], res["intervalo_crudo"]
    _linea("\n  LOS TRES INTERVALOS, LADO A LADO")
    _linea(f"    sin conformalizar   {crudo.cobertura * 100:5.1f}% de cobertura · ±{crudo.ancho_mediano_pct:.0f}%")
    _linea(f"    CQR conformal       {cqr.cobertura * 100:5.1f}% · ±{cqr.ancho_mediano_pct:.0f}%")
    _linea(f"    normalizado         {res['intervalo'].cobertura * 100:5.1f}% · ±{res['intervalo'].ancho_mediano_pct:.0f}%")
    _linea("  Los dos conformales tienen la MISMA garantía; sólo difieren en el")
    _linea("  score, y por tanto en el ancho. El primero no tiene garantía ninguna.")
    if res["intervalo"].cobertura < 1 - res["alpha"]:
        _linea(f"\n  La cobertura quedó {(1 - res['alpha'] - res['intervalo'].cobertura) * 100:.1f} puntos bajo el objetivo, y es")
        _linea("  esperable: la partición por bloque hace que los barrios de")
        _linea("  calibración y los de prueba sean DISTINTOS, lo que rompe a")
        _linea("  propósito la intercambiabilidad de la que depende la garantía")
        _linea("  exacta. Es la condición real —valuar donde no hubo comparables—")
        _linea("  y no se corrige subiendo el nivel hasta que el número quede bonito.")

    if res.get("niveles"):
        _linea("\n  QUÉ CUESTA CADA NIVEL DE CONFIANZA")
        _linea("    confianza   cobertura   ancho")
        for a, iv in res["niveles"]:
            _linea(f"      {(1 - a) * 100:3.0f}%        {iv.cobertura * 100:5.1f}%    ±{iv.ancho_mediano_pct:.0f}%")
        _linea("  Con el score normalizado bajar el nivel no exige reentrenar nada.")

    # Cubrir no es lo mismo que servir. Un intervalo puede tener la garantía
    # perfecta y ser inútil para decidir, y decir sólo lo primero sería vender
    # una precisión que no existe.
    ancho = res["intervalo"].ancho_mediano_pct
    if ancho > 60:
        _linea(f"\n  ⚠ PERO ±{ancho:.0f}% ES DEMASIADO ANCHO PARA DECIDIR.")
        _linea("  La garantía se cumple; la utilidad, no. Un intervalo así dice")
        _linea("  poco más que 'no sé', y el motivo no es el método sino que el")
        _linea("  modelo se equivoca " f"{res['punto']['apilado'].mdape_pct:.0f}% en la mediana: un intervalo")
        _linea("  honesto sobre un error así TIENE que ser ancho. Se estrecha con")
        _linea("  más inventario y mejores atributos, no apretando el intervalo.")
        _linea("  Para una banda más angosta con garantía menor: --alpha 0.20 (80%).")

    _linea(f"\nQUÉ EMPUJA EL PRECIO  (método: {res['importancia'].metodo})")
    _linea(res["importancia"].texto())

    _linea("\nLO QUE ESTO NO ES")
    _linea("  · Precio de OFERTA, no de cierre. El sistema estima a qué precio se")
    _linea("    OFRECE un inmueble así, no a cuánto se vende. No se aplica ningún")
    _linea("    descuento porque no hay transacciones con que calibrarlo.")
    _linea("  · No es un avalúo con validez legal salvo que lo suscriba un perito.")
    _linea(f"  · La muestra es de {len(d):,} inmuebles para 16 alcaldías. El intervalo")
    _linea("    es honesto, pero es ancho porque el dato es poco: la manera de")
    _linea("    estrecharlo es más inventario, no más modelo.")
    if d.descartadas.get("sin_dato"):
        _linea("  · Faltan parques, transporte y equipamiento (OSM sin descargar):")
        _linea("    python -m pipelines.fase0 --osm")
    _linea("=" * 66)


def main() -> int:
    ap = argparse.ArgumentParser(description="BrickBit Atlas · Fase 2")
    ap.add_argument("--operacion", default="venta", choices=["venta", "renta"])
    ap.add_argument("--alpha", type=float, default=None,
                    help="1-alpha es la cobertura objetivo (por defecto, config.yaml)")
    ap.add_argument("--informe", action="store_true")
    args = ap.parse_args()

    cfg = cargar()
    res = None
    if not args.informe:
        _linea(f"BrickBit Atlas · Fase 2 · semilla {cfg.semilla}")
        _linea()
        res = construir(cfg, args.operacion, args.alpha)
    informe(cfg, res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
