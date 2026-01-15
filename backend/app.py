import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.chat import router as chat_router
from backend.routes.webhook import router as webhook_router
from backend.db.init_db import init_db

# --------------------------------------------------
# APP
# --------------------------------------------------

app = FastAPI(
    title="Olhar Sob Medida - WhatsApp Bot",
    version="1.0.0",
)

# --------------------------------------------------
# STARTUP
# --------------------------------------------------

@app.on_event("startup")
async def on_startup():
    print("🚀 Iniciando aplicação...")
    init_db()
    print("✅ Application startup complete.")

# --------------------------------------------------
# MIDDLEWARE
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# ROUTES
# --------------------------------------------------

@app.get("/", tags=["system"])
async def root():
    return {
        "status": "running",
        "service": "Olhar Sob Medida",
    }

@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}

# --------------------
# CHAT (Swagger / Testes)
# --------------------
app.include_router(
    chat_router,
    prefix="/chat",
    tags=["chat"]
)

# --------------------
# WEBHOOK / ADMIN
# --------------------
# ⚠️ Sem prefixo para que:
# - /webhook
# - /admin/recreate-db
# fiquem acessíveis corretamente
app.include_router(
    webhook_router,
    prefix=""
)

# --------------------------------------------------
# LOCAL DEV ONLY
# --------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 10000))
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )