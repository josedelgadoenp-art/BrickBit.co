"""
Ensamblado de la matriz de modelado y partición espacial.

Aquí se junta lo que la Fase 0 ingirió (los listados) con lo que la Fase 1
construyó (la malla H3 con sus variables de amenidad, accesibilidad y rezagos
espaciales). Cada inmueble hereda las variables de la celda donde cae.

LA PARTICIÓN ES POR BLOQUE, NO POR FILA. Es la decisión más importante del
módulo y conviene entender por qué. Si se parte al azar, dos departamentos del
mismo edificio —o de la misma cuadra— caen uno en entrenamiento y otro en
prueba. El modelo entonces no predice: recuerda al vecino. El desempeño sale
espectacular y es mentira, y el error se descubre el día que se valúa un
inmueble en una zona donde no había comparables. Los bloques son celdas H3 de
resolución 6 (~3.2 km de arista): un bloque entero va completo a entrenamiento,
a calibración o a prueba, nunca repartido.

EL OBJETIVO ES ln(precio/m²). Se modela el precio unitario y en logaritmo por
tres razones: el precio por m² es lo comparable entre inmuebles de distinto
tamaño; su distribución es marcadamente asimétrica y el logaritmo la simetriza;
y en semi-log los coeficientes se leen como porcentajes, que es como se habla
del mercado. La superficie entra además como variable, porque el precio por m²
NO es constante con el tamaño —un depto de 40 m² casi siempre vale más por m²
que uno de 200— y forzar esa constancia sería un supuesto falso.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from .. import lago
from ..config import Config, cargar
from ..geo import _xy, puntos

# Atributos del inmueble que entran como variables. `amenidades` queda fuera:
# es una lista libre por portal y sin vocabulario común no es comparable.
ATRIBUTOS = [
    "superficie_construida_m2", "superficie_terreno_m2", "recamaras", "banos",
    "medios_banos", "estacionamientos", "antiguedad_anios", "niveles",
]

# Columnas de la malla que NO son variables: identificadores y geometría.
NO_VARIABLES = {"h3", "bloque", "lat", "lng", "lisa_p", "lisa_sig", "lisa_cuadrante"}

MINIMO_PARA_MODELAR = 200


@dataclass
class Datos:
    """La matriz lista para modelar, con todo lo que hace falta para auditarla."""

    X: pd.DataFrame
    y: pd.Series                       # ln(precio/m²)
    bloque: pd.Series                  # H3 res-6: la unidad de la partición
    superficie: pd.Series              # para volver del precio/m² al precio
    coords: np.ndarray                 # métricas (EPSG:6372), para W y GWR
    operacion: str
    tipo_referencia: str | None = None   # la categoría que se dejó fuera
    descartadas: dict[str, list[str]] = field(default_factory=dict)
    n_sin_celda: int = 0

    def __len__(self) -> int:
        return len(self.y)


def _celda_de_cada_inmueble(props: pd.DataFrame, feats: pd.DataFrame, cfg: Config):
    """
    Índice de la celda de malla que le toca a cada inmueble.

    Primero por identidad de celda H3 —exacto y barato—. Los que caen en una
    celda que la malla no tiene (la malla se recorta a los polígonos de código
    postal, así que hay huecos en los bordes) se asignan al centro de celda más
    cercano en vez de descartarse: un inmueble a 200 m de la malla se parece
    muchísimo a su vecino, y tirarlo perdería una observación de las pocas que
    hay. Se cuenta cuántos fueron y se declara en el informe.
    """
    import h3

    res = int(cfg["modelado"]["h3"]["resolucion_malla"])
    h = pd.Series(
        [h3.latlng_to_cell(la, lo, res) for la, lo in zip(props["lat"], props["lng"])],
        index=props.index, dtype="string",
    )
    pos = pd.Series(np.arange(len(feats)), index=feats["h3"].astype("string"))
    idx = h.map(pos)

    faltan = idx.isna()
    n_faltan = int(faltan.sum())
    if n_faltan:
        arbol = cKDTree(_xy(puntos(feats, cfg=cfg), cfg))
        p = _xy(puntos(props.loc[faltan], cfg=cfg), cfg)
        _, vecino = arbol.query(p, k=1, workers=-1)
        idx.loc[faltan] = vecino
    return idx.astype(int).to_numpy(), n_faltan


def _columnas_utiles(X: pd.DataFrame, minimo_no_nulo: float = 0.5):
    """
    Quita lo que no puede informar y dice por qué se fue.

    Tres causas, distintas entre sí:
      · `sin_dato`   la columna está entera en NaN. Es el caso de las variables
                     de OSM cuando no se ha descargado: existen con ausencia
                     declarada, y meterlas al modelo sólo añadiría ruido.
      · `casi_vacia` tiene dato en menos de la mitad de los inmuebles. Imputar
                     la mayoría de una columna es inventarse la variable.
      · `constante`  no varía, así que no puede explicar nada.
    """
    fuera = {"sin_dato": [], "casi_vacia": [], "constante": []}
    quedan = []
    for c in X.columns:
        s = X[c]
        llenos = float(s.notna().mean())
        if llenos == 0:
            fuera["sin_dato"].append(c)
        elif llenos < minimo_no_nulo:
            fuera["casi_vacia"].append(c)
        elif s.nunique(dropna=True) <= 1:
            fuera["constante"].append(c)
        else:
            quedan.append(c)
    return X[quedan], fuera


def ensamblar(cfg: Config | None = None, operacion: str = "venta") -> Datos:
    """
    Junta listados + malla y devuelve la matriz de una operación.

    Venta y renta se modelan POR SEPARADO. No son el mismo mercado: los
    determinantes del precio de venta (expectativa de plusvalía, escrituración,
    crédito) y los de la renta (flujo, rotación) difieren, y mezclarlos con una
    variable indicadora obligaría a compartir todos los demás coeficientes.
    """
    cfg = cfg or cargar()
    if not lago.existe("properties", cfg):
        raise FileNotFoundError(
            "No hay listados en el lago. Corre la Fase 0 después del scraper:\n"
            "  node tools/c21-scraper.mjs todo  →  python -m pipelines.fase0"
        )
    if not lago.existe("features_malla", cfg):
        raise FileNotFoundError("Falta `features_malla`. Corre: python -m pipelines.fase1")

    props = lago.leer("properties", cfg)
    props = props.loc[props["operacion"].eq(operacion)].reset_index(drop=True)
    if len(props) < MINIMO_PARA_MODELAR:
        raise ValueError(
            f"Sólo hay {len(props)} inmuebles en {operacion}: por debajo de "
            f"{MINIMO_PARA_MODELAR} no se puede validar por bloques ni calibrar "
            "un intervalo. Un modelo aquí daría un número sin respaldo."
        )

    feats = lago.leer("features_malla", cfg)
    fila, n_sin_celda = _celda_de_cada_inmueble(props, feats, cfg)

    de_malla = [c for c in feats.columns if c not in NO_VARIABLES and feats[c].dtype.kind in "if"]
    M = feats.iloc[fila][de_malla].reset_index(drop=True)

    # --- atributos del inmueble ---
    A = props[ATRIBUTOS].astype(float).reset_index(drop=True)
    sup = A["superficie_construida_m2"].where(
        A["superficie_construida_m2"].notna() & (A["superficie_construida_m2"] > 0),
        A["superficie_terreno_m2"],
    )
    A["ln_superficie"] = np.log(sup)
    # Baños totales: medio baño es medio baño, y contarlos por separado obliga
    # al modelo a aprender esa suma con datos que no le sobran.
    A["banos_totales"] = A["banos"].fillna(0) + 0.5 * A["medios_banos"].fillna(0)
    A.loc[A["banos"].isna() & A["medios_banos"].isna(), "banos_totales"] = np.nan
    A["tiene_terreno"] = props["superficie_terreno_m2"].reset_index(drop=True).notna().astype(float)

    # Indicadoras de tipo, dejando UNA fuera como categoría de referencia: con
    # todas dentro más la constante, las columnas suman 1 y la matriz es
    # singular. La primera versión quitaba `tipo_otro` por nombre, y cuando esa
    # categoría no existía en los datos no se quitaba ninguna: statsmodels lo
    # cazó con un SingularMatrixWarning y los coeficientes salían indeterminados.
    # Ahora se quita la categoría MÁS FRECUENTE —la referencia natural, contra la
    # que se leen las demás— y se guarda cuál fue, porque sin saberlo los
    # coeficientes de tipo no se pueden interpretar.
    serie_tipo = props["tipo"].astype(str).reset_index(drop=True)
    tipo = pd.get_dummies(serie_tipo, prefix="tipo", dtype=float)
    referencia = None
    if tipo.shape[1] > 1:
        referencia = str(serie_tipo.value_counts().idxmax())
        tipo = tipo.drop(columns=[f"tipo_{referencia}"])

    X = pd.concat([A, tipo, M], axis=1)
    X, descartadas = _columnas_utiles(X)

    y = np.log(props["precio_m2_asking"].astype(float).reset_index(drop=True))
    bloque = feats.iloc[fila]["bloque"].reset_index(drop=True).astype("string")
    coords = _xy(puntos(props, cfg=cfg), cfg)

    ok = np.isfinite(y.to_numpy()) & np.isfinite(sup.to_numpy()) & bloque.notna().to_numpy()
    return Datos(
        X=X.loc[ok].reset_index(drop=True),
        y=y.loc[ok].reset_index(drop=True),
        bloque=bloque.loc[ok].reset_index(drop=True),
        superficie=sup.loc[ok].reset_index(drop=True),
        coords=coords[ok],
        operacion=operacion,
        tipo_referencia=referencia,
        descartadas=descartadas,
        n_sin_celda=n_sin_celda,
    )


def particion(
    bloque: pd.Series,
    cfg: Config | None = None,
    fracciones: tuple[float, float, float] | None = None,
) -> dict[str, np.ndarray]:
    """
    Reparte los BLOQUES —no las filas— en entrenamiento, calibración y prueba.

    Los bloques se barajan con la semilla del proyecto y se van repartiendo
    hasta llenar cada cupo. Como los bloques tienen tamaños muy distintos (el
    centro concentra inventario), las fracciones resultantes no salen exactas;
    se prefiere eso a partir un bloque, que reintroduciría la fuga que la
    partición existe para evitar.

    La calibración es su propio conjunto y no se toca al entrenar: el intervalo
    conforme sólo tiene garantía si se calibra con datos que el modelo nunca vio.
    """
    cfg = cfg or cargar()
    if fracciones is None:
        fracciones = tuple(cfg["modelado"]["validacion"].get("fracciones", (0.6, 0.2, 0.2)))
    rng = np.random.default_rng(int(cfg.semilla))
    tam = bloque.value_counts()

    # DE MAYOR A MENOR, no al azar.
    #
    # Los bloques de la CDMX son muy desiguales: el centro concentra el
    # inventario y un solo bloque puede valer el 20% de la muestra. Con los
    # bloques barajados, si uno enorme sale temprano se lleva un conjunto entero
    # por delante y ya no hay cómo recuperar el equilibrio con los chicos que
    # quedan. Medido: pidiendo 60/20/20 salía 49/24/27 en una simulación y
    # 76/10/14 sobre los datos reales —la calibración quedó en 183 filas, con
    # grupos de Mondrian de 61, y el cuantil conforme del 95% pasó a ser el
    # tercer valor más grande de 61: puro ruido, cobertura 98% y +-121% de ancho.
    #
    # Colocar primero los grandes es la heurística estándar de reparto
    # multiconjunto (longest-processing-time-first): los bloques grandes se
    # acomodan cuando todos los cupos están libres, y los chicos sirven después
    # para afinar. El barajado se conserva sólo para desempatar entre bloques
    # del mismo tamaño, que es donde sí conviene no tener un sesgo fijo.
    orden = tam.index.to_numpy()
    rng.shuffle(orden)
    orden = sorted(orden, key=lambda b: -int(tam[b]))

    n = int(tam.sum())
    cupos = [f * n for f in fracciones]
    destino: dict[str, list] = {"entrena": [], "calibra": [], "prueba": []}
    nombres = list(destino)
    acumulado = [0.0, 0.0, 0.0]

    for b in orden:
        # Al bloque que va: el que más lejos está de su cupo, en proporción.
        deficit = [(acumulado[i] - cupos[i]) / max(cupos[i], 1.0) for i in range(3)]
        i = int(np.argmin(deficit))
        destino[nombres[i]].append(b)
        acumulado[i] += float(tam[b])

    en = {k: bloque.isin(v).to_numpy() for k, v in destino.items()}
    vacios = [k for k, v in en.items() if v.sum() == 0]
    if vacios:
        raise ValueError(
            f"La partición dejó vacío(s) {', '.join(vacios)}: hay muy pocos bloques "
            f"({len(orden)}) para partir en tres sin fuga espacial."
        )
    return en
