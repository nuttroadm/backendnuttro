"""
Backend Solo Nuttro - Servidor Principal
Importa e organiza as rotas do Web e Mobile
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import socketio

from database import init_db, engine

# Importar routers
from serverweb import api_router as web_router
from serverapp import app_router, auth_router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# LIFESPAN
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Iniciando Backend Solo Nuttro...")
    logger.info("📊 Criando/verificando tabelas...")
    success = await init_db()
    if success:
        logger.info("✅ Servidor pronto!")
    else:
        logger.warning("⚠️ Erro na inicialização do banco")
    yield
    await engine.dispose()
    logger.info("👋 Servidor encerrado")

# ============================================
# APP PRINCIPAL
# ============================================

app = FastAPI(
    title="Nuttro Solo API",
    description="Backend unificado para Web (Nutricionistas) e Mobile (Pacientes)",
    version="1.0.0",
    lifespan=lifespan
)

# ============================================
# INCLUIR ROUTERS
# ============================================

app.include_router(web_router)
app.include_router(app_router)
app.include_router(auth_router)  # Rotas de autenticação de pacientes

# ============================================
# CORS
# ============================================

# Configurar CORS baseado em variáveis de ambiente
import os
from dotenv import load_dotenv
from pathlib import Path

# Carregar .env
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
if ALLOWED_ORIGINS != "*":
    ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS.split(",")]
else:
    ALLOWED_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# SOCKET.IO
# ============================================

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio, app)

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Iniciando Backend Solo Nuttro na porta {port}...")
    uvicorn.run(socket_app, host="0.0.0.0", port=port)
