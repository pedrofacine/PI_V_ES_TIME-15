from sqlmodel import create_engine, Session, SQLModel

# Por favor, mexer !
# 1. Onde o banco está (URL)
# 2. O Engine (O motor que traduz Python para SQL)
# O 'check_same_thread' é necessário apenas para SQLite
# 3. O Dependency Injection (Para usar nas rotas)
sqlite_url = "sqlite:///database.db"


engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})


def get_session():
    with Session(engine) as session:
        yield session
        