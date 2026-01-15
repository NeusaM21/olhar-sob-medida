from backend.db.session import Base, engine
import backend.db.models

def init_db():
    """Cria as tabelas automaticamente se ainda não existirem."""
    print("📦 Criando tabelas do banco...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tabelas criadas com sucesso!")