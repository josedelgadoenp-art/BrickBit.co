"""
Métricas de punto y de intervalo.

Dos familias, y la segunda importa más que la primera.

EL ERROR PUNTUAL se reporta en pesos por m², no en logaritmos. Un R² de 0.82
sobre ln(precio/m²) no le dice nada a nadie; "la mitad de las valuaciones se
equivoca menos de 12%" sí. Se usa la mediana del error porcentual absoluto
(MdAPE) además de la media (MAPE) porque unos pocos anuncios con el precio mal
capturado arrastran la media y darían una impresión peor que la real.

LA COBERTURA es la métrica que decide si el sistema sirve. Un intervalo del 95%
que cubre 78% no es un intervalo del 95%: es un número inventado con dos barras.
Se reporta la cobertura global y la de cada segmento, porque una global correcta
puede esconder segmentos rotos.

RETRANSFORMACIÓN. Al deshacer el logaritmo, exp(ŷ) NO es la media del precio
sino su MEDIANA: para la media haría falta exp(ŷ + σ²/2), y ese ajuste supone
errores log-normales homocedásticos, que aquí no se cumple. Se reporta la
mediana y se dice que es la mediana. Es lo correcto para valuación, además: la
pregunta del mercado es "cuál es el precio típico de un inmueble así", no "cuál
es su valor esperado bajo un supuesto distribucional".
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Punto:
    n: int
    r2_log: float
    mae_pct: float
    mdape_pct: float
    dentro_10_pct: float
    dentro_20_pct: float

    def texto(self) -> str:
        return (
            f"    n={self.n:,}  ·  R²(log)={self.r2_log:.3f}\n"
            f"    error porcentual: mediana {self.mdape_pct:.1f}%  ·  media {self.mae_pct:.1f}%\n"
            f"    dentro de ±10%: {self.dentro_10_pct:.1f}%  ·  dentro de ±20%: {self.dentro_20_pct:.1f}%"
        )


def punto(y_log: np.ndarray, pred_log: np.ndarray) -> Punto:
    """Error en la escala de pesos, aunque el modelo viva en logaritmos."""
    y_log = np.asarray(y_log, float)
    pred_log = np.asarray(pred_log, float)
    ok = np.isfinite(y_log) & np.isfinite(pred_log)
    y_log, pred_log = y_log[ok], pred_log[ok]

    real, est = np.exp(y_log), np.exp(pred_log)
    ape = np.abs(est - real) / real * 100.0
    ss_res = float(np.sum((y_log - pred_log) ** 2))
    ss_tot = float(np.sum((y_log - y_log.mean()) ** 2))
    return Punto(
        n=len(y_log),
        r2_log=1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
        mae_pct=float(np.mean(ape)),
        mdape_pct=float(np.median(ape)),
        dentro_10_pct=float(np.mean(ape <= 10) * 100),
        dentro_20_pct=float(np.mean(ape <= 20) * 100),
    )


@dataclass
class Intervalo:
    n: int
    objetivo: float
    cobertura: float
    ancho_mediano_pct: float
    por_grupo: pd.DataFrame

    def cumple(self, holgura: float = 0.02) -> bool:
        """Cubre lo prometido, con una holgura por el ruido de muestreo."""
        return self.cobertura >= self.objetivo - holgura

    def texto(self) -> str:
        marca = "✓" if self.cumple() else "✗"
        t = [
            f"    {marca} cobertura {self.cobertura * 100:.1f}%  (objetivo {self.objetivo * 100:.0f}%)",
            f"    ancho mediano: ±{self.ancho_mediano_pct:.1f}% del valor estimado",
        ]
        if not self.por_grupo.empty:
            t.append("    por segmento:")
            for r in self.por_grupo.itertuples():
                m = "✓" if r.cobertura >= self.objetivo - 0.05 else "✗"
                t.append(
                    f"      {m} {r.grupo:<22} {r.cobertura * 100:5.1f}%  "
                    f"±{r.ancho_pct:4.1f}%   n={r.n:,}"
                )
        return "\n".join(t)


def intervalo(
    y_log: np.ndarray,
    lo_log: np.ndarray,
    hi_log: np.ndarray,
    alpha: float,
    grupos: pd.Series | None = None,
) -> Intervalo:
    """
    Cobertura empírica y ancho. El ancho se expresa como porcentaje del valor
    estimado —el punto medio geométrico del intervalo— porque ±350,000 pesos
    significa cosas muy distintas en Iztapalapa y en Polanco.
    """
    y_log = np.asarray(y_log, float)
    lo_log = np.asarray(lo_log, float)
    hi_log = np.asarray(hi_log, float)
    ok = np.isfinite(y_log) & np.isfinite(lo_log) & np.isfinite(hi_log)

    dentro = (y_log >= lo_log) & (y_log <= hi_log)
    centro = np.exp((lo_log + hi_log) / 2.0)
    ancho_pct = (np.exp(hi_log) - np.exp(lo_log)) / (2.0 * centro) * 100.0

    filas = []
    if grupos is not None:
        g = pd.Series(grupos).astype(str).to_numpy()
        for nombre in sorted(pd.unique(g[ok])):
            s = ok & (g == nombre)
            if not s.any():
                continue
            filas.append({
                "grupo": nombre,
                "n": int(s.sum()),
                "cobertura": float(dentro[s].mean()),
                "ancho_pct": float(np.median(ancho_pct[s])),
            })

    return Intervalo(
        n=int(ok.sum()),
        objetivo=1.0 - float(alpha),
        cobertura=float(dentro[ok].mean()) if ok.any() else float("nan"),
        ancho_mediano_pct=float(np.median(ancho_pct[ok])) if ok.any() else float("nan"),
        por_grupo=pd.DataFrame(filas).sort_values("n", ascending=False) if filas else pd.DataFrame(),
    )
