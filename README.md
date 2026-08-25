# SmartScout 🎯

> Plataforma de análise de vídeos esportivos com Inteligência Artificial. Envie um vídeo de partida, selecione o atleta pelo número da camisa e receba automaticamente todos os clipes com os lances em que ele participou.

---

## Sumário

- [SmartScout 🎯](#smartscout-)
  - [Sumário](#sumário)
  - [Sobre o projeto](#sobre-o-projeto)
  - [Tecnologias](#tecnologias)
    - [Backend](#backend)
    - [Frontend](#frontend)
  - [Arquitetura](#arquitetura)
  - [Funcionalidades](#funcionalidades)
  - [Pré-requisitos](#pré-requisitos)
  - [Instalação e execução](#instalação-e-execução)
    - [Backend](#backend-1)
    - [Frontend](#frontend-1)
  - [Variáveis de ambiente](#variáveis-de-ambiente)
    - [Backend — `backend/.env`](#backend--backendenv)
    - [Frontend — `frontend/.env`](#frontend--frontendenv)
  - [Estrutura de pastas](#estrutura-de-pastas)
  - [Fluxo da aplicação](#fluxo-da-aplicação)
  - [Rotas da API](#rotas-da-api)
    - [Autenticação — `/api/v1/auth`](#autenticação--apiv1auth)
    - [Jobs — `/api/v1/jobs`](#jobs--apiv1jobs)
    - [Uploads — `/api/v1/uploads`](#uploads--apiv1uploads)

---

## Sobre o projeto

O **SmartScout** foi desenvolvido para resolver um problema real: analistas e treinadores perdiam horas editando vídeos manualmente para extrair lances de jogadores específicos.

Com o SmartScout, o processo é totalmente automatizado:

1. O usuário faz upload do vídeo da partida
2. Informa o número da camisa do jogador
3. A IA rastreia o atleta durante toda a partida usando YOLO + DeepSort
4. Os clipes com os lances são gerados automaticamente e disponibilizados para download

---

## Tecnologias

### Backend
| Tecnologia | Versão | Uso |
|---|---|---|
| Python | 3.11+ | Linguagem principal |
| FastAPI | 0.133 | Framework web / API REST |
| SQLModel | 0.0.37 | ORM + validação de dados |
| PostgreSQL | — | Banco de dados |
| PyTorch | 2.0+ | Base para os modelos de IA |
| Ultralytics (YOLO) | 8.0+ | Detecção de jogadores |
| DeepSort | 1.3+ | Rastreamento de jogadores |
| OpenCV | 4.8+ | Processamento de vídeo |
| Supervision | 0.18+ | Utilitários de visão computacional |
| Passlib + bcrypt | — | Hash de senhas |
| Python-Jose | — | Autenticação JWT |
| Resend | — | Envio de e-mails |
| Uvicorn | 0.41 | Servidor ASGI |

### Frontend
| Tecnologia | Versão | Uso |
|---|---|---|
| React | 19 | Biblioteca de UI |
| TypeScript | 5.9 | Tipagem estática |
| Vite | 7.3 | Build tool |
| React Router DOM | 7.13 | Roteamento |
| Lucide React | 0.577 | Ícones |
| RC Slider | 11.1 | Slider de corte de vídeo |

---

## Arquitetura
<img width="4695" height="1997" alt="Diagrama de Arquitetura" src="https://github.com/user-attachments/assets/1552ba4a-bf89-48c4-aba0-290b3e5beba8" />

O frontend se comunica com o backend via REST e **Server-Sent Events (SSE)** para acompanhar o progresso do processamento em tempo real.

---

## Funcionalidades

- **Landing page** com apresentação do produto, seções de como funciona, funcionalidades e sobre nós
- **Autenticação completa** — cadastro, login, proteção de rotas e redefinição de senha por e-mail
- **Upload de vídeo** com preview, suporte a drag-and-drop e controle de corte por tempo (trim)
- **Rastreamento por número de camisa** via YOLO + DeepSort + EasyOCR
- **Acompanhamento em tempo real** via SSE — os clipes aparecem conforme são gerados
- **Seleção manual de jogador** — caso a detecção automática precise de confirmação
- **Download em lote** de todos os clipes gerados
- **Histórico de análises** organizado por data
- **Redefinição de senha** com envio de e-mail via Resend

---

## Pré-requisitos

- Python 3.11+
- Node.js 18+
- PostgreSQL
- GPU NVIDIA com CUDA 11.8+ (recomendado para o pipeline de IA)
- Conta no [Resend](https://resend.com) para envio de e-mails

---

## Instalação e execução

### Backend

**1. Clone o repositório e entre na pasta do backend:**
```bash
cd backend
```

**2. Crie e ative o ambiente virtual:**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

**3. Instale as dependências:**
```bash
# API (sem torch/CUDA)
pip install -r requirements/api.txt

# Worker de visão computacional (com torch/YOLO) — opcional, roda separado
# pip install -r requirements/worker.txt
```

> As dependências foram divididas em `requirements/base.txt` (comuns), `requirements/api.txt`
> (servidor) e `requirements/worker.txt` (ML). A imagem da API não baixa mais o torch.

**4. Configure as variáveis de ambiente:**

Crie um arquivo `.env` na pasta `backend/` com o conteúdo descrito na seção [Variáveis de ambiente](#variáveis-de-ambiente).

**5. Aplique as migrações do banco:**
```bash
# a partir da pasta backend/
alembic upgrade head
```

> O schema é gerido por **Alembic** (migrações versionadas) — o `create_all` no startup foi
> removido. Toda alteração de modelo agora exige uma migração:
> `alembic revision --autogenerate -m "descricao"` e depois `alembic upgrade head`.

**6. Inicie o servidor:**
```bash
python -m uvicorn app.main:app --reload
```

O backend estará disponível em `http://localhost:8000`.
A documentação interativa da API estará em `http://localhost:8000/docs`.

> **Com Docker (alternativa):** na raiz do projeto, `docker compose up` sobe `redis`, `api`
> e `web` de uma vez. O Postgres continua externo (Supabase, via `DATABASE_URL`).

---

### Frontend

**1. Entre na pasta do frontend:**
```bash
cd frontend
```

**2. Instale as dependências:**
```bash
npm install
```

**3. Configure as variáveis de ambiente:**

Crie um arquivo `.env` na pasta `frontend/` com o conteúdo descrito na seção [Variáveis de ambiente](#variáveis-de-ambiente).

**4. Inicie o servidor de desenvolvimento:**
```bash
npm run dev
```

O frontend estará disponível em `http://localhost:5173`.

---

## Variáveis de ambiente

### Backend — `backend/.env`

```env
# Banco de dados
DATABASE_URL=postgresql://usuario:senha@localhost:5432/smartscout

# JWT
SECRET_KEY=sua_chave_secreta_aqui
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# E-mail (Resend)
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxx
RESEND_FROM_EMAIL=onboarding@resend.dev
FRONTEND_URL=http://localhost:5173
```

### Frontend — `frontend/.env`

```env
VITE_API_PATH=http://localhost:8000/api/v1
```

---

## Estrutura de pastas

```
PI_V_ES_TIME-15/
├── backend/
│   ├── app/
│   │   ├── core/                # Infra transversal
│   │   │   ├── config.py        # Constantes/JWT
│   │   │   ├── database.py      # Engine + sessão SQLModel
│   │   │   ├── deps.py          # Dependências (get_current_user)
│   │   │   ├── security.py      # Hash de senha + JWT
│   │   │   ├── email.py         # Envio de e-mails via Resend
│   │   │   ├── exceptions.py    # Exceções de domínio (§10.2)
│   │   │   └── storage.py       # Abstração de armazenamento
│   │   ├── modules/             # Um pacote por domínio
│   │   │   ├── identity/        # Autenticação + User
│   │   │   │   ├── models.py
│   │   │   │   ├── schemas.py
│   │   │   │   └── router.py
│   │   │   └── clips/           # Vídeos, jobs e clipes
│   │   │       ├── models.py
│   │   │       ├── schemas.py
│   │   │       └── router.py
│   │   └── main.py              # Monta routers + handler de exceção
│   ├── alembic/                 # Migrações versionadas
│   │   └── versions/
│   ├── alembic.ini
│   ├── uploads/
│   │   ├── videos/              # Vídeos enviados
│   │   └── clips/               # Clipes gerados
│   └── requirements/            # base.txt · api.txt · worker.txt
│
└── frontend/
    └── src/
        ├── assets/
        ├── components/
        │   ├── clip-card/
        │   ├── grid/
        │   ├── Header/
        │   └── PrivateRoute/
        ├── layouts/
        │   └── MainLayout.tsx
        ├── pages/
        │   ├── LandingPage/
        │   ├── Login/
        │   ├── SignUp/
        │   ├── resetPassword/
        │   ├── NewPassword/
        │   ├── input/
        │   ├── JobContainerPage/
        │   ├── processing-clips/
        │   ├── select-player/
        │   └── clips-history/
        ├── services/
        │   └── api.ts
        └── App.tsx
```

---

## Fluxo da aplicação

```
Usuário acessa "/"
        │
        ├─ Não logado ──► Landing Page ──► /login ou /signup
        │
        └─ Logado ──────► Landing Page com botão "Iniciar análise"
                                  │
                                  ▼
                            /app (Input)
                            Upload de vídeo + nº da camisa
                                  │
                                  ▼
                    /processing-clips/:jobId
                            │
                            ├─ FAST_SCAN / WAITING_USER
                            │       └─► Tela de seleção de jogador
                            │
                            └─ TRACKING → EXTRACTING → COMPLETED
                                    └─► Clipes gerados em tempo real
                                              │
                                              ▼
                                    Download dos clipes
```

---

## Rotas da API

### Autenticação — `/api/v1/auth`

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/register` | Cadastro de usuário |
| `POST` | `/login` | Login e geração de token JWT |
| `GET` | `/me` | Dados do usuário autenticado |
| `POST` | `/forgot-password` | Solicita redefinição de senha |
| `POST` | `/reset-password` | Redefine a senha com token |

### Jobs — `/api/v1/jobs`

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/jobs` | Cria um novo job de processamento |
| `GET` | `/jobs/:id/stream` | SSE — acompanha o progresso em tempo real |
| `POST` | `/jobs/:id/confirm` | Confirma o jogador selecionado |

### Uploads — `/api/v1/uploads`

Servidos como arquivos estáticos pelo FastAPI.
