# Mover ML para worker (Celery + Redis) — Design F0

**Data:** 2026-08-26
**Status:** Aprovado (aguardando revisão do spec)
**Fase:** F0 — conclui o split que removeu torch/ml da imagem da API

## Contexto

A fase F0 dividiu os requirements (`base/api/worker`) e removeu `torch` da imagem
da API (`torch` só existe em `requirements/worker.txt`). Porém a API ainda carrega
ML no boot, o que quebra o container:

```
File "/app/app/main.py", line 21, in <module>
    from ml.scripts.process_video import _get_pipeline
ModuleNotFoundError: No module named 'ml'
```

Causa: `main.py` importa `ml` no topo do módulo e chama `_get_pipeline()` no
startup; e o `router.py` roda o ML in-process via `threading.Thread`. O pacote
`ml/` fica na raiz do repo, fora do build context `./backend`, e a imagem da API
não tem `torch`.

### Fatos do código atual (verificados)

- Fila já pretendida: `base.txt` traz `celery>=5.3` e `redis>=5.0`; o `docker-compose`
  já provê `redis` como broker (`REDIS_URL=redis://redis:6379/0`).
- Os imports de `ml` em `router.py` (`run_fast_scan` L155, `run_full_tracking` L227)
  **já são lazy** (dentro do corpo da função) → um módulo de tasks pode ser importado
  pela API sem puxar `torch`.
- Callbacks escrevem candidatos/clips no **DB compartilhado** (Postgres/Supabase) em
  tempo real; `check_stop` e o endpoint SSE funcionam por **polling no DB** → são
  agnósticos a onde o ML roda.
- `ml.scripts.process_video` importa `ml.scripts.video_pipeline` (torch/ultralytics),
  então o worker precisa de `app.*` **e** `ml.*` importáveis no path.
- Host tem GPU NVIDIA GTX 1050 Ti (4GB). `worker.txt` usa wheels CUDA 11.8 (`cu118`).

## Decisões

| Decisão | Escolha |
|---|---|
| Fila de tasks | Celery + Redis (já são dependências) |
| GPU do worker | GPU no Docker (passthrough via NVIDIA Container Toolkit no WSL2) |
| Warmup do modelo | Lazy — carrega no 1º job via `_get_pipeline()` em cache |
| Result backend do Celery | Nenhum (`task_ignore_result=True`); resultado vai pro DB |
| Concorrência do worker | `--concurrency=1` (1 modelo na VRAM, evita OOM na 1050 Ti) |

## Arquitetura

```
api (sem torch)  --.delay()-->  Redis (broker)  -->  worker (torch + GPU)
      │                                                     │
      └──────────── Postgres/Supabase (DB compartilhado) ───┘
                              ▲
                    SSE lê o DB por polling (inalterado)
```

## Componentes

### 1. `backend/app/celery_app.py` (novo)
Instância Celery compartilhada.
- `broker = REDIS_URL` (env; default `redis://redis:6379/0`).
- Sem result backend. `task_ignore_result = True`.
- `include=["app.modules.clips.tasks"]` para o worker registrar as tasks.

### 2. `backend/app/modules/clips/tasks.py` (novo)
Move `run_fast_scan` e `run_full_tracking` do `router.py` para cá, decoradas com
`@celery_app.task`.
- Import de `ml` permanece **lazy dentro da função** (a API importa o módulo sem
  puxar torch).
- Warmup lazy no 1º job via `_get_pipeline()` (cache do próprio pipeline).
- Callbacks de DB (`save_candidate_to_db`, `save_clip_to_db`), `check_stop`,
  `update_job_status` e transições de status permanecem idênticos.
- Remover os hacks de `sys.path` (`parents[3]`) — o layout do worker garante o path.

### 3. `backend/app/modules/clips/router.py` (editar)
- `create_job`: troca `threading.Thread(target=run_fast_scan, ...)` por
  `run_fast_scan.delay(...)`.
- `confirm_player`: troca a thread por `run_full_tracking.delay(...)`.
- Remove `import threading` e os hacks de `sys.path`.
- SSE (`stream_job_status`), listagem de clips e schemas: **inalterados**.

### 4. `backend/app/main.py` (editar)
- Remove o import de `ml` no topo (L21) e o bloco de warmup `_get_pipeline()` do
  `@app.on_event("startup")`.
- Remove o hack de `sys.path` (`parents[2]`) se não for mais necessário.
- O startup da API mantém apenas a criação das pastas de upload e mounts.

### 5. `backend/Dockerfile.worker` (novo)
- Base com CUDA runtime compatível com cu118 (ex.: imagem Python + libs CUDA, ou
  base `nvidia/cuda:11.8`-runtime + Python 3.11).
- `pip install -r requirements/worker.txt`.
- `COPY backend/ /app` e `COPY ml/ /app/ml`; `WORKDIR /app`; `ENV PYTHONPATH=/app`.
- `CMD ["celery", "-A", "app.celery_app", "worker", "--concurrency=1", "--loglevel=info"]`.

### 6. `docker-compose.yml` (editar)
Adiciona serviço `worker`:
- `build`: context = **raiz do repo** (`.`), `dockerfile: backend/Dockerfile.worker`
  (precisa alcançar `backend/` e `ml/`).
- `env_file: ./backend/.env`; `environment: REDIS_URL=redis://redis:6379/0`.
- `depends_on: [redis]`.
- GPU passthrough:
  ```yaml
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
  ```
- Ajustar `.dockerignore` se necessário para não excluir `ml/`.

## Fluxo de abort (2 fases)

Com `--concurrency=1`: se `confirm_player` dispara o tracking enquanto o fast_scan
ainda roda, o tracking entra na fila; o `check_stop` do fast_scan detecta
`status != FAST_SCAN`, encerra, libera o worker e o tracking roda em seguida. Sem
mudança de lógica.

## Fora de escopo (YAGNI)

- Reprocessar clips/jobs antigos.
- Retry/back-off automático, dead-letter queue.
- Métricas/monitoramento do Celery (flower).
- Result backend / consulta de resultado via Celery.

## Riscos

- **GPU no Docker/Windows** depende do NVIDIA Container Toolkit configurado no WSL2.
  Se ausente, o `worker` falha ao reservar o device (ou, sem a seção `deploy`, o
  torch cai para CPU). Fallback documentado: rodar o worker sem a seção `deploy`
  (CPU-only) para validar o fluxo, e ligar a GPU depois.
- Imagem do worker é grande (torch + CUDA). Build inicial demorado.

## Critérios de sucesso

1. `docker compose up -d --build` sobe `redis`, `api`, `web` e `worker` sem crash.
2. `docker compose logs api` **não** mostra `ModuleNotFoundError: No module named 'ml'`.
3. A API responde (ex.: `GET /` ou `/docs`) sem carregar ML.
4. Upload de vídeo → job dispara no worker → candidatos aparecem via SSE →
   confirmação → clips gerados. (Validação funcional end-to-end.)
5. `docker compose logs worker` mostra a task recebida e o pipeline carregado no 1º job.
