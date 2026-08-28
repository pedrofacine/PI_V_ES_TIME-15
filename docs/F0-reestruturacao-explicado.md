# F0 — Reestruturação Base: o que foi feito (explicado de forma simples)

> Este documento explica, em linguagem direta, **tudo** que a fase **F0** mudou no backend do
> SmartScout. Serve para qualquer pessoa da equipe entender a nova organização — mesmo sem ter
> acompanhado a implementação. Se você só tem 30 segundos, leia o "Resumo em uma frase" e a
> tabela "Antes → Depois".

---

## Resumo em uma frase

Reorganizamos o backend de um monte de pastas soltas (`routers/`, `models/`, `schemas/`) para
uma estrutura por **módulos de domínio** (`identity`, `clips`) com uma base compartilhada
(`core/`), **sem adicionar nenhuma funcionalidade nova** — só arrumamos a casa para as próximas
fases construírem em cima sem tropeçar.

**Por que fazer isso?** O código estava crescendo e tudo era importado de todo lugar. Cada nova
feature ia ficar mais difícil e arriscada. O F0 paga essa dívida agora, uma vez, para as sete
fases seguintes (F1, F2, F3, M1…M7) andarem rápido.

**Regra de ouro do F0:** o comportamento da API continua **idêntico**. Nenhuma tela quebra,
nenhuma rota muda de endereço. (Exceção: um único código de erro mudou — explicado lá embaixo.)

---

## Antes → Depois (o mapa da mudança)

**Antes** — tudo agrupado por "tipo de arquivo":

```
backend/app/
├── config.py            ← configurações soltas na raiz
├── database.py          ← conexão com o banco solta na raiz
├── core/
│   ├── auth.py          ← dependência de autenticação
│   ├── security.py
│   └── email.py
├── models/              ← TODAS as tabelas juntas
│   ├── user.py
│   ├── video.py
│   ├── processingJob.py
│   ├── clip.py
│   ├── candidates.py
│   └── password_reset.py
├── routers/             ← TODAS as rotas juntas
│   ├── auth.py
│   ├── jobs.py
│   ├── clips.py
│   ├── users.py         ← morto (nunca usado)
│   ├── videos.py        ← morto
│   └── fast_scan.py     ← morto
├── schemas/
│   ├── auth.py
│   └── user_schema.py   ← morto
└── main.py
```

**Depois** — agrupado por "assunto" (domínio):

```
backend/app/
├── core/                ← INFRAESTRUTURA compartilhada por todos
│   ├── config.py        ← (veio da raiz)
│   ├── database.py      ← (veio da raiz)
│   ├── deps.py          ← (era core/auth.py, renomeado)
│   ├── security.py
│   ├── email.py
│   ├── exceptions.py    ← NOVO: erros de domínio
│   └── storage.py       ← NOVO: abstração de arquivos
├── modules/             ← Um pacote por ASSUNTO
│   ├── identity/        ← tudo de "usuário e login"
│   │   ├── models.py    (User + PasswordResetToken)
│   │   ├── schemas.py
│   │   └── router.py
│   └── clips/           ← tudo de "vídeo, job e clipe"
│       ├── models.py    (Video + ProcessingJob + Clip + Candidate)
│       ├── schemas.py
│       └── router.py
└── main.py              ← só monta as rotas e o tratador de erros
```

A ideia central: **"coisas que mudam juntas ficam juntas"**. Quando você for mexer em login, tudo
está em `modules/identity/`. Quando for mexer em clipes, tudo está em `modules/clips/`. Você não
precisa mais caçar o model em uma pasta, a rota em outra e o schema em uma terceira.

---

## A anatomia de um módulo

Cada módulo em `modules/` segue sempre o mesmo desenho:

| Arquivo | O que faz | Analogia |
|---|---|---|
| `router.py` | Recebe a requisição HTTP, valida entrada, devolve resposta | O **garçom**: anota o pedido e entrega o prato |
| `models.py` | As tabelas do banco (SQLModel) daquele assunto | O **estoque**: o que existe guardado |
| `schemas.py` | Os formatos de entrada/saída (o "contrato" com quem chama) | O **cardápio**: o que pode pedir e como vem |
| `service.py` | Regra de negócio (ainda **não existe** no F0) | A **cozinha**: onde a decisão acontece |
| `repository.py` | Acesso a dados (ainda **não existe** no F0) | O **almoxarife**: só ele mexe no estoque |

No F0 criamos só `router`, `models` e `schemas`, porque é o que já tinha conteúdo. `service` e
`repository` entram quando a lógica for separada (fases F1/F2). Não criamos pastas vazias à toa.

---

## O que mudou, passo a passo (e por quê)

Foram **11 commits**, cada um pequeno e com os testes passando. Em ordem:

### 1. Removemos código morto
Três rotas (`users.py`, `videos.py`, `fast_scan.py`) e um schema (`user_schema.py`) que **nunca
eram usados** (não estavam ligados ao app; `fast_scan.py` até importava caminhos quebrados).
Apagar isso primeiro diminuiu a bagunça antes de mexer no resto.

### 2. Juntamos a infraestrutura em `core/`
- `config.py` e `database.py` saíram da raiz e foram para `core/` (o lugar certo para "coisas
  que todo mundo usa").
- `core/auth.py` virou `core/deps.py` — o nome "deps" (dependências) descreve melhor o que ele é:
  a peça que o FastAPI injeta nas rotas para saber **quem é o usuário logado**.
- Ninguém precisa decorar isso: todos os `import` foram atualizados juntos, e os testes garantiram
  que nada quebrou.

### 3. Criamos uma forma única de tratar erros (`core/exceptions.py`)
**O problema antigo:** as rotas misturavam regra de negócio com detalhes de HTTP, montando
`HTTPException(status_code=404, ...)` na mão, cada uma do seu jeito.

**A solução:** uma família de "erros de domínio" com significado claro, e **um único ponto** no
`main.py` que traduz cada um para o código HTTP certo:

| Erro de domínio | Vira o código HTTP | Quando usar |
|---|---|---|
| `NotFoundError` | 404 | Não achei o recurso |
| `ForbiddenError` | 403 | Você não pode fazer isso |
| `ConflictError` | 409 | Estado conflita com a ação |
| `QuotaExceededError` | 402 | Estourou o limite do plano |
| `ValidationError` | 422 | Dados inválidos |
| `DomainError` (base) | 500 | Erro interno inesperado |

Agora a rota só diz `raise NotFoundError("Job não encontrado")` e **não precisa saber** que isso
é um 404. Mais limpo e consistente.

### 4. Criamos uma abstração de armazenamento (`core/storage.py`)
Antes, salvar um vídeo era um `open(caminho, "wb")` cravado no meio da rota. Agora existe um
`StorageBackend` com um `LocalStorageBackend` (grava em disco). Se um dia trocarmos para S3 ou
Supabase Storage, muda só essa peça — o resto do código nem fica sabendo.

### 5. Extraímos o módulo `identity`
Toda a autenticação (rotas de registro/login/reset de senha, o model `User`, o
`PasswordResetToken` e os schemas) foi para `modules/identity/`. **As URLs continuam iguais**
(`/api/v1/auth/register`, `/api/v1/auth/login`, etc.).

### 6. Extraímos o módulo `clips`
Tudo de vídeo/job/clipe (as rotas de `jobs.py` + `clips.py`, e os models `Video`, `ProcessingJob`,
`Clip`, `Candidate`) foi para `modules/clips/`. As URLs continuam iguais
(`/api/v1/jobs/...` e `/api/v1/clips/`). Aqui também:
- trocamos os `HTTPException` pelos erros de domínio novos;
- o upload de vídeo passou a usar o `StorageBackend`;
- **o processamento de vídeo continua igual** (ainda roda em threads, com a IA carregada na API).
  Trocar isso por uma fila (Celery) é assunto da **próxima fase, a F1**.

### 7. Separamos as dependências (`requirements/`)
Antes era um `requirements.txt` gigante que misturava o servidor web com o `torch`/YOLO (pesadão).
Agora são três:

| Arquivo | Contém | Para quê |
|---|---|---|
| `base.txt` | fastapi, sqlmodel, alembic, celery, redis… | comum aos dois |
| `api.txt` | `base` + uvicorn, resend, websockets | o servidor da API |
| `worker.txt` | `base` + torch, ultralytics, opencv… | o processador de vídeo (futuro) |

**Ganho concreto:** a imagem da API não baixa mais o `torch` (economia enorme de tempo/espaço).

### 8. Adotamos migrações de banco com Alembic
**O problema antigo:** o app criava as tabelas sozinho no boot (`create_all`). Isso funciona no
começo, mas quando você muda um model, o banco não se atualiza — e não há histórico do schema.

**A solução:** o **Alembic** gerencia o banco por "migrações" — arquivos versionados que descrevem
cada mudança de schema. Geramos uma migração **baseline** (`dc5867a2d8e8_baseline.py`) que
representa o schema atual, e marcamos seu banco como "já nessa versão" (sem recriar nada, sem
tocar nos seus dados). O `create_all` saiu do startup.

**O que isso muda para você no dia a dia:** sempre que alterar um model, rode:
```bash
# a partir de backend/
alembic revision --autogenerate -m "o que mudou"   # cria a migração
alembic upgrade head                                # aplica no banco
```

### 9. Adicionamos Docker Compose
Um `docker-compose.yml` na raiz sobe **`redis` + `api` + `web`** com um comando
(`docker compose up`). O Postgres continua externo (Supabase). O worker de GPU fica de fora por
enquanto (entra na F1). Cada serviço tem seu `Dockerfile`.

---

## ⚠️ A ÚNICA mudança de comportamento em toda a fase

Confirmar um job que **já passou** da fase de confirmação (ex.: um job `COMPLETED`) agora responde
**409 Conflict** em vez de **400 Bad Request**.

- Rota afetada: `POST /api/v1/jobs/{id}/confirm`
- Motivo: 409 ("conflito de estado") é semanticamente mais correto, e veio de graça com a nova
  família de erros de domínio.
- Impacto no frontend: praticamente nulo (é um caso de borda que só mostra uma mensagem de erro).

Se a equipe preferir manter o 400, é um ajuste de **uma linha** no tratador de erros.

---

## Como rodar o projeto agora

**Opção A — local:**
```bash
cd backend
pip install -r requirements/api.txt   # sem torch
alembic upgrade head                  # aplica migrações
python -m uvicorn app.main:app --reload
```

**Opção B — Docker (sobe tudo de uma vez):**
```bash
docker compose up        # na raiz do projeto: redis + api + web
```

> Detalhe de ambiente: os testes do backend rodam a partir da pasta `backend/`
> (`cd backend && python -m pytest ../tests/unit/backend`). Rodar da raiz falha na coleta por um
> detalhe de caminho relativo do mount de `uploads` — é esperado, não é bug.

---

## O que **NÃO** faz parte do F0 (para não gerar confusão)

Estas coisas foram deliberadamente deixadas para as próximas fases:

| Item | Fase |
|---|---|
| Fila assíncrona (Celery/Redis) e tirar a IA da API | F1 |
| Quebrar o `video_pipeline.py` (45 KB) | F1 / M7 |
| Perfis multi-papel (atleta/scout/clube), campo `role` | F2 |
| Trocar prefixos de URL (`/jobs` → `/clips/jobs`) e reescrever o `services/api.ts` do front | F1 |
| Camadas `service.py` / `repository.py` nos módulos | quando a lógica for separada (F1/F2) |
| Feed, busca, oportunidades, chat, entitlements | M1–M6 |

---

## Verificação (a prova de que está tudo certo)

- **Testes:** 29 testes de backend passando (eram 24; +5 dos novos `exceptions`/`storage`). As 3
  falhas de ML pré-existentes não foram tocadas (são de outra camada).
- **Rotas:** nenhuma URL mudou — os testes cobrem `/api/v1/auth/*`, `/api/v1/jobs/*` e
  `/api/v1/clips/`.
- **Banco:** as 6 tabelas originais intactas + a tabela de controle `alembic_version`. Nenhum dado
  tocado.
- **Estrutura antiga:** zero referências a `app.routers` / `app.models` / `app.database` sobrando.

---

## Os 11 commits (na ordem)

```
chore(f0): remove dead routers (users, videos, fast_scan) e schema orfao
refactor(f0): move database para core/ e remove registro de models redundante
refactor(f0): move config para core/
refactor(f0): renomeia core/auth.py para core/deps.py
feat(f0): hierarquia de excecoes de dominio + handler unico
feat(f0): abstracao StorageBackend com backend local
refactor(f0): extrai modulo identity (auth + user models)
refactor(f0): extrai modulo clips (jobs+clips), aplica excecoes de dominio e storage
chore(f0): split de requirements em base/api/worker
feat(f0): alembic baseline e remocao do create_all no startup
feat(f0): docker-compose com redis/api/web e Dockerfiles sem torch na api
```

Referências: o plano detalhado está em `docs/superpowers/plans/2026-08-25-f0-reestruturacao-base.md`
e a spec de arquitetura em `docs/superpowers/specs/2026-08-11-smartscout-rede-social-design.md`.
