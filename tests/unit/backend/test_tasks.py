"""Testes da configuração do Celery e registro das tasks de ML."""


def test_celery_app_broker_is_redis():
    from app.celery_app import celery_app

    assert celery_app.conf.broker_url.startswith("redis://")
    # Sem result backend: resultado vai pro DB, não pro Celery.
    assert celery_app.conf.result_backend in (None, "")
    assert celery_app.conf.task_ignore_result is True


def test_ml_tasks_are_registered():
    # Importar o app registra o módulo de tasks via `include`.
    from app.celery_app import celery_app
    import app.modules.clips.tasks  # noqa: F401

    registered = set(celery_app.tasks.keys())
    assert "app.modules.clips.tasks.run_fast_scan" in registered
    assert "app.modules.clips.tasks.run_full_tracking" in registered


def test_importing_tasks_does_not_import_torch():
    """A API importa este módulo; ele não pode puxar torch no topo (import lazy)."""
    import sys

    sys.modules.pop("torch", None)
    import importlib
    import app.modules.clips.tasks as tasks_mod
    importlib.reload(tasks_mod)

    assert "torch" not in sys.modules
