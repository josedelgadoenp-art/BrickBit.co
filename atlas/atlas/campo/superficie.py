"""
Superficie continua de precio y su gradiente.

Los listados son puntos sueltos y desiguales: cientos en Benito Juárez, cuatro
en Milpa Alta. La superficie los convierte en un campo continuo sobre toda la
ciudad, con una virtud que un mapa de puntos no tiene: **dice también cuánto no
sabe**. En las zonas sin comparables la incertidumbre se dispara, y eso es una
respuesta, no un hueco.

SE USA UN PROCESO GAUSSIANO, que es kriging con otro nombre. La equivalencia no
es casual: el kriging ordinario de la geoestadística y la regresión por proceso
gaussiano con kernel estacionario son el mismo estimador. Se implementa con
scikit-learn porque ya está instalado y porque da la desviación estándar
posterior sin trabajo extra.

EL KERNEL ES MATÉRN CON ν=1.5, no el gaussiano (RBF). El RBF supone que la
superficie es infinitamente diferenciable, o sea absurdamente suave: los precios
inmobiliarios cambian de golpe al cruzar una avenida o el borde de una colonia, y
un kernel demasiado suave difumina exactamente esos bordes, que son lo
interesante. Matérn ν=1.5 admite una superficie continua y una vez diferenciable,
que es lo que se necesita para calcular el gradiente sin inventar suavidad.

EL GRADIENTE ∇p es lo que el documento llama las "flechas": hacia dónde y con
qué fuerza sube el precio desde cada punto. Como la superficie está en logaritmo,
el gradiente se lee en **por ciento por kilómetro**, que es directamente
interpretable: "moviéndote 1 km hacia el poniente, el precio por m² sube 12%".

Y NO ES UN CAMPO DE CRECIMIENTO. Es la pendiente del precio ACTUAL en el
espacio, no su cambio en el tiempo. Que un lugar esté al pie de una pendiente
pronunciada sugiere que hay un diferencial que el mercado podría cerrar, pero
sugerir no es medir. El crecimiento por celda necesita dos capturas separadas en
el tiempo y hoy sólo hay una.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..config import Config, cargar

# Máximo de puntos para ajustar el GP. El coste es O(n³) en el ajuste, y por
# encima de unos miles deja de compensar: la superficie ya no cambia y la espera
# sí. Se muestrea con la semilla del proyecto para que sea reproducible.
MAXIMO_AJUSTE = 3000


@dataclass
class Superficie:
    """El campo de precio evaluado sobre la malla."""

    valores: np.ndarray          # ln(precio/m²) predicho por celda
    sigma: np.ndarray            # incertidumbre TOTAL (nivel + ruido de anuncio)
    sigma_nivel: np.ndarray      # sólo la del nivel: qué tan bien se conoce la zona
    grad_x: np.ndarray           # ∂ln(p)/∂x, por metro
    grad_y: np.ndarray
    escala_m: float              # longitud característica aprendida
    ruido: float                 # varianza del ruido de anuncio

    @property
    def pendiente_pct_km(self) -> np.ndarray:
        """Magnitud del gradiente en % por kilómetro."""
        return np.hypot(self.grad_x, self.grad_y) * 1000.0 * 100.0

    @property
    def rumbo(self) -> np.ndarray:
        """Hacia dónde sube el precio, en grados desde el norte."""
        return (np.degrees(np.arctan2(self.grad_x, self.grad_y)) + 360.0) % 360.0

    def texto(self) -> str:
        p = self.pendiente_pct_km
        return (
            f"    escala característica {self.escala_m / 1000:.2f} km\n"
            f"    incertidumbre del NIVEL de la zona: mediana ±"
            f"{np.median(self.sigma_nivel) * 100:.0f}% · máxima ±"
            f"{np.max(self.sigma_nivel) * 100:.0f}%\n"
            f"    dispersión entre anuncios de una misma zona: ±"
            f"{np.sqrt(self.ruido) * 100:.0f}%  (irreducible con estos datos)\n"
            f"    pendiente del precio: mediana {np.median(p):.1f}%/km · "
            f"percentil 90 {np.percentile(p, 90):.1f}%/km"
        )


def ajustar(
    xy: np.ndarray,
    y: np.ndarray,
    cfg: Config | None = None,
    escala_inicial_m: float = 3000.0,
):
    """
    Ajusta el proceso gaussiano sobre coordenadas MÉTRICAS.

    Métricas y no grados: el kernel mide distancias, y en grados un kilómetro
    norte-sur y uno este-oeste no valen lo mismo. La escala se aprende de los
    datos por máxima verosimilitud, acotada entre 300 m —por debajo, el modelo
    interpola ruido de anuncio— y 30 km, que es más que la ciudad.
    """
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel

    cfg = cfg or cargar()
    rng = np.random.default_rng(int(cfg.semilla))
    if len(y) > MAXIMO_AJUSTE:
        sel = rng.choice(len(y), MAXIMO_AJUSTE, replace=False)
        xy, y = xy[sel], y[sel]

    centro = xy.mean(axis=0)
    media = float(np.mean(y))
    kernel = (
        ConstantKernel(np.var(y), (1e-3, 1e3))
        * Matern(length_scale=escala_inicial_m, length_scale_bounds=(300.0, 30000.0), nu=1.5)
        # El WhiteKernel es el que impide que la superficie pase por cada punto:
        # dos departamentos del mismo edificio tienen precios distintos y eso es
        # ruido de anuncio, no estructura espacial. Sin él, el GP interpola ese
        # ruido y el gradiente sale lleno de picos falsos.
        + WhiteKernel(noise_level=0.1, noise_level_bounds=(1e-3, 1.0))
    )
    gp = GaussianProcessRegressor(
        kernel=kernel, normalize_y=False, n_restarts_optimizer=1,
        random_state=int(cfg.semilla),
    )
    gp.fit(xy - centro, y - media)
    return gp, centro, media


def evaluar(gp, centro: np.ndarray, media: float, xy: np.ndarray,
            paso_m: float = 250.0) -> Superficie:
    """
    Evalúa la superficie y su gradiente sobre unos puntos.

    El gradiente se calcula por diferencias centradas: se pregunta al GP el
    valor a `paso_m` a cada lado en cada eje. Se podría derivar el kernel
    analíticamente, pero las diferencias centradas sobre una superficie ya
    suavizada dan lo mismo con mucho menos código que mantener, y el paso de
    250 m es más chico que la escala que el modelo aprende.
    """
    z = xy - centro
    val, sig = gp.predict(z, return_std=True)

    def en(dx, dy):
        return gp.predict(z + np.array([dx, dy]))

    grad_x = (en(paso_m, 0) - en(-paso_m, 0)) / (2 * paso_m)
    grad_y = (en(0, paso_m) - en(0, -paso_m)) / (2 * paso_m)

    k = gp.kernel_
    escala, ruido = np.nan, np.nan
    for p, v in k.get_params().items():
        if p.endswith("length_scale") and np.isscalar(v):
            escala = float(v)
        if p.endswith("noise_level") and np.isscalar(v):
            ruido = float(v)

    # LA SIGMA DE SKLEARN INCLUYE EL RUIDO DE ANUNCIO, y confundir las dos hace
    # que la superficie parezca inútil. Comprobado: con un WhiteKernel de 0.0785
    # la sigma devuelta era 0.281 y la del nivel 0.024-0.054, un orden de
    # magnitud menos. Son preguntas distintas:
    #   · sigma        ¿cuánto puede valer ESTE anuncio concreto?
    #   · sigma_nivel  ¿cuánto vale el m² TÍPICO de esta zona?
    # La segunda es la que interesa para un mapa, y es la que se conoce bien.
    # La primera incluye la variación entre dos departamentos de la misma
    # cuadra, que es real y no baja por poner más modelo.
    nivel = np.sqrt(np.maximum(np.asarray(sig, float) ** 2 - float(ruido), 0.0))
    return Superficie(
        valores=val + media, sigma=sig, sigma_nivel=nivel,
        grad_x=grad_x, grad_y=grad_y, escala_m=escala, ruido=ruido,
    )


def frontera(precios_log: np.ndarray, w, umbral: float = 0.05) -> pd.DataFrame:
    """
    Dónde el precio va MUY por debajo del de su vecindario.

    Es el cuadrante bajo-alto del LISA, y es la lectura de negocio de la fase:
    un punto barato rodeado de caros es donde el diferencial tiene recorrido.

    ⚠ SE CALCULA SOBRE LOS LISTADOS, NO SOBRE LA SUPERFICIE SUAVIZADA. La
    primera versión se lo aplicaba al proceso gaussiano y devolvía CERO celdas
    en toda la ciudad —lo cual parecía decir "no hay oportunidad en la CDMX"
    cuando en realidad era imposible por construcción—: con una escala
    característica de 6.66 km, dos celdas vecinas a 174 m tienen valores casi
    idénticos, así que una superficie suave no puede contener un hoyo local.
    Suavizar es exactamente borrar lo que esta función busca.

    Se declara como lo que es: un diferencial PRESENTE, no una plusvalía futura.
    Que el mercado lo cierre depende de POR QUÉ está abierto, y esa razón puede
    ser una barrera física, un uso de suelo o una diferencia real de calidad que
    ninguna de estas variables ve.
    """
    from ..features.pesos import lisa

    y = np.asarray(precios_log, float)
    cl = lisa(w, y, permutaciones=999)
    cl["brecha"] = np.asarray(w.sparse @ y) - y
    cl["es_frontera"] = (cl["lisa_cuadrante"] == "BA") & (cl["lisa_p"] < umbral)
    return cl
