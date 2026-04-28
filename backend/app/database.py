import os
from sqlmodel import SQLModel, create_engine, Session
from dotenv import load_dotenv

# Importa os models para que SQLModel.metadata registre as tabelas antes de create_all
from app.models import User, Video, ProcessingJob, Clip  # noqa: F401

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL não definida no .env (use a connection string do Supabase)")

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"connect_timeout": 10},
)


def create_db_and_tables():
    """Cria todas as tabelas no banco (Supabase/PostgreSQL)."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Generator de sessão para uso em rotas/dependências FastAPI."""
    with Session(engine) as session:
        yield session