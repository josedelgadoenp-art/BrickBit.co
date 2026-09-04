"""
Modelos hedónicos: OLS semi-log y Durbin espacial (SDM).

Son el modelo INTERPRETABLE del Atlas. No compiten con el boosting en precisión
y no es su trabajo: existen para que alguien —un comité de crédito, un perito,
una autoridad— pueda leer qué empuja el precio y en qué dirección. Un número sin
explicación no se puede defender, y el documento pide un sistema auditable.

POR QUÉ UN NÚCLEO COMPACTO Y NO LAS 130 VARIABLES.
La malla trae ~130 columnas: distancia, tres conteos y accesibilidad por cada
familia, más sus rezagos W·X. Para el boosting eso está bien —los árboles se
defienden solos de la redundancia—. Para una regresión con ~1,300 observaciones
sería un desastre: `dist_abasto_m`, `n_abasto_300m` y `acc_abasto` miden casi lo
mismo, la matriz queda cuasi-singular y los coeficientes salen enormes, de signo
arbitrario y con errores estándar inútiles. Colinealidad, no información.
Así que el hedónico usa un núcleo elegido por criterio, no por búsqueda: la
accesibilidad gravitacional de cada familia (que resume distancia y densidad en
una sola cifra), la distancia al comercio más cercano, el rezago del empleo y el
Moran local. El boosting se queda con todo lo demás.

SDM = y = ρ·W·y + X·β + W·X·θ + ε
El término ρ·W·y captura el desbordamiento: el precio de un inmueble depende del
de sus vecinos, no sólo de sus propios atributos. W·X·θ captura que los atributos
del VECINDARIO también valen (vivir rodeado de comercio, no sólo tenerlo). La I
de Moran de la Fase 1 (0.96 sobre densidad de empleo) ya decía que ignorar esto
dejaría el modelo mal especificado; aquí se mide sobre el precio.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from libpysal.weights import W
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Núcleo espacial del hedónico: una variable por concepto, no cuatro por familia.
NUCLEO_ESPACIAL = [
    "acc_denue", "acc_abasto", "acc_alimentos", "acc_servicios", "acc_industria",
    "dist_abasto_m", "dist_alimentos_m", "dist_servicios_m", "dist_industria_m",
    "W_acc_denue", "lisa_I",
]
NUCLEO_INMUEBLE = [
    "ln_superficie", "recamaras", "banos_totales", "estacionamientos",
    "antiguedad_anios", "niveles", "tiene_terreno",
]


def columnas_nucleo(X: pd.DataFrame) -> list[str]:
    """Las del núcleo que de verdad existen, más las indicadoras de tipo."""
    base = [c for c in NUCLEO_INMUEBLE + NUCLEO_ESPACIAL if c in X.columns]
    return base + [c for c in X.columns if c.startswith("tipo_")]


def _rango_completo(Z: np.ndarray, nombres: list[str], tol: float = 1e-8):
    """
    Se queda con un subconjunto de columnas linealmente independiente.

    Aunque el núcleo esté elegido a mano, en el Durbin se duplica con W·X y ahí
    sí aparecen dependencias: dos variables casi idénticas y sus rezagos pueden
    volver la matriz cuasi-singular. Con QR pivotante se detecta cuáles sobran y
    se quitan, en vez de dejar que la estimación devuelva coeficientes
    indeterminados con cara de resultado. Se devuelve también qué se quitó, para
    poder decirlo.
    """
    Q, R, piv = _qr_pivotante(Z)
    diag = np.abs(np.diag(R))
    if diag.size == 0:
        return Z, nombres, []
    rango = int(np.sum(diag > tol * diag[0]))
    conserva = sorted(piv[:rango])
    fuera = [nombres[i] for i in range(len(nombres)) if i not in set(conserva)]
    return Z[:, conserva], [nombres[i] for i in conserva], fuera


def _qr_pivotante(Z: np.ndarray):
    from scipy.linalg import qr

    return qr(Z, mode="economic", pivoting=True)


def podar_por_vif(Z: np.ndarray, nombres: list[str], umbral: float = 10.0):
    """
    Quita variables hasta que ninguna tenga un factor de inflación de varianza
    por encima de `umbral`.

    POR QUÉ NO BASTABA EL FILTRO DE RANGO. El QR pivotante sólo detecta
    dependencias EXACTAS. La colinealidad real es casi-exacta y pasa entera por
    ese filtro. Medido sobre los datos de la CDMX: `dist_servicios_m` salió con
    −0.91 y `dist_abasto_m` con +0.78 —dos variables que miden prácticamente lo
    mismo, con signos opuestos y magnitudes enormes—, y el hedónico pasó de
    R²=0.456 dentro de muestra a **R²=0.002 fuera**. No es sobreajuste: es que
    unos coeficientes que se cancelan entre sí no transfieren a otro barrio.

    El VIF de la variable j es 1/(1−R²_j), donde R²_j sale de regresarla contra
    las demás; con las columnas estandarizadas es el elemento j de la diagonal
    de la inversa de la matriz de correlación. Un VIF de 10 significa que su
    error estándar está inflado más de tres veces.
    """
    Z = np.asarray(Z, dtype=float)
    vivos = list(range(Z.shape[1]))
    fuera: list[str] = []
    while len(vivos) > 1:
        M = Z[:, vivos]
        R = np.corrcoef(M, rowvar=False)
        R = np.nan_to_num(R, nan=0.0)
        try:
            vif = np.diag(np.linalg.pinv(R))
        except np.linalg.LinAlgError:
            break
        peor = int(np.argmax(vif))
        if not np.isfinite(vif[peor]) or vif[peor] <= umbral:
            break
        fuera.append(nombres[vivos[peor]])
        vivos.pop(peor)
    return Z[:, vivos], [nombres[i] for i in vivos], fuera


def ridge_por_bloque(X: pd.DataFrame, y: pd.Series, bloque: pd.Series,
                     columnas: list[str] | None = None):
    """
    Hedónico regularizado, para PREDECIR (no para interpretar).

    Interpretar y predecir son dos trabajos distintos y aquí se hacen con dos
    herramientas distintas, a propósito:

      · para LEER el modelo → OLS sobre variables podadas por VIF, con errores
        robustos. Coeficientes pocos, estables y con un significado defendible.
      · para PREDECIR → cresta sobre el núcleo completo. La penalización reparte
        el peso entre variables colineales en vez de dárselo todo a una con
        signo arbitrario, y así el ajuste sí transfiere a un barrio que el
        modelo no vio.

    El α se elige por validación cruzada POR BLOQUE ESPACIAL, no al azar: si se
    eligiera al azar, la regularización se calibraría contra vecinos filtrados y
    saldría demasiado floja justo donde hace falta.
    """
    from sklearn.linear_model import RidgeCV
    from sklearn.model_selection import GroupKFold

    cols = columnas or columnas_nucleo(X)
    prep = preparador()
    Z = prep.fit_transform(X[cols])
    k = int(min(5, pd.Series(bloque).nunique()))
    cv = GroupKFold(n_splits=k).split(Z, y, groups=bloque.to_numpy()) if k >= 2 else None
    m = RidgeCV(alphas=np.logspace(-2, 4, 25), cv=list(cv) if cv is not None else None)
    m.fit(Z, y)
    return prep, m, cols


def preparador() -> Pipeline:
    """
    Imputa por mediana y estandariza.

    La regresión no admite NaN, y la mediana es preferible a la media porque
    superficie, antigüedad y precio son asimétricos. Estandarizar no cambia el
    ajuste pero hace comparables las magnitudes de los coeficientes, que es para
    lo que se lee este modelo.
    """
    return Pipeline([
        ("imputa", SimpleImputer(strategy="median")),
        ("escala", StandardScaler()),
    ])


@dataclass
class ResultadoOLS:
    coeficientes: pd.DataFrame
    r2: float
    r2_ajustado: float
    n: int
    moran_residuos: tuple[float, float] | None = None
    quitadas: list[str] = field(default_factory=list)

    def texto(self, top: int = 10) -> str:
        c = self.coeficientes.reindex(
            self.coeficientes["coef"].abs().sort_values(ascending=False).index
        ).head(top)
        filas = [
            f"    {r.variable:<22} {r.coef:+8.4f}  p={r.p:.3g}"
            for r in c.itertuples()
        ]
        if self.quitadas:
            filas.append(f"    ({len(self.quitadas)} variables fuera por colinealidad: "
                         + ", ".join(self.quitadas[:6])
                         + ("…" if len(self.quitadas) > 6 else "") + ")")
        return "\n".join(filas)


def ols(X: pd.DataFrame, y: pd.Series, columnas: list[str] | None = None) -> ResultadoOLS:
    """
    OLS semi-log con errores estándar robustos (HC1).

    Robustos porque la heterocedasticidad en precios inmobiliarios es la regla,
    no la excepción: la dispersión del precio por m² crece con el nivel. Con
    errores clásicos los p-valores saldrían optimistas.
    """
    import statsmodels.api as sm

    cols = columnas or columnas_nucleo(X)
    prep = preparador()
    Z = np.asarray(prep.fit_transform(X[cols]), dtype=float)
    # Mismo cuidado que en el SDM: aunque el núcleo esté elegido a mano, en unos
    # datos concretos dos variables pueden resultar linealmente dependientes
    # —`tiene_terreno` con `tipo_casa`, por ejemplo, si sólo las casas traen
    # terreno—. Sin esto statsmodels avisa con SingularMatrixWarning y devuelve
    # coeficientes indeterminados que se leerían como si significaran algo.
    Z, cols, quitadas = _rango_completo(Z, list(cols))
    # Y después la colinealidad casi-exacta, que el filtro de rango no ve.
    Z, cols, por_vif = podar_por_vif(Z, list(cols))
    quitadas = list(quitadas) + por_vif
    Z = sm.add_constant(Z, has_constant="add")
    m = sm.OLS(np.asarray(y, dtype=float), Z).fit(cov_type="HC1")

    coef = pd.DataFrame({
        "variable": ["(constante)"] + list(cols),
        "coef": m.params,
        "ee": m.bse,
        "p": m.pvalues,
    })
    return ResultadoOLS(coef, float(m.rsquared), float(m.rsquared_adj), int(m.nobs),
                        quitadas=quitadas)


@dataclass
class ResultadoSDM:
    rho: float
    rho_p: float
    pseudo_r2: float
    n: int
    k: int
    directos: pd.DataFrame
    quitadas: list[str] = field(default_factory=list)

    @property
    def degenerado(self) -> bool:
        """
        ρ pegado a los extremos con un ajuste nulo no es un hallazgo: es el
        síntoma de una estimación que no convergió a nada útil. Se detecta y se
        dice, porque un ρ de −0.93 impreso sin contexto se leería como si el
        mercado tuviera desbordamiento negativo fuerte, que sería una conclusión
        económica falsa sacada de un problema numérico.
        """
        return abs(self.rho) > 0.98 or self.pseudo_r2 < 0.02

    def texto(self) -> str:
        if self.degenerado:
            return (
                f"    ⚠ estimación degenerada: ρ={self.rho:+.4f} con pseudo R²="
                f"{self.pseudo_r2:.4f}.\n"
                "      No se reporta como resultado. Suele significar que W deja\n"
                "      islas o que el diseño sigue mal condicionado; con esta\n"
                "      muestra el SDM no aporta y manda el hedónico."
            )
        signo = "positivo" if self.rho > 0 else "negativo"
        t = (
            f"    ρ = {self.rho:+.4f} (p={self.rho_p:.3g}) — desbordamiento {signo}\n"
            f"    pseudo R² = {self.pseudo_r2:.4f} sobre {self.n:,} inmuebles, {self.k} variables"
        )
        if self.quitadas:
            t += f"\n    {len(self.quitadas)} columnas colineales fuera del diseño"
        return t


def sdm(X: pd.DataFrame, y: pd.Series, w: W, columnas: list[str] | None = None) -> ResultadoSDM:
    """
    Durbin espacial por máxima verosimilitud.

    Se construye W·X explícitamente y se estima un modelo de rezago sobre
    [X, W·X]: eso ES el Durbin, escrito de forma que se ve lo que se está
    estimando en vez de esconderlo en un argumento.

    ρ significativo y positivo es el resultado que se espera y el que justifica
    todo el aparato espacial del sistema. Si saliera nulo, habría que decirlo y
    quedarse con el modelo simple.
    """
    from spreg import ML_Lag

    cols = columnas or columnas_nucleo(X)
    prep = preparador()
    Z = np.asarray(prep.fit_transform(X[cols]), dtype=float)
    WZ = np.asarray(w.sparse @ Z, dtype=float)
    Zd, nombres, quitadas = _rango_completo(
        np.hstack([Z, WZ]), list(cols) + [f"W_{c}" for c in cols]
    )

    m = ML_Lag(np.asarray(y, dtype=float).reshape(-1, 1), Zd, w=w,
               name_y="ln_precio_m2", name_x=nombres)

    # betas trae [constante, X…, W·X…, ρ]. Los efectos directos son la primera
    # mitad; los indirectos salen de los W·X y de ρ, y su descomposición formal
    # (efectos totales de LeSage-Pace) no se reporta aquí para no dar por exacto
    # un cálculo que exige la inversa (I−ρW)⁻¹ completa.
    betas = np.asarray(m.betas).ravel()
    directos = pd.DataFrame({
        "variable": nombres,
        "coef": betas[1:1 + len(nombres)],
    })
    return ResultadoSDM(
        rho=float(betas[-1]),
        rho_p=float(m.z_stat[-1][1]) if getattr(m, "z_stat", None) is not None else float("nan"),
        pseudo_r2=float(m.pr2),
        n=int(m.n), k=len(nombres),
        directos=directos,
        quitadas=quitadas,
    )


def moran_del_precio(coords_gdf, y: pd.Series, cfg, permutaciones: int = 999,
                     tipos: tuple[str, ...] = ("knn", "banda")):
    """
    I de Moran del precio y el W que la maximiza.

    La Fase 1 midió la estructura espacial de la ACTIVIDAD ECONÓMICA porque
    todavía no había listados. Ésta es la medición que faltaba: la del precio.
    """
    from ..features import pesos

    w, eleccion = pesos.elegir(coords_gdf, y.to_numpy(), cfg, permutaciones=199, tipos=tipos)
    I, p = pesos.moran(w, y.to_numpy(), permutaciones=permutaciones)
    eleccion.moran_I, eleccion.moran_p = I, p
    return w, eleccion
