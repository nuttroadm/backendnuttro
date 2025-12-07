"""
Configuração do banco de dados PostgreSQL
Backend Solo Nuttro
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
import logging
from pathlib import Path

from models import Base, Nutricionista

# Carregar variáveis de ambiente
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URL do banco de dados
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:AoLcSmiQwJYUHltrLzhl@orderlymanatee-postgres.cloudfy.live:8856/db"
)

# Se a URL começar com postgres://, converter para postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Criar engine assíncrono
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db():
    """Dependency para obter sessão do banco"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Inicializa o banco de dados criando todas as tabelas"""
    try:
        async with engine.begin() as conn:
            # Criar todas as tabelas
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("✅ Tabelas criadas/verificadas com sucesso!")
        
        # Criar nutricionista admin padrão se não existir
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            from passlib.context import CryptContext
            
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            
            result = await session.execute(
                select(Nutricionista).where(Nutricionista.email == "admin@nuttro.com")
            )
            admin = result.scalar_one_or_none()
            
            if not admin:
                admin = Nutricionista(
                    email="admin@nuttro.com",
                    nome="Administrador",
                    senha_hash=pwd_context.hash("admin123"),
                    plano="enterprise",
                    ativo=True
                )
                session.add(admin)
                await session.commit()
                logger.info("✅ Nutricionista admin criado: admin@nuttro.com / admin123")
            else:
                logger.info("ℹ️ Nutricionista admin já existe")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar banco de dados: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def check_connection():
    """Verifica conexão com o banco"""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Erro na conexão com o banco: {e}")
        return False

