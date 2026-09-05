"""
Índice temporal de precios: el panel SHF.

Es la ÚNICA fuente temporal que el Atlas tiene hoy, y conviene entender
exactamente qué es y qué no es antes de apoyarse en ella.

QUÉ ES. El Índice de Precios de la Vivienda de la Sociedad Hipotecaria Federal,
promedio anual por estado, 2005-2026: 32 zonas × 22 años. Se construye con los
avalúos de las viviendas con crédito hipotecario garantizado, así que mide
**transacciones reales**, no ofertas. Eso lo hace complementario de los listados
de la Fase 2, que son precios de oferta: uno tiene la profundidad temporal que al
otro le falta, y el otro tiene el detalle espacial que a éste le falta.

QUÉ NO ES. Es ESTATAL. Para la CDMX hay una sola serie, no una por alcaldía ni
por colonia. Así que sirve para saber cómo se ha movido la ciudad entera, y no
sirve para saber qué barrio se movió más. Esa segunda pregunta necesita listados
repetidos en el tiempo, y hoy sólo hay una captura.

Y ES NOMINAL. Un 7.7% de crecimiento anual mediano no es 7.7% de plusvalía real:
en México la inflación de esos años se comió una parte grande. El módulo puede
deflactar si se le pasa una serie de INPC; mientras no la haya, las cifras se
declaran como nominales en vez de dejar que alguien las lea como reales.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..config import Config, cargar


@dataclass
class Panel:
    """El panel SHF listo para modelar: zonas × años."""

    nivel: pd.DataFrame          # índice, filas = año, columnas = zona
    crecimiento: pd.DataFrame    # log-diferencias anuales
    coords: pd.DataFrame         # lat/lng por zona, para el W de la difusión
    fuente: str
    real: bool = False           # ¿está deflactado?

    @property
    def anios(self) -> list[int]:
        return list(self.nivel.index)

    def texto(self) -> str:
        g = self.crecimiento.stack().dropna() * 100
        etiqueta = "real" if self.real else "NOMINAL"
        return (
            f"    {self.nivel.shape[1]} zonas × {self.nivel.shape[0]} años "
            f"({self.anios[0]}–{self.anios[-1]})\n"
            f"    crecimiento anual {etiqueta}: mediana {g.median():.2f}% · "
            f"rango {g.min():.1f}% a {g.max():.1f}%"
        )


def cargar_panel(cfg: Config | None = None, inpc: pd.Series | None = None) -> Panel:
    """
    Lee `data/shf_series.json` y `data/estados.json` y arma el panel.

    `inpc` deflacta si se le pasa (índice anual con el mismo año base). Si no se
    pasa, el panel queda en términos nominales y `real` lo declara: es la
    diferencia entre "la vivienda subió 7.7%" y "la vivienda subió 7.7% más que
    todo lo demás", que no son lo mismo ni de lejos.
    """
    cfg = cfg or cargar()
    raiz = cfg.ruta("raiz_datos_repo")

    with open(raiz / "shf_series.json", encoding="utf-8") as fh:
        bruto = json.load(fh)
    series = bruto["series"]
    fuente = bruto.get("meta", {}).get("fuente", "SHF")

    nivel = pd.DataFrame(
        {zona: {int(a): float(v) for a, v in datos.items()} for zona, datos in series.items()}
    ).sort_index()

    with open(raiz / "estados.json", encoding="utf-8") as fh:
        estados = json.load(fh)["estados"]
    coords = pd.DataFrame(
        [{"zona": e["nombre"], "lat": float(e["lat"]), "lng": float(e["lng"])} for e in estados]
    ).set_index("zona")
    # Sólo zonas presentes en las dos fuentes, y en orden estable.
    comunes = sorted(set(nivel.columns) & set(coords.index))
    nivel = nivel[comunes]
    coords = coords.loc[comunes]

    real = False
    if inpc is not None:
        d = inpc.reindex(nivel.index)
        if d.notna().all():
            nivel = nivel.div(d, axis=0) * float(d.iloc[-1])
            real = True

    # Log-diferencias: son la tasa compuesta y se suman a lo largo del tiempo,
    # que es lo que hace falta para acumular horizontes sin componer a mano.
    crecimiento = np.log(nivel).diff()

    return Panel(nivel=nivel, crecimiento=crecimiento, coords=coords,
                 fuente=fuente, real=real)


def resumen_zona(panel: Panel, zona: str = "Ciudad de México") -> pd.DataFrame:
    """Nivel y crecimiento de una zona, año por año."""
    if zona not in panel.nivel.columns:
        raise KeyError(f"{zona} no está en el panel. Hay: {list(panel.nivel.columns)[:5]}…")
    return pd.DataFrame({
        "indice": panel.nivel[zona],
        "crec_%": panel.crecimiento[zona] * 100,
    })


def acumulado(panel: Panel, zona: str, desde: int, hasta: int) -> float:
    """
    Cuánto acumuló una zona entre dos años, en veces.

    Se lee directo del índice y no se compone desde la tasa media: componer una
    media de tasas anuales da un número distinto —y siempre optimista— cuando la
    serie tiene años malos, porque la media aritmética de tasas no es la tasa
    media geométrica.
    """
    s = panel.nivel[zona]
    return float(s.loc[hasta] / s.loc[desde])
