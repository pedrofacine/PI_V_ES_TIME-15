"""Testes da configuração do Celery e registro das tasks de ML."""


def test_celery_app_broker_is_redis():
    from app.celery_app import celery_app

    assert celery_app.conf.broker_url.startswith("redis://")
    # Sem result backend: resultado vai pro DB, não pro Celery.
    assert celery_app.conf.result_backend in (None, "")
    assert celery_app.conf.task_ignore_result is True
