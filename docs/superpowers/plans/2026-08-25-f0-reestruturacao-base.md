# F0 — Reestruturação Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reestruturar o backend do SmartScout de `app/{routers,models,schemas}` planos para `app/core/` + `app/modules/{identity,clips}/`, introduzindo Alembic baseline, hierarquia de exceções de domínio, abstração de storage, split de requirements e docker-compose — **sem nenhuma feature nova e preservando o comportamento observável da API** (uma única exceção de contrato documentada abaixo).

**Architecture:** Monolito modular. `core/` guarda infraestrutura transversal (config, database, deps, exceptions, storage, security, email). Cada módulo de produto tem a anatomia `router · service · repository · models · schemas` — no F0 só `identity` e `clips` existem, e só com os arquivos que já têm conteúdo real (`router`, `models`, `schemas`); `service`/`repository` entram quando a lógica for extraída (F2/F1). O pipeline de visão continua rodando **inline com threads** dentro de `clips` — a troca por Celery é F1, fora deste plano.

**Tech Stack:** FastAPI, SQLModel, Alembic, Pydantic, python-jose (JWT), bcrypt, pytest + TestClient (SQLite in-memory), Docker Compose, Postgres (Supabase, externo).

**Branch:** `f0/reestruturacao-base` (única, PR curto — Onda 0 da spec). Padrão de branches definido: `<fase>/<slug>` minúsculo.

**Spec de referência:** `docs/superpowers/specs/2026-08-11-smartscout-rede-social-design.md` (§4.2 estrutura, §4.3 contrato, §10.1 alembic, §10.2 erros, §11 roadmap).

---

## ⚠️ Única mudança de contrato HTTP no F0

`POST /api/v1/jobs/{id}/confirm` num job em estado não-confirmável (ex.: `COMPLETED`) **passa de `400` para `409 Conflict`** (via `ConflictError`, §10.2). Todos os outros status codes e todas as URLs permanecem idênticos. O frontend não muda neste plano. Se a equipe vetar essa mudança, manter o `ConflictError` mas ajustar o handler para 400 — decisão de 1 linha na Task 6.

---

## Decisões de escopo (defaults aplicados)

| Decisão | Escolha | Motivo |
|---|---|---|
| Profundidade do refactor de `clips` | **Toque mínimo** — mover jobs.py/clips.py preservando threads+ML inline | F1 reescreve `clips` para Celery; extrair service/repository agora seria retrabalho |
| Prefixos HTTP / frontend | **Manter prefixos, backend-only** | Onda 0 é backend; troca `/jobs`→`/clips/jobs` + reescrita de `services/api.ts` fica no F1 |
| Módulos criados | **Só `identity` e `clips`** | Demais (`profiles`, `feed`, `discovery`, `opportunities`, `messaging`, `entitlements`) entram na fase que os preenche (F2, M1…) |
| `core/events.py` | **Não criar** | Nenhuma feature do F0 usa event bus (YAGNI); entra quando M1/M5 precisarem |
| `service.py` / `repository.py` vazios | **Não criar** | Criados quando houver lógica para extrair (F2 identity, F1 clips) |

---

## Estrutura de arquivos ao final do F0

```
backend/
├─ alembic.ini                         (novo)
├─ alembic/
│  ├─ env.py                           (novo, target_metadata = SQLModel.metadata)
│  ├─ script.py.mako                   (gerado por alembic init)
│  └─ versions/
│     └─ <hash>_baseline.py            (novo, autogenerate do schema atual)
├─ app/
│  ├─ core/
│  │  ├─ __init__.py
│  │  ├─ config.py                     (movido de app/config.py)
│  │  ├─ database.py                   (movido de app/database.py, sem import de models)
│  │  ├─ deps.py                       (renomeado de app/core/auth.py)
│  │  ├─ security.py                   (inalterado exceto import de config)
│  │  ├─ email.py                      (inalterado)
│  │  ├─ exceptions.py                 (novo)
│  │  └─ storage.py                    (novo)
│  ├─ modules/
│  │  ├─ __init__.py                   (novo)
│  │  ├─ identity/
│  │  │  ├─ __init__.py
│  │  │  ├─ models.py                  (User + PasswordResetToken)
│  │  │  ├─ schemas.py                 (de app/schemas/auth.py)
│  │  │  └─ router.py                  (de app/routers/auth.py)
│  │  └─ clips/
│  │     ├─ __init__.py
│  │     ├─ models.py                  (Video + ProcessingJob + Clip + Candidate)
│  │     ├─ schemas.py                 (ConfirmPlayerRequest)
│  │     └─ router.py                  (merge de jobs.py + clips.py)
│  └─ main.py                          (imports novos, handler de exceção, sem create_all no startup)
└─ requirements/
   ├─ base.txt                         (novo)
   ├─ api.txt                          (novo)
   └─ worker.txt                       (novo)

docker-compose.yml                     (novo, redis + api + web)
backend/Dockerfile                     (novo, instala requirements/api.txt)
frontend/Dockerfile                    (novo, vite dev)

REMOVIDOS:
  app/config.py, app/database.py, app/core/auth.py
  app/models/ (dir inteiro), app/schemas/ (dir inteiro)
  app/routers/ (dir inteiro: auth, clips, jobs, users, videos, fast_scan)
  backend/requirements.txt
```

---

### Task 1: Branch + rede de segurança (baseline verde)

Fase de refactor puro: o que garante que não quebramos nada é a suíte verde **antes** e depois de cada passo.

**Files:** nenhum (setup + verificação).

- [ ] **Step 1: Criar a branch a partir da branch de spec**

```bash
git checkout -b f0/reestruturacao-base
```

- [ ] **Step 2: Rodar a suíte inteira e confirmar verde**

Run: `python -m pytest`
Expected: PASS (todos os testes atuais). Anote o número de testes que passaram — é o baseline que TODA task seguinte precisa manter.

Se algo já estiver vermelho antes de começar, **pare** e reporte — não é papel do F0 consertar testes pré-quebrados.

---

### Task 2: Deletar routers mortos

`users.py`, `videos.py` e `fast_scan.py` não são montados no `main.py`, ninguém os importa, e `fast_scan.py` importa caminhos quebrados (`backend.app.models`). `schemas/user_schema.py` só é usado por `users.py`.

**Files:**
- Delete: `backend/app/routers/users.py`, `backend/app/routers/videos.py`, `backend/app/routers/fast_scan.py`
- Delete: `backend/app/schemas/user_schema.py`
- Modify: `backend/app/schemas/__init__.py`

- [ ] **Step 1: Confirmar que estão realmente mortos**

Run: `grep -rn "routers.users\|routers.videos\|fast_scan\|user_schema" backend tests --include=*.py | grep -v __pycache__`
Expected: apenas auto-referências dentro dos próprios arquivos a deletar e a linha de `jobs.py` que define seu *próprio* `run_fast_scan` local (não importa o router). Nenhum `include_router` desses.

- [ ] **Step 2: Deletar os arquivos**

```bash
git rm backend/app/routers/users.py backend/app/routers/videos.py backend/app/routers/fast_scan.py backend/app/schemas/user_schema.py
```

- [ ] **Step 3: Limpar `schemas/__init__.py`**

O arquivo hoje re-exporta de `schemas.auth`. `schemas/auth.py` ainda existe (sai na Task 8). Deixe apenas o re-export de auth, sem referência a `user_schema`. Substitua o conteúdo por:

```python
# app.schemas
from app.schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    Token,
    TokenPayload,
)
```

(Se o arquivo já não referenciava `user_schema`, nenhum edit é necessário — confirme com Read.)

- [ ] **Step 4: Rodar a suíte**

Run: `python -m pytest`
Expected: PASS, mesmo número da Task 1.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore(f0): remove dead routers (users, videos, fast_scan) e schema orfao"
```

---

### Task 3: Mover `database.py` para `core/`

`app/database.py` → `app/core/database.py`. Remove-se o import de models usado só para registrar tabelas no `create_all` — a metadata é populada pelos imports de router no `main.py`, e o Alembic (Task 10) importará os models explicitamente. `create_db_and_tables` permanece (usado no startup até a Task 10).

**Files:**
- Move: `backend/app/database.py` → `backend/app/core/database.py`
- Modify (imports): `backend/app/main.py`, `backend/app/core/auth.py`, `backend/app/routers/auth.py`, `backend/app/routers/clips.py`, `backend/app/routers/jobs.py`, `tests/unit/backend/conftest.py`

- [ ] **Step 1: Mover o arquivo**

```bash
git mv backend/app/database.py backend/app/core/database.py
```

- [ ] **Step 2: Remover o import de models de `core/database.py`**

Em `backend/app/core/database.py`, apague a linha:

```python
from app.models import User, Video, ProcessingJob, Clip  # noqa: F401
```

e o comentário logo acima dela (`# Importa os models ...`). O resto do arquivo fica idêntico.

- [ ] **Step 3: Atualizar todos os importadores**

Troque `from app.database import` → `from app.core.database import` nestes arquivos:

- `backend/app/main.py:17` — `from app.database import create_db_and_tables` → `from app.core.database import create_db_and_tables`
- `backend/app/core/auth.py:10` — `from app.database import get_session` → `from app.core.database import get_session`
- `backend/app/routers/auth.py:7` — idem
- `backend/app/routers/clips.py:10` — idem
- `backend/app/routers/jobs.py:16` — `from app.database import get_session, engine` → `from app.core.database import get_session, engine`
- `backend/app/routers/jobs.py` — nas 4 ocorrências internas `from app.database import get_session` (linhas ~89, ~117, ~144, ~172, ~202) → `from app.core.database import get_session`
- `tests/unit/backend/conftest.py:18` — `from app.database import get_session` → `from app.core.database import get_session`

Run para achar sobras: `grep -rn "app.database" backend tests --include=*.py | grep -v __pycache__`
Expected: nenhuma linha.

- [ ] **Step 4: Rodar a suíte**

Run: `python -m pytest`
Expected: PASS, mesmo número da Task 1.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(f0): move database para core/ e remove registro de models redundante"
```

---

### Task 4: Mover `config.py` para `core/`

`app/config.py` → `app/core/config.py`. Único importador real é `core/security.py` (as constantes de JWT). `YOLO_MODEL_PATH` e `BACKEND_DIR` são código morto pré-existente — **mover intacto, não deletar** (fora do escopo do F0).

**Files:**
- Move: `backend/app/config.py` → `backend/app/core/config.py`
- Modify: `backend/app/core/security.py`

- [ ] **Step 1: Mover o arquivo**

```bash
git mv backend/app/config.py backend/app/core/config.py
```

- [ ] **Step 2: Atualizar o import em `security.py`**

`backend/app/core/security.py:10`:

```python
from app.config import JWT_ALGORITHM, JWT_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES
```

→

```python
from app.core.config import JWT_ALGORITHM, JWT_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES
```

Run: `grep -rn "from app.config\|import app.config" backend tests --include=*.py | grep -v __pycache__`
Expected: nenhuma linha.

- [ ] **Step 3: Rodar a suíte**

Run: `python -m pytest`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(f0): move config para core/"
```

---

### Task 5: Renomear `core/auth.py` para `core/deps.py`

A spec (§4.2) nomeia o arquivo de dependências transversais como `deps`. `get_current_user` é a dependência canônica.

**Files:**
- Move: `backend/app/core/auth.py` → `backend/app/core/deps.py`
- Modify: `backend/app/routers/auth.py`, `backend/app/routers/clips.py`, `backend/app/routers/jobs.py`

- [ ] **Step 1: Mover o arquivo**

```bash
git mv backend/app/core/auth.py backend/app/core/deps.py
```

- [ ] **Step 2: Atualizar importadores**

Troque `from app.core.auth import get_current_user` → `from app.core.deps import get_current_user` em:
- `backend/app/routers/auth.py:5`
- `backend/app/routers/clips.py:12`
- `backend/app/routers/jobs.py:18`

Run: `grep -rn "app.core.auth" backend tests --include=*.py | grep -v __pycache__`
Expected: nenhuma linha.

- [ ] **Step 3: Rodar a suíte**

Run: `python -m pytest`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(f0): renomeia core/auth.py para core/deps.py"
```

---

### Task 6: Hierarquia de exceções de domínio + handler único

§10.2: `DomainError` e subclasses em `core/exceptions.py`; **um** handler no `main.py` traduz para HTTP. Router deixa de montar `HTTPException`.

**Files:**
- Create: `backend/app/core/exceptions.py`
- Modify: `backend/app/main.py`
- Test: `tests/unit/backend/test_exceptions.py`

- [ ] **Step 1: Escrever o teste que falha**

Create `tests/unit/backend/test_exceptions.py`:

```python
from app.core.exceptions import (
    DomainError,
    NotFoundError,
    ForbiddenError,
    ConflictError,
    QuotaExceededError,
    ValidationError,
)


def test_status_codes():
    assert DomainError().status_code == 500
    assert NotFoundError().status_code == 404
    assert ForbiddenError().status_code == 403
    assert ConflictError().status_code == 409
    assert QuotaExceededError().status_code == 402
    assert ValidationError().status_code == 422


def test_custom_detail_and_default():
    assert NotFoundError("Job não encontrado.").detail == "Job não encontrado."
    assert NotFoundError().detail == NotFoundError.default_detail
    assert str(ConflictError("x")) == "x"


def test_hierarchy():
    for exc in [NotFoundError, ForbiddenError, ConflictError, QuotaExceededError, ValidationError]:
        assert issubclass(exc, DomainError)
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `python -m pytest tests/unit/backend/test_exceptions.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.core.exceptions'`.

- [ ] **Step 3: Implementar `core/exceptions.py`**

Create `backend/app/core/exceptions.py`:

```python
"""
Hierarquia de exceções de domínio (§10.2 da spec).

Services levantam estas exceções; um único handler em main.py as traduz
para respostas HTTP. Routers não montam HTTPException.
"""


class DomainError(Exception):
    """Base. Mapeada para 500 quando não for uma subclasse mais específica."""

    status_code: int = 500
    default_detail: str = "Erro interno."

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class NotFoundError(DomainError):
    status_code = 404
    default_detail = "Recurso não encontrado."


class ForbiddenError(DomainError):
    status_code = 403
    default_detail = "Acesso negado."


class ConflictError(DomainError):
    status_code = 409
    default_detail = "Conflito de estado."


class QuotaExceededError(DomainError):
    status_code = 402
    default_detail = "Cota excedida."


class ValidationError(DomainError):
    status_code = 422
    default_detail = "Dados inválidos."
```

- [ ] **Step 4: Rodar o teste e ver passar**

Run: `python -m pytest tests/unit/backend/test_exceptions.py -v`
Expected: PASS.

- [ ] **Step 5: Registrar o handler único no `main.py`**

Em `backend/app/main.py`, adicione o import no topo (junto aos outros imports de `app.*`):

```python
from fastapi.responses import JSONResponse
from app.core.exceptions import DomainError
```

e, logo após a criação do `app = FastAPI(...)` e antes dos `include_router`, adicione:

```python
@app.exception_handler(DomainError)
def handle_domain_error(request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
```

(`StreamingResponse` já é importado de `fastapi.responses`; adicione `JSONResponse` na mesma linha ou numa nova — confirme com Read para não duplicar.)

- [ ] **Step 6: Rodar a suíte inteira**

Run: `python -m pytest`
Expected: PASS. O handler será exercitado ponta-a-ponta na Task 9 (quando o router de `clips` passar a levantar `NotFoundError`/`ConflictError`).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(f0): hierarquia de excecoes de dominio + handler unico"
```

---

### Task 7: Abstração de storage (`core/storage.py`)

§4.2 lista `StorageBackend` em `core/`. Introduz a abstração com backend local (o único hoje). Será usada no upload de vídeo em `clips` (Task 9).

**Files:**
- Create: `backend/app/core/storage.py`
- Test: `tests/unit/backend/test_storage.py`

- [ ] **Step 1: Escrever o teste que falha**

Create `tests/unit/backend/test_storage.py`:

```python
from pathlib import Path

from app.core.storage import LocalStorageBackend


def test_save_writes_file_and_returns_path(tmp_path: Path):
    backend = LocalStorageBackend(root=tmp_path)
    stored = backend.save(b"conteudo do video", "videos/abc_test.mp4")

    saved = Path(stored)
    assert saved.exists()
    assert saved.read_bytes() == b"conteudo do video"
    assert saved == tmp_path / "videos" / "abc_test.mp4"


def test_path_for_resolves_key(tmp_path: Path):
    backend = LocalStorageBackend(root=tmp_path)
    assert backend.path_for("clips/x.mp4") == tmp_path / "clips" / "x.mp4"
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `python -m pytest tests/unit/backend/test_storage.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.core.storage'`.

- [ ] **Step 3: Implementar `core/storage.py`**

Create `backend/app/core/storage.py`:

```python
"""
Abstração de armazenamento de arquivos (§4.2 da spec).

No F0 só existe o backend local em disco. A interface permite trocar por
S3/Supabase Storage sem tocar nos módulos que a consomem.
"""
from abc import ABC, abstractmethod
from pathlib import Path


class StorageBackend(ABC):
    @abstractmethod
    def save(self, data: bytes, key: str) -> str:
        """Grava `data` sob `key` e retorna o caminho/identificador armazenado."""

    @abstractmethod
    def path_for(self, key: str) -> Path:
        """Resolve `key` para um caminho local (usado pelo servidor de estáticos)."""


class LocalStorageBackend(StorageBackend):
    def __init__(self, root: Path):
        self.root = Path(root)

    def save(self, data: bytes, key: str) -> str:
        dest = self.root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return str(dest)

    def path_for(self, key: str) -> Path:
        return self.root / key


# Backend padrão do processo (uploads locais na raiz do backend).
_UPLOADS_ROOT = Path(__file__).resolve().parents[2] / "uploads"


def get_storage() -> StorageBackend:
    return LocalStorageBackend(root=_UPLOADS_ROOT)
```

- [ ] **Step 4: Rodar o teste e ver passar**

Run: `python -m pytest tests/unit/backend/test_storage.py -v`
Expected: PASS.

- [ ] **Step 5: Rodar a suíte inteira**

Run: `python -m pytest`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(f0): abstracao StorageBackend com backend local"
```

---

### Task 8: Módulo `identity`

Move autenticação para `app/modules/identity/`. Rotas HTTP **inalteradas** (`/api/v1/auth/*`).

**Files:**
- Create: `backend/app/modules/__init__.py`, `backend/app/modules/identity/__init__.py`
- Create: `backend/app/modules/identity/models.py`, `schemas.py`, `router.py`
- Modify: `backend/app/main.py`, `backend/app/core/deps.py`, `backend/app/models/__init__.py`, `backend/app/routers/clips.py`, `backend/app/routers/jobs.py`, `tests/unit/backend/test_auth.py`
- Delete: `backend/app/routers/auth.py`, `backend/app/schemas/auth.py`, `backend/app/schemas/__init__.py`, `backend/app/models/user.py`, `backend/app/models/password_reset.py`

- [ ] **Step 1: Criar os pacotes**

```bash
mkdir -p backend/app/modules/identity
printf '# app.modules\n' > backend/app/modules/__init__.py
printf '# app.modules.identity\n' > backend/app/modules/identity/__init__.py
```

- [ ] **Step 2: Criar `identity/models.py`** (merge de `user.py` + `password_reset.py`)

Create `backend/app/modules/identity/models.py`:

```python
import uuid
from datetime import datetime, timezone
from typing import List, TYPE_CHECKING

from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from app.modules.clips.models import Video


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    first_name: str
    last_name: str
    max_clips_allowed: int = Field(default=20)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    videos: List["Video"] = Relationship(back_populates="user")


class PasswordResetToken(SQLModel, table=True):
    __tablename__ = "password_reset_tokens"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    token: str = Field(index=True, unique=True)
    expires_at: datetime
    used: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 3: Criar `identity/schemas.py`**

```bash
git mv backend/app/schemas/auth.py backend/app/modules/identity/schemas.py
```

O conteúdo de `schemas/auth.py` não tem imports de `app.*`, então nada a editar dentro dele.

- [ ] **Step 4: Criar `identity/router.py`**

```bash
git mv backend/app/routers/auth.py backend/app/modules/identity/router.py
```

Depois edite o bloco de imports no topo de `backend/app/modules/identity/router.py`. Substitua:

```python
from app.core.auth import get_current_user
from sqlmodel import Session, select
from app.database import get_session
from app.models import User
from app.schemas.auth import UserCreate, UserLogin, UserResponse, Token, TokenPayload
from app.core.security import hash_password, verify_password, create_access_token
from pydantic import BaseModel, Field
import os
import secrets
from datetime import datetime, timedelta, timezone
from app.models.password_reset import PasswordResetToken
from app.core.email import send_reset_email
from app.core.security import hash_password
```

por:

```python
from app.core.deps import get_current_user
from sqlmodel import Session, select
from app.core.database import get_session
from app.modules.identity.models import User, PasswordResetToken
from app.modules.identity.schemas import UserCreate, UserLogin, UserResponse, Token, TokenPayload
from app.core.security import hash_password, verify_password, create_access_token
from pydantic import BaseModel, Field
import secrets
from datetime import datetime, timedelta, timezone
from app.core.email import send_reset_email
```

(Note: `import os` era não usado; `from app.core.security import hash_password` estava duplicado — ambos removidos porque foram tornados órfãos por esta mudança, conforme regra de mudanças cirúrgicas.)

- [ ] **Step 5: Atualizar `core/deps.py`**

`backend/app/core/deps.py:11` — `from app.models import User` → `from app.modules.identity.models import User`.

- [ ] **Step 6: Atualizar imports de `User` nos routers de clips ainda-não-movidos**

Ainda nesta task, para manter a suíte verde:
- `backend/app/routers/clips.py:11` — hoje `from app.models import User, Video, ProcessingJob, Clip`. Troque para:
  ```python
  from app.modules.identity.models import User
  from app.models import Video, ProcessingJob, Clip
  ```
- `backend/app/routers/jobs.py:17` — hoje `from app.models import User, Video, ProcessingJob, Clip, Candidate`. Troque para:
  ```python
  from app.modules.identity.models import User
  from app.models import Video, ProcessingJob, Clip, Candidate
  ```

- [ ] **Step 7: Atualizar `models/__init__.py`** (remover User e PasswordResetToken)

Substitua o conteúdo de `backend/app/models/__init__.py` por:

```python
# app/models/__init__.py
from .video import Video
from .processingJob import ProcessingJob
from .clip import Clip
from .candidates import Candidate

__all__ = ["Video", "ProcessingJob", "Clip", "Candidate"]
```

- [ ] **Step 8: Deletar os arquivos órfãos**

```bash
git rm backend/app/models/user.py backend/app/models/password_reset.py backend/app/schemas/__init__.py
```

(`schemas/__init__.py` re-exportava de `schemas.auth`, que agora é `identity/schemas.py`; nada mais importa `app.schemas`.)

- [ ] **Step 9: Montar o router no `main.py`**

Em `backend/app/main.py`:
- `from app.routers import auth, jobs, clips` → `from app.routers import jobs, clips` e adicione `from app.modules.identity.router import router as identity_router`.
- Troque a linha `app.include_router(auth.router, prefix="/api/v1")` por `app.include_router(identity_router, prefix="/api/v1")`.

- [ ] **Step 10: Atualizar `test_auth.py`**

`tests/unit/backend/test_auth.py:18` — `from app.models import User` → `from app.modules.identity.models import User`. (Linha 19, `from app.core.security import hash_password`, permanece.)

- [ ] **Step 11: Rodar a suíte**

Run: `python -m pytest`
Expected: PASS. Verifique especialmente `tests/unit/backend/test_auth.py` (rotas `/api/v1/auth/register`, `/login`, etc. intactas).

- [ ] **Step 12: Commit**

```bash
git add -A
git commit -m "refactor(f0): extrai modulo identity (auth + user models)"
```

---

### Task 9: Módulo `clips`

Move jobs + clips para `app/modules/clips/`, consolida os models, aplica exceções de domínio e o storage. Threads + ML **permanecem inline** (F1 troca por Celery). Rotas inalteradas (`/api/v1/jobs/*`, `/api/v1/clips/*`).

**Files:**
- Create: `backend/app/modules/clips/__init__.py`, `models.py`, `schemas.py`, `router.py`
- Modify: `backend/app/main.py`, `tests/unit/backend/test_jobs.py`
- Delete: `backend/app/routers/jobs.py`, `backend/app/routers/clips.py`, `backend/app/routers/__init__.py`, `backend/app/models/` (dir inteiro), `backend/app/schemas/` (dir inteiro)

- [ ] **Step 1: Criar o pacote**

```bash
mkdir -p backend/app/modules/clips
printf '# app.modules.clips\n' > backend/app/modules/clips/__init__.py
```

- [ ] **Step 2: Criar `clips/models.py`** (merge de video + processingJob + clip + candidates; corrige o TYPE_CHECKING quebrado de `candidates.py`)

Create `backend/app/modules/clips/models.py`:

```python
import uuid
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from app.modules.identity.models import User


class Video(SQLModel, table=True):
    __tablename__ = "videos"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    original_filename: str
    storage_path: str
    duration_seconds: Optional[float] = None
    file_size_mb: Optional[float] = None
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    user: Optional["User"] = Relationship(back_populates="videos")
    jobs: List["ProcessingJob"] = Relationship(back_populates="video")


class ProcessingJob(SQLModel, table=True):
    __tablename__ = "processing_jobs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    video_id: uuid.UUID = Field(foreign_key="videos.id")
    target_number: int
    status: str
    hitl_thumbnail_path: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    video: Optional["Video"] = Relationship(back_populates="jobs")
    clips: List["Clip"] = Relationship(back_populates="job")
    candidates: List["Candidate"] = Relationship(
        back_populates="job",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Clip(SQLModel, table=True):
    __tablename__ = "clips"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    job_id: uuid.UUID = Field(foreign_key="processing_jobs.id")
    storage_path: str
    start_timestamp: float
    end_timestamp: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    job: Optional["ProcessingJob"] = Relationship(back_populates="clips")


class Candidate(SQLModel, table=True):
    __tablename__ = "candidates"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    job_id: uuid.UUID = Field(foreign_key="processing_jobs.id")
    signature: str
    name: str
    number: int
    color_hex: Optional[str] = None
    image_path: str
    is_target: bool = Field(default=False)

    job: Optional["ProcessingJob"] = Relationship(back_populates="candidates")
```

- [ ] **Step 3: Criar `clips/schemas.py`** (o `ConfirmPlayerRequest` que estava inline em `jobs.py`)

Create `backend/app/modules/clips/schemas.py`:

```python
from pydantic import BaseModel


class ConfirmPlayerRequest(BaseModel):
    candidate_signature: str
    start_ts: int = 0
    end_ts: int = 0
```

- [ ] **Step 4: Criar `clips/router.py`** a partir de `jobs.py`

```bash
git mv backend/app/routers/jobs.py backend/app/modules/clips/router.py
```

- [ ] **Step 5: Reescrever o bloco de imports de `clips/router.py`**

Substitua o bloco de imports do topo (linhas ~5–24 do antigo `jobs.py`) por:

```python
import traceback
import uuid
import threading
import json
import time
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.core.database import get_session, engine
from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError, ConflictError, DomainError
from app.core.storage import get_storage
from app.modules.identity.models import User
from app.modules.clips.models import Video, ProcessingJob, Clip, Candidate
from app.modules.clips.schemas import ConfirmPlayerRequest
```

Remova, mais abaixo, a definição inline de `class ConfirmPlayerRequest(BaseModel)` (agora em `schemas.py`) e o `from pydantic import BaseModel` se tornar-se órfão. Os 4 `from app.database import get_session` internos às funções de thread já foram trocados para `from app.core.database import get_session` na Task 3 — confirme.

- [ ] **Step 6: Trocar `HTTPException` por exceções de domínio em `confirm_player`**

No corpo de `confirm_player` (antigo `jobs.py:312+`), aplique:

```python
    job = session.get(ProcessingJob, job_id)
    if not job:
        raise NotFoundError("Job não encontrado.")

    if job.status not in ["FAST_SCAN", "WAITING_USER"]:
        raise ConflictError("Este job não aceita mais confirmações.")

    if not job.video:
        raise DomainError("Erro interno: Vídeo não atrelado ao Job.")
```

(`NotFoundError`→404 preserva o comportamento; `ConflictError`→**409** é a única mudança de contrato, documentada no topo; `DomainError`→500 preserva o 500 do vídeo-não-atrelado.)

- [ ] **Step 7: Usar o `StorageBackend` no upload de `create_job`**

Em `create_job`, substitua o trecho que grava o arquivo em disco:

```python
    content = await video.read()
    with open(video_path, "wb") as f:
        f.write(content)

    size_mb = len(content) / (1024 * 1024)
```

por:

```python
    content = await video.read()
    storage = get_storage()
    video_path = storage.save(content, f"videos/{video_id}_{safe_name}")

    size_mb = len(content) / (1024 * 1024)
```

e ajuste a criação do `Video` para `storage_path=str(video_path)` (já é string retornada por `save`). Remova a linha antiga `video_path = UPLOAD_DIR / f"{video_id}_{safe_name}"` que a precedia. `UPLOAD_DIR`/`CLIPS_DIR` continuam definidos e usados (o `CLIPS_DIR` ainda é usado pelo pipeline ML via `output_dir`).

- [ ] **Step 8: Anexar `list_clips` de `clips.py` ao `router.py`**

Copie as funções `list_clips` e `_format_duration` de `backend/app/routers/clips.py` para o final de `backend/app/modules/clips/router.py`, adaptando: o `list_clips` de `clips.py` usa `@router.get("/")` com prefix `/clips`, mas o router deste módulo tem prefix `/jobs`. **Para preservar as URLs**, o módulo `clips` precisa de **dois** routers com prefixos diferentes (`/jobs` e `/clips`) no mesmo arquivo. Adicione, após o `router = APIRouter(prefix="/jobs", tags=["jobs"])` existente:

```python
clips_router = APIRouter(prefix="/clips", tags=["clips"])
brasilia = timezone(timedelta(hours=-3))


@clips_router.get("/")
def list_clips(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    jobs = session.exec(
        select(ProcessingJob)
        .join(Video, ProcessingJob.video_id == Video.id)
        .where(Video.user_id == current_user.id)
        .where(ProcessingJob.status == "COMPLETED")
        .order_by(ProcessingJob.created_at.desc())
    ).all()

    result = []
    for job in jobs:
        clips = session.exec(select(Clip).where(Clip.job_id == job.id)).all()
        if not clips:
            continue
        result.append({
            "job_id": str(job.id),
            "target_number": job.target_number,
            "generated_at": job.updated_at.astimezone(brasilia).strftime("%d/%m/%Y - %H:%M"),
            "clips": [
                {
                    "id": str(c.id),
                    "file_url": f"/uploads/clips/{job.id}/{Path(c.storage_path).name}",
                    "duration": _format_duration(c.end_timestamp - c.start_timestamp),
                }
                for c in clips
            ],
        })
    return result


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    m = total // 60
    s = total % 60
    return f"{m}:{s:02d}"
```

Adicione `timedelta` ao import de `datetime` no topo: `from datetime import datetime, timezone, timedelta`.

- [ ] **Step 9: Deletar os arquivos antigos e diretórios vazios**

```bash
git rm backend/app/routers/clips.py
git rm backend/app/routers/__init__.py
git rm backend/app/models/__init__.py backend/app/models/video.py backend/app/models/processingJob.py backend/app/models/clip.py backend/app/models/candidates.py
```

Após isso `backend/app/routers/`, `backend/app/models/` e `backend/app/schemas/` devem estar vazios. Confirme: `find backend/app/routers backend/app/models backend/app/schemas -type f 2>/dev/null` → vazio (ou "No such file").

- [ ] **Step 10: Montar os dois routers no `main.py`**

Em `backend/app/main.py`:
- Remova `from app.routers import jobs, clips`.
- Adicione `from app.modules.clips.router import router as clips_jobs_router, clips_router`.
- Substitua `app.include_router(jobs.router, prefix="/api/v1")` e `app.include_router(clips.router, prefix="/api/v1")` por:
  ```python
  app.include_router(clips_jobs_router, prefix="/api/v1")
  app.include_router(clips_router, prefix="/api/v1")
  ```

- [ ] **Step 11: Atualizar `test_jobs.py`** (imports + alvos de patch)

Em `tests/unit/backend/test_jobs.py`:
- `from app.models import User, Video, ProcessingJob` (linha 14) →
  ```python
  from app.modules.identity.models import User
  from app.modules.clips.models import Video, ProcessingJob
  ```
- Todos os `patch("app.routers.jobs.threading.Thread")` → `patch("app.modules.clips.router.threading.Thread")` (linhas ~92, ~113, ~128, ~157, ~170, ~191).
- Todos os `patch("app.routers.jobs.engine", engine)` → `patch("app.modules.clips.router.engine", engine)` (linhas ~218, ~237).
- **Atualizar a asserção de contrato:** em `test_confirm_player_wrong_status` (linha ~163), `assert resp.status_code == 400` → `assert resp.status_code == 409`. Adicione um comentário: `# F0 §10.2: estado não-confirmável agora é 409 Conflict (era 400)`.

- [ ] **Step 12: Rodar a suíte inteira**

Run: `python -m pytest`
Expected: PASS. Confirma que exceções (404 job-not-found, 409 wrong-status), storage e as rotas `/api/v1/jobs/*` + `/api/v1/clips/*` estão intactas.

- [ ] **Step 13: Commit**

```bash
git add -A
git commit -m "refactor(f0): extrai modulo clips (jobs+clips), aplica excecoes de dominio e storage"
```

---

### Task 10: Alembic baseline

§10.1: migração baseline a partir do schema atual; `create_all` sai do startup. Toda alteração de modelo passa a exigir migração.

**Files:**
- Create: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/alembic/versions/<hash>_baseline.py`
- Modify: `backend/app/main.py`, `tests/unit/backend/conftest.py`

- [ ] **Step 1: Confirmar `alembic` instalável e inicializar**

Run (a partir de `backend/`): `python -m alembic init alembic`
Expected: cria `backend/alembic/` e `backend/alembic.ini`. (Se `alembic` não estiver instalado: `pip install alembic` — ele entra em `requirements/base.txt` na Task 11.)

- [ ] **Step 2: Configurar `alembic/env.py`** para usar `DATABASE_URL` e `SQLModel.metadata`

Substitua o miolo de `backend/alembic/env.py` para: (a) inserir a raiz do projeto e `backend/` no `sys.path`; (b) ler `DATABASE_URL` do ambiente; (c) importar os models de cada módulo para popular a metadata; (d) apontar `target_metadata` para `SQLModel.metadata`. Bloco de referência a colar no topo (após os imports padrão gerados pelo alembic):

```python
import os
import sys
from pathlib import Path

from sqlmodel import SQLModel
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
for p in (str(PROJECT_ROOT), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

load_dotenv()

# Importa os models para registrar todas as tabelas na metadata.
import app.modules.identity.models  # noqa: F401,E402
import app.modules.clips.models  # noqa: F401,E402

config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
target_metadata = SQLModel.metadata
```

Garanta que `run_migrations_online()` / `run_migrations_offline()` usem `target_metadata` (o template do alembic já faz isso; só troque o `target_metadata = None` gerado).

- [ ] **Step 3: Gerar a migração baseline**

Run (a partir de `backend/`, com `DATABASE_URL` apontando para o Postgres/Supabase — ou um Postgres de dev): `python -m alembic revision --autogenerate -m "baseline"`
Expected: cria `backend/alembic/versions/<hash>_baseline.py` com `create_table` para `users`, `videos`, `processing_jobs`, `clips`, `candidates`, `password_reset_tokens`.

- [ ] **Step 4: Verificar que a baseline aplica limpo**

Se o banco já tem as tabelas (schema atual via `create_all`), marque a baseline como aplicada sem recriar: `python -m alembic stamp head`. Se for um banco limpo: `python -m alembic upgrade head`.
Expected: `alembic current` mostra o hash da baseline.

- [ ] **Step 5: Remover `create_all` do startup**

Em `backend/app/main.py`, na função `on_startup`, remova a chamada `create_db_and_tables()` e o import `from app.core.database import create_db_and_tables` se tornar-se órfão. Mantenha a criação das pastas de upload e o aquecimento do pipeline (comportamento inalterado — YOLO na API só sai no F1). A função `create_db_and_tables` em `core/database.py` permanece (usada por ferramentas/scripts), mas não é mais chamada no boot.

- [ ] **Step 6: Ajustar `conftest.py`** (o patch de `create_db_and_tables` no startup)

`tests/unit/backend/conftest.py` faz `with patch("app.main.create_db_and_tables", ...)`. Como o startup não chama mais essa função, remova esse `with patch(...)` aninhado (linha ~54), mantendo o `patch("app.main._get_pipeline", ...)`. Os testes criam tabelas via `SQLModel.metadata.create_all(engine)` na fixture `engine` — inalterado.

- [ ] **Step 7: Rodar a suíte**

Run: `python -m pytest`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(f0): alembic baseline e remocao do create_all no startup"
```

---

### Task 11: Split de requirements

§4.1: `base.txt` (comum), `api.txt` (`-r base.txt` + servidor/web) e `worker.txt` (`-r base.txt` + ML/torch). A imagem da API deixa de baixar torch.

**Files:**
- Create: `backend/requirements/base.txt`, `api.txt`, `worker.txt`
- Delete: `backend/requirements.txt`

- [ ] **Step 1: Criar `requirements/base.txt`**

Create `backend/requirements/base.txt` (comum aos dois processos; inclui `alembic`, `celery` e `redis` — declarados já no F0 para o F1 não mexer nesta estrutura):

```
fastapi==0.133.1
sqlmodel==0.0.37
SQLAlchemy==2.0.48
alembic>=1.13
pydantic==2.12.5
pydantic-settings==2.13.1
python-dotenv==1.2.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt>=4.0
python-multipart==0.0.22
email-validator==2.3.0
psycopg2-binary==2.9.10
celery>=5.3
redis>=5.0
```

- [ ] **Step 2: Criar `requirements/api.txt`**

```
-r base.txt
uvicorn==0.41.0
resend==2.29.0
websockets==16.0
```

- [ ] **Step 3: Criar `requirements/worker.txt`**

```
-r base.txt
--extra-index-url https://download.pytorch.org/whl/cu118
torch>=2.0.0
torchvision>=0.15.0
torchaudio>=2.0.0
ultralytics>=8.0.0
opencv-python-headless>=4.8.0
supervision>=0.18.0
easyocr>=1.7.0
deep-sort-realtime>=1.3.0
imageio-ffmpeg>=0.6.0
```

- [ ] **Step 4: Remover o requirements monolítico**

```bash
git rm backend/requirements.txt
```

- [ ] **Step 5: Verificar que `api.txt` resolve (sem torch)**

Run: `pip install --dry-run -r backend/requirements/api.txt`
Expected: resolve sem baixar `torch`/`ultralytics`. (Se `--dry-run` não estiver disponível na versão do pip, criar um venv descartável e instalar; o critério é: nenhum pacote de ML na árvore de `api.txt`.)

- [ ] **Step 6: Rodar a suíte** (garante que nada dependia do arquivo antigo)

Run: `python -m pytest`
Expected: PASS. Confirme também que `requirements-test.txt` na raiz continua válido (inalterado).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore(f0): split de requirements em base/api/worker"
```

---

### Task 12: Docker Compose (redis + api + web)

§4.1: o Compose sobe `redis`, `api` e `web`. Worker fica de fora (profile opcional entra no F1). Postgres é externo (Supabase).

**Files:**
- Create: `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, `.dockerignore`

- [ ] **Step 1: `backend/Dockerfile`** (instala só `api.txt` — sem torch)

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/api.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

- [ ] **Step 2: `frontend/Dockerfile`** (vite dev)

Create `frontend/Dockerfile`:

```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

- [ ] **Step 3: `docker-compose.yml`** na raiz

Create `docker-compose.yml`:

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api:
    build: ./backend
    env_file: ./backend/.env
    environment:
      - REDIS_URL=redis://redis:6379/0
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    depends_on:
      - redis

  web:
    build: ./frontend
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    depends_on:
      - api
```

(Postgres não aparece: é o Supabase externo, referenciado por `DATABASE_URL` no `backend/.env`.)

- [ ] **Step 4: `.dockerignore`** na raiz

Create `.dockerignore`:

```
**/__pycache__
**/node_modules
**/.venv
**/uploads
**/.git
**/*.pyc
.coverage
```

- [ ] **Step 5: Validar a composição**

Run: `docker compose config`
Expected: imprime a composição resolvida sem erro de sintaxe. (Se Docker estiver disponível, um smoke test opcional: `docker compose up redis api` e `curl http://localhost:8000/docs` retorna 200. O worker/GPU não faz parte deste teste.)

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(f0): docker-compose com redis/api/web e Dockerfiles sem torch na api"
```

---

### Task 13: Verificação final + nota no README

**Files:**
- Modify: `README.md` (seção de execução, se existir)

- [ ] **Step 1: Suíte completa a partir da raiz**

Run: `python -m pytest`
Expected: PASS — mesmo (ou maior, pelos novos testes de `exceptions`/`storage`) número da Task 1. Zero falhas.

- [ ] **Step 2: Import smoke test do app** (garante que o boot resolve)

Run: `python -c "import os; os.environ.setdefault('DATABASE_URL','sqlite://'); os.environ.setdefault('JWT_SECRET_KEY','x'); from app.main import app; print([r.path for r in app.routes if getattr(r,'path','').startswith('/api/v1')])"` (a partir de `backend/`, com o mock de ML se necessário)
Expected: lista contém `/api/v1/auth/register`, `/api/v1/auth/login`, `/api/v1/jobs/`, `/api/v1/jobs/{job_id}/confirm`, `/api/v1/jobs/{job_id}/stream`, `/api/v1/clips/`. **Nenhuma URL mudou** em relação ao main.

- [ ] **Step 3: Grep de sobras da estrutura antiga**

Run: `grep -rn "app.routers\|from app.models\|from app.database\|from app.config\|from app.schemas\|app.core.auth" backend tests --include=*.py | grep -v __pycache__`
Expected: nenhuma linha (todas migradas para `app.modules.*` / `app.core.*`).

- [ ] **Step 4: Atualizar o README** com a nova forma de rodar (compose + alembic). Adicione uma subseção curta: subir com `docker compose up`, aplicar migrações com `alembic upgrade head` a partir de `backend/`, e a nota de que toda mudança de modelo agora exige `alembic revision --autogenerate`.

- [ ] **Step 5: Commit final**

```bash
git add -A
git commit -m "docs(f0): atualiza README com compose e fluxo de migracoes"
```

- [ ] **Step 6: Abrir o PR curto** (Onda 0)

```bash
git push -u origin f0/reestruturacao-base
```

Descreva no PR: escopo do F0, a **única mudança de contrato** (confirm em estado inválido: 400→409), e o lembrete de que todo mundo deve rebasar em cima antes das ondas F1/F2/F3.

---

## Self-Review (checklist do autor)

**Cobertura da spec (§ do design doc):**
- §4.2 estrutura de pastas → Tasks 3–9 (core/ + modules/identity + modules/clips). *Módulos não-usados adiados por decisão de escopo (documentada).*
- §4.1 split de requirements + compose → Tasks 11–12.
- §10.1 Alembic baseline + `create_all` fora do startup → Task 10.
- §10.2 hierarquia de exceções + handler único + router sem HTTPException → Tasks 6 e 9.
- §4.2 StorageBackend → Tasks 7 e 9.
- "deletar routers mortos" → Task 2.
- "mover models existentes" → Tasks 8–9.
- **Zero feature nova** → nenhuma rota/campo novo; única mudança de contrato (409) isolada e sinalizada.

**Fora de escopo do F0 (confirmado adiado):** Celery/worker (F1), YOLO fora da API (F1), quebra de `video_pipeline.py` (F1/M7), `role`/perfis multi-papel (F2), troca de prefixos HTTP + reescrita de `services/api.ts` (F1), `service.py`/`repository.py`/`events.py` (fases que introduzem a lógica).

**Consistência de tipos/nomes:** `NotFoundError`/`ConflictError`/`DomainError` definidos na Task 6 e usados na Task 9 com as mesmas assinaturas; `get_storage()`/`LocalStorageBackend.save/path_for` definidos na Task 7 e consumidos na Task 9; `get_session`/`engine` importados de `app.core.database` em todo o código pós-Task 3; os dois routers (`router` prefix `/jobs`, `clips_router` prefix `/clips`) montados coerentemente na Task 9/main.py.

**Invariante de execução:** toda task termina com `python -m pytest` verde. Fase de refactor puro — a suíte é a rede de segurança.
