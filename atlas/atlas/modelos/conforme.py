"""
Intervalos conformes: CQR y Mondrian.

Ésta es la pieza que convierte el AVM en algo defendible. Un modelo que dice
"este departamento vale 4.2 millones" está diciendo menos de lo que parece; lo
que hace falta saber es cuánto puede equivocarse, y que ese "cuánto" esté
respaldado y no sea una barra de error decorativa.

QUÉ GARANTIZA. La predicción conforme da cobertura **marginal** de (1−α):
sobre inmuebles nuevos del mismo mercado, el intervalo contiene el precio real
al menos el (1−α)·100% de las veces. No exige que el modelo esté bien
especificado ni que los errores sean normales; sólo intercambiabilidad entre
calibración y despliegue. Es de las pocas garantías honestas que se pueden dar
en valuación automatizada.

Y AQUÍ ESA INTERCAMBIABILIDAD SE ROMPE A PROPÓSITO. La partición del Atlas es
por bloque espacial: los barrios de calibración y los de prueba son barrios
DISTINTOS. Eso viola justamente el supuesto del que cuelga la garantía exacta,
y por eso la cobertura medida puede caer un par de puntos por debajo del
objetivo. No es un defecto que haya que tapar subiendo el nivel hasta que el
número quede bonito: es la condición real de despliegue —valuar donde no hubo
comparables— y medirla así es el único modo de saber qué pasa entonces. Con una
partición al azar la cobertura saldría clavada en el objetivo, y ese número no
diría nada sobre el barrio siguiente.

QUÉ NO GARANTIZA, Y POR ESO EXISTE MONDRIAN. La cobertura marginal es un
promedio sobre TODO el mercado, y un promedio puede esconder un desastre: un
intervalo puede cubrir 95% en global y sólo 70% en departamentos de lujo, si
cubre de más en el segmento numeroso. Para quien vende un inmueble caro, el 95%
global no le sirve de nada. Mondrian corrige eso calibrando por separado dentro
de cada segmento, con lo que la cobertura se sostiene **condicionada al grupo**.

CQR (Romano, Patterson & Candès, 2019) parte de los cuantiles estimados por el
boosting y los corrige con el residual conforme

    E_i = max( q̂_lo(x_i) − y_i ,  y_i − q̂_hi(x_i) )

Si el intervalo del modelo se quedó corto en la calibración, E es positivo y la
corrección lo ensancha; si se pasó de ancho, E es negativo y lo aprieta. La
virtud sobre un conformal de residuo simple es que el ancho SIGUE SIENDO
ADAPTATIVO: donde el modelo sabe menos —pocos comparables— los cuantiles ya
venían separados y el intervalo sale ancho, que es la verdad.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

def minimo_por_grupo(alpha: float) -> int:
    """
    Cuántas observaciones necesita un grupo para calibrarse por separado.

    Hay un piso DURO, que es aritmética y no criterio: la corrección conforme es
    el ⌈(n+1)(1−α)⌉-ésimo valor ordenado, así que con n < 1/α − 1 el índice cae
    fuera de la muestra y no existe corrección finita. Con α=0.05 son 19.

    Se pide el doble de ese piso, y nunca menos de 30, porque justo en el piso
    la corrección es el máximo de la muestra: válida, sí, pero tan inestable que
    un solo anuncio con el precio mal capturado decidiría el ancho del intervalo
    de todo un segmento.
    """
    duro = int(np.ceil(1.0 / float(alpha))) - 1
    return max(2 * (duro + 1), 30)


MINIMO_POR_GRUPO = 40      # el de α=0.05, para quien llame sin especificar


def _cuantil_conforme(E: np.ndarray, alpha: float) -> float:
    """
    Cuantil conforme: el ⌈(n+1)(1−α)⌉-ésimo valor ordenado de E.

    El (n+1) y el techo no son un detalle cosmético: son lo que convierte una
    cobertura aproximada en la garantía en muestra finita. Con n pequeño la
    diferencia contra el percentil ingenuo es grande y siempre en la dirección
    de cubrir de menos, que es la dirección peligrosa.

    Si n es tan chico que el índice pedido excede la muestra, no hay corrección
    finita posible y se devuelve infinito: el intervalo se declara no informativo
    en vez de fingir una garantía que no se tiene.
    """
    E = np.asarray(E, dtype=float)
    E = E[np.isfinite(E)]
    n = len(E)
    if n == 0:
        return float("inf")
    k = int(np.ceil((n + 1) * (1.0 - alpha)))
    if k > n:
        return float("inf")
    return float(np.sort(E)[k - 1])


@dataclass
class Conformal:
    """Las correcciones aprendidas en calibración, listas para aplicar."""

    alpha: float
    global_: float
    por_grupo: dict[str, float] = field(default_factory=dict)
    n_por_grupo: dict[str, int] = field(default_factory=dict)
    grupos_sin_calibrar: list[str] = field(default_factory=list)
    pool: float | None = None                       # corrección del cubo de chicos
    grupos_en_pool: list[str] = field(default_factory=list)

    def correccion(self, grupos: pd.Series | None) -> np.ndarray:
        """
        La corrección de cada fila: la de su grupo si lo tiene calibrado, la
        global si no. Un grupo raro no se queda sin intervalo; se queda con el
        del mercado entero, y el informe dice cuáles fueron.
        """
        if grupos is None:
            return np.full(1, self.global_)
        return np.array([self.por_grupo.get(str(g), self.global_) for g in grupos])

    def texto(self) -> str:
        filas = [f"    global{'':<24} {self.global_:+.4f}"]
        for g, q in sorted(self.por_grupo.items(), key=lambda kv: -self.n_por_grupo.get(kv[0], 0)):
            filas.append(f"    {g:<30} {q:+.4f}   n={self.n_por_grupo.get(g, 0):,}")
        if self.grupos_en_pool:
            filas.append(
                f"    agrupados y calibrados juntos ({self.pool:+.4f}): "
                + ", ".join(self.grupos_en_pool)
            )
        if self.grupos_sin_calibrar:
            filas.append(
                f"    ⚠ sin calibrar, usan la global y NO tienen garantía propia: "
                + ", ".join(self.grupos_sin_calibrar)
            )
        return "\n".join(filas)


def calibrar_desde_scores(
    E: np.ndarray,
    alpha: float,
    grupos_cal: pd.Series | None = None,
    minimo_por_grupo: int = MINIMO_POR_GRUPO,
) -> Conformal:
    """
    La maquinaria común: cuantil conforme global, por grupo, y cubo de chicos.

    Está separada porque las dos formas de intervalo que usa el Atlas —CQR y
    normalizado— sólo difieren en CÓMO se calcula el score de disconformidad.
    Todo lo demás —el ⌈(n+1)(1−α)⌉, Mondrian, el agrupamiento de los segmentos
    chicos— es idéntico, y duplicarlo habría garantizado que las dos versiones
    se separaran con el tiempo.
    """
    E = np.asarray(E, dtype=float)
    c = Conformal(alpha=float(alpha), global_=_cuantil_conforme(E, alpha))

    if grupos_cal is None:
        return c
    g = pd.Series(grupos_cal).astype(str).to_numpy()

    chicos = []
    for nombre in pd.unique(g):
        sel = g == nombre
        n = int(sel.sum())
        q = _cuantil_conforme(E[sel], alpha) if n >= minimo_por_grupo else float("inf")
        if np.isfinite(q):
            c.por_grupo[nombre] = q
            c.n_por_grupo[nombre] = n
        else:
            chicos.append(nombre)

    # LOS GRUPOS CHICOS SE JUNTAN Y SE CALIBRAN COMO UNO, en vez de caer a la
    # corrección global. Es la diferencia entre tener garantía y no tenerla: la
    # global la dominan los grupos numerosos, así que aplicarla a un segmento
    # atípico da un intervalo que no cubre. Medido sobre datos reales, el grupo
    # `depto·barato` —12 inmuebles en calibración, sin calibrar— cubrió 69.6%
    # cuando prometía 95%. Un intervalo del 95% que cubre 70% no es un intervalo
    # del 95%. Al agrupar los chicos en un solo cubo, ese cubo sí tiene bastantes
    # observaciones para una corrección conforme válida sobre su unión.
    if chicos:
        sel = np.isin(g, chicos)
        n = int(sel.sum())
        q = _cuantil_conforme(E[sel], alpha)
        if np.isfinite(q) and n >= minimo_por_grupo:
            for nombre in chicos:
                c.por_grupo[nombre] = q
                c.n_por_grupo[nombre] = int((g == nombre).sum())
            c.pool = q
            c.grupos_en_pool = list(chicos)
        else:
            c.grupos_sin_calibrar = [f"{x} (n={int((g == x).sum())})" for x in chicos]
    return c


def calibrar(
    y_cal: np.ndarray,
    lo_cal: np.ndarray,
    hi_cal: np.ndarray,
    alpha: float,
    grupos_cal: pd.Series | None = None,
    minimo_por_grupo: int = MINIMO_POR_GRUPO,
) -> Conformal:
    """
    CQR: calibra a partir de los cuantiles estimados por el boosting.

    El conjunto de calibración no puede haber participado del entrenamiento ni
    de la selección de hiperparámetros. Si participara, los residuales serían
    optimistas y la garantía se caería sin hacer ruido —el intervalo seguiría
    saliendo, sólo que cubriendo menos de lo que promete—.
    """
    y_cal = np.asarray(y_cal, dtype=float)
    E = np.maximum(np.asarray(lo_cal, float) - y_cal, y_cal - np.asarray(hi_cal, float))
    return calibrar_desde_scores(E, alpha, grupos_cal, minimo_por_grupo)


def calibrar_normalizado(
    y_cal: np.ndarray,
    pred_cal: np.ndarray,
    sigma_cal: np.ndarray,
    alpha: float,
    grupos_cal: pd.Series | None = None,
    minimo_por_grupo: int = MINIMO_POR_GRUPO,
) -> Conformal:
    """
    Conformal localmente adaptativo: score = |y − ŷ| / σ̂(x).

    La alternativa a CQR, y con muestras chicas suele ganarle por mucho. CQR
    tiene que estimar los cuantiles 2.5% y 97.5% directamente, y esa cola se
    apoya en el 2.5% de las observaciones —unas 24 de 953 en la CDMX—: el
    resultado es ruidoso y, al conformalizarlo, ancho. Aquí σ̂(x) se ajusta con
    TODAS las observaciones y el conformal sólo tiene que encontrar un factor
    de escala.

    Sigue siendo adaptativo —donde el modelo sabe menos, σ̂ es grande y el
    intervalo se abre— y conserva la misma garantía de cobertura, que no depende
    de que σ̂ sea correcto: si σ̂ fuera basura, el intervalo saldría ancho pero
    seguiría cubriendo. σ̂ compra estrechez, no validez.

    Ventaja de regalo: cambiar α no exige reentrenar nada. Con CQR, pasar de un
    intervalo del 95% a uno del 80% obliga a ajustar dos modelos de cuantil
    nuevos; aquí es otro cuantil de los mismos scores.
    """
    y_cal = np.asarray(y_cal, dtype=float)
    s = np.maximum(np.asarray(sigma_cal, float), 1e-6)
    E = np.abs(y_cal - np.asarray(pred_cal, float)) / s
    return calibrar_desde_scores(E, alpha, grupos_cal, minimo_por_grupo)


def aplicar_normalizado(
    pred: np.ndarray, sigma: np.ndarray, c: Conformal, grupos: pd.Series | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Intervalo ŷ ± Q·σ̂(x): ancho proporcional a lo que el modelo suele fallar ahí."""
    d = (c.correccion(grupos) if grupos is not None else np.full(len(pred), c.global_))
    d = d * np.maximum(np.asarray(sigma, float), 1e-6)
    pred = np.asarray(pred, float)
    return pred - d, pred + d


def aplicar(
    lo: np.ndarray, hi: np.ndarray, c: Conformal, grupos: pd.Series | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """
    Ensancha (o aprieta) el intervalo del modelo con la corrección conforme.

    Se fuerza lo ≤ hi al final: con correcciones negativas grandes las dos puntas
    podrían cruzarse, y un intervalo invertido es un error de programa, no un
    resultado. Cuando pasa, se colapsa al punto medio.
    """
    d = c.correccion(grupos) if grupos is not None else np.full(len(lo), c.global_)
    bajo = np.asarray(lo, float) - d
    alto = np.asarray(hi, float) + d
    cruzados = bajo > alto
    if cruzados.any():
        medio = (bajo[cruzados] + alto[cruzados]) / 2.0
        bajo[cruzados] = alto[cruzados] = medio
    return bajo, alto


def segmentos(
    tipo: pd.Series, alcaldia_o_bloque: pd.Series | None = None, precio_m2: pd.Series | None = None
) -> pd.Series:
    """
    Define los grupos de Mondrian.

    El segmento es `tipo × tercil de precio`. La elección no es arbitraria: son
    los dos ejes por los que un intervalo promedio falla de forma más visible.
    Un terreno no se valúa como un departamento, y el error relativo en el
    extremo caro del mercado —donde hay menos comparables y más heterogeneidad—
    es sistemáticamente mayor que en el medio.

    Los terciles se calculan sobre el conjunto que se pase, y para que un
    inmueble nuevo caiga en el mismo tercil hay que usar los MISMOS cortes; por
    eso `cortes_de` y `aplicar_cortes` van aparte.
    """
    t = pd.Series(tipo).astype(str).str.replace("tipo_", "", regex=False)
    if precio_m2 is None:
        return t
    ter = pd.qcut(pd.Series(precio_m2).rank(method="first"), 3,
                  labels=["barato", "medio", "caro"])
    return (t + "·" + ter.astype(str)).astype(str)


def elegir_segmentacion(
    tipo: pd.Series, valores: pd.Series, alpha: float, cobertura_minima: float = 0.75
) -> tuple[str, pd.Series, np.ndarray | None]:
    """
    Elige la segmentación MÁS FINA que la muestra de calibración puede sostener.

    ⚠ `valores` DEBE ser el precio PREDICHO, no el observado. El grupo de
    Mondrian tiene que poder calcularse en el momento de valuar, y en ese
    momento el precio real es justamente lo que no se sabe. Usar el observado
    daría una cobertura preciosa en la evaluación y se caería en producción,
    donde no hay con qué asignar el grupo. Es el mismo error de fuga que la
    partición por bloques evita en el espacio, pero en la variable objetivo.

    El problema, medido: con 290 inmuebles de calibración y `tipo × tercil`
    salen nueve grupos, y ocho quedan por debajo del mínimo. Mondrian entonces
    no hace nada —todos caen a la corrección global— y el sistema paga la
    complejidad sin cobrar el beneficio. Peor: el informe *parece* segmentado.

    Así que se prueba de fina a gruesa —tipo×tercil, tercil, tipo— y se toma la
    primera en la que al menos `cobertura_minima` de los inmuebles cae en grupos
    calibrables. Si ninguna llega, se declara global y se dice. Es preferible un
    intervalo global honesto a nueve intervalos "por segmento" que en realidad
    son el mismo número repetido.

    Devuelve (nombre, segmentos, cortes). `cortes` es None cuando la
    segmentación no usa terciles.
    """
    t = pd.Series(tipo).astype(str).reset_index(drop=True)
    v = pd.Series(valores).astype(float).reset_index(drop=True)
    minimo = minimo_por_grupo(alpha)
    cortes = cortes_de(v)
    ter = aplicar_cortes(pd.Series([""] * len(v)), v, cortes).str.lstrip("·")

    candidatas = [
        ("tipo × tercil", (t + "·" + ter).astype(str), cortes),
        ("tercil de precio", ter.astype(str), cortes),
        ("tipo", t, None),
    ]
    for nombre, seg, c in candidatas:
        tam = seg.value_counts()
        calibrables = tam[tam >= minimo]
        if float(calibrables.sum()) / max(len(seg), 1) >= cobertura_minima:
            return nombre, seg, c
    return "global (la muestra no sostiene segmentos)", pd.Series(["todos"] * len(t)), None


def cortes_de(valores: pd.Series) -> np.ndarray:
    """Los dos cortes de tercil, para reaplicarlos idénticos a datos nuevos."""
    v = pd.Series(valores).astype(float)
    return np.asarray(np.nanpercentile(v, [100 / 3, 200 / 3]), dtype=float)


def aplicar_cortes(tipo: pd.Series, valores: pd.Series, cortes: np.ndarray) -> pd.Series:
    """Segmento de datos nuevos usando los cortes aprendidos, no los suyos."""
    t = pd.Series(tipo).astype(str).str.replace("tipo_", "", regex=False).reset_index(drop=True)
    v = pd.Series(valores).astype(float).reset_index(drop=True)
    etiqueta = np.where(v <= cortes[0], "barato", np.where(v <= cortes[1], "medio", "caro"))
    return pd.Series(t.to_numpy() + "·" + etiqueta, dtype=str)


def segmentar(
    nombre: str, tipo: pd.Series, valores: pd.Series, cortes: np.ndarray | None
) -> pd.Series:
    """
    Reaplica a datos nuevos la segmentación que `elegir_segmentacion` eligió.

    Los cortes son los aprendidos en calibración, no los de estos datos: si cada
    conjunto usara sus propios terciles, "caro" significaría cosas distintas en
    calibración y en producción y la corrección se aplicaría al grupo equivocado.
    """
    t = pd.Series(tipo).astype(str).reset_index(drop=True)
    if nombre.startswith("global"):
        return pd.Series(["todos"] * len(t))
    if nombre == "tipo":
        return t
    ter = aplicar_cortes(pd.Series([""] * len(t)), valores, cortes).str.lstrip("·")
    if nombre == "tercil de precio":
        return ter.astype(str)
    return (t + "·" + ter).astype(str)
