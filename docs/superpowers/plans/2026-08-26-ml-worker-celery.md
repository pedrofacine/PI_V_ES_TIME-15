# ML Worker (Celery + Redis) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mover o processamento de ML da API (in-process via threads) para um worker Celery dedicado, concluindo o split da fase F0 e destravando o boot do container `api`.

**Architecture:** A API deixa de importar/rodar ML. Ela publica tasks no Redis (`.delay()`); um serviço `worker` (com `torch`/GPU) consome as tasks e escreve resultados no DB Postgres/Supabase compartilhado. O SSE e os callbacks de DB continuam iguais (já são via polling no banco).

**Tech Stack:** FastAPI, Celery 5.3+, Redis, SQLModel/Postgres, Docker Compose, torch (cu118), pytest.

---

## File Structure

- `backend/app/celery_app.py` — **novo**. Instância Celery (broker Redis, sem result backend).
- `backend/app/modules/clips/tasks.py` — **novo**. Tasks `run_fast_scan` e `run_full_tracking` (movidas do router). Import de `ml` permanece lazy dentro da função.
- `backend/app/modules/clips/router.py` — **editar**. Troca threads por `.delay()`; remove `threading` e hacks de `sys.path`.
- `backend/app/main.py` — **editar**. Remove import de `ml` e warmup no startup.
- `backend/Dockerfile.worker` — **novo**. Imagem CUDA + `worker.txt`, copia `backend/` e `ml/`.
- `docker-compose.yml` — **editar**. Serviço `worker` com GPU passthrough.
- `.dockerignore` — **editar** (se necessário) para não excluir `ml/`.
- `tests/unit/backend/test_jobs.py` — **editar**. Mockar `.delay` no lugar de `threading.Thread`.
- `tests/unit/backend/test_tasks.py` — **novo**. Testa registro das tasks e config do Celery.

Comandos de teste rodam a partir de `backend/` (onde `app` é importável), como o `conftest.py` já assume.

---

### Task 1: Instância Celery

**Files:**
- Create: `backend/app/celery_app.py`
- Test: `tests/unit/backend/test_tasks.py`

- [ ] **Step 1: Write the failing test**

Criar `tests/unit/backend/test_tasks.py`:

```python
"""Testes da configuração do Celery e registro das tasks de ML."""


def test_celery_app_broker_is_redis():
    from app.celery_app import celery_app

    assert celery_app.conf.broker_url.startswith("redis://")
    # Sem result backend: resultado vai pro DB, não pro Celery.
    assert celery_app.conf.result_backend in (None, "")
    assert celery_app.conf.task_ignore_result is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest ../tests/unit/backend/test_tasks.py::test_celery_app_broker_is_redis -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.celery_app'`.

- [ ] **Step 3: Write minimal implementation**

Criar `backend/app/celery_app.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest ../tests/unit/backend/test_tasks.py::test_celery_app_broker_is_redis -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/celery_app.py tests/unit/backend/test_tasks.py
git commit -m "feat(f0): instancia Celery com broker Redis para o worker de ML"
```

---

### Task 2: Mover as tasks de ML para `tasks.py`

**Files:**
- Create: `backend/app/modules/clips/tasks.py`
- Test: `tests/unit/backend/test_tasks.py` (adicionar teste)

- [ ] **Step 1: Write the failing test**

Adicionar a `tests/unit/backend/test_tasks.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest ../tests/unit/backend/test_tasks.py::test_ml_tasks_are_registered -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.modules.clips.tasks'`.

- [ ] **Step 3: Write minimal implementation**

Criar `backend/app/modules/clips/tasks.py` movendo as funções do `router.py`. As
funções auxiliares (`update_job_status`, callbacks) e o import lazy de `ml` são
copiados **sem mudança de lógica**; apenas os hacks de `sys.path` (`parents[3]`) são
removidos e as funções ganham o decorator `@celery_app.task`:

```python
"""Tasks Celery de processamento de vídeo (rodam no worker, com torch/GPU).

Movidas de `router.py`. O import de `ml` é feito DENTRO da task (lazy), então a
API pode importar este módulo (para publicar via `.delay()`) sem puxar torch.
"""
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.celery_app import celery_app
from app.modules.clips.models import ProcessingJob, Clip, Candidate

BASE_DIR = Path(__file__).resolve().parents[2]
CLIPS_DIR = BASE_DIR / "uploads" / "clips"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)


def update_job_status(job_id: uuid.UUID, status: str):
    """Atualiza o status do job no DB de forma isolada."""
    from app.core.database import get_session
    session = next(get_session())
    try:
        job = session.get(ProcessingJob, job_id)
        if job:
            job.status = status
            job.updated_at = datetime.now(timezone.utc)
            session.commit()
    except Exception as e:
        session.rollback()
        print(f"[db error] Falha ao atualizar status: {e}")
    finally:
        session.close()


@celery_app.task(name="app.modules.clips.tasks.run_fast_scan")
def run_fast_scan(job_id: uuid.UUID, video_path: str, target_number: int, start_ts: int, end_ts: int):
    """FASE 1: busca expressa; salva candidatos no DB em tempo real."""
    print(f"[FAST SCAN] Iniciando job {job_id}")
    update_job_status(job_id, "FAST_SCAN")

    def save_candidate_to_db(cand_dict):
        from app.core.database import get_session
        session = next(get_session())
        try:
            novo_candidato = Candidate(
                job_id=job_id,
                signature=cand_dict["id"],
                name=cand_dict["name"],
                number=cand_dict["number"],
                color_hex=cand_dict["color"],
                image_path=cand_dict["image"],
                is_target=(cand_dict["number"] == target_number),
            )
            session.add(novo_candidato)
            job = session.get(ProcessingJob, job_id)
            if job:
                job.updated_at = datetime.now(timezone.utc)
            session.commit()
        except Exception as e:
            print(f"[DB ERROR] Erro ao salvar candidato: {e}")
            session.rollback()
        finally:
            session.close()

    def check_stop():
        from app.core.database import get_session
        session = next(get_session())
        try:
            job = session.get(ProcessingJob, job_id)
            if not job:
                return True
            return job.status != "FAST_SCAN"
        finally:
            session.close()

    try:
        from ml.scripts.process_video import _get_pipeline
        pipeline = _get_pipeline()
        output_dir = str(CLIPS_DIR / str(job_id))

        pipeline.fast_scan(
            video_path=video_path,
            output_dir=output_dir,
            target_number=target_number,
            frames_to_skip=30,
            on_candidate_found=save_candidate_to_db,
            should_stop=check_stop,
            start_ts=start_ts,
            end_ts=end_ts,
        )

        from app.core.database import get_session
        session = next(get_session())
        try:
            job = session.get(ProcessingJob, job_id)
            if job and job.status == "FAST_SCAN":
                job.status = "WAITING_USER"
                session.commit()
                print("[FAST SCAN] Vídeo inteiro verificado. Aguardando usuário.")
        finally:
            session.close()

    except Exception:
        print("[FAST SCAN ERROR] Falha:")
        print(traceback.format_exc())
        update_job_status(job_id, "ERROR")


@celery_app.task(name="app.modules.clips.tasks.run_full_tracking")
def run_full_tracking(job_id: uuid.UUID, video_path: str, target_number: int, target_signature: str, start_ts: int, end_ts: int):
    """FASE 2: rastreio rigoroso filtrando pela assinatura (número + cor)."""
    print(f"[TRACKING] Iniciando recorte final do job {job_id}")
    update_job_status(job_id, "TRACKING")

    def save_clip_to_db(clip_dict):
        from app.core.database import get_session
        session = next(get_session())
        try:
            new_clip = Clip(
                job_id=job_id,
                storage_path=clip_dict["path"],
                start_timestamp=clip_dict["start_ts"],
                end_timestamp=clip_dict["end_ts"],
            )
            session.add(new_clip)
            job = session.get(ProcessingJob, job_id)
            if job:
                job.updated_at = datetime.now(timezone.utc)
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"[db error] Falha ao salvar clipe: {e}")
        finally:
            session.close()

    def set_extracting_status():
        print("[TRACKING] Iniciando recorte de clipes. Mudando status para EXTRACTING.")
        update_job_status(job_id, "EXTRACTING")

    try:
        from ml.scripts.process_video import _get_pipeline
        pipeline = _get_pipeline()
        output_dir = str(CLIPS_DIR / str(job_id))

        pipeline.process(
            video_path=video_path,
            target_number=target_number,
            target_signature=target_signature,
            output_dir=output_dir,
            start_ts=start_ts,
            end_ts=end_ts,
            on_clip_generated=save_clip_to_db,
            on_extracting_start=set_extracting_status,
            debug=True,
        )

        update_job_status(job_id, "COMPLETED")
        print(f"[TRACKING] Job {job_id} concluído.")

    except Exception:
        print("[TRACKING ERROR] Falha:")
        print(traceback.format_exc())
        update_job_status(job_id, "ERROR")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest ../tests/unit/backend/test_tasks.py -v`
Expected: PASS (3 testes).

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/clips/tasks.py tests/unit/backend/test_tasks.py
git commit -m "feat(f0): tasks Celery run_fast_scan/run_full_tracking (import ml lazy)"
```

---

### Task 3: API publica via `.delay()` (remover threads do router)

**Files:**
- Modify: `backend/app/modules/clips/router.py`
- Modify: `tests/unit/backend/test_jobs.py`

- [ ] **Step 1: Atualizar os testes existentes para mockar `.delay`**

Em `tests/unit/backend/test_jobs.py`, os testes hoje mockam
`app.modules.clips.router.threading.Thread`. Trocar para mockar as tasks importadas
no router. Substituições:

`test_create_job_success`:
```python
    with patch("app.modules.clips.router.run_fast_scan") as mock_task:
        response = client.post(
            "/api/v1/jobs/",
            data={"target_number": "10", "start_ts": "0", "end_ts": "0"},
            files={"video": ("test.mp4", b"fake video bytes", "video/mp4")},
            headers=auth_headers(token),
        )

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "PENDING"
    mock_task.delay.assert_called_once()
```

`test_create_job_invalid_number_negative` e `test_create_job_invalid_number_too_large`:
trocar `patch("app.modules.clips.router.threading.Thread")` por
`patch("app.modules.clips.router.run_fast_scan")`.

`test_confirm_player_wrong_status`: trocar por
`patch("app.modules.clips.router.run_full_tracking")`.

`test_confirm_player_success` e `test_confirm_player_fast_scan_status`:
```python
    with patch("app.modules.clips.router.run_full_tracking") as mock_task:
        resp = client.post(
            f"/api/v1/jobs/{job.id}/confirm",
            json={"candidate_signature": "10_#ff0000", "start_ts": 0, "end_ts": 0},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "TRACKING"
    mock_task.delay.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest ../tests/unit/backend/test_jobs.py -v`
Expected: FAIL — `AttributeError`/`ModuleNotFoundError` em `app.modules.clips.router.run_fast_scan` (ainda não importado no router).

- [ ] **Step 3: Editar o `router.py`**

No topo, remover `import threading`, `import traceback`, `import time` **apenas se
não usados** (obs.: `time` é usado no SSE, `traceback` deixa de ser usado após a
remoção das funções). Manter `time`. Remover as funções `update_job_status`,
`run_fast_scan`, `run_full_tracking` (foram para `tasks.py`) e adicionar o import:

```python
from app.modules.clips.tasks import run_fast_scan, run_full_tracking
```

Em `create_job`, substituir o bloco da thread:

```python
    # 4. Publica o FAST SCAN (fase 1) na fila do worker
    run_fast_scan.delay(job.id, str(video_path), target_number, start_ts, end_ts)

    return {"job_id": str(job.id), "status": job.status}
```

Em `confirm_player`, substituir o bloco da thread:

```python
    run_full_tracking.delay(
        job.id, job.video.storage_path, job.target_number,
        payload.candidate_signature, payload.start_ts, payload.end_ts,
    )

    return {"message": "Processamento retomado.", "status": "TRACKING"}
```

O `stream_job_status` (SSE), `list_clips`, `_format_duration` e imports de
`Session/engine` permanecem inalterados.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest ../tests/unit/backend/test_jobs.py -v`
Expected: PASS (todos os testes de jobs).

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/clips/router.py tests/unit/backend/test_jobs.py
git commit -m "refactor(f0): API publica jobs de ML via Celery .delay() (sem threads)"
```

---

### Task 4: Remover ML do boot da API

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Editar `main.py`**

Remover a linha 21 `from ml.scripts.process_video import _get_pipeline` e, no
`@app.on_event("startup")`, remover as 3 linhas do warmup:

```python
    print("[SISTEMA] Iniciando aquecimento da IA (carregando modelos)...")
    _get_pipeline()
    print("[SISTEMA] IA carregada na memória e pronta para uso!")
```

O `on_startup` fica apenas com a criação das pastas de upload:

```python
@app.on_event("startup")
def on_startup():
    # Schema agora é gerido por Alembic (migrações versionadas), não mais create_all.
    Path("uploads/videos").mkdir(parents=True, exist_ok=True)
    Path("uploads/clips").mkdir(parents=True, exist_ok=True)
```

Remover também o bloco de hack de `sys.path` no topo (linhas 1-6: `import sys`,
`PROJECT_ROOT = ...parents[2]`, `sys.path.insert(...)`), pois a API não importa mais
`ml`. Manter o `from pathlib import Path`.

- [ ] **Step 2: Verificar que a API importa sem torch**

Run: `cd backend && python -c "import app.main; print('OK: app.main importado sem torch')"`
Expected: imprime `OK: app.main importado sem torch` sem erro (mesmo sem `torch`/`ml` instalados no ambiente da API).

- [ ] **Step 3: Rodar a suíte da API para garantir que nada quebrou**

Run: `cd backend && python -m pytest ../tests/unit/backend -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py
git commit -m "refactor(f0): remove carga de ML do startup da API"
```

---

### Task 5: Dockerfile do worker

**Files:**
- Create: `backend/Dockerfile.worker`

- [ ] **Step 1: Criar `backend/Dockerfile.worker`**

```dockerfile
# Worker de ML: precisa de torch/CUDA. Base com runtime CUDA 11.8 (compat. cu118).
FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3.11-dev python3-pip \
        ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.11 /usr/bin/python

WORKDIR /app

# Requirements ficam em backend/requirements/. O build context é a raiz do repo.
COPY backend/requirements/ requirements/
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements/worker.txt

# App e pacote ml precisam ser importáveis como top-level (app.*, ml.*).
COPY backend/ /app/
COPY ml/ /app/ml/

CMD ["celery", "-A", "app.celery_app", "worker", "--concurrency=1", "--loglevel=info"]
```

- [ ] **Step 2: Verificar sintaxe do build (sem subir ainda)**

Run: `docker build -f backend/Dockerfile.worker -t smartscout-worker:test . 2>&1 | tail -20`
Expected: build conclui (pode demorar por causa do torch). Se o host não tiver
NVIDIA Container Toolkit, o **build** ainda funciona (a GPU só é exigida em runtime).

- [ ] **Step 3: Commit**

```bash
git add backend/Dockerfile.worker
git commit -m "feat(f0): Dockerfile do worker Celery (CUDA 11.8 + torch + ml)"
```

---

### Task 6: Serviço `worker` no compose + `.dockerignore`

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.dockerignore`

- [ ] **Step 1: Garantir que `ml/` não é ignorado**

Verificar `.dockerignore`: as entradas atuais (`**/__pycache__`, `**/node_modules`,
`**/.venv`, `**/uploads`, `**/.git`, `**/*.pyc`, `.coverage`) **não** excluem `ml/`.
Nenhuma mudança necessária, a menos que o passo 3 falhe por arquivo ausente.

- [ ] **Step 2: Adicionar o serviço `worker` ao `docker-compose.yml`**

Adicionar, após o serviço `api`:

```yaml
  worker:
    build:
      context: .
      dockerfile: backend/Dockerfile.worker
    env_file: ./backend/.env
    environment:
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./backend/uploads:/app/uploads
    depends_on:
      - redis
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

Observação: o `context` do `worker` é a raiz do repo (`.`), diferente do `api`
(`./backend`), porque o worker precisa copiar `backend/` **e** `ml/`. O volume de
`uploads` é compartilhado com a API para que os clipes gerados fiquem visíveis via
`StaticFiles`.

- [ ] **Step 3: Validar a config do compose**

Run: `docker compose config >/dev/null && echo "compose OK"`
Expected: imprime `compose OK` (YAML válido, serviço `worker` reconhecido).

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml .dockerignore
git commit -m "feat(f0): serviço worker no compose com GPU passthrough"
```

---

### Task 7: Verificação integrada (subida completa)

**Files:** nenhum (verificação end-to-end).

- [ ] **Step 1: Subir tudo com build**

Run: `docker compose up -d --build`
Expected: `redis`, `api`, `web` e `worker` criados e iniciados.

- [ ] **Step 2: Confirmar que a API não crasha mais**

Run: `docker compose ps` e `docker compose logs api --tail=30`
Expected: `api` em `Up`; logs **sem** `ModuleNotFoundError: No module named 'ml'`.

- [ ] **Step 3: Confirmar que a API responde**

Run: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/docs`
Expected: `200`.

- [ ] **Step 4: Confirmar que o worker está pronto**

Run: `docker compose logs worker --tail=30`
Expected: log do Celery `celery@... ready.` e as duas tasks listadas em `[tasks]`
(`app.modules.clips.tasks.run_fast_scan`, `run_full_tracking`).

Se o worker falhar por GPU (NVIDIA Container Toolkit ausente no WSL2), aplicar o
**fallback CPU**: comentar o bloco `deploy:` do serviço `worker` no compose e repetir
o Step 1. Registrar no PR que a GPU exige o toolkit no WSL2.

- [ ] **Step 5: (Opcional, se houver vídeo de teste) validação funcional**

Fazer login no frontend (http://localhost:5173), subir um vídeo curto, confirmar um
jogador e observar os clipes aparecerem. Acompanhar `docker compose logs worker -f`
para ver a task recebida e o pipeline carregado no 1º job.

- [ ] **Step 6: Commit final (docs)**

Atualizar o `README.md` se necessário para citar o serviço `worker` e o requisito de
GPU/WSL2, então:

```bash
git add README.md
git commit -m "docs(f0): documenta worker Celery e requisito de GPU no Docker"
```

---

## Self-Review

**Spec coverage:**
- Celery instance → Task 1 ✓
- tasks.py (import ml lazy) → Task 2 ✓
- router usa .delay() → Task 3 ✓
- main.py sem ML → Task 4 ✓
- Dockerfile.worker (CUDA + torch + ml) → Task 5 ✓
- compose worker + GPU → Task 6 ✓
- Critérios de sucesso 1-5 → Task 7 ✓
- Warmup lazy → preservado em Task 2 (`_get_pipeline()` dentro da task) ✓
- Fallback CPU → Task 7 Step 4 ✓

**Placeholder scan:** sem TBD/TODO; todo passo com código ou comando exato.

**Type consistency:** nomes de tasks (`run_fast_scan`, `run_full_tracking`) e nomes
Celery (`app.modules.clips.tasks.*`) consistentes entre Tasks 2, 3 e 7. Assinaturas
das tasks batem com as chamadas `.delay(...)` no router.
