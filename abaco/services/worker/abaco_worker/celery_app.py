"""Celery: la ejecucion pesada sale del hilo de la peticion.

Compilar es de milisegundos y se hace sincronico en la API. Ejecutar puede
tardar minutos —un XGBoost, un VAR con muchos rezagos, una matriz de pesos de
50 mil puntos— y por eso se encola.

Sin Redis a la mano, Celery corre en modo `eager`: la tarea se ejecuta en el
mismo proceso. No es lo que se quiere en produccion, pero hace que `uvicorn` a
secas sea suficiente para trabajar. Que arrancar el sistema exija levantar
cuatro contenedores es como se pierde a la gente que solo quiere probarlo.
"""

from __future__ import annotations

import os

from celery import Celery

REDIS = os.environ.get("ABACO_REDIS", "").strip()
EAGER = not REDIS

app = Celery(
    "abaco",
    broker=REDIS or "memory://",
    backend=REDIS or "cache+memory://",
    include=["abaco_worker.tareas"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Mexico_City",
    enable_utc=True,
    task_always_eager=EAGER,
    task_eager_propagates=False,
    task_time_limit=int(os.environ.get("ABACO_LIMITE_SEGUNDOS", "900")),
    task_soft_time_limit=int(os.environ.get("ABACO_LIMITE_SEGUNDOS", "900")) - 30,
    worker_max_tasks_per_child=50,      # contra fugas de memoria de las bibliotecas nativas
    worker_prefetch_multiplier=1,       # tareas largas: que no acapare una sola
)
