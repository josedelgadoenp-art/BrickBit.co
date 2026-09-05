"""La tarea que ejecuta un grafo, con progreso por nodo."""

from __future__ import annotations

import os
import resource
import shutil
import time
from pathlib import Path
from typing import Any

from abak_core import GrafoSpec, compilar, emitir
from abak_core.registry import cargar_todos
from abak_core.runtime.almacen import ALMACEN
from abak_core.runtime.cache import CacheDisco
from abak_core.runtime.ejecutor import Ejecutor
from abak_core.nodes.fuentes.http import dir_fuentes
from abak_core.runtime.exportar import archivos_del_programa

from .celery_app import app

cargar_todos()

LIMITE_MEMORIA_GB = float(os.environ.get("ABAK_LIMITE_MEMORIA_GB", "0") or 0)


def _limitar_memoria() -> None:
    """Tope duro de memoria del proceso.

    Un usuario puede pedir, sin mala intencion, una matriz de pesos de 200 mil
    puntos y llevarse el contenedor por delante. Con el limite, el proceso
    recibe MemoryError, el traductor de errores lo convierte en «el analisis no
    cabe en memoria» y el resto de las ejecuciones siguen vivas.
    """
    if LIMITE_MEMORIA_GB <= 0:
        return
    tope = int(LIMITE_MEMORIA_GB * 1024**3)
    try:
        suave, duro = resource.getrlimit(resource.RLIMIT_AS)
        resource.setrlimit(resource.RLIMIT_AS, (tope, duro if duro > 0 else tope))
    except (ValueError, OSError):
        pass  # en algunos entornos no se puede; no es motivo para no ejecutar


@app.task(name="abak.ejecutar_grafo", bind=True)
def ejecutar_grafo(self: Any, ejecucion_id: str, grafo_json: dict[str, Any],
                   objetivo: str | None = None) -> dict[str, Any]:
    _limitar_memoria()
    inicio = time.time()
    ALMACEN.actualizar_ejecucion(ejecucion_id, estado="corriendo", iniciado=inicio)

    grafo = GrafoSpec.model_validate(grafo_json)
    programa = compilar(grafo, objetivo=objetivo)

    if programa.hay_errores:
        ALMACEN.actualizar_ejecucion(
            ejecucion_id, estado="error", terminado=time.time(),
            diagnosticos=[d.model_dump() for d in programa.diagnosticos],
            bitacora=[f"{d.codigo}: {d.mensaje}" for d in programa.diagnosticos])
        return {"ok": False}

    # Los archivos que el programa lee se juntan en una carpeta por ejecucion, y
    # esa carpeta es la que ve el codigo generado a traves de RUTA_DATOS. Asi el
    # script no sabe nada de como Abak guarda las cosas.
    dir_datos = ALMACEN.dir_salida(ejecucion_id) / "datos"
    dir_datos.mkdir(parents=True, exist_ok=True)
    for destino, origen in archivos_del_programa(programa).items():
        ruta = dir_datos / Path(destino).relative_to("datos")
        ruta.parent.mkdir(parents=True, exist_ok=True)
        if os.path.exists(origen) and not ruta.exists():
            ruta.write_bytes(Path(origen).read_bytes())
    os.environ["ABAK_DATOS"] = str(dir_datos)
    os.environ["ABAK_SALIDA"] = str(ALMACEN.dir_salida(ejecucion_id))

    emision = emitir(programa)

    ejecutor = Ejecutor(
        cache=CacheDisco(ALMACEN.dir_cache()),
        progreso=lambda nodo, estado, detalle: ALMACEN.progreso_nodo(
            ejecucion_id, nodo, estado, detalle),
        cancelado=lambda: ALMACEN.cancelacion_pedida(ejecucion_id),
    )
    resultado = ejecutor.ejecutar(programa, emision)

    # Lo que se haya descargado en esta corrida pasa a la caché global de
    # fuentes: la siguiente ejecución (y la exportación) ya no lo vuelven a
    # pedir, que es justo lo que hace reproducible un análisis con datos en vivo.
    _guardar_fuentes(dir_datos / "fuentes")

    ALMACEN.actualizar_ejecucion(
        ejecucion_id,
        estado="listo" if resultado.ok else ("cancelado" if ALMACEN.cancelacion_pedida(ejecucion_id) else "error"),
        terminado=time.time(), ms_total=resultado.ms_total,
        bitacora=resultado.bitacora[-400:],
        diagnosticos=[d.model_dump() for d in programa.diagnosticos],
        nodos={
            n.nodo_id: {
                "estado": n.estado, "ms": n.ms, "etiqueta": n.etiqueta, "op": n.op,
                "artefactos": n.artefactos,
                "error": None if n.error is None else {
                    "titulo": n.error.titulo, "detalle": n.error.detalle,
                    "sugerencia": n.error.sugerencia, "excepcion": n.error.excepcion,
                    "traceback": n.error.traceback,
                },
            } for n in resultado.nodos
        },
    )
    return {"ok": resultado.ok, "ms": resultado.ms_total}


def _guardar_fuentes(origen: Path) -> None:
    """Copia la caché de fuentes de una corrida a la caché global."""
    if not origen.is_dir():
        return
    destino = dir_fuentes()
    destino.mkdir(parents=True, exist_ok=True)
    for archivo in origen.glob("*.json"):
        objetivo = destino / archivo.name
        if not objetivo.exists():
            try:
                shutil.copy2(archivo, objetivo)
            except OSError:
                pass  # no poder cachear nunca tumba un análisis que sí corrió
