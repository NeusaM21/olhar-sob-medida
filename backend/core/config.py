import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env para o ambiente local
load_dotenv()

class Settings:
    APP_NAME: str = "Olhar Sob Medida - IA Assistente"
    ENV: str = os.getenv("ENV", "development")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./olhar_sob_medida.db")

    # --- Configurações de IA (Gemini) ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    AI_MODEL: str = os.getenv("AI_MODEL", "models/gemini-2.0-flash")

    # --- Integração Z-API (WhatsApp) ---
    # IDs extraídos do painel Z-API e configurados no Render
    Z_API_INSTANCE_ID: str = os.getenv("Z_API_INSTANCE_ID", "")
    Z_API_TOKEN: str = os.getenv("Z_API_TOKEN", "")
    # O Client-Token é essencial para a segurança da sua conta e para evitar o erro 400
    ZAPI_CLIENT_TOKEN: str = os.getenv("ZAPI_CLIENT_TOKEN", "")

    # --- Integração Google Sheets ---
    # Variáveis identificadas no seu dashboard do Render
    GOOGLE_SHEETS_CREDENTIALS: str = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")
    PLANILHA_NOME: str = os.getenv("PLANILHA_NOME", "")

    # --- Configurações de Sistema ---
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"

# Instancia a configuração para ser usada em todo o projeto
settings = Settings()