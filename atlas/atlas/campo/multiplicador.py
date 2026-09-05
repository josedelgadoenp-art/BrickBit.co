"""
Multiplicador espacial (I − ρW)⁻¹: dónde un cambio pesa más.

Es la consecuencia práctica del ρ que midió la Fase 2. En un modelo de rezago
espacial

    y = ρ·W·y + X·β + ε        ⟹        y = (I − ρW)⁻¹ · (X·β + ε)

un cambio en UN punto no se queda en ese punto: sube el precio de sus vecinos,
que a su vez suben el de los suyos, y así en una serie que converge mientras
|ρ| < 1. La matriz (I − ρW)⁻¹ contiene ese eco completo.

FILAS Y COLUMNAS DICEN COSAS DISTINTAS, Y ES FÁCIL LEER LA EQUIVOCADA.

La **fila** i es cuánto le llega a la celda i desde todas partes. Con W
estandarizado por filas esa suma vale exactamente 1/(1 − ρ) **para todas las
celdas**, sin excepción: es una identidad algebraica, no un resultado. Un mapa
de sumas de fila sale plano por construcción y no informa de nada. (La primera
versión de este módulo reportaba justamente eso: derrame 0.275 idéntico en las
12,259 celdas.)

La **columna** j es lo que sí varía: cuánto mueve al SISTEMA ENTERO un cambio
originado en la celda j. Ahí sí importa la posición en la red — una celda que es
vecina de muchas otras empuja más lejos que una en el borde—, y es la lectura
que interesa: dónde una obra pública, un desarrollo o una estación nueva mueven
más ciudad por peso invertido.

Se reportan las dos, con el nombre correcto:
  · **propio** (la diagonal): cuánto de un cambio hecho en casa se queda en casa.
  · **influencia** (la suma de la columna): cuánto mueve ese cambio en total.

LO QUE ESTO NO ES. No es causal. ρ se estimó de un corte transversal de precios
de oferta, y un ρ positivo también aparece cuando dos vecinos comparten una
causa no observada —la misma escuela, el mismo drenaje, el mismo problema de
inseguridad— sin que uno empuje al otro. El multiplicador describe cómo se
propagaría un cambio SI el modelo de rezago fuera cierto; que lo sea es un
supuesto, y aquí se declara como tal.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Multiplicador:
    """Efectos propios y derramados de cada unidad."""

    propio: np.ndarray          # diagonal: lo que se queda en casa
    influencia: np.ndarray      # suma de columna: lo que mueve en todo el sistema
    rho: float
    total_teorico: float        # suma de FILA, idéntica para todas por construcción

    def texto(self) -> str:
        inf = self.influencia
        return (
            f"    ρ = {self.rho:.3f} → cada celda RECIBE {self.total_teorico:.3f}× "
            f"(suma de fila, idéntica para todas: es una identidad, no un hallazgo)\n"
            f"    efecto propio: mediana {np.median(self.propio):.4f} · "
            f"máximo {np.max(self.propio):.4f}\n"
            f"    INFLUENCIA (lo que mueve en el sistema): mediana {np.median(inf):.3f} · "
            f"p90 {np.percentile(inf, 90):.3f} · máxima {np.max(inf):.3f}\n"
            f"    la celda más influyente mueve {np.max(inf) / np.median(inf):.1f}× "
            f"lo que mueve la mediana"
        )

    def tabla(self, etiquetas) -> pd.DataFrame:
        return pd.DataFrame({
            "unidad": list(etiquetas),
            "efecto_propio": self.propio,
            "influencia": self.influencia,
        }).sort_values("influencia", ascending=False).reset_index(drop=True)


def calcular(w, rho: float, exacto_hasta: int = 4000) -> Multiplicador:
    """
    Efectos del multiplicador espacial.

    Con pocas unidades se invierte (I − ρW) directamente. Con muchas, invertir
    una matriz densa de n×n es inviable —12 mil celdas serían 1.1 GB sólo para
    guardarla— y se usa la serie de Neumann

        (I − ρW)⁻¹ = I + ρW + ρ²W² + ρ³W³ + …

    que converge porque |ρ| < 1 y W está estandarizado por filas. Se corta
    cuando el término nuevo deja de mover el resultado, y como ρ ≈ 0.3 eso pasa
    pronto: el término k-ésimo pesa ρᵏ, así que al octavo ya vale 0.00007.
    """
    if not -1.0 < float(rho) < 1.0:
        raise ValueError(
            f"ρ = {rho} está fuera de (−1, 1): la serie no converge y el "
            "multiplicador no existe. Un ρ así indica que el modelo espacial "
            "no convergió, no que el efecto sea enorme."
        )
    rho = float(rho)
    n = w.n
    total = 1.0 / (1.0 - rho)

    if n <= exacto_hasta:
        M = np.linalg.inv(np.eye(n) - rho * w.full()[0])
        return Multiplicador(propio=np.diag(M).copy(), influencia=M.sum(axis=0),
                             rho=rho, total_teorico=total)

    # Serie de Neumann. No hace falta la matriz entera —12 mil celdas densas
    # serían 1.1 GB— sino dos cosas: la diagonal y la suma de columnas.
    #
    # La suma de columnas se acumula con un vector fila: 1ᵀ(ρW)ᵏ = (1ᵀ(ρW)ᵏ⁻¹)·(ρW).
    # Eso es una multiplicación vector-matriz dispersa por término, no una
    # matriz-matriz, y es lo que hace viable el cálculo a esta escala.
    from scipy.sparse import identity

    S = w.sparse
    propio = np.ones(n)
    columnas = np.ones(n)
    fila_v = np.ones(n)
    Wk = identity(n, format="csr")
    for k in range(1, 60):
        fila_v = fila_v @ S
        aporte_col = rho ** k * fila_v
        columnas = columnas + aporte_col
        # La diagonal necesita las potencias de W; se cortan antes porque
        # decaen mucho más rápido (los ciclos cortos son raros en un KNN).
        if k <= 12:
            Wk = Wk @ S
            propio = propio + rho ** k * Wk.diagonal()
        if np.max(np.abs(aporte_col)) < 1e-9:
            break
    return Multiplicador(propio=propio, influencia=columnas,
                         rho=rho, total_teorico=total)
