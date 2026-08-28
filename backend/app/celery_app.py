"""Instância Celery compartilhada entre a API (publica tasks) e o worker (executa).

A API importa este módulo apenas para publicar tasks (`.delay()`); ela NÃO importa
`torch`/`ml`. O worker usa `celery -A app.celery_app worker` para consumir a fila.
"""
import os

from celery import Celery

# Registro dos mappers: este modulo e o entrypoint do worker (equivalente ao
# main.py da API). Relationships referenciam classes por string (ex.: Video.user
# -> "User"), e o SQLAlchemy so resolve nomes de classes efetivamente importadas.
# A API registra tudo via routers; o worker precisa importar aqui, senao qualquer
# task que toque o banco falha com "expression 'User' failed to locate a name".
from app.modules.identity import models as _identity_models  # noqa: F401
from app.modules.clips import models as _clips_models  # noqa: F401

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "smartscout",
    broker=REDIS_URL,
    include=["app.modules.clips.tasks"],
)

# Sem result backend: o progresso e os resultados são gravados no DB pelos
# callbacks das tasks; o SSE lê o DB. Não usamos o resultado do Celery.
celery_app.conf.task_ignore_result = True
