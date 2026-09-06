"""Contratos del grafo: lo que viaja del lienzo al backend.

React Flow manda mucho ruido visual (`selected`, `dragging`, `style`, handles
internos). El contrato se queda **sólo con lo semántico**, más la posición, que
es lo único visual que hay que persistir para volver a dibujar el lienzo.

Que el contrato sea `GrafoSpec` y no "lo que mande React Flow" es lo que
permite cambiar de biblioteca de lienzo sin tocar una línea del backend.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

VERSION_ESQUEMA = "1"


class Posicion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    x: float = 0.0
    y: float = 0.0


class NodoSpec(BaseModel):
    """Un bloque del lienzo."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=64)
    op: str = Field(min_length=1, max_length=120)
    etiqueta: str | None = Field(default=None, max_length=120)
    params: dict[str, Any] = Field(default_factory=dict)
    posicion: Posicion = Field(default_factory=Posicion)
    notas: str | None = Field(default=None, max_length=2000)

    @field_validator("id")
    @classmethod
    def _id_limpio(cls, v: str) -> str:
        if not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError("El id de un nodo solo admite letras, numeros, '-' y '_'")
        return v


class AristaSpec(BaseModel):
    """Una conexion entre el puerto de salida de un nodo y el de entrada de otro."""

    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    origen: str
    puerto_origen: str = "salida"
    destino: str
    puerto_destino: str = "entrada"

    def clave(self) -> tuple[str, str, str, str]:
        return (self.origen, self.puerto_origen, self.destino, self.puerto_destino)


class GrafoSpec(BaseModel):
    """El documento completo: la topologia mas los metadatos de la sesion."""

    model_config = ConfigDict(extra="ignore")

    version_esquema: Literal["1"] = VERSION_ESQUEMA
    titulo: str = Field(default="Analisis sin titulo", max_length=200)
    nodos: list[NodoSpec] = Field(default_factory=list)
    aristas: list[AristaSpec] = Field(default_factory=list)
    semilla: int = Field(default=42, ge=0, le=2**31 - 1)

    def nodo(self, nodo_id: str) -> NodoSpec | None:
        return next((n for n in self.nodos if n.id == nodo_id), None)

    def entrantes(self, nodo_id: str) -> list[AristaSpec]:
        return [a for a in self.aristas if a.destino == nodo_id]

    def salientes(self, nodo_id: str) -> list[AristaSpec]:
        return [a for a in self.aristas if a.origen == nodo_id]

    def huella(self) -> str:
        """sha256 de la topologia, ignorando posiciones.

        Mover un nodo en el lienzo no cambia el analisis, asi que no debe
        invalidar nada. Esta huella se escribe en el encabezado del script
        exportado para poder rastrear de que grafo salio.
        """
        canonico = {
            "version": self.version_esquema,
            "semilla": self.semilla,
            "nodos": sorted(
                ({"id": n.id, "op": n.op, "params": n.params} for n in self.nodos),
                key=lambda d: d["id"],
            ),
            "aristas": sorted(a.clave() for a in self.aristas),
        }
        crudo = json.dumps(canonico, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(crudo.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Esquema de tabla: lo que el compilador propaga por el DAG
# ---------------------------------------------------------------------------


class Columna(BaseModel):
    """Una columna, tal como el compilador la conoce *antes* de ejecutar nada.

    `es_estimado` es la marca que viaja por todo el grafo: una columna que salio
    de un pronostico contamina lo que toca, y la interfaz la pinta en ambar
    hasta en la tabla final. El principio de la casa -un dato estimado nunca se
    presenta como hecho- deja de depender de que alguien se acuerde de marcarlo.
    """

    model_config = ConfigDict(extra="ignore")

    nombre: str
    tipo: Literal["numerica", "categorica", "fecha", "booleana", "texto", "geometria"] = "numerica"
    es_estimado: bool = False
    fuente: str | None = None
    nota: str | None = None


class Esquema(BaseModel):
    """El esquema de una tabla en un punto del grafo."""

    model_config = ConfigDict(extra="ignore")

    columnas: list[Columna] = Field(default_factory=list)
    indice_temporal: str | None = None
    id_entidad: str | None = None
    n_filas: int | None = None

    def nombres(self) -> list[str]:
        return [c.nombre for c in self.columnas]

    def get(self, nombre: str) -> Columna | None:
        return next((c for c in self.columnas if c.nombre == nombre), None)

    def tiene(self, nombre: str) -> bool:
        return self.get(nombre) is not None

    def numericas(self) -> list[str]:
        return [c.nombre for c in self.columnas if c.tipo == "numerica"]

    def hay_estimados(self, nombres: list[str]) -> bool:
        return any((c := self.get(n)) is not None and c.es_estimado for n in nombres)

    def con(self, *nuevas: Columna, quitar: list[str] | None = None, **cambios: Any) -> "Esquema":
        """Copia con columnas agregadas o quitadas. Las nuevas pisan a las viejas del mismo nombre."""
        fuera = set(quitar or [])
        pisadas = {c.nombre for c in nuevas}
        base = [c for c in self.columnas if c.nombre not in fuera and c.nombre not in pisadas]
        datos = self.model_dump()
        datos["columnas"] = [c.model_dump() for c in base + list(nuevas)]
        datos.update(cambios)
        return Esquema.model_validate(datos)

    @staticmethod
    def de_dataframe(df: Any, fuente: str | None = None) -> "Esquema":
        """Deduce el esquema de un DataFrame ya materializado."""
        import pandas as pd

        def clasificar(s: Any) -> str:
            if pd.api.types.is_datetime64_any_dtype(s):
                return "fecha"
            if pd.api.types.is_bool_dtype(s):
                return "booleana"
            if pd.api.types.is_numeric_dtype(s):
                return "numerica"
            if isinstance(s.dtype, pd.CategoricalDtype):
                return "categorica"
            return "texto"

        cols = [Columna(nombre=str(c), tipo=clasificar(df[c]), fuente=fuente) for c in df.columns]
        indice = None
        if isinstance(df.index, (pd.DatetimeIndex, pd.PeriodIndex)):
            indice = df.index.name or "__indice__"
        entidad = None
        if isinstance(df.index, pd.MultiIndex) and df.index.nlevels >= 2:
            entidad = df.index.names[0]
            indice = df.index.names[1]
        return Esquema(columnas=cols, indice_temporal=indice, id_entidad=entidad, n_filas=int(len(df)))
