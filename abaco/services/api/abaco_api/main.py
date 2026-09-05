"""API de Abaco.

Reparto de responsabilidades: la API **compila** de forma sincrona (son
milisegundos, y es lo que alimenta la pestana Codigo en vivo y los subrayados
rojos del lienzo) y **encola** la ejecucion, que si puede tardar minutos.

Un grafo invalido nunca llega al worker.
"""

from __future__ import annotations

import os

from abaco_core.registry import cargar_todos
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routers import datos, ejecuciones, grafos, registro

DESCRIPCION = """
Motor de analisis economico sin codigo.

El lienzo se compila a un programa de Python legible, y ese programa es el que
se ejecuta. `POST /api/v1/grafos/codigo` devuelve exactamente el mismo codigo
que corre `POST /api/v1/ejecuciones`: no es una reconstruccion.
"""


def crear_app() -> FastAPI:
    cargar_todos()

    app = FastAPI(
        title="Abaco", version="0.1.0", description=DESCRIPCION,
        docs_url="/api/docs", openapi_url="/api/openapi.json",
    )

    origenes = [o for o in os.environ.get(
        "ABACO_ORIGENES", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o]
    app.add_middleware(
        CORSMiddleware, allow_origins=origenes, allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )

    for router in (registro.router, grafos.router, ejecuciones.router, datos.router):
        app.include_router(router, prefix="/api/v1")

    @app.get("/api/v1/salud", tags=["sistema"])
    def salud() -> dict[str, object]:
        from abaco_core.registry import REGISTRO
        from abaco_worker.celery_app import EAGER

        return {
            "ok": True,
            "herramientas": len(REGISTRO),
            "modo_ejecucion": "en proceso (sin Redis)" if EAGER else "cola Celery",
        }

    @app.exception_handler(ValueError)
    def _valor(_req, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detalle": str(exc)})

    return app


app = crear_app()
