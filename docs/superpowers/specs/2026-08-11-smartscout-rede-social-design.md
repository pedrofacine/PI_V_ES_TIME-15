# SmartScout — Evolução para Rede Social Profissional

**Data:** 2026-08-11
**Status:** Aprovado
**Escopo de origem:** `specs/pdfs/Escopo PI6 - SmartScout.pdf`

---

## Sumário

- [1. Contexto e objetivo](#1-contexto-e-objetivo)
- [2. Estado atual e problemas](#2-estado-atual-e-problemas)
- [3. Decisões de arquitetura](#3-decisões-de-arquitetura)
- [4. Topologia e fronteiras](#4-topologia-e-fronteiras)
- [5. Modelo de domínio](#5-modelo-de-domínio)
- [6. Fluxo assíncrono de clipes](#6-fluxo-assíncrono-de-clipes)
- [7. Política de retenção](#7-política-de-retenção)
- [8. Entitlements](#8-entitlements)
- [9. Frontend](#9-frontend)
- [10. Migrações, erros e testes](#10-migrações-erros-e-testes)
- [11. Roadmap decomposto](#11-roadmap-decomposto)
- [12. Riscos](#12-riscos)
- [13. Fora de escopo](#13-fora-de-escopo)

---

## 1. Contexto e objetivo

O SmartScout hoje é uma **ferramenta linear**: o usuário sobe o vídeo de uma partida,
informa o número da camisa, e a IA devolve os clipes daquele atleta.

A evolução do PI6 transforma o produto em uma **rede social profissional** que aproxima
atletas de scouts e clubes. O gerador de clipes deixa de ser o produto e passa a ser
**um módulo entre outros**, disponível conforme o plano do usuário. Os clipes gerados
ganham finalidade nova: são o portfólio que o atleta publica no feed para ser avaliado.

Essa inversão é o eixo do design. Tudo que segue existe para suportá-la sem que a
plataforma vire um monolito acoplado onde nenhum módulo pode evoluir sozinho.

---

## 2. Estado atual e problemas

### 2.1 O que existe

| Camada | Stack | Estado |
|---|---|---|
| `backend/` | FastAPI 0.133, SQLModel 0.0.37, PostgreSQL (Supabase) | 6 models, 6 routers |
| `frontend/` | React 19, TypeScript 5.9, Vite 7.3, CSS puro | ~10 páginas |
| `ml/` | PyTorch, Ultralytics YOLO, DeepSort, EasyOCR, OpenCV | pipeline funcional |

### 2.2 Problemas que bloqueiam a evolução

Estes não são débitos cosméticos — cada um impede diretamente algum requisito do PDF.

1. **A API carrega o modelo de visão na própria memória.**
   `backend/app/main.py:50` chama `_get_pipeline()` no evento de startup. Consequências:
   o processo web só sobe onde houver GPU; a imagem da API arrasta ~2 GB de torch; e um
   job pesado degrada as requisições HTTP de todos os usuários. Impede o requisito 2.2.

2. **Background com `threading.Thread(daemon=True)`.**
   `backend/app/routers/jobs.py:298` e `:339`. Threads daemon morrem com o processo: se a
   API reinicia no meio de um job, o registro fica em `TRACKING` para sempre, sem nenhum
   mecanismo de recuperação. Não há retry, timeout nem visibilidade.

3. **SSE por polling de banco.**
   `backend/app/routers/jobs.py:83` faz `time.sleep(2.0)` em laço, consultando
   `processing_jobs`, `clips` e `candidates` a cada 2 s **por cliente conectado**.

4. **Regra de negócio dentro dos routers.**
   `jobs.py` tem 346 linhas misturando HTTP, orquestração de ML, gerência de threads,
   sessões de banco e tratamento de erro. Não é testável em unidade.

5. **Sem migrações.**
   `backend/app/database.py:26` usa `SQLModel.metadata.create_all`, que cria tabela nova
   mas **nunca altera coluna existente**. Com ~14 tabelas e a equipe inteira mexendo em
   modelos, o schema de cada máquina diverge em silêncio.

6. **Código morto.**
   `routers/users.py`, `routers/videos.py` e `routers/fast_scan.py` existem mas nunca
   foram registrados no `main.py`.

7. **`ml/scripts/video_pipeline.py` tem 45 KB em um único arquivo.**
   Impede o requisito 2.1: qualquer mudança de precisão ou a adição de goleiro é uma
   roleta sobre código que ninguém consegue ler inteiro.

8. **Frontend sem camada de estado de servidor.**
   `services/api.ts` é um módulo único de 7,6 KB. Feed paginado, busca com filtros e
   lista de oportunidades exigem cache e invalidação.

---

## 3. Decisões de arquitetura

| # | Decisão | Alternativas descartadas | Razão |
|---|---|---|---|
| D1 | Docker Compose local + Supabase (Postgres externo) | Compose 100% local; cloud gerenciada | Mantém o banco que já funciona; sem custo de nuvem; GPU fica local |
| D2 | Worker separado, mesmo repositório | Microsserviço com repo próprio; fila sem separar processo | Separa deploy e recursos sem o atrito de multi-repo para uma equipe acadêmica |
| D3 | Monolito modular por domínio | Camadas horizontais; Clean/Hexagonal | 8 domínios novos: coesão por módulo mantém arquivos pequenos e dá dono claro. Clean duplicaria cada entidade, contrariando o propósito do SQLModel |
| D4 | Celery + Redis | RQ; fila em Postgres | Beat resolve o job agendado de retenção; Redis já é necessário para o chat |
| D5 | Storage em disco atrás de `StorageBackend` | MinIO; Supabase Storage | Mudança mínima agora, com a porta aberta para S3 sem tocar em domínio |
| D6 | WebSocket nativo no FastAPI + Redis pub/sub | Supabase Realtime; REST polling | Tempo real de verdade, sem amarrar o domínio a vendor, com autorização própria por conversa |
| D7 | Frontend reescrito com design system | Só feature-based; empilhar páginas | O produto muda de natureza; CSS puro não sustenta feed, chat e busca |
| D8 | Entitlements sem gateway de pagamento | Gateway em sandbox; sem plano nenhum | Foco no controle de acesso. `Subscription` encaixa depois trocando a leitura dentro do service |

### D3 — a regra que sustenta o monolito modular

> **Um módulo importa apenas o `service.py` de outro módulo.
> Nunca `repository.py`, nunca `models.py`, nunca tabela alheia.**

Sem essa regra, "monolito modular" é só uma organização de pastas. Exemplo concreto:
quando `feed` publica um post com clipe, ele **não** executa `UPDATE clips SET status=...`;
ele chama `clips_service.mark_as_permanent(clip_id)`. O módulo `clips` continua sendo o
único lugar do sistema que conhece o ciclo de vida de um clipe.

---

## 4. Topologia e fronteiras

### 4.1 Processos

| Serviço | Conteúdo | Restrição |
|---|---|---|
| `api` | FastAPI + SQLModel. **Sem torch, sem CUDA.** | Não importa `ml.*` |
| `worker` | Celery, `concurrency=1`. Dono exclusivo do pipeline de visão. | Não importa `app.modules.*.router` |
| `beat` | Celery Beat. Só agenda retenção e varredura de jobs órfãos. | — |
| `redis` | Broker do Celery **e** pub/sub de chat e progresso. | — |
| `web` | Vite dev server. | — |
| Postgres | Supabase, externo ao Compose. | — |

`requirements.txt` hoje é único e mistura os dois mundos. Passa a ser:

```
requirements/
├─ base.txt      # fastapi, sqlmodel, alembic, celery, redis, ...
├─ api.txt       # -r base.txt  + uvicorn, resend, websockets
└─ worker.txt    # -r base.txt  + torch, ultralytics, opencv, easyocr, deep-sort
```

A imagem da API deixa de baixar torch.

**GPU em container.** O worker roda em WSL2 + nvidia-container-toolkit **ou** nativo no
host (`celery -A worker.celery_app worker -P solo`). O Compose sobe `redis`, `api` e `web`;
o worker fica em um profile opcional. O Compose **não** é pré-requisito para a GPU
funcionar — essa é a contingência do risco R1.

### 4.2 Estrutura de pastas

```
backend/
├─ alembic/
│  └─ versions/
├─ app/
│  ├─ core/                 config, database, security, deps,
│  │                        exceptions, storage, events
│  ├─ modules/
│  │  ├─ identity/          router · service · repository · models · schemas
│  │  ├─ profiles/
│  │  ├─ clips/
│  │  ├─ feed/
│  │  ├─ discovery/
│  │  ├─ opportunities/
│  │  ├─ messaging/
│  │  └─ entitlements/
│  └─ main.py               só monta routers e handlers
├─ worker/
│  ├─ celery_app.py
│  ├─ tasks/
│  │  ├─ clip_generation.py
│  │  ├─ retention.py
│  │  └─ health.py
│  └─ callbacks.py          escreve no banco + publica no Redis
└─ requirements/

ml/                         biblioteca pura: sem FastAPI, sem SQLModel

frontend/src/
├─ app/                     router, providers, shell
├─ shared/                  ui/ (shadcn) · lib/http · hooks · types
└─ features/
   ├─ auth/  profiles/  feed/  discovery/
   └─ opportunities/  messaging/  clips/
        cada uma: api.ts · hooks/ · components/ · pages/
```

Cada módulo do backend tem a mesma anatomia:

| Arquivo | Responsabilidade |
|---|---|
| `router.py` | HTTP: rota, validação de entrada, serialização. Sem regra. |
| `service.py` | Regra de negócio. Levanta exceções de domínio. Único ponto de entrada para outros módulos. |
| `repository.py` | Acesso a dados. Só o próprio módulo usa. |
| `models.py` | Tabelas SQLModel do módulo. |
| `schemas.py` | DTOs de entrada e saída. |

**Mudança de contrato HTTP.** Os prefixos passam a seguir o módulo: `/api/v1/jobs` vira
`/api/v1/clips/jobs`, e `/api/v1/uploads` passa a ser servido pelo módulo `clips`. É
quebra de contrato com o frontend atual, absorvida em F0/F1 junto com a reescrita de
`services/api.ts`. A versão `v1` é mantida — não há consumidor externo para versionar.

### 4.3 Contrato entre `api` e `worker`

O único acoplamento permitido são três coisas:

1. O payload da task Celery.
2. A tabela `processing_jobs`.
3. O canal Redis `job:{job_id}:progress`.

```
POST /clips/jobs ──► api grava Video + Job(PENDING) ──► enfileira ──► 202
                                                            │
   worker consome ──► publica progresso no Redis ───────────┘
                            │
   api assina o canal ──► SSE para o browser
```

### 4.4 Fronteira com `ml/`

O pacote `ml/` continua sendo biblioteca pura. O acoplamento acontece pelos callbacks
(`on_candidate_found`, `on_clip_generated`, `on_extracting_start`) que hoje o router
injeta e que passam a ser injetados pelo worker — são eles que escrevem no banco e
publicam no Redis. Esse desenho de callbacks já existe e está correto; muda apenas quem
os fornece.

O que muda **dentro** de `ml/` é a quebra de `video_pipeline.py` (45 KB), pré-requisito
para as melhorias do requisito 2.1.

---

## 5. Modelo de domínio

### 5.1 Multi-papel

Um `User` (credencial + papel) e **um perfil 1:1 por papel**. Achatar os três papéis em
colunas nullable de uma tabela só produziria ~25 colunas majoritariamente NULL, sem
nenhuma constraint possível: atleta tem posição, pé dominante, altura e data de
nascimento; clube tem CNPJ e categorias de base; scout tem organização e credencial.

```
users (id, email, password_hash, first_name, last_name, role, plan, created_at)
  role ∈ {ATHLETE, SCOUT, CLUB}   ← definido no cadastro, imutável
  plan ∈ {FREE, PRO}
   │
   ├─1:1─ athlete_profiles (user_id PK/FK, position, birth_date, height_cm,
   │                        dominant_foot, state, city, current_club, bio, avatar_path)
   ├─1:1─ scout_profiles   (user_id PK/FK, organization, credential,
   │                        state, city, bio, avatar_path)
   └─1:1─ club_profiles    (user_id PK/FK, legal_name, cnpj, categories,
                            state, city, bio, avatar_path)
```

O perfil é criado na mesma transação do cadastro. Um `User` sem perfil correspondente ao
seu papel é estado inválido.

### 5.2 Tabelas por módulo

| Módulo | Tabelas | Situação |
|---|---|---|
| `identity` | `users`, `password_reset_tokens` | existem; ganham `role` e `plan` |
| `profiles` | `athlete_profiles`, `scout_profiles`, `club_profiles` | novas |
| `clips` | `videos`, `processing_jobs`, `clips`, `candidates` | existem; movidas e estendidas |
| `feed` | `posts`, `post_likes`, `post_comments` | novas |
| `opportunities` | `opportunities`, `applications` | novas |
| `messaging` | `conversations`, `conversation_participants`, `messages` | novas |
| `entitlements` | nenhuma | lê `users.plan` contra matriz em config |

### 5.3 Campos novos em tabelas existentes

| Tabela | Campo | Motivo |
|---|---|---|
| `users` | `role`, `plan` | multi-papel e entitlements |
| `clips` | `status ∈ {TEMPORARY, PERMANENT}` | política de retenção |
| `processing_jobs` | `user_id` | checagem de quota e autorização sem join por `video` |
| `processing_jobs` | `heartbeat_at` | detecção de job órfão |
| `processing_jobs` | `error_message` | diagnóstico de falha |

`users.max_clips_allowed` (hoje hardcoded em `models/user.py:18`) é removido; o limite
passa a vir da matriz de planos.

### 5.4 Feed

```
posts (id, author_user_id, clip_id NULL, caption, visibility, created_at)
post_likes (post_id, user_id, created_at)          PK composta
post_comments (id, post_id, author_user_id, body, created_at)
```

`clip_id` é nullable: um post pode ser só texto. Quando é preenchido, `feed_service`
chama `clips_service.mark_as_permanent(clip_id)` — nunca escreve na tabela `clips`.

### 5.5 Oportunidades

```
opportunities (id, owner_user_id, title, description, mode, location,
               starts_at, application_deadline, status, created_at)
  mode ∈ {PRESENCIAL, ONLINE}
  status ∈ {OPEN, CLOSED}
applications (id, opportunity_id, athlete_user_id, message, status, created_at)
  status ∈ {PENDING, ACCEPTED, REJECTED}
  UNIQUE (opportunity_id, athlete_user_id)
```

Só `SCOUT` e `CLUB` criam oportunidade; só `ATHLETE` se inscreve. Regra no service,
reforçada por dependência de rota.

### 5.6 Mensageria

```
conversations (id, created_at, last_message_at)
conversation_participants (conversation_id, user_id)   PK composta
messages (id, conversation_id, sender_user_id, body, created_at, read_at)
```

Conversa entre exatamente dois participantes nesta fase. `last_message_at` é
desnormalizado para ordenar a lista de conversas sem varrer `messages`.

### 5.7 Busca (requisito 1.3)

Não introduz tabela. São queries sobre `athlete_profiles` com índices em
`(position, state)` e `birth_date`. **Idade é derivada de `birth_date` na query** —
guardar idade em coluna é um bug esperando envelhecer.

---

## 6. Fluxo assíncrono de clipes

### 6.1 Máquina de estados

O fluxo de duas fases existente se mantém; muda quem executa. **Duas tasks Celery**, com
o job parado em `WAITING_USER` entre elas.

```
POST /clips/jobs      entitlements.assert_can_create_job(user)
                      grava Video + Job(PENDING) ──► fast_scan_task ──► 202
                                                          │
                      Job(FAST_SCAN)  ◄── candidatos aparecendo
                                                          │
                      Job(WAITING_USER) ── usuário escolhe ──┐
                                                             ▼
POST /clips/jobs/{id}/confirm ──────────────────► tracking_task
                      Job(TRACKING → EXTRACTING → COMPLETED)

qualquer estado ──► ERROR (com error_message)
```

### 6.2 Progresso em tempo real

O worker publica em `job:{job_id}:progress`; a API assina e repassa via SSE.

**Pub/sub não tem histórico**: quem conecta no meio não recebe nada. Portanto o endpoint
SSE **emite primeiro o estado atual lido do banco** e só depois entra no stream. Sem isso,
um F5 durante o processamento deixa a tela vazia até o próximo evento.

Isso substitui o laço de polling de `jobs.py:83`.

### 6.3 Falhas tratadas

| Falha | Tratamento |
|---|---|
| Job órfão (worker/API caiu) | `heartbeat_at` atualizado pelo worker; task do Beat marca como `ERROR` o que passar do limite |
| Retry duplicando clipe | `UNIQUE (job_id, start_timestamp)` torna a task idempotente |
| GPU travada | `soft_time_limit` na task; ao estourar vira `ERROR` com mensagem, sem pendurar o worker |
| Falha transitória | `autoretry_for` com backoff exponencial e teto de tentativas |

---

## 7. Política de retenção

Requisito 2.3. Task diária do Celery Beat:

| Alvo | Regra |
|---|---|
| `clips` com `status = TEMPORARY` e `created_at > 14 dias` | apaga arquivo e registro |
| `clips` com `status = PERMANENT` | **nunca apaga** |
| `videos` brutos com `uploaded_at > 14 dias` **e sem job em andamento** | apaga arquivo |
| `candidates` de jobs encerrados | thumbnails apagadas junto com o vídeo |

**`TEMPORARY → PERMANENT` é transição de mão única.** Um clipe publicado uma vez nunca
mais é elegível para exclusão pela retenção, mesmo que o post seja removido depois.

Isso vale para a **retenção automática**. Exclusão explícita pelo dono (`DELETE /clips/{id}`)
continua permitida em qualquer status e remove o post associado junto.

O vídeo bruto é sempre expurgado após 14 dias, publicado ou não: o PDF garante
permanência ao *clipe*, não ao arquivo original. A exceção é o vídeo vinculado a um job
que ainda não chegou a estado terminal — apagá-lo mataria um processamento em curso.

Toda exclusão passa por `StorageBackend.delete()`. **Nenhum `os.remove` solto no
domínio** — é essa interface que permite trocar disco por S3 depois sem tocar em regra
de negócio.

Como `api` e `worker` compartilham o disco, o Compose monta um volume nomeado nos dois
serviços. Quando o worker roda nativo no host, o caminho é o mesmo diretório local.

---

## 8. Entitlements

Sem gateway de pagamento nesta fase (D8). O módulo expõe uma única porta:

```python
entitlements_service.assert_can_create_job(user)  # levanta QuotaExceeded
```

Os limites vivem em uma matriz de configuração, não espalhados em `if` pelas rotas:

| Plano | Jobs por mês | Duração máx. de vídeo |
|---|---|---|
| `FREE` | limitado | limitado |
| `PRO` | ampliado | ampliado |

Os valores concretos são parâmetro de configuração, definidos na implementação de M6.

O módulo `clips` é o único consumidor. Quando houver assinatura de verdade, entra uma
tabela `subscriptions` e muda **apenas a leitura dentro do service** — nenhum outro
módulo é afetado.

---

## 9. Frontend

O produto muda de natureza: de ferramenta linear para app social onde o gerador de
clipes é uma aba com cadeado.

### 9.1 Estrutura

```
src/
├─ app/        router, providers, shell
├─ shared/     ui/ (shadcn) · lib/http · hooks · types
└─ features/   auth · profiles · feed · discovery ·
               opportunities · messaging · clips
```

### 9.2 Decisões

- **TanStack Query** para estado de servidor. Feed paginado, busca com filtros e lista de
  oportunidades são todos cache e invalidação; escrever isso à mão com `useState` e
  `useEffect` em seis features é onde o projeto atolaria.
- `services/api.ts` (7,6 KB) vira um `httpClient` único em `shared/lib` (JWT e tratamento
  de 401) mais um `api.ts` por feature.
- **Três canais distintos, sem misturar:** REST para CRUD, SSE para progresso de job,
  WebSocket para chat.
- **Rotas cientes de papel:** `<RoleRoute allow={["SCOUT","CLUB"]}>` guarda a publicação
  de peneira; `<PlanRoute allow={["PRO"]}>` guarda o gerador de clipes. O gate é **sempre**
  reforçado no backend — o front apenas evita a viagem perdida.
- **Tailwind + shadcn/ui** substituem o CSS puro. O `index.css` de 4,6 KB e os estilos por
  página não sustentam feed, chat e busca com filtros.

---

## 10. Migrações, erros e testes

### 10.1 Alembic

Entra em F0, não depois. Migração baseline a partir do schema atual; `create_all` sai do
startup (`database.py:26`). Toda alteração de modelo passa a exigir migração versionada.

### 10.2 Erros

Hierarquia de exceções de domínio em `core/exceptions.py`:

```
DomainError
├─ NotFoundError      → 404
├─ ForbiddenError     → 403
├─ ConflictError      → 409
├─ QuotaExceededError → 402
└─ ValidationError    → 422
```

Services levantam exceção de domínio; **um handler único no `main.py` traduz para HTTP**.
Router não monta `HTTPException` — hoje `jobs.py` mistura as duas coisas.

### 10.3 Testes

A estrutura `tests/unit`, `tests/integration` e `conftest.py` já existe.

| Camada | Como |
|---|---|
| `service.py` | unitário, repository fake — é onde mora a regra |
| `router.py` | integração, `TestClient` + banco de teste |
| tasks Celery | `task_always_eager=True`, sem broker |
| pipeline ML | benchmark em `benchmark/`, que já tem `benchmark_model.py` |

### 10.4 Autenticação no WebSocket

Navegador não envia header customizado no handshake. O JWT vai no query param e é
validado **antes** do `accept()`, junto com a autorização por participação na conversa.
Aceitar a conexão e só depois rejeitar é vazamento.

---

## 11. Roadmap decomposto

Cada item é um **sub-projeto próprio** (spec → plano → implementação), não uma tarefa.
Organizado em ondas, não em datas: o mapeamento para sprints depende do tamanho da equipe
e do calendário do semestre.

### 11.1 Grafo de dependências

```
                        ┌─────────────────┐
                        │  F0  Fundação   │  ← sem paralelismo
                        └────────┬────────┘
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
      ┌───────────────┐  ┌──────────────┐  ┌────────────────┐
      │ F1  Async/GPU │  │ F2 Identidade│  │ F3 Front base  │
      └───────┬───────┘  └──────┬───────┘  └───────┬────────┘
              │                 │                  │
              │        ┌────────┼────────┬─────────┤
              ▼        ▼        ▼        ▼         ▼
        ┌──────────────────┐ ┌──────┐ ┌──────┐ ┌───────┐
        │ M1 Feed + M2 Ret.│ │M3 Bus│ │M4 Op.│ │M5 Chat│
        └──────────────────┘ └──────┘ └──────┘ └───────┘
              ▲
        ┌─────┴──────┐        ┌──────────────────────────┐
        │M6 Entitlem.│        │ M7 Visão Computacional   │ ← trilha paralela,
        └────────────┘        └──────────────────────────┘   só depende de F1
```

### 11.2 Fundação

| # | Sub-projeto | Escopo | Tam. |
|---|---|---|---|
| **F0** | Reestruturação base | `modules/`, `core/` (config, deps, exceptions, `StorageBackend`), Alembic baseline, split de requirements, docker-compose (redis/api/web), mover models existentes, deletar routers mortos. **Zero feature nova.** | M |
| **F1** | Pipeline assíncrono | Celery + Redis, pacote `worker/`, tirar YOLO da API, as duas tasks, progresso pub/sub + SSE com estado inicial, heartbeat e job órfão, `soft_time_limit`, constraint de idempotência, Beat com limpeza de `TEMPORARY`. → **PDF 2.2 e parte de 2.3** | G |
| **F2** | Identidade multi-papel | `role` no User, três tabelas de perfil, cadastro por papel, CRUD de perfil, avatar. → **PDF 1.1** | M |
| **F3** | Frontend base | Tailwind + shadcn, `features/`, `httpClient`, TanStack Query, shell com navegação, `RoleRoute` e `PlanRoute`. | G |

### 11.3 Módulos de produto

| # | Sub-projeto | Depende de | Tam. |
|---|---|---|---|
| **M6** | Entitlements | F0 | P |
| **M1** | Feed e publicação de clipes | F1, F2, F3 | G |
| **M2** | Retenção completa (`PERMANENT`) | M1 | P |
| **M3** | Busca e filtros | F2, F3 | M |
| **M4** | Oportunidades e inscrições | F2, F3 | M |
| **M5** | Chat | F2, F3, Redis (F1) | G |
| **M7** | Visão computacional | F1 | G |

### 11.4 Ondas

**Onda 0 — F0.** Sequencial e isolado. Toca praticamente todos os arquivos do backend;
qualquer trabalho em paralelo vira conflito de merge. PR curto, uma pessoa ou um par,
todo mundo rebasa em cima.

**Onda 1 — F1 ‖ F2 ‖ F3.** Três frentes que não se cruzam: F1 vive em `clips` e `worker`,
F2 em `identity` e `profiles`, F3 no frontend. **F1 vai para quem tem a máquina com GPU**
e começa aqui por ser o maior risco técnico do semestre.

**Onda 2 — M6 → M1 ‖ M3 ‖ início de M7.** M6 é pequeno e precisa existir antes de M1 para
a narrativa "gerador de clipes é recurso pago" fechar. M1 é a pedra angular: costura o
produto antigo ao novo. M7 abre a trilha de ML, que daqui em diante roda independente.

**Onda 3 — M4 ‖ M5 ‖ M2 ‖ M7.** M5 é o segundo maior risco — WebSocket, autorização no
handshake, reconexão. Não deixar para a última onda.

**Onda 4 — integração e defesa.** Retenção validada ponta a ponta (só testável de verdade
após M1 e M2), hardening, README e diagrama de arquitetura atualizados.

### 11.5 Rastreabilidade com o PDF

| Requisito | Onde |
|---|---|
| 1.1 Perfis especializados | F2 |
| 1.2 Feed e clipes | M1 |
| 1.3 Busca e filtros | M3 |
| 1.4 Peneiras | M4 |
| 1.5 Chat | M5 |
| 2.1 Precisão de corte e goleiro | M7 |
| 2.2 Escalabilidade e assíncrono | F1 |
| 2.3 Retenção | F1 (limpeza) + M2 (permanência) |
| Assinatura (acréscimo da equipe) | M6 |

---

## 12. Riscos

| # | Risco | Mitigação |
|---|---|---|
| **R1** | CUDA em container no Windows é atrito real | Worker roda nativo no host, fora do Compose. O contrato com a API (fila + banco + Redis) é o mesmo nos dois modos |
| **R2** | F0 não entrega nada visível e por isso costuma ser pulado | Pular custa o dobro nas sete ondas seguintes. É pré-requisito declarado de todos os outros sub-projetos |
| **R3** | F3 é grande e fácil de subestimar | Se apertar o prazo, o corte é o redesenho visual — **não** a estrutura de `features/` |
| **R4** | M5 (chat) concentra complexidade de WebSocket, autorização e reconexão | Agendado na Onda 3, não na última |
| **R5** | Quebrar `video_pipeline.py` (45 KB) pode regredir a precisão atual | `benchmark/benchmark_model.py` roda antes e depois da quebra, como baseline comparável |

---

## 13. Fora de escopo

Registrado explicitamente para evitar reabertura:

- Gateway de pagamento real e cobrança recorrente (só entitlements — D8).
- Troca de papel após o cadastro (`role` é imutável).
- Conversas em grupo (mensageria é 1:1 nesta fase).
- Aplicativo mobile nativo.
- Feed algorítmico ou sistema de recomendação (ordenação cronológica).
- Notificações push.
- Migração de storage para S3/MinIO (a interface `StorageBackend` deixa preparado).
