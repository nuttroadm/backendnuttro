"""
Arquivo compartilhado com funções e constantes comuns
usado por serverweb.py e serverapp.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timezone, timedelta
import re
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr

from database import get_db
from models import Nutricionista, Paciente

# ============================================
# PYDANTIC MODELS
# ============================================

class NutricionistaCreate(BaseModel):
    email: EmailStr
    nome: str
    senha: str
    crn: Optional[str] = None

class PacienteCreate(BaseModel):
    cpf: str
    nome: str
    email: Optional[EmailStr] = None
    senha: str
    telefone: Optional[str] = None
    data_nascimento: Optional[str] = None
    sexo: Optional[str] = None
    objetivo: Optional[str] = None

class LoginRequest(BaseModel):
    email: Optional[str] = None
    cpf: Optional[str] = None
    senha: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_type: str
    user: Dict[str, Any]

# Configuração
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "nuttro-solo-secret-key-2024-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 dias

# Evolution API
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "https://orderlymanatee-evolution.cloudfy.live")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "LzKrIvkg0gI28IzfBjoROnFKjWyTgj54")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ============================================
# HELPERS
# ============================================

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def validate_cpf(cpf: str) -> bool:
    cpf = re.sub(r'[^0-9]', '', cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for i in range(9, 11):
        value = sum((int(cpf[num]) * ((i + 1) - num) for num in range(0, i)))
        digit = ((value * 10) % 11) % 10
        if digit != int(cpf[i]):
            return False
    return True

def nutricionista_to_dict(n: Nutricionista) -> dict:
    return {
        "id": str(n.id),
        "email": n.email,
        "nome": n.nome,
        "crn": n.crn,
        "telefone": n.telefone,
        "foto_url": n.foto_url,
        "especialidades": n.especialidades,
        "plano": n.plano,
        "ativo": n.ativo,
        "created_at": n.created_at.isoformat() if n.created_at else None
    }

def paciente_to_dict(p: Paciente) -> dict:
    return {
        "id": str(p.id),
        "nutricionista_id": str(p.nutricionista_id),
        "cpf": p.cpf,
        "nome": p.nome,
        "email": p.email,
        "telefone": p.telefone,
        "data_nascimento": p.data_nascimento.isoformat() if p.data_nascimento else None,
        "sexo": p.sexo,
        "objetivo": p.objetivo,
        "altura_cm": p.altura_cm,
        "peso_atual_kg": p.peso_atual_kg,
        "peso_meta_kg": p.peso_meta_kg,
        "status": p.status,
        "nivel_adesao": p.nivel_adesao,
        "kanban_status": p.kanban_status,
        "dias_jornada": p.dias_jornada,
        "endereco": p.endereco,
        "observacoes": p.observacoes,
        "created_at": p.created_at.isoformat() if p.created_at else None
    }

# ============================================
# AUTH DEPENDENCIES
# ============================================

async def get_current_nutricionista(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Nutricionista:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        from jose import JWTError
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        user_type: str = payload.get("type")
        if not user_id or user_type != "nutricionista":
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(Nutricionista).where(Nutricionista.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exception
    return user

async def get_current_paciente(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Paciente:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        from jose import JWTError
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        user_type: str = payload.get("type")
        if not user_id or user_type != "paciente":
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(Paciente).where(Paciente.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exception
    return user

