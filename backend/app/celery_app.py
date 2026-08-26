"""Instância Celery compartilhada entre a API (publica tasks) e o worker (executa).

A API importa este módulo apenas para publicar tasks (`.delay()`); ela NÃO importa
`torch`/`ml`. O worker usa `celery -A app.celery_app worker` para consumir a fila.
"""
import os

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "smartscout",
    broker=REDIS_URL,
    include=["app.modules.clips.tasks"],
)

# Sem result backend: o progresso e os resultados são gravados no DB pelos
# callbacks das tasks; o SSE lê o DB. Não usamos o resultado do Celery.
celery_app.conf.task_ignore_result = True
