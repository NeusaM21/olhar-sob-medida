from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.core.config import settings

# URL do banco (pega do config)
DATABASE_URL = settings.DATABASE_URL

# Criar engine do SQLAlchemy
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # Necessário para SQLite
)

# Sessão padrão
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para os modelos
Base = declarative_base()

def get_db():
    """Cria uma sessão de banco para ser usada nas rotas"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()