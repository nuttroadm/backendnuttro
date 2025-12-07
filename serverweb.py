"""
Nuttro Backend - PostgreSQL + Evolution API
Cria tabelas automaticamente na inicialização
"""

from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, or_
from sqlalchemy.orm import selectinload
from dotenv import load_dotenv
import os
import logging
import re
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import uuid
from datetime import datetime, timezone, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from google.oauth2 import id_token
from google.auth.transport import requests
import socketio
import httpx

# Importar configuração do banco
from database import init_db, get_db, engine, AsyncSessionLocal
from models import (
    Nutricionista, Paciente, WhatsAppSession, Conversa,
    Mensagem, StatusPersonalizado, Consulta, Agendamento
)
from shared import (
    get_current_nutricionista, paciente_to_dict, nutricionista_to_dict,
    EVOLUTION_API_URL, EVOLUTION_API_KEY, get_password_hash, create_access_token,
    verify_password, SECRET_KEY, ALGORITHM, validate_cpf
)
from ai_agents import (
    get_consulta_insight_agent,
    get_meal_analysis_agent,
    get_patient_chat_agent,
    get_meal_plan_agent
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "nuttro-secret-key-change-in-production-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "https://orderlymanatee-evolution.cloudfy.live")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "LzKrIvkg0gI28IzfBjoROnFKjWyTgj54")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Socket.IO
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=True
)

# Lifespan events - Cria tabelas automaticamente
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - Criar tabelas
    logger.info("🚀 Iniciando servidor...")
    logger.info("📊 Criando/verificando tabelas do banco de dados...")
    success = await init_db()
    if success:
        logger.info("✅ Servidor pronto!")
    else:
        logger.warning("⚠️ Aviso: Algumas tabelas podem não ter sido criadas")
    yield
    # Shutdown
    await engine.dispose()
    logger.info("👋 Servidor encerrado")

# Create the main app
app = FastAPI(
    title="Nuttro API",
    description="Sistema de CRM nutricional com WhatsApp",
    version="2.0.0",
    lifespan=lifespan
)

api_router = APIRouter(prefix="/api")

# ============================================
# PYDANTIC MODELS (Request/Response)
# ============================================

class NutricionistaCreate(BaseModel):
    email: EmailStr
    nome: str
    senha: str
    tipo: str = "nutricionista"

# LoginRequest não é mais usado - usando Request direto

class GoogleLoginRequest(BaseModel):
    credential: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

class PacienteCreate(BaseModel):
    nome: str
    email: EmailStr
    telefone: Optional[str] = None
    data_nascimento: Optional[str] = None
    objetivo: Optional[str] = None

class PacienteUpdate(BaseModel):
    nome: Optional[str] = None
    telefone: Optional[str] = None
    objetivo: Optional[str] = None
    status: Optional[str] = None
    nivel_adesao: Optional[str] = None
    email: Optional[EmailStr] = None
    cpf: Optional[str] = None
    kanban_status: Optional[str] = None

class ConsultaCreate(BaseModel):
    paciente_id: str
    tipo: str = "primeira_consulta"
    anamnese: Optional[Dict[str, Any]] = None
    avaliacao_fisica: Optional[Dict[str, Any]] = None
    avaliacao_emocional: Optional[Dict[str, Any]] = None
    avaliacao_comportamental: Optional[Dict[str, Any]] = None
    avaliacao_bem_estar: Optional[Dict[str, Any]] = None
    plano_alimentar: Optional[Dict[str, Any]] = None
    metas: Optional[List[Dict[str, Any]]] = None

class MensagemCreate(BaseModel):
    paciente_id: Optional[str] = None
    conversa_id: Optional[str] = None
    conteudo: str
    tipo: str = "texto"
    marcacao: Optional[str] = None

class AgendamentoCreate(BaseModel):
    paciente_id: Optional[str] = None
    titulo: str
    data_hora: datetime
    duracao_minutos: int = 60
    tipo: str = "consulta"
    observacoes: Optional[str] = None

# ============================================
# HELPER FUNCTIONS
# ============================================

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def usuario_to_dict(usuario: Nutricionista) -> dict:
    """Converte modelo Nutricionista para dict (alias para compatibilidade)"""
    return {
        "id": str(usuario.id),
        "email": usuario.email,
        "nome": usuario.nome,
        "crn": usuario.crn,
        "foto_url": usuario.foto_url,
        "google_id": usuario.google_id,
        "ativo": usuario.ativo,
        "plano": usuario.plano,
        "created_at": usuario.created_at.isoformat() if usuario.created_at else None,
        "updated_at": usuario.updated_at.isoformat() if usuario.updated_at else None,
    }

async def get_nutricionista(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Nutricionista:
    """Obtém usuário atual do token JWT"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(Nutricionista).where(Nutricionista.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user

# ============================================
# ROUTES - AUTHENTICATION
# ============================================

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(
    user_create: NutricionistaCreate,
    db: AsyncSession = Depends(get_db)
):
    """Registrar novo usuário"""
    # Verificar se email já existe
    result = await db.execute(select(Nutricionista).where(Nutricionista.email == user_create.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email já cadastrado")
    
    # Criar usuário
    new_user = Nutricionista(
        email=user_create.email,
        nome=user_create.nome,
        senha_hash=get_password_hash(user_create.senha),
        tipo=user_create.tipo
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Criar token
    access_token = create_access_token(data={"sub": str(new_user.id)})
    
    return TokenResponse(
        access_token=access_token,
        user=usuario_to_dict(new_user)
    )

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Login com email e senha - aceita JSON ou form-data"""
    try:
        content_type = request.headers.get("content-type", "")
        body = {}
        
        # Tentar ler como JSON primeiro
        if "application/json" in content_type:
            try:
                body = await request.json()
                logger.info(f"Request JSON recebido: {list(body.keys())}")
            except Exception as e:
                logger.warning(f"Erro ao ler JSON: {e}")
                body = {}
        
        # Se não for JSON, tentar form-data
        if not body and ("application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type):
            try:
                form_data = await request.form()
                body = dict(form_data)
                logger.info(f"Request form-data recebido: {list(body.keys())}")
            except Exception as e:
                logger.warning(f"Erro ao ler form-data: {e}")
        
        # Se ainda não tiver body, tentar ler como texto
        if not body:
            try:
                body_text = await request.body()
                logger.info(f"Request body raw: {body_text[:100]}")
                if body_text:
                    import json
                    body = json.loads(body_text)
            except:
                pass
        
        logger.info(f"Body final: {list(body.keys()) if isinstance(body, dict) else type(body)}")
        
        # Tentar extrair email e senha de várias formas
        email = None
        password = None
        
        if isinstance(body, dict):
            email = body.get("email") or body.get("Email") or body.get("EMAIL") or body.get("username") or body.get("user")
            password = body.get("senha") or body.get("password") or body.get("Password") or body.get("PASSWORD") or body.get("Senha")
        
        logger.info(f"Email extraído: {email}, Password: {'*' * len(password) if password else 'None'}")
        
        if not email:
            logger.error(f"Email não encontrado. Body recebido: {body}")
            raise HTTPException(status_code=422, detail="Email é obrigatório")
        
        if not password:
            logger.error(f"Senha não encontrada. Body recebido: {body}")
            raise HTTPException(status_code=422, detail="Senha é obrigatória")
        
        logger.info(f"Tentativa de login: email={email}")
        
        result = await db.execute(select(Nutricionista).where(Nutricionista.email == email))
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning(f"Usuário não encontrado: {email}")
            raise HTTPException(status_code=400, detail="Email ou senha incorretos")
        
        if not user.senha_hash:
            logger.warning(f"Usuário sem senha hash: {email}")
            raise HTTPException(status_code=400, detail="Email ou senha incorretos")
        
        if not verify_password(password, user.senha_hash):
            logger.warning(f"Senha incorreta para: {email}")
            raise HTTPException(status_code=400, detail="Email ou senha incorretos")
        
        logger.info(f"Login bem-sucedido: {email}")
        access_token = create_access_token(data={"sub": str(user.id)})
        
        return TokenResponse(
            access_token=access_token,
            user=usuario_to_dict(user)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no login: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@api_router.post("/auth/google", response_model=TokenResponse)
async def google_login(
    request: GoogleLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login com Google OAuth"""
    try:
        idinfo = id_token.verify_oauth2_token(
            request.credential, 
            requests.Request(), 
            GOOGLE_CLIENT_ID
        )
        
        email = idinfo['email']
        nome = idinfo.get('name', email.split('@')[0])
        google_id = idinfo['sub']
        foto_url = idinfo.get('picture')
        
        # Verificar se usuário existe
        result = await db.execute(select(Nutricionista).where(Nutricionista.email == email))
        user = result.scalar_one_or_none()
        
        if not user:
            # Criar novo usuário
            user = Nutricionista(
                email=email,
                nome=nome,
                google_id=google_id,
                foto_url=foto_url,
                tipo="nutricionista"
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        else:
            # Atualizar info do Google se necessário
            if not user.google_id:
                user.google_id = google_id
                user.foto_url = foto_url
                await db.commit()
        
        access_token = create_access_token(data={"sub": str(user.id)})
        
        return TokenResponse(
            access_token=access_token,
            user=usuario_to_dict(user)
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro na autenticação Google: {str(e)}")

@api_router.get("/auth/me")
async def get_me(nutricionista: Nutricionista = Depends(get_current_nutricionista)):
    """Obter dados do usuário atual"""
    return usuario_to_dict(nutricionista)

# ============================================
# ROUTES - PACIENTES
# ============================================

@api_router.post("/pacientes")
async def create_paciente(
    paciente_create: PacienteCreate,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Criar novo paciente"""
    # Validar CPF
    cpf_limpo = re.sub(r'[^0-9]', '', paciente_create.cpf)
    if not validate_cpf(cpf_limpo):
        raise HTTPException(status_code=400, detail="CPF inválido")
    
    # Verificar se CPF já existe (único no sistema)
    result = await db.execute(
        select(Paciente).where(Paciente.cpf == cpf_limpo)
    )
    paciente_existente = result.scalar_one_or_none()
    if paciente_existente:
        raise HTTPException(
            status_code=400, 
            detail=f"CPF já cadastrado. Este CPF está vinculado ao paciente {paciente_existente.nome}. Não é possível criar uma nova conta com este CPF."
        )
    
    # Verificar se email já existe (se fornecido)
    if paciente_create.email:
        result = await db.execute(
            select(Paciente).where(Paciente.email == paciente_create.email)
        )
        email_existente = result.scalar_one_or_none()
        if email_existente:
            raise HTTPException(
                status_code=400,
                detail=f"Email já cadastrado. Este email está vinculado ao paciente {email_existente.nome}. Não é possível criar uma nova conta com este email."
            )
    
    # Criar paciente
    new_paciente = Paciente(
        nutricionista_id=nutricionista.id,
        cpf=cpf_limpo,
        nome=paciente_create.nome,
        email=paciente_create.email,
        telefone=paciente_create.telefone,
        data_nascimento=datetime.fromisoformat(paciente_create.data_nascimento) if paciente_create.data_nascimento else None,
        objetivo=paciente_create.objetivo,
        senha_hash=get_password_hash(paciente_create.senha) if paciente_create.senha else None
    )
    db.add(new_paciente)
    await db.commit()
    await db.refresh(new_paciente)
    
    return {
        "id": str(new_paciente.id),
        "nome": new_paciente.nome,
        "email": new_paciente.email,
        "telefone": new_paciente.telefone,
        "objetivo": new_paciente.objetivo,
        "status": new_paciente.status,
        "created_at": new_paciente.created_at.isoformat() if new_paciente.created_at else None
    }

@api_router.get("/pacientes")
async def get_pacientes(
    status: Optional[str] = None,
    objetivo: Optional[str] = None,
    nivel_adesao: Optional[str] = None,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Listar pacientes"""
    query = select(Paciente).where(Paciente.nutricionista_id == nutricionista.id)
    
    if status:
        query = query.where(Paciente.status == status)
    if objetivo:
        query = query.where(Paciente.objetivo == objetivo)
    if nivel_adesao:
        query = query.where(Paciente.nivel_adesao == nivel_adesao)
    
    result = await db.execute(query)
    pacientes = result.scalars().all()
    
    return [
        {
            "id": str(p.id),
            "nome": p.nome,
            "email": p.email,
            "telefone": p.telefone,
            "objetivo": p.objetivo,
            "status": p.status,
            "nivel_adesao": p.nivel_adesao,
            "kanban_status": p.kanban_status,
            "data_nascimento": p.data_nascimento.isoformat() if p.data_nascimento else None,
            "created_at": p.created_at.isoformat() if p.created_at else None
        }
        for p in pacientes
    ]

def paciente_to_dict(p: Paciente) -> dict:
    """Converte modelo Paciente para dict"""
    return {
        "id": str(p.id),
        "nome": p.nome,
        "email": p.email,
        "telefone": p.telefone,
        "objetivo": p.objetivo,
        "status": p.status,
        "nivel_adesao": p.nivel_adesao,
        "kanban_status": p.kanban_status,
        "data_nascimento": p.data_nascimento.isoformat() if p.data_nascimento else None,
        "email": p.email,
        "cpf": p.cpf,
        "endereco": p.endereco,
        "observacoes": p.observacoes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None
    }

@api_router.get("/pacientes/{paciente_id}")
async def get_paciente(
    paciente_id: str,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Buscar paciente específico por ID"""
    try:
        result = await db.execute(
            select(Paciente).where(
                Paciente.id == uuid.UUID(paciente_id),
                Paciente.nutricionista_id == nutricionista.id
            )
        )
        paciente = result.scalar_one_or_none()
        
        if not paciente:
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
        
        return paciente_to_dict(paciente)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de paciente inválido")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar paciente: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/pacientes/{paciente_id}")
async def update_paciente(
    paciente_id: str, 
    paciente_update: PacienteUpdate, 
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Atualizar paciente - Otimizado para performance"""
    try:
        paciente_uuid = uuid.UUID(paciente_id)
        
        # OTIMIZAÇÃO: Se apenas kanban_status está sendo atualizado, usar update direto (muito mais rápido)
        update_data = paciente_update.model_dump(exclude_unset=True)
        if len(update_data) == 1 and 'kanban_status' in update_data:
            # Update direto sem select - muito mais rápido
            update_data['updated_at'] = datetime.now(timezone.utc)
            result = await db.execute(
                update(Paciente)
                .where(
                    Paciente.id == paciente_uuid,
                    Paciente.nutricionista_id == nutricionista.id
                )
                .values(**update_data)
            )
            
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Paciente não encontrado")
            
            await db.commit()
            
            # Retornar apenas o que foi atualizado para resposta rápida
            return {"id": paciente_id, "kanban_status": update_data['kanban_status'], "updated": True}
        
        # Para outras atualizações, usar o método completo
        result = await db.execute(
            select(Paciente).where(
                Paciente.id == paciente_uuid,
                Paciente.nutricionista_id == nutricionista.id
            )
        )
        paciente = result.scalar_one_or_none()
        
        if not paciente:
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
        
        # Atualizar campos se fornecidos
        if paciente_update.nome is not None:
            paciente.nome = paciente_update.nome
        if paciente_update.telefone is not None:
            paciente.telefone = paciente_update.telefone
        if paciente_update.objetivo is not None:
            paciente.objetivo = paciente_update.objetivo
        if paciente_update.status is not None:
            paciente.status = paciente_update.status
        if paciente_update.nivel_adesao is not None:
            paciente.nivel_adesao = paciente_update.nivel_adesao
        if paciente_update.email is not None:
            paciente.email = paciente_update.email
        if paciente_update.cpf is not None:
            paciente.cpf = paciente_update.cpf
        if paciente_update.kanban_status is not None:
            paciente.kanban_status = paciente_update.kanban_status
        
        paciente.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(paciente)
        
        return paciente_to_dict(paciente)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de paciente inválido")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar paciente: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/pacientes/{paciente_id}")
async def delete_paciente(
    paciente_id: str,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Deletar paciente"""
    try:
        result = await db.execute(
            select(Paciente).where(
                Paciente.id == uuid.UUID(paciente_id),
                Paciente.nutricionista_id == nutricionista.id
            )
        )
        paciente = result.scalar_one_or_none()
        
        if not paciente:
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
        
        await db.delete(paciente)
        await db.commit()
        
        return {"message": "Paciente deletado com sucesso"}
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de paciente inválido")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao deletar paciente: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ROUTES - AGENDAMENTOS
# ============================================

class AgendamentoUpdate(BaseModel):
    titulo: Optional[str] = None
    data_hora: Optional[datetime] = None
    duracao_minutos: Optional[int] = None
    tipo: Optional[str] = None
    observacoes: Optional[str] = None
    status: Optional[str] = None
    paciente_id: Optional[str] = None

def agendamento_to_dict(a: Agendamento, paciente_nome: str = None) -> dict:
    """Converte modelo Agendamento para dict"""
    return {
        "id": str(a.id),
        "nutricionista_id": str(a.nutricionista_id),
        "paciente_id": str(a.paciente_id) if a.paciente_id else None,
        "paciente_nome": paciente_nome,
        "titulo": a.titulo,
        "data_hora": a.data_hora.isoformat() if a.data_hora else None,
        "duracao_minutos": getattr(a, 'duracao_minutos', 60),
        "tipo": getattr(a, 'tipo', 'consulta'),
        "status": a.status,
        "observacoes": getattr(a, 'observacoes', None),
        "link_videochamada": getattr(a, 'link_videochamada', None),
        "lembrete_enviado": getattr(a, 'lembrete_enviado', False),
        "confirmacao_paciente": getattr(a, 'confirmacao_paciente', False),
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None
    }

@api_router.get("/agendamentos")
async def get_agendamentos(
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    paciente_id: Optional[str] = None,
    status: Optional[str] = None,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Listar agendamentos do nutricionista"""
    try:
        query = select(Agendamento).where(Agendamento.nutricionista_id == nutricionista.id)
        
        if data_inicio:
            query = query.where(Agendamento.data_hora >= datetime.fromisoformat(data_inicio))
        if data_fim:
            query = query.where(Agendamento.data_hora <= datetime.fromisoformat(data_fim))
        if paciente_id:
            query = query.where(Agendamento.paciente_id == uuid.UUID(paciente_id))
        if status:
            query = query.where(Agendamento.status == status)
        
        query = query.order_by(Agendamento.data_hora.asc())
        
        result = await db.execute(query)
        agendamentos = result.scalars().all()
        
        # Buscar nomes dos pacientes - tratar None
        paciente_ids = [a.paciente_id for a in agendamentos if a.paciente_id is not None]
        pacientes_dict = {}
        if paciente_ids:
            result = await db.execute(select(Paciente).where(Paciente.id.in_(paciente_ids)))
            pacientes = result.scalars().all()
            pacientes_dict = {p.id: p.nome for p in pacientes}
        
        return [
            agendamento_to_dict(a, pacientes_dict.get(a.paciente_id) if a.paciente_id else None)
            for a in agendamentos
        ]
    except Exception as e:
        logger.error(f"Erro ao buscar agendamentos: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/agendamentos")
async def create_agendamento(
    agendamento_create: AgendamentoCreate,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Criar novo agendamento"""
    try:
        # Verificar se paciente existe (se fornecido)
        if agendamento_create.paciente_id:
            result = await db.execute(
                select(Paciente).where(
                    Paciente.id == uuid.UUID(agendamento_create.paciente_id),
                    Paciente.nutricionista_id == nutricionista.id
                )
            )
            paciente = result.scalar_one_or_none()
            if not paciente:
                raise HTTPException(status_code=404, detail="Paciente não encontrado")
        
        novo_agendamento = Agendamento(
            nutricionista_id=nutricionista.id,
            paciente_id=uuid.UUID(agendamento_create.paciente_id) if agendamento_create.paciente_id else None,
            titulo=agendamento_create.titulo,
            data_hora=agendamento_create.data_hora,
            duracao_minutos=agendamento_create.duracao_minutos,
            tipo=agendamento_create.tipo,
            observacoes=agendamento_create.observacoes,
            status="agendado"
        )
        db.add(novo_agendamento)
        await db.commit()
        await db.refresh(novo_agendamento)
        
        return agendamento_to_dict(novo_agendamento)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar agendamento: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/agendamentos/{agendamento_id}")
async def get_agendamento(
    agendamento_id: str,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Buscar agendamento específico"""
    try:
        result = await db.execute(
            select(Agendamento).where(
                Agendamento.id == uuid.UUID(agendamento_id),
                Agendamento.nutricionista_id == nutricionista.id
            )
        )
        agendamento = result.scalar_one_or_none()
        
        if not agendamento:
            raise HTTPException(status_code=404, detail="Agendamento não encontrado")
        
        # Buscar nome do paciente
        paciente_nome = None
        if agendamento.paciente_id:
            result = await db.execute(select(Paciente).where(Paciente.id == agendamento.paciente_id))
            paciente = result.scalar_one_or_none()
            if paciente:
                paciente_nome = paciente.nome
        
        return agendamento_to_dict(agendamento, paciente_nome)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de agendamento inválido")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar agendamento: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/agendamentos/{agendamento_id}")
async def update_agendamento(
    agendamento_id: str,
    agendamento_update: AgendamentoUpdate,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Atualizar agendamento"""
    try:
        result = await db.execute(
            select(Agendamento).where(
                Agendamento.id == uuid.UUID(agendamento_id),
                Agendamento.nutricionista_id == nutricionista.id
            )
        )
        agendamento = result.scalar_one_or_none()
        
        if not agendamento:
            raise HTTPException(status_code=404, detail="Agendamento não encontrado")
        
        # Atualizar campos se fornecidos
        if agendamento_update.titulo is not None:
            agendamento.titulo = agendamento_update.titulo
        if agendamento_update.data_hora is not None:
            agendamento.data_hora = agendamento_update.data_hora
        if agendamento_update.duracao_minutos is not None:
            agendamento.duracao_minutos = agendamento_update.duracao_minutos
        if agendamento_update.tipo is not None:
            agendamento.tipo = agendamento_update.tipo
        if agendamento_update.observacoes is not None:
            agendamento.observacoes = agendamento_update.observacoes
        if agendamento_update.status is not None:
            agendamento.status = agendamento_update.status
        if agendamento_update.paciente_id is not None:
            agendamento.paciente_id = uuid.UUID(agendamento_update.paciente_id) if agendamento_update.paciente_id else None
        
        agendamento.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(agendamento)
        
        return agendamento_to_dict(agendamento)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID inválido")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar agendamento: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/agendamentos/{agendamento_id}")
async def delete_agendamento(
    agendamento_id: str,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Deletar agendamento"""
    try:
        result = await db.execute(
            select(Agendamento).where(
                Agendamento.id == uuid.UUID(agendamento_id),
                Agendamento.nutricionista_id == nutricionista.id
            )
        )
        agendamento = result.scalar_one_or_none()
        
        if not agendamento:
            raise HTTPException(status_code=404, detail="Agendamento não encontrado")
        
        await db.delete(agendamento)
        await db.commit()
        
        return {"message": "Agendamento deletado com sucesso"}
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de agendamento inválido")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao deletar agendamento: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ROUTES - CONSULTAS
# ============================================

class ConsultaUpdate(BaseModel):
    tipo: Optional[str] = None
    anamnese: Optional[Dict[str, Any]] = None
    avaliacao_fisica: Optional[Dict[str, Any]] = None
    avaliacao_emocional: Optional[Dict[str, Any]] = None
    avaliacao_comportamental: Optional[Dict[str, Any]] = None
    avaliacao_bem_estar: Optional[Dict[str, Any]] = None
    plano_alimentar: Optional[Dict[str, Any]] = None
    metas: Optional[List[Dict[str, Any]]] = None
    status: Optional[str] = None

def consulta_to_dict(c: Consulta, paciente_nome: str = None) -> dict:
    """Converte modelo Consulta para dict"""
    return {
        "id": str(c.id),
        "nutricionista_id": str(c.nutricionista_id),
        "paciente_id": str(c.paciente_id) if c.paciente_id else None,
        "paciente_nome": paciente_nome,
        "tipo": c.tipo,
        "data_consulta": c.data_consulta.isoformat() if c.data_consulta else None,
        "duracao_minutos": getattr(c, 'duracao_minutos', 60),
        "anamnese": c.anamnese,
        "avaliacao_fisica": c.avaliacao_fisica,
        "avaliacao_emocional": c.avaliacao_emocional,
        "avaliacao_comportamental": c.avaliacao_comportamental,
        "avaliacao_bem_estar": c.avaliacao_bem_estar,
        "plano_alimentar_id": str(c.plano_alimentar_id) if getattr(c, 'plano_alimentar_id', None) else None,
        "metas_definidas": getattr(c, 'metas_definidas', []),
        "status": c.status,
        "observacoes": getattr(c, 'observacoes', None),
        "proximos_passos": getattr(c, 'proximos_passos', None),
        "insights_ia": getattr(c, 'insights_ia', None),
        "recomendacoes_ia": getattr(c, 'recomendacoes_ia', None),
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None
    }

@api_router.get("/consultas")
async def get_consultas(
    paciente_id: Optional[str] = None,
    tipo: Optional[str] = None,
    status: Optional[str] = None,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Listar consultas do nutricionista"""
    try:
        query = select(Consulta).where(Consulta.nutricionista_id == nutricionista.id)
        
        if paciente_id:
            query = query.where(Consulta.paciente_id == uuid.UUID(paciente_id))
        if tipo:
            query = query.where(Consulta.tipo == tipo)
        if status:
            query = query.where(Consulta.status == status)
        
        query = query.order_by(Consulta.data_consulta.desc())
        
        result = await db.execute(query)
        consultas = result.scalars().all()
        
        # Buscar nomes dos pacientes - tratar None
        paciente_ids = [c.paciente_id for c in consultas if c.paciente_id is not None]
        pacientes_dict = {}
        if paciente_ids:
            result = await db.execute(select(Paciente).where(Paciente.id.in_(paciente_ids)))
            pacientes = result.scalars().all()
            pacientes_dict = {p.id: p.nome for p in pacientes}
        
        return [
            consulta_to_dict(c, pacientes_dict.get(c.paciente_id) if c.paciente_id else None)
            for c in consultas
        ]
    except Exception as e:
        logger.error(f"Erro ao buscar consultas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/consultas")
async def create_consulta(
    consulta_create: ConsultaCreate,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Criar nova consulta"""
    try:
        # Verificar se paciente existe
        result = await db.execute(
            select(Paciente).where(
                Paciente.id == uuid.UUID(consulta_create.paciente_id),
                Paciente.nutricionista_id == nutricionista.id
            )
        )
        paciente = result.scalar_one_or_none()
        if not paciente:
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
        
        nova_consulta = Consulta(
            nutricionista_id=nutricionista.id,
            paciente_id=uuid.UUID(consulta_create.paciente_id),
            tipo=consulta_create.tipo,
            data_consulta=datetime.now(timezone.utc),
            anamnese=consulta_create.anamnese,
            avaliacao_fisica=consulta_create.avaliacao_fisica,
            avaliacao_emocional=consulta_create.avaliacao_emocional,
            avaliacao_comportamental=consulta_create.avaliacao_comportamental,
            avaliacao_bem_estar=consulta_create.avaliacao_bem_estar,
            # plano_alimentar removido - usar plano_alimentar_id ou criar PlanoAlimentar separadamente
            # Se metas for fornecido, converter para metas_definidas
            metas_definidas=consulta_create.metas if hasattr(consulta_create, 'metas') and consulta_create.metas else [],
            status="em_andamento"
        )
        db.add(nova_consulta)
        await db.commit()
        # Não fazer refresh para evitar erros com atributos que não existem
        # O objeto já está atualizado após o commit
        
        return consulta_to_dict(nova_consulta, paciente.nome)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar consulta: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/consultas/{consulta_id}")
async def get_consulta(
    consulta_id: str,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Buscar consulta específica"""
    try:
        result = await db.execute(
            select(Consulta).where(
                Consulta.id == uuid.UUID(consulta_id),
                Consulta.nutricionista_id == nutricionista.id
            )
        )
        consulta = result.scalar_one_or_none()
        
        if not consulta:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        
        # Buscar nome do paciente
        result = await db.execute(select(Paciente).where(Paciente.id == consulta.paciente_id))
        paciente = result.scalar_one_or_none()
        paciente_nome = paciente.nome if paciente else None
        
        return consulta_to_dict(consulta, paciente_nome)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de consulta inválido")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar consulta: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/consultas/{consulta_id}")
async def update_consulta(
    consulta_id: str,
    consulta_update: ConsultaUpdate,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Atualizar consulta"""
    try:
        result = await db.execute(
            select(Consulta).where(
                Consulta.id == uuid.UUID(consulta_id),
                Consulta.nutricionista_id == nutricionista.id
            )
        )
        consulta = result.scalar_one_or_none()
        
        if not consulta:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        
        # Atualizar campos se fornecidos
        if consulta_update.tipo is not None:
            consulta.tipo = consulta_update.tipo
        if consulta_update.anamnese is not None:
            consulta.anamnese = consulta_update.anamnese
        if consulta_update.avaliacao_fisica is not None:
            consulta.avaliacao_fisica = consulta_update.avaliacao_fisica
        if consulta_update.avaliacao_emocional is not None:
            consulta.avaliacao_emocional = consulta_update.avaliacao_emocional
        if consulta_update.avaliacao_comportamental is not None:
            consulta.avaliacao_comportamental = consulta_update.avaliacao_comportamental
        if consulta_update.avaliacao_bem_estar is not None:
            consulta.avaliacao_bem_estar = consulta_update.avaliacao_bem_estar
        # plano_alimentar removido - usar plano_alimentar_id ou criar PlanoAlimentar separadamente
        # metas removido - usar metas_definidas
        # Se metas for fornecido, converter para metas_definidas
        if consulta_update.metas is not None:
            consulta.metas_definidas = consulta_update.metas
        if consulta_update.status is not None:
            consulta.status = consulta_update.status
        
        consulta.updated_at = datetime.now(timezone.utc)
        await db.commit()
        # Não fazer refresh para evitar erros com atributos que não existem
        # O objeto já está atualizado após o commit
        
        return consulta_to_dict(consulta)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de consulta inválido")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar consulta: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/consultas/{consulta_id}")
async def delete_consulta(
    consulta_id: str,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Deletar consulta"""
    try:
        result = await db.execute(
            select(Consulta).where(
                Consulta.id == uuid.UUID(consulta_id),
                Consulta.nutricionista_id == nutricionista.id
            )
        )
        consulta = result.scalar_one_or_none()
        
        if not consulta:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        
        await db.delete(consulta)
        await db.commit()
        
        return {"message": "Consulta deletada com sucesso"}
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de consulta inválido")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao deletar consulta: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ROUTES - DASHBOARD
# ============================================

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Estatísticas do dashboard"""
    try:
        # Total de pacientes
        result = await db.execute(
            select(func.count(Paciente.id)).where(Paciente.nutricionista_id == nutricionista.id)
        )
        total_pacientes = result.scalar() or 0
        
        # Pacientes ativos
        result = await db.execute(
            select(func.count(Paciente.id)).where(
                Paciente.nutricionista_id == nutricionista.id,
                Paciente.status == "ativo"
            )
        )
        pacientes_ativos = result.scalar() or 0
        
        # Pacientes inativos
        result = await db.execute(
            select(func.count(Paciente.id)).where(
                Paciente.nutricionista_id == nutricionista.id,
                Paciente.status == "inativo"
            )
        )
        pacientes_inativos = result.scalar() or 0
        
        # Engajamento médio (mock por enquanto)
        engajamento_medio = 75
        
        return {
            "total_pacientes": total_pacientes,
            "pacientes_ativos": pacientes_ativos,
            "pacientes_inativos": pacientes_inativos,
            "engajamento_medio": engajamento_medio
        }
    except Exception as e:
        logger.error(f"Erro ao buscar stats do dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ROUTES - IA (Assistente IA Web)
# ============================================

class AnalisarRefeicaoRequest(BaseModel):
    descricao: str
    paciente_id: Optional[str] = None

class SugestoesPlanoRequest(BaseModel):
    objetivo: str
    paciente_id: Optional[str] = None
    peso_atual: Optional[float] = None
    peso_meta: Optional[float] = None
    altura: Optional[float] = None
    atividade_fisica: Optional[str] = None
    restricoes: Optional[List[str]] = None
    # Dados da consulta para contexto completo
    anamnese: Optional[Dict[str, Any]] = None
    avaliacao_fisica: Optional[Dict[str, Any]] = None
    avaliacao_emocional: Optional[Dict[str, Any]] = None
    avaliacao_comportamental: Optional[Dict[str, Any]] = None
    avaliacao_bem_estar: Optional[Dict[str, Any]] = None

class CoachComportamentalRequest(BaseModel):
    desafios: str
    paciente_id: Optional[str] = None

class ChatIARequest(BaseModel):
    message: str
    paciente_id: Optional[str] = None

@api_router.post("/ia/analisar-refeicao")
async def analisar_refeicao_ia(
    request: AnalisarRefeicaoRequest,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Analisar refeição usando IA"""
    try:
        agent = get_meal_analysis_agent()
        
        # Buscar contexto do paciente se fornecido
        patient_context = {}
        if request.paciente_id:
            result = await db.execute(
                select(Paciente).where(
                    Paciente.id == uuid.UUID(request.paciente_id),
                    Paciente.nutricionista_id == nutricionista.id
                )
            )
            paciente = result.scalar_one_or_none()
            if paciente:
                patient_context = {
                    "nome": paciente.nome,
                    "objetivo": paciente.objetivo,
                    "peso_atual": paciente.peso_atual_kg,
                    "peso_meta": paciente.peso_meta_kg,
                    "restricoes": paciente.restricoes_alimentares or []
                }
        
        # Analisar refeição
        analise = await agent.analyze(
            image_base64="",  # Apenas descrição por enquanto
            patient_context=patient_context,
            meal_plan={}
        )
        
        return {"analise": analise}
    except Exception as e:
        logger.error(f"Erro ao analisar refeição: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/ia/sugestoes-plano")
async def sugestoes_plano_ia(
    request: SugestoesPlanoRequest,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Gerar sugestões de plano alimentar completo usando IA"""
    try:
        from ai_agents import get_meal_plan_agent
        
        # Buscar dados do paciente se paciente_id fornecido
        paciente_info = {}
        consulta_data = {}
        
        if hasattr(request, 'paciente_id') and request.paciente_id:
            result = await db.execute(
                select(Paciente).where(Paciente.id == uuid.UUID(request.paciente_id))
            )
            paciente = result.scalar_one_or_none()
            if paciente:
                paciente_info = {
                    "nome": paciente.nome,
                    "peso_atual_kg": paciente.peso_atual_kg,
                    "altura_cm": paciente.altura_cm,
                    "data_nascimento": paciente.data_nascimento.isoformat() if paciente.data_nascimento else None,
                    "profissao": getattr(paciente, 'profissao', None),
                    "objetivo": paciente.objetivo
                }
                
                # Buscar última consulta
                result = await db.execute(
                    select(Consulta)
                    .where(Consulta.paciente_id == paciente.id)
                    .order_by(Consulta.data_consulta.desc())
                    .limit(1)
                )
                ultima_consulta = result.scalar_one_or_none()
                if ultima_consulta:
                    consulta_data = {
                        "anamnese": ultima_consulta.anamnese,
                        "avaliacao_fisica": ultima_consulta.avaliacao_fisica,
                        "avaliacao_emocional": ultima_consulta.avaliacao_emocional,
                        "avaliacao_comportamental": ultima_consulta.avaliacao_comportamental,
                        "avaliacao_bem_estar": ultima_consulta.avaliacao_bem_estar
                    }
        
        # Preparar dados para a IA
        if not paciente_info.get('nome'):
            paciente_info = {
                "nome": "Paciente",
                "peso_atual_kg": request.peso_atual or 70,
                "altura_cm": request.altura or 170,
                "objetivo": request.objetivo
            }
        
        # Se dados da consulta vieram no request, usar eles (prioridade)
        if request.anamnese or request.avaliacao_fisica:
            consulta_data = {
                "anamnese": request.anamnese or {},
                "avaliacao_fisica": request.avaliacao_fisica or {},
                "avaliacao_emocional": request.avaliacao_emocional or {},
                "avaliacao_comportamental": request.avaliacao_comportamental or {},
                "avaliacao_bem_estar": request.avaliacao_bem_estar or {}
            }
        
        # Gerar plano com IA
        agent = get_meal_plan_agent()
        plano = await agent.generate_meal_plan(
            paciente_info=paciente_info,
            consulta_data=consulta_data,
            objetivo=request.objetivo,
            restricoes=request.restricoes
        )
        
        return {"plano": plano}
    except Exception as e:
        logger.error(f"Erro ao gerar sugestões de plano: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/ia/coach-comportamental")
async def coach_comportamental_ia(
    request: CoachComportamentalRequest,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Coach comportamental usando IA"""
    try:
        # Por enquanto, retornar orientações básicas
        orientacao = f"""
Com base nos desafios descritos: {request.desafios}

Orientações:
1. Estabeleça pequenas metas alcançáveis
2. Crie rotinas consistentes
3. Celebre pequenas vitórias
4. Busque apoio quando necessário
5. Mantenha foco no progresso, não na perfeição

Lembre-se: mudanças duradouras acontecem gradualmente.
        """.strip()
        
        return {"orientacao": orientacao}
    except Exception as e:
        logger.error(f"Erro no coach comportamental: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/ia/chat")
async def chat_ia_web(
    request: ChatIARequest,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Chat livre com IA"""
    try:
        agent = get_patient_chat_agent()
        
        # Buscar contexto do paciente se fornecido
        patient_context = {}
        if request.paciente_id:
            result = await db.execute(
                select(Paciente).where(
                    Paciente.id == uuid.UUID(request.paciente_id),
                    Paciente.nutricionista_id == nutricionista.id
                )
            )
            paciente = result.scalar_one_or_none()
            if paciente:
                patient_context = {
                    "nome": paciente.nome,
                    "objetivo": paciente.objetivo or "Não definido",
                    "dias_jornada": paciente.dias_jornada or 0,
                    "nivel_adesao": paciente.nivel_adesao or "média"
                }
        
        # Chat com IA
        response = await agent.chat(
            message=request.message,
            patient_context=patient_context,
            history=[]
        )
        
        return {"response": response}
    except Exception as e:
        logger.error(f"Erro no chat IA: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ROUTES - WHATSAPP (Evolution API)
# ============================================

@api_router.post("/whatsapp/create-instance")
async def create_whatsapp_instance(
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Criar instância WhatsApp na Evolution API"""
    try:
        instance_name = f"nuttro_{nutricionista.id}"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{EVOLUTION_API_URL}/instance/create",
                headers={
                    "apikey": EVOLUTION_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "instanceName": instance_name,
                    "qrcode": True,
                    "integration": "WHATSAPP-BAILEYS"
                },
                timeout=30.0
            )
            
            if response.status_code == 201:
                data = response.json()
                
                # Verificar se já existe sessão
                result = await db.execute(
                    select(WhatsAppSession).where(WhatsAppSession.nutricionista_id == nutricionista.id)
                )
                session = result.scalar_one_or_none()
                
                if session:
                    session.instance_name = instance_name
                    session.instance_id = data.get("instance", {}).get("instanceId")
                    session.status = "pending"
                    session.updated_at = datetime.now(timezone.utc)
                else:
                    session = WhatsAppSession(
                        nutricionista_id=nutricionista.id,
                        instance_name=instance_name,
                        instance_id=data.get("instance", {}).get("instanceId"),
                        status="pending"
                    )
                    db.add(session)
                
                await db.commit()
                return {"message": "Instância criada", "instance_name": instance_name}
            else:
                raise HTTPException(status_code=response.status_code, detail="Erro ao criar instância")
    except Exception as e:
        logger.error(f"Erro ao criar instância: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/whatsapp/qrcode")
async def get_whatsapp_qrcode(
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Obter QR Code para conexão WhatsApp"""
    try:
        instance_name = f"nuttro_{nutricionista.id}"
        logger.info(f"🔍 Buscando QR Code para instância: {instance_name}")
        
        # Verificar se sessão existe
        result = await db.execute(
            select(WhatsAppSession).where(WhatsAppSession.nutricionista_id == nutricionista.id)
        )
        session = result.scalar_one_or_none()
        
        # Se não existir, criar
        if not session:
            logger.info(f"📱 Criando nova instância WhatsApp: {instance_name}")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{EVOLUTION_API_URL}/instance/create",
                    headers={
                        "apikey": EVOLUTION_API_KEY,
                        "Content-Type": "application/json"
                    },
                    json={
                        "instanceName": instance_name,
                        "qrcode": True,
                        "integration": "WHATSAPP-BAILEYS"
                    },
                    timeout=30.0
                )
                
                logger.info(f"Evolution API response status: {response.status_code}")
                logger.info(f"Evolution API response: {response.text[:500]}")
                
                if response.status_code != 201:
                    raise HTTPException(
                        status_code=500, 
                        detail=f"Erro ao criar instância: {response.status_code} - {response.text}"
                    )
                
                session = WhatsAppSession(
                    nutricionista_id=nutricionista.id,
                    instance_name=instance_name,
                    status="pending"
                )
                db.add(session)
                await db.commit()
                logger.info(f"✅ Instância criada no banco: {instance_name}")
        
        # Buscar QR Code
        logger.info(f"📲 Buscando QR Code da Evolution API...")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{EVOLUTION_API_URL}/instance/connect/{instance_name}",
                headers={"apikey": EVOLUTION_API_KEY},
                timeout=30.0
            )
            
            logger.info(f"QR Code response status: {response.status_code}")
            logger.info(f"QR Code response body: {response.text[:500]}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"QR Code data keys: {list(data.keys())}")
                
                # Evolution API retorna:
                # - "code": string raw do QR code (para gerar QR no frontend)
                # - "base64": imagem PNG em base64 (para exibir diretamente)
                # - "pairingCode": código de pareamento (null se não disponível)
                
                qr_code_raw = data.get("code")  # String para gerar QR
                qr_code_base64 = data.get("base64")  # Imagem base64
                pairing_code = data.get("pairingCode")
                
                if qr_code_raw or qr_code_base64:
                    # Atualizar QR code na sessão (salvar a imagem base64)
                    session.qr_code = qr_code_base64 or qr_code_raw
                    session.qr_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=2)
                    await db.commit()
                    
                    logger.info(f"✅ QR Code gerado com sucesso!")
                    return {
                        "qr_code": qr_code_raw,  # String raw para QRCode component
                        "qr_code_base64": qr_code_base64,  # Imagem para exibir diretamente
                        "pairing_code": pairing_code,
                        "status": "pending",
                        "message": "Escaneie o QR Code com seu WhatsApp"
                    }
                else:
                    # Verificar se já está conectado
                    state = data.get("instance", {}).get("state")
                    if state == "open":
                        session.status = "connected"
                        await db.commit()
                    return {
                        "qr_code": None,
                            "qr_code_base64": None,
                        "status": "connected",
                        "message": "WhatsApp já conectado"
                    }
                    
                    logger.warning(f"⚠️ QR Code não encontrado na resposta. Data completo: {data}")
                    return {
                        "qr_code": None,
                        "qr_code_base64": None,
                        "status": "waiting",
                        "message": "Aguardando geração do QR Code...",
                        "debug_data": data
                    }
            else:
                logger.error(f"❌ Erro ao buscar QR Code: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=500, 
                    detail=f"Erro ao buscar QR Code: {response.status_code}"
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao gerar QR Code: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/whatsapp/status")
async def get_whatsapp_status(
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Verificar status da conexão WhatsApp"""
    try:
        instance_name = f"nuttro_{nutricionista.id}"
        
        # Verificar no banco local
        result = await db.execute(
            select(WhatsAppSession).where(WhatsAppSession.nutricionista_id == nutricionista.id)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            return {
                "connected": False,
                "status": "disconnected",
                "message": "Nenhuma instância WhatsApp criada"
            }
        
        # Verificar status na Evolution API
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{EVOLUTION_API_URL}/instance/connectionState/{instance_name}",
                headers={"apikey": EVOLUTION_API_KEY},
                timeout=10.0
            )
            
            logger.info(f"Status response: {response.status_code} - {response.text[:200]}")
            
            if response.status_code == 200:
                data = response.json()
                state = data.get("state") or data.get("instance", {}).get("state")
                
                if state == "open":
                    # Atualizar status no banco
                    session.status = "connected"
                    session.last_connection_at = datetime.now(timezone.utc)
                    await db.commit()
                    
                    return {
                        "connected": True,
                        "status": "connected",
                        "phone": session.phone or "",
                        "phone_name": session.phone_name or ""
                    }
                else:
                    return {
                        "connected": False,
                        "status": state or "disconnected",
                        "message": f"Estado atual: {state}"
                    }
            else:
                return {
                    "connected": False,
                    "status": "error",
                    "message": f"Erro ao verificar status: {response.status_code}"
                }
    except Exception as e:
        logger.error(f"Erro ao verificar status: {str(e)}")
        return {
            "connected": False,
            "status": "error",
            "message": str(e)
        }

@api_router.post("/whatsapp/disconnect")
async def disconnect_whatsapp(
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Desconectar sessão WhatsApp"""
    try:
        instance_name = f"nuttro_{nutricionista.id}"
        
        # Desconectar na Evolution API
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{EVOLUTION_API_URL}/instance/logout/{instance_name}",
                headers={"apikey": EVOLUTION_API_KEY},
                timeout=10.0
            )
        
            logger.info(f"Disconnect response: {response.status_code}")
        
        # Atualizar no banco
        result = await db.execute(
            select(WhatsAppSession).where(WhatsAppSession.nutricionista_id == nutricionista.id)
        )
        session = result.scalar_one_or_none()
        
        if session:
            session.status = "disconnected"
            session.qr_code = None
            await db.commit()
        
        return {"message": "Desconectado com sucesso"}
    except Exception as e:
        logger.error(f"Erro ao desconectar: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ROUTES - WHATSAPP CHATS (Evolution API)
# ============================================

@api_router.get("/whatsapp/chats")
async def get_whatsapp_chats(
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Buscar todos os chats/conversas do WhatsApp via Evolution API"""
    try:
        instance_name = f"nuttro_{nutricionista.id}"
        
        async with httpx.AsyncClient() as client:
            # Buscar todos os chats - Evolution API v2 usa POST com body vazio
            response = await client.post(
                f"{EVOLUTION_API_URL}/chat/findChats/{instance_name}",
                headers={
                    "apikey": EVOLUTION_API_KEY,
                    "Content-Type": "application/json"
                },
                json={},  # Body vazio para buscar todos
                timeout=60.0
            )
            
            logger.info(f"FindChats response: {response.status_code}")
            
            if response.status_code == 200:
                chats = response.json()
                logger.info(f"Chats encontrados: {len(chats) if isinstance(chats, list) else 'não é lista'}")
                
                # Formatar chats para o frontend
                formatted_chats = []
                for chat in chats if isinstance(chats, list) else []:
                    # Extrair informações do chat
                    remote_jid = chat.get("remoteJid") or chat.get("id") or chat.get("jid", "")
                    
                    # Ignorar chats de grupo e status
                    if "@g.us" in remote_jid or "status@broadcast" in remote_jid or "@lid" in remote_jid:
                        continue
                    
                    # Extrair número do telefone
                    phone = remote_jid.replace("@s.whatsapp.net", "").replace("@c.us", "")
                    
                    # Extrair última mensagem
                    last_message = chat.get("lastMessage", {})
                    last_message_content = ""
                    if last_message:
                        msg = last_message.get("message", {})
                        last_message_content = (
                            msg.get("conversation") or
                            msg.get("extendedTextMessage", {}).get("text") if isinstance(msg.get("extendedTextMessage"), dict) else None or
                            "[Mídia]"
                        )
                    
                    formatted_chat = {
                        "id": remote_jid,
                        "phone": phone,
                        "name": chat.get("pushName") or chat.get("name") or chat.get("notify") or phone,
                        "lastMessage": last_message_content,
                        "lastMessageTime": last_message.get("messageTimestamp") if last_message else None,
                        "unreadCount": chat.get("unreadCount", 0),
                        "profilePicUrl": chat.get("profilePicUrl") or None,
                        "isGroup": "@g.us" in remote_jid,
                        "updatedAt": chat.get("updatedAt")
                    }
                    formatted_chats.append(formatted_chat)
                
                # Ordenar por última mensagem (mais recente primeiro)
                formatted_chats.sort(
                    key=lambda x: x.get("lastMessageTime") or 0,
                    reverse=True
                )
                
                logger.info(f"Retornando {len(formatted_chats)} chats formatados")
                return formatted_chats
            else:
                logger.error(f"Erro ao buscar chats: {response.status_code} - {response.text}")
                return []
                
    except Exception as e:
        logger.error(f"Erro ao buscar chats: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/whatsapp/messages/{remote_jid:path}")
async def get_whatsapp_messages(
    remote_jid: str,
    limit: int = 50,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Buscar mensagens de um chat específico via Evolution API"""
    try:
        instance_name = f"nuttro_{nutricionista.id}"
        
        # Decodificar o remote_jid se necessário
        from urllib.parse import unquote
        remote_jid = unquote(remote_jid)
        
        logger.info(f"Buscando mensagens para: {remote_jid}")
        
        async with httpx.AsyncClient() as client:
            # Buscar mensagens do chat - Evolution API v2
            response = await client.post(
                f"{EVOLUTION_API_URL}/chat/findMessages/{instance_name}",
                headers={
                    "apikey": EVOLUTION_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "where": {
                        "key": {
                            "remoteJid": remote_jid
                        }
                    },
                    "limit": limit
                },
                timeout=60.0
            )
            
            logger.info(f"FindMessages response: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                # Evolution API v2 retorna { messages: { records: [...] } }
                messages_data = data.get("messages", {})
                messages = messages_data.get("records", []) if isinstance(messages_data, dict) else messages_data
                
                logger.info(f"Mensagens encontradas: {len(messages)}")
                
                # Formatar mensagens para o frontend
                formatted_messages = []
                for msg in messages:
                    key = msg.get("key", {})
                    message_content = msg.get("message", {})
                    
                    # Extrair conteúdo da mensagem
                    content = (
                        message_content.get("conversation") or
                        (message_content.get("extendedTextMessage", {}).get("text") if isinstance(message_content.get("extendedTextMessage"), dict) else None) or
                        (message_content.get("imageMessage", {}).get("caption") if isinstance(message_content.get("imageMessage"), dict) else None) or
                        (message_content.get("videoMessage", {}).get("caption") if isinstance(message_content.get("videoMessage"), dict) else None) or
                        "[Mídia]"
                    )
                    
                    # Determinar tipo de mensagem
                    msg_type = msg.get("messageType", "text")
                    if msg_type == "conversation":
                        msg_type = "text"
                    
                    formatted_msg = {
                        "id": key.get("id", ""),
                        "fromMe": key.get("fromMe", False),
                        "remoteJid": key.get("remoteJid", ""),
                        "content": content,
                        "type": msg_type,
                        "timestamp": msg.get("messageTimestamp", 0),
                        "status": msg.get("status", ""),
                        "pushName": msg.get("pushName", "")
                    }
                    formatted_messages.append(formatted_msg)
                
                # Ordenar por timestamp (mais antigo primeiro para exibição)
                formatted_messages.sort(key=lambda x: x.get("timestamp", 0))
                
                return formatted_messages
            else:
                logger.error(f"Erro ao buscar mensagens: {response.status_code} - {response.text}")
                return []
                
    except Exception as e:
        logger.error(f"Erro ao buscar mensagens: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/whatsapp/send")
async def send_whatsapp_message(
    request: Request,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Enviar mensagem via WhatsApp usando Evolution API"""
    try:
        body = await request.json()
        remote_jid = body.get("remoteJid") or body.get("phone")
        message = body.get("message") or body.get("text") or body.get("content")
        
        if not remote_jid or not message:
            raise HTTPException(status_code=400, detail="remoteJid e message são obrigatórios")
        
        instance_name = f"nuttro_{nutricionista.id}"
        
        # Formatar número se necessário
        if "@" not in remote_jid:
            # É um número de telefone, precisa formatar
            phone = remote_jid.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
            if not phone.startswith("55"):
                phone = f"55{phone}"
            remote_jid = f"{phone}@s.whatsapp.net"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{EVOLUTION_API_URL}/message/sendText/{instance_name}",
                headers={
                    "apikey": EVOLUTION_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "number": remote_jid.replace("@s.whatsapp.net", "").replace("@c.us", ""),
                    "text": message
                },
                timeout=30.0
            )
            
            logger.info(f"SendText response: {response.status_code} - {response.text[:200]}")
            
            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "message": "Mensagem enviada com sucesso",
                    "data": response.json()
                }
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Erro ao enviar mensagem: {response.text}"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# ROUTES - MENSAGENS
# ============================================

@api_router.get("/mensagens/{paciente_id}")
async def get_mensagens(
    paciente_id: str,
    limit: int = 50,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Buscar mensagens de um paciente"""
    try:
        # Buscar conversa do paciente
        result = await db.execute(
            select(Conversa).where(
                Conversa.nutricionista_id == nutricionista.id,
                Conversa.paciente_id == paciente_id
            )
        )
        conversa = result.scalar_one_or_none()
        
        if not conversa:
            return []
        
        # Buscar mensagens
        result = await db.execute(
            select(Mensagem).where(
                Mensagem.conversa_id == conversa.id
            ).order_by(Mensagem.created_at.asc()).limit(limit)
        )
        mensagens = result.scalars().all()
        
        return [
            {
                "id": str(m.id),
                "paciente_id": str(m.paciente_id) if m.paciente_id else None,
                "remetente": m.remetente,
                "conteudo": m.conteudo,
                "tipo": m.tipo,
                "midia_url": m.midia_url,
                "lida": m.lida,
                "timestamp": m.created_at.isoformat() if m.created_at else None,
                "marcacao": conversa.marcacao
            }
            for m in mensagens
        ]
    except Exception as e:
        logger.error(f"Erro ao buscar mensagens: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class MensagemCreate(BaseModel):
    paciente_id: str
    conteudo: str
    tipo: str = "texto"

@api_router.post("/mensagens")
async def send_mensagem(
    mensagem_data: MensagemCreate,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Enviar mensagem para paciente via WhatsApp"""
    try:
        # Buscar paciente
        result = await db.execute(
            select(Paciente).where(
                Paciente.id == mensagem_data.paciente_id,
                Paciente.nutricionista_id == nutricionista.id
            )
        )
        paciente = result.scalar_one_or_none()
        
        if not paciente:
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
        
        if not paciente.telefone:
            raise HTTPException(status_code=400, detail="Paciente não possui telefone cadastrado")
        
        # Buscar ou criar conversa
        result = await db.execute(
            select(Conversa).where(
                Conversa.nutricionista_id == nutricionista.id,
                Conversa.paciente_id == mensagem_data.paciente_id
            )
        )
        conversa = result.scalar_one_or_none()
        
        if not conversa:
            conversa = Conversa(
                nutricionista_id=nutricionista.id,
                paciente_id=mensagem_data.paciente_id,
                telefone=paciente.telefone,
                nome_contato=paciente.nome
            )
            db.add(conversa)
            await db.commit()
            await db.refresh(conversa)
        
        # Enviar via Evolution API
        instance_name = f"nuttro_{nutricionista.id}"
        telefone_formatado = paciente.telefone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
        if not telefone_formatado.startswith("55"):
            telefone_formatado = f"55{telefone_formatado}"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{EVOLUTION_API_URL}/message/sendText/{instance_name}",
                headers={
                    "apikey": EVOLUTION_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "number": telefone_formatado,
                    "text": mensagem_data.conteudo
                },
                timeout=30.0
            )
            
            logger.info(f"Evolution sendText response: {response.status_code} - {response.text[:200]}")
            
            if response.status_code not in [200, 201]:
                logger.error(f"Erro ao enviar mensagem via Evolution: {response.text}")
        
        # Salvar mensagem no banco
        nova_mensagem = Mensagem(
            conversa_id=conversa.id,
            nutricionista_id=nutricionista.id,
            paciente_id=mensagem_data.paciente_id,
            remetente="nutricionista",
            conteudo=mensagem_data.conteudo,
            tipo=mensagem_data.tipo
        )
        db.add(nova_mensagem)
        
        # Atualizar conversa
        conversa.last_message_at = datetime.now(timezone.utc)
        conversa.last_message_preview = mensagem_data.conteudo[:100]
        
        await db.commit()
        await db.refresh(nova_mensagem)
        
        # Emitir via Socket.IO
        await sio.emit('nova_mensagem', {
            "id": str(nova_mensagem.id),
            "paciente_id": str(mensagem_data.paciente_id),
            "remetente": "nutricionista",
            "conteudo": mensagem_data.conteudo,
            "tipo": mensagem_data.tipo,
            "timestamp": nova_mensagem.created_at.isoformat()
        }, room=f"paciente_{mensagem_data.paciente_id}")
        
        return {
            "id": str(nova_mensagem.id),
            "message": "Mensagem enviada com sucesso"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@api_router.patch("/mensagens/{mensagem_id}/marcacao")
async def update_mensagem_marcacao(
    mensagem_id: str,
    marcacao: str,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Atualizar marcação de uma mensagem/conversa"""
    try:
        # Buscar mensagem
        result = await db.execute(
            select(Mensagem).where(Mensagem.id == mensagem_id)
        )
        mensagem = result.scalar_one_or_none()
        
        if not mensagem:
            raise HTTPException(status_code=404, detail="Mensagem não encontrada")
        
        # Atualizar marcação na conversa
        result = await db.execute(
            select(Conversa).where(Conversa.id == mensagem.conversa_id)
        )
        conversa = result.scalar_one_or_none()
        
        if conversa:
            conversa.marcacao = marcacao
            await db.commit()
        
        return {"message": "Marcação atualizada com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar marcação: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ROUTES - MARCAÇÃO DE CONVERSAS
# ============================================

class ConversaMarcacaoUpdate(BaseModel):
    marcacao: str  # agendado, ainda_a_agendar, aguardando_resposta, null

@api_router.patch("/conversas/{conversa_id}/marcacao")
async def update_conversa_marcacao(
    conversa_id: str,
    data: ConversaMarcacaoUpdate,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Atualizar marcação de uma conversa"""
    try:
        result = await db.execute(
            select(Conversa).where(
                Conversa.id == conversa_id,
                Conversa.nutricionista_id == nutricionista.id
            )
        )
        conversa = result.scalar_one_or_none()
        
        if not conversa:
            raise HTTPException(status_code=404, detail="Conversa não encontrada")
        
        conversa.marcacao = data.marcacao if data.marcacao != "null" else None
        conversa.updated_at = datetime.now(timezone.utc)
        await db.commit()
        
        return {"message": "Marcação atualizada com sucesso", "marcacao": conversa.marcacao}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar marcação da conversa: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.patch("/whatsapp/chats/{remote_jid}/marcacao")
async def update_whatsapp_chat_marcacao(
    remote_jid: str,
    data: ConversaMarcacaoUpdate,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Atualizar marcação de um chat do WhatsApp (cria conversa local se não existir)"""
    try:
        # Extrair telefone do remote_jid
        telefone = remote_jid.replace("@s.whatsapp.net", "").replace("@g.us", "")
        
        # Buscar ou criar conversa
        result = await db.execute(
            select(Conversa).where(
                Conversa.nutricionista_id == nutricionista.id,
                Conversa.telefone.contains(telefone[-8:])
            )
        )
        conversa = result.scalar_one_or_none()
        
        if not conversa:
            # Criar nova conversa local para este chat
            conversa = Conversa(
                nutricionista_id=nutricionista.id,
                telefone=telefone,
                nome_contato=telefone,  # Será atualizado depois
                marcacao=data.marcacao if data.marcacao != "null" else None
            )
            db.add(conversa)
        else:
            conversa.marcacao = data.marcacao if data.marcacao != "null" else None
            conversa.updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(conversa)
        
        return {
            "message": "Marcação atualizada com sucesso",
            "conversa_id": str(conversa.id),
            "marcacao": conversa.marcacao
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar marcação do chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ROTAS - CONVERSAS (Observações e Marcações por Telefone)
# ============================================

@api_router.put("/conversas/{telefone}/observacoes")
async def update_conversa_observacoes_by_phone(
    telefone: str,
    request: Request,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Atualizar observações de uma conversa por telefone - cria se não existir"""
    try:
        body = await request.json()
        observacoes = body.get("observacoes", "")
        
        # Normalizar telefone
        telefone = telefone.replace("%40", "@")
        telefone_normalized = telefone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "").replace("@s.whatsapp.net", "").replace("@g.us", "").replace("@c.us", "")
        
        async with AsyncSessionLocal() as isolated_db:
            try:
                result = await isolated_db.execute(
                    select(Conversa).where(
                        Conversa.nutricionista_id == nutricionista.id,
                        or_(
                            Conversa.telefone == telefone,
                            Conversa.telefone == telefone_normalized,
                            Conversa.telefone.contains(telefone_normalized[-8:] if len(telefone_normalized) >= 8 else telefone_normalized)
                        )
                    )
                )
                conversa = result.scalar_one_or_none()
                
                if not conversa:
                    conversa = Conversa(
                        nutricionista_id=nutricionista.id,
                        telefone=telefone_normalized,
                        nome_contato=telefone,
                        observacoes=observacoes
                    )
                    isolated_db.add(conversa)
                else:
                    conversa.observacoes = observacoes
                    conversa.updated_at = datetime.now(timezone.utc)
                
                await isolated_db.commit()
                await isolated_db.refresh(conversa)
                
                return {"success": True, "observacoes": conversa.observacoes}
            except Exception as e:
                if isolated_db.is_active:
                    await isolated_db.rollback()
                logger.error(f"Erro interno ao atualizar observações: {e}")
                raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar observações: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar observações: {str(e)}")

@api_router.put("/conversas/{telefone}/marcacao")
async def update_conversa_marcacao_by_phone(
    telefone: str,
    request: Request,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Atualizar marcação de uma conversa por telefone - cria se não existir"""
    try:
        body = await request.json()
        marcacao = body.get("marcacao")
        
        # Normalizar telefone
        telefone = telefone.replace("%40", "@")
        telefone_normalized = telefone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "").replace("@s.whatsapp.net", "").replace("@g.us", "").replace("@c.us", "")
        
        async with AsyncSessionLocal() as isolated_db:
            try:
                result = await isolated_db.execute(
                    select(Conversa).where(
                        Conversa.nutricionista_id == nutricionista.id,
                        or_(
                            Conversa.telefone == telefone,
                            Conversa.telefone == telefone_normalized,
                            Conversa.telefone.contains(telefone_normalized[-8:] if len(telefone_normalized) >= 8 else telefone_normalized)
                        )
                    )
                )
                conversa = result.scalar_one_or_none()
                
                if not conversa:
                    conversa = Conversa(
                        nutricionista_id=nutricionista.id,
                        telefone=telefone_normalized,
                        nome_contato=telefone,
                        marcacao=marcacao if marcacao and marcacao != "null" else None
                    )
                    isolated_db.add(conversa)
                else:
                    conversa.marcacao = marcacao if marcacao and marcacao != "null" else None
                    conversa.updated_at = datetime.now(timezone.utc)
                
                await isolated_db.commit()
                await isolated_db.refresh(conversa)
                
                return {"success": True, "marcacao": conversa.marcacao}
            except Exception as e:
                if isolated_db.is_active:
                    await isolated_db.rollback()
                logger.error(f"Erro interno ao atualizar marcação: {e}")
                raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar marcação: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar marcação: {str(e)}")

@api_router.get("/whatsapp/chats/marcacoes")
async def get_whatsapp_chats_marcacoes(
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Buscar todas as marcações de conversas do usuário"""
    try:
        result = await db.execute(
            select(Conversa).where(
                Conversa.nutricionista_id == nutricionista.id,
                Conversa.marcacao.isnot(None)
            )
        )
        conversas = result.scalars().all()
        
        # Retornar mapa de telefone -> marcação
        marcacoes = {}
        for c in conversas:
            marcacoes[c.telefone] = {
                "conversa_id": str(c.id),
                "marcacao": c.marcacao,
                "nome_contato": c.nome_contato
            }
        
        return marcacoes
    except Exception as e:
        logger.error(f"Erro ao buscar marcações: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ROUTES - STATUS PERSONALIZADOS
# ============================================

class StatusPersonalizadoCreate(BaseModel):
    nome: str
    cor: str = "#6B2FFF"
    icone: str = None

class StatusPersonalizadoUpdate(BaseModel):
    nome: str = None
    cor: str = None
    icone: str = None
    ativo: bool = None
    ordem: int = None

@api_router.get("/status-personalizados")
async def get_status_personalizados(
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Listar status personalizados do nutricionista"""
    try:
        result = await db.execute(
            select(StatusPersonalizado).where(
                StatusPersonalizado.nutricionista_id == nutricionista.id,
                StatusPersonalizado.ativo == True
            ).order_by(StatusPersonalizado.ordem)
        )
        status_list = result.scalars().all()
        
        # Adicionar status padrão se não houver nenhum
        default_status = [
            {"id": "agendado", "nome": "Agendado", "cor": "#3B82F6", "icone": "calendar", "is_default": True},
            {"id": "ainda_a_agendar", "nome": "Ainda a Agendar", "cor": "#F59E0B", "icone": "clock", "is_default": True},
            {"id": "aguardando_resposta", "nome": "Aguardando Resposta", "cor": "#8B5CF6", "icone": "message-circle", "is_default": True}
        ]
        
        custom_status = [
            {
                "id": str(s.id),
                "nome": s.nome,
                "cor": s.cor,
                "icone": s.icone,
                "ordem": s.ordem,
                "is_default": False
            }
            for s in status_list
        ]
        
        return default_status + custom_status
    except Exception as e:
        logger.error(f"Erro ao buscar status personalizados: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/status-personalizados")
async def create_status_personalizado(
    data: StatusPersonalizadoCreate,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Criar novo status personalizado"""
    try:
        # Contar status existentes para definir ordem
        result = await db.execute(
            select(StatusPersonalizado).where(
                StatusPersonalizado.nutricionista_id == nutricionista.id
            )
        )
        count = len(result.scalars().all())
        
        novo_status = StatusPersonalizado(
            nutricionista_id=nutricionista.id,
            nome=data.nome,
            cor=data.cor,
            icone=data.icone,
            ordem=count + 1
        )
        db.add(novo_status)
        await db.commit()
        await db.refresh(novo_status)
        
        return {
            "id": str(novo_status.id),
            "nome": novo_status.nome,
            "cor": novo_status.cor,
            "icone": novo_status.icone,
            "ordem": novo_status.ordem
        }
    except Exception as e:
        logger.error(f"Erro ao criar status personalizado: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.patch("/status-personalizados/{status_id}")
async def update_status_personalizado(
    status_id: str,
    data: StatusPersonalizadoUpdate,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Atualizar status personalizado"""
    try:
        result = await db.execute(
            select(StatusPersonalizado).where(
                StatusPersonalizado.id == status_id,
                StatusPersonalizado.nutricionista_id == nutricionista.id
            )
        )
        status = result.scalar_one_or_none()
        
        if not status:
            raise HTTPException(status_code=404, detail="Status não encontrado")
        
        if data.nome is not None:
            status.nome = data.nome
        if data.cor is not None:
            status.cor = data.cor
        if data.icone is not None:
            status.icone = data.icone
        if data.ativo is not None:
            status.ativo = data.ativo
        if data.ordem is not None:
            status.ordem = data.ordem
        
        await db.commit()
        
        return {"message": "Status atualizado com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar status personalizado: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/status-personalizados/{status_id}")
async def delete_status_personalizado(
    status_id: str,
    nutricionista: Nutricionista = Depends(get_current_nutricionista),
    db: AsyncSession = Depends(get_db)
):
    """Excluir status personalizado"""
    try:
        result = await db.execute(
            select(StatusPersonalizado).where(
                StatusPersonalizado.id == status_id,
                StatusPersonalizado.nutricionista_id == nutricionista.id
            )
        )
        status = result.scalar_one_or_none()
        
        if not status:
            raise HTTPException(status_code=404, detail="Status não encontrado")
        
        await db.delete(status)
        await db.commit()
        
        return {"message": "Status excluído com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao excluir status personalizado: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ROUTES - WEBHOOKS (Evolution API)
# ============================================

@api_router.post("/webhooks/evolution")
async def evolution_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Webhook para receber eventos da Evolution API"""
    try:
        data = await request.json()
        event_type = data.get("event")
        instance_name = data.get("instance")
        
        logger.info(f"Webhook Evolution: {event_type} - {instance_name}")
        
        if event_type == "messages.upsert":
            # Nova mensagem recebida
            messages = data.get("data", [])
            for msg in messages:
                if msg.get("key", {}).get("fromMe"):
                    continue  # Ignorar mensagens enviadas por nós
                
                remote_jid = msg.get("key", {}).get("remoteJid", "")
                telefone = remote_jid.replace("@s.whatsapp.net", "")
                conteudo = msg.get("message", {}).get("conversation") or msg.get("message", {}).get("extendedTextMessage", {}).get("text", "")
                
                # Extrair nutricionista_id do instance_name
                if instance_name and instance_name.startswith("nuttro_"):
                    nutricionista_id = instance_name.replace("nuttro_", "")
                    
                    # Buscar conversa pelo telefone
                    result = await db.execute(
                        select(Conversa).where(
                            Conversa.nutricionista_id == nutricionista_id,
                            Conversa.telefone.contains(telefone[-8:])  # Últimos 8 dígitos
                        )
                    )
                    conversa = result.scalar_one_or_none()
                    
                    if conversa:
                        # Salvar mensagem
                        nova_mensagem = Mensagem(
                            conversa_id=conversa.id,
                            nutricionista_id=nutricionista_id,
                            paciente_id=conversa.paciente_id,
                            remetente="paciente",
                            conteudo=conteudo,
                            tipo="texto",
                            whatsapp_id=msg.get("key", {}).get("id")
                        )
                        db.add(nova_mensagem)
                        
                        # Atualizar conversa
                        conversa.last_message_at = datetime.now(timezone.utc)
                        conversa.last_message_preview = conteudo[:100]
                        conversa.unread_count = (conversa.unread_count or 0) + 1
                        
                        await db.commit()
                        await db.refresh(nova_mensagem)
                        
                        # Emitir via Socket.IO
                        await sio.emit('nova_mensagem', {
                            "id": str(nova_mensagem.id),
                            "paciente_id": str(conversa.paciente_id) if conversa.paciente_id else None,
                            "remetente": "paciente",
                            "conteudo": conteudo,
                            "tipo": "texto",
                            "timestamp": nova_mensagem.created_at.isoformat()
                        }, room=f"paciente_{conversa.paciente_id}")
        
        elif event_type == "connection.update":
            # Atualização de conexão
            state = data.get("data", {}).get("state")
            if instance_name and instance_name.startswith("nuttro_"):
                nutricionista_id = instance_name.replace("nuttro_", "")
                
                result = await db.execute(
                    select(WhatsAppSession).where(WhatsAppSession.instance_name == instance_name)
                )
                session = result.scalar_one_or_none()
                
                if session:
                    if state == "open":
                        session.status = "connected"
                        session.last_connection_at = datetime.now(timezone.utc)
                    elif state == "close":
                        session.status = "disconnected"
                    
                    await db.commit()
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Erro no webhook Evolution: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}

# Include router
app.include_router(api_router)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Socket.IO
socket_app = socketio.ASGIApp(sio, app)

# Iniciar servidor quando executado diretamente
if __name__ == "__main__":
    import uvicorn
    print("🚀 Iniciando servidor Nuttro...")
    uvicorn.run(socket_app, host="0.0.0.0", port=8000)

