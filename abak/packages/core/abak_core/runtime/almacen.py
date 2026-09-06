"""Almacen de sesion: grafos, ejecuciones, archivos subidos y artefactos.

Vive en el nucleo (y no en la API) porque el worker tambien lo necesita y
porque no tiene ninguna dependencia web: es sistema de archivos y JSON.

Esta implementacion es la de desarrollo: todo cae en `.abak/`. En produccion
los grafos van a Postgres (JSONB versionado), los datasets a un almacen de
objetos y el estado de ejecucion a Redis; el contrato de esta clase es el que
esas implementaciones tienen que cumplir.
"""

from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any


def _ahora() -> float:
    return time.time()


class Almacen:
    def __init__(self, raiz: str | Path | None = None) -> None:
        self.raiz = Path(raiz or os.environ.get("ABAK_INICIO", ".abak")).resolve()
        for sub in ("grafos", "ejecuciones", "subidas", "cache", "salidas"):
            (self.raiz / sub).mkdir(parents=True, exist_ok=True)

    # -- grafos ---------------------------------------------------------------

    def guardar_grafo(self, grafo: dict[str, Any], grafo_id: str | None = None) -> str:
        grafo_id = grafo_id or f"g_{uuid.uuid4().hex[:12]}"
        destino = self.raiz / "grafos" / f"{grafo_id}.json"
        historial = self.raiz / "grafos" / grafo_id
        if destino.exists():
            # Versionado simple: la version anterior no se pierde al guardar.
            historial.mkdir(exist_ok=True)
            shutil.copy(destino, historial / f"{int(_ahora())}.json")
        destino.write_text(json.dumps({"id": grafo_id, "actualizado": _ahora(), "grafo": grafo},
                                      ensure_ascii=False), encoding="utf-8")
        return grafo_id

    def leer_grafo(self, grafo_id: str) -> dict[str, Any] | None:
        ruta = self.raiz / "grafos" / f"{grafo_id}.json"
        if not ruta.exists():
            return None
        return json.loads(ruta.read_text(encoding="utf-8"))

    def listar_grafos(self, limite: int = 50) -> list[dict[str, Any]]:
        salida = []
        for ruta in sorted((self.raiz / "grafos").glob("*.json"),
                           key=lambda p: p.stat().st_mtime, reverse=True)[:limite]:
            doc = json.loads(ruta.read_text(encoding="utf-8"))
            salida.append({"id": doc["id"], "actualizado": doc["actualizado"],
                           "titulo": doc["grafo"].get("titulo", "Sin titulo"),
                           "nodos": len(doc["grafo"].get("nodos", []))})
        return salida

    # -- ejecuciones ----------------------------------------------------------

    def nueva_ejecucion(self, grafo: dict[str, Any]) -> str:
        ejecucion_id = f"e_{uuid.uuid4().hex[:12]}"
        self.escribir_ejecucion(ejecucion_id, {
            "id": ejecucion_id, "estado": "en_cola", "creado": _ahora(),
            "grafo": grafo, "nodos": {}, "bitacora": [], "ms_total": None,
        })
        return ejecucion_id

    def escribir_ejecucion(self, ejecucion_id: str, doc: dict[str, Any]) -> None:
        ruta = self.raiz / "ejecuciones" / f"{ejecucion_id}.json"
        tmp = ruta.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(ruta)  # atomico: la interfaz consulta mientras el worker escribe

    def leer_ejecucion(self, ejecucion_id: str) -> dict[str, Any] | None:
        ruta = self.raiz / "ejecuciones" / f"{ejecucion_id}.json"
        if not ruta.exists():
            return None
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def actualizar_ejecucion(self, ejecucion_id: str, **cambios: Any) -> dict[str, Any] | None:
        doc = self.leer_ejecucion(ejecucion_id)
        if doc is None:
            return None
        doc.update(cambios)
        self.escribir_ejecucion(ejecucion_id, doc)
        return doc

    def progreso_nodo(self, ejecucion_id: str, nodo_id: str, estado: str,
                      detalle: dict[str, Any] | None = None) -> None:
        doc = self.leer_ejecucion(ejecucion_id)
        if doc is None:
            return
        doc.setdefault("nodos", {})[nodo_id] = {"estado": estado, **(detalle or {})}
        self.escribir_ejecucion(ejecucion_id, doc)

    def pedir_cancelacion(self, ejecucion_id: str) -> bool:
        doc = self.leer_ejecucion(ejecucion_id)
        if doc is None or doc["estado"] in ("listo", "error", "cancelado"):
            return False
        self.actualizar_ejecucion(ejecucion_id, cancelar=True)
        return True

    def cancelacion_pedida(self, ejecucion_id: str) -> bool:
        doc = self.leer_ejecucion(ejecucion_id)
        return bool(doc and doc.get("cancelar"))

    # -- archivos subidos -----------------------------------------------------

    def guardar_subida(self, nombre: str, contenido: bytes) -> dict[str, Any]:
        archivo_id = f"a_{uuid.uuid4().hex[:12]}"
        carpeta = self.raiz / "subidas" / archivo_id
        carpeta.mkdir(parents=True, exist_ok=True)
        limpio = Path(nombre).name  # nunca se confia en la ruta que manda el cliente
        (carpeta / limpio).write_bytes(contenido)
        return {"archivo_id": archivo_id, "nombre": limpio, "bytes": len(contenido)}

    def ruta_subida(self, archivo_id: str, nombre: str) -> Path:
        return self.raiz / "subidas" / archivo_id / Path(nombre).name

    def dir_datos(self, archivo_id: str) -> Path:
        return self.raiz / "subidas" / archivo_id

    def dir_subidas(self) -> Path:
        """Donde viven los archivos convertidos a Parquet."""
        d = self.raiz / "subidas"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # -- caches y salidas -----------------------------------------------------

    def dir_cache(self) -> Path:
        return self.raiz / "cache"

    def dir_salida(self, ejecucion_id: str) -> Path:
        d = self.raiz / "salidas" / ejecucion_id
        d.mkdir(parents=True, exist_ok=True)
        return d


ALMACEN = Almacen()
