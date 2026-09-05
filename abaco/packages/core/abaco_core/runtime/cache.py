"""Cache por huella de contenido.

    huella(nodo) = sha256(op ‖ version ‖ params ‖ [huellas de los padres] ‖ semilla)

Consecuencia practica: mover un nodo en el lienzo no invalida nada (la posicion
no entra en la huella), pero cambiar un parametro invalida ese nodo y todo lo
que esta aguas abajo, y nada mas. En un flujo con un XGBoost de cuatro minutos,
cambiar el color de una grafica al final tarda lo que tarda dibujar la grafica.
"""

from __future__ import annotations

import pickle
import shutil
import time
from pathlib import Path
from typing import Any, Protocol


class Cache(Protocol):
    def tiene(self, huella: str) -> bool: ...
    def leer(self, huella: str) -> dict[str, Any]: ...
    def escribir(self, huella: str, valores: dict[str, Any]) -> None: ...
    def limpiar(self) -> None: ...


class CacheMemoria:
    """Para pruebas y para una sola ejecucion. No sobrevive al proceso."""

    def __init__(self, tope: int = 256) -> None:
        self._d: dict[str, dict[str, Any]] = {}
        self._orden: list[str] = []
        self._tope = tope

    def tiene(self, huella: str) -> bool:
        return huella in self._d

    def leer(self, huella: str) -> dict[str, Any]:
        return dict(self._d[huella])

    def escribir(self, huella: str, valores: dict[str, Any]) -> None:
        self._d[huella] = dict(valores)
        self._orden.append(huella)
        while len(self._orden) > self._tope:
            viejo = self._orden.pop(0)
            self._d.pop(viejo, None)

    def limpiar(self) -> None:
        self._d.clear()
        self._orden.clear()


class CacheDisco:
    """Cache por sesion en disco.

    Los DataFrames van a Parquet (columnar, tipado, comprimido) y lo demas a
    pickle. Un objeto que no se puede serializar no rompe la ejecucion: se
    marca la huella como no cacheable y ese nodo se recalcula siempre.
    """

    def __init__(self, raiz: str | Path, ttl_horas: float = 24.0) -> None:
        self.raiz = Path(raiz)
        self.raiz.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_horas * 3600

    def _dir(self, huella: str) -> Path:
        return self.raiz / huella[:2] / huella

    def tiene(self, huella: str) -> bool:
        d = self._dir(huella)
        if not (d / "_ok").exists():
            return False
        if self.ttl and (time.time() - (d / "_ok").stat().st_mtime) > self.ttl:
            shutil.rmtree(d, ignore_errors=True)
            return False
        return True

    def leer(self, huella: str) -> dict[str, Any]:
        import pandas as pd

        d = self._dir(huella)
        valores: dict[str, Any] = {}
        for archivo in sorted(d.iterdir()):
            if archivo.name == "_ok":
                continue
            nombre = archivo.stem
            if archivo.suffix == ".parquet":
                valores[nombre] = pd.read_parquet(archivo)
            elif archivo.suffix == ".pkl":
                with archivo.open("rb") as fh:
                    valores[nombre] = pickle.load(fh)
        return valores

    def escribir(self, huella: str, valores: dict[str, Any]) -> None:
        import pandas as pd

        d = self._dir(huella)
        d.mkdir(parents=True, exist_ok=True)
        try:
            for nombre, valor in valores.items():
                if isinstance(valor, pd.DataFrame):
                    valor.to_parquet(d / f"{nombre}.parquet")
                elif isinstance(valor, pd.Series):
                    valor.to_frame().to_parquet(d / f"{nombre}.parquet")
                else:
                    with (d / f"{nombre}.pkl").open("wb") as fh:
                        pickle.dump(valor, fh, protocol=pickle.HIGHEST_PROTOCOL)
            (d / "_ok").write_text("1")
        except Exception:
            # No poder cachear nunca es motivo para tumbar un analisis que si corrio.
            shutil.rmtree(d, ignore_errors=True)

    def limpiar(self) -> None:
        shutil.rmtree(self.raiz, ignore_errors=True)
        self.raiz.mkdir(parents=True, exist_ok=True)


class SinCache:
    def tiene(self, huella: str) -> bool: return False
    def leer(self, huella: str) -> dict[str, Any]: return {}
    def escribir(self, huella: str, valores: dict[str, Any]) -> None: return None
    def limpiar(self) -> None: return None
