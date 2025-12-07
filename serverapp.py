"""
Rotas do Mobile (Pacientes)
Todas as rotas relacionadas ao aplicativo React Native
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import datetime, timezone
import logging
import re
import uuid

from database import get_db
from models import Paciente, CheckIn, Refeicao, ChatMessage, Nutricionista
from ai_agents import (
    get_checkin_analysis_agent,
    get_meal_analysis_agent,
    get_patient_chat_agent
)
from shared import (
    get_current_paciente, paciente_to_dict, PacienteCreate, LoginRequest,
    validate_cpf, get_password_hash, create_access_token, verify_password
)
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Router para rotas mobile
app_router = APIRouter(prefix="/api/mobile", tags=["Mobile - Pacientes"])

# Router para autenticação de pacientes (fora do /mobile)
auth_router = APIRouter(prefix="/api/auth", tags=["Auth - Pacientes"])

# ============================================
# PYDANTIC MODELS
# ============================================

class CheckInCreate(BaseModel):
    data: Optional[str] = None
    consistencia_plano: int
    frequencia_refeicoes: int
    tempo_refeicao: Optional[int] = None
    vegetais_frutas: int
    ingestao_liquido: int
    energia_fisica: int
    atividade_fisica: Optional[int] = None
    qualidade_sono: int
    confianca_jornada: int
    satisfacao_corpo: Optional[int] = None
    humor: Optional[str] = None
    notas: Optional[str] = None

class RefeicaoCreate(BaseModel):
    tipo: str
    foto_base64: Optional[str] = None
    descricao: Optional[str] = None

class ChatRequest(BaseModel):
    message: str

# ============================================
# ROTAS MOBILE - PACIENTES
# ============================================

@app_router.get("/me")
async def get_mobile_me(
    paciente: Paciente = Depends(get_current_paciente),
    db: AsyncSession = Depends(get_db)
):
    """Obter dados do paciente atual (mobile)"""
    return paciente_to_dict(paciente)

@app_router.get("/dashboard")
async def mobile_dashboard(
    paciente: Paciente = Depends(get_current_paciente),
    db: AsyncSession = Depends(get_db)
):
    """Dashboard do paciente no app"""
    # Calcular estatísticas
    result = await db.execute(
        select(func.count(CheckIn.id)).where(CheckIn.paciente_id == paciente.id)
    )
    total_checkins = result.scalar() or 0
    
    result = await db.execute(
        select(func.count(Refeicao.id)).where(Refeicao.paciente_id == paciente.id)
    )
    total_refeicoes = result.scalar() or 0
    
    from models import Meta
    result = await db.execute(
        select(func.count(Meta.id)).where(
            Meta.paciente_id == paciente.id,
            Meta.status == 'concluida'
        )
    )
    metas_concluidas = result.scalar() or 0
    
    # Buscar último check-in
    result = await db.execute(
        select(CheckIn).where(CheckIn.paciente_id == paciente.id)
        .order_by(CheckIn.created_at.desc()).limit(1)
    )
    ultimo_checkin = result.scalar_one_or_none()
    
    return {
        "paciente": paciente_to_dict(paciente),
        "stats": {
            "dias_jornada": paciente.dias_jornada,
            "total_checkins": total_checkins,
            "total_refeicoes": total_refeicoes,
            "metas_concluidas": metas_concluidas
        },
        "ultimo_checkin": ultimo_checkin.data.isoformat() if ultimo_checkin else None
    }

@app_router.post("/checkin")
async def create_checkin(
    data: CheckInCreate,
    paciente: Paciente = Depends(get_current_paciente),
    db: AsyncSession = Depends(get_db)
):
    """Criar check-in diário"""
    # Criar check-in
    checkin = CheckIn(
        paciente_id=paciente.id,
        data=datetime.fromisoformat(data.data) if data.data else datetime.now(timezone.utc),
        consistencia_plano=data.consistencia_plano,
        frequencia_refeicoes=data.frequencia_refeicoes,
        tempo_refeicao=data.tempo_refeicao,
        vegetais_frutas=data.vegetais_frutas,
        ingestao_liquido=data.ingestao_liquido,
        energia_fisica=data.energia_fisica,
        atividade_fisica=data.atividade_fisica,
        qualidade_sono=data.qualidade_sono,
        confianca_jornada=data.confianca_jornada,
        satisfacao_corpo=data.satisfacao_corpo,
        humor=data.humor,
        notas=data.notas
    )
    
    db.add(checkin)
    
    # Atualizar último check-in do paciente
    paciente.last_checkin_at = datetime.now(timezone.utc)
    paciente.dias_jornada = (paciente.dias_jornada or 0) + 1
    
    await db.commit()
    await db.refresh(checkin)
    
    # Análise da IA (assíncrona)
    try:
        agent = get_checkin_analysis_agent()
        # Buscar últimos check-ins para análise
        result = await db.execute(
            select(CheckIn).where(CheckIn.paciente_id == paciente.id)
            .order_by(CheckIn.created_at.desc()).limit(7)
        )
        recent_checkins = result.scalars().all()
        
        analysis = await agent.analyze(
            checkins=[{
                "data": c.data.isoformat() if c.data else None,
                "consistencia_plano": c.consistencia_plano,
                "vegetais_frutas": c.vegetais_frutas,
                "ingestao_liquido": c.ingestao_liquido,
                "energia_fisica": c.energia_fisica,
                "qualidade_sono": c.qualidade_sono
            } for c in recent_checkins],
            patient_info={"nome": paciente.nome, "objetivo": paciente.objetivo},
            metas=[]
        )
        
        checkin.analise_ia = analysis
        await db.commit()
        
    except Exception as e:
        logger.error(f"Erro na análise de IA: {e}")
    
    return {
        "id": str(checkin.id),
        "message": "Check-in registrado com sucesso!",
        "analise_ia": checkin.analise_ia
    }

@app_router.get("/checkins")
async def get_checkins(
    limit: int = 30,
    paciente: Paciente = Depends(get_current_paciente),
    db: AsyncSession = Depends(get_db)
):
    """Listar check-ins do paciente"""
    result = await db.execute(
        select(CheckIn).where(CheckIn.paciente_id == paciente.id)
        .order_by(CheckIn.created_at.desc()).limit(limit)
    )
    checkins = result.scalars().all()
    
    return [{
        "id": str(c.id),
        "data": c.data.isoformat() if c.data else None,
        "consistencia_plano": c.consistencia_plano,
        "frequencia_refeicoes": c.frequencia_refeicoes,
        "vegetais_frutas": c.vegetais_frutas,
        "ingestao_liquido": c.ingestao_liquido,
        "energia_fisica": c.energia_fisica,
        "qualidade_sono": c.qualidade_sono,
        "confianca_jornada": c.confianca_jornada,
        "humor": c.humor,
        "analise_ia": c.analise_ia
    } for c in checkins]

@app_router.post("/refeicao")
async def create_refeicao(
    data: RefeicaoCreate,
    paciente: Paciente = Depends(get_current_paciente),
    db: AsyncSession = Depends(get_db)
):
    """Registrar refeição com análise de IA"""
    refeicao = Refeicao(
        paciente_id=paciente.id,
        tipo=data.tipo,
        data_hora=datetime.now(timezone.utc),
        foto_base64=data.foto_base64,
        descricao=data.descricao
    )
    
    # Se tem foto, analisar com IA
    if data.foto_base64:
        try:
            agent = get_meal_analysis_agent()
            analysis = await agent.analyze(
                image_base64=data.foto_base64,
                patient_context={
                    "nome": paciente.nome,
                    "objetivo": paciente.objetivo
                }
            )
            
            refeicao.itens_identificados = analysis.get("itens", [])
            refeicao.porcoes = analysis.get("porcoes", {})
            refeicao.macros = analysis.get("macros", {})
            refeicao.calorias_estimadas = analysis.get("calorias_estimadas", 0)
            refeicao.feedback_ia = analysis.get("feedback", "")
            refeicao.sugestoes_ia = analysis.get("sugestoes", [])
            refeicao.alinhamento_plano = analysis.get("alinhamento_plano", "atencao")
            
        except Exception as e:
            logger.error(f"Erro na análise de refeição: {e}")
    
    db.add(refeicao)
    await db.commit()
    await db.refresh(refeicao)
    
    return {
        "id": str(refeicao.id),
        "tipo": refeicao.tipo,
        "data_hora": refeicao.data_hora.isoformat(),
        "itens": refeicao.itens_identificados,
        "macros": refeicao.macros,
        "calorias": refeicao.calorias_estimadas,
        "feedback": refeicao.feedback_ia,
        "sugestoes": refeicao.sugestoes_ia,
        "alinhamento": refeicao.alinhamento_plano
    }

@app_router.get("/refeicoes")
async def get_refeicoes(
    limit: int = 20,
    paciente: Paciente = Depends(get_current_paciente),
    db: AsyncSession = Depends(get_db)
):
    """Listar refeições do paciente"""
    result = await db.execute(
        select(Refeicao).where(Refeicao.paciente_id == paciente.id)
        .order_by(Refeicao.created_at.desc()).limit(limit)
    )
    refeicoes = result.scalars().all()
    
    return [{
        "id": str(r.id),
        "tipo": r.tipo,
        "data_hora": r.data_hora.isoformat() if r.data_hora else None,
        "itens": r.itens_identificados,
        "calorias": r.calorias_estimadas,
        "alinhamento": r.alinhamento_plano,
        "feedback": r.feedback_ia
    } for r in refeicoes]

@app_router.post("/chat")
async def chat_with_ai(
    data: ChatRequest,
    paciente: Paciente = Depends(get_current_paciente),
    db: AsyncSession = Depends(get_db)
):
    """Chat com IA"""
    # Buscar histórico
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.paciente_id == paciente.id)
        .order_by(ChatMessage.created_at.desc()).limit(20)
    )
    history = result.scalars().all()
    
    chat_history = [{"role": m.role, "content": m.content} for m in reversed(history)]
    
    # Buscar contexto
    result = await db.execute(
        select(CheckIn).where(CheckIn.paciente_id == paciente.id)
        .order_by(CheckIn.created_at.desc()).limit(5)
    )
    recent_checkins = result.scalars().all()
    
    context = {
        "nome": paciente.nome,
        "objetivo": paciente.objetivo or "não definido",
        "dias_jornada": paciente.dias_jornada or 0,
        "nivel_adesao": paciente.nivel_adesao or "média",
        "ultima_consulta": "não registrada",
        "metas": [],
        "checkins_resumo": f"{len(recent_checkins)} check-ins recentes",
        "refeicoes_resumo": "dados disponíveis"
    }
    
    # Processar com IA
    agent = get_patient_chat_agent()
    response = await agent.chat(data.message, context, chat_history)
    
    # Salvar mensagens
    user_msg = ChatMessage(
        paciente_id=paciente.id,
        role="user",
        content=data.message
    )
    ai_msg = ChatMessage(
        paciente_id=paciente.id,
        role="assistant",
        content=response
    )
    
    db.add(user_msg)
    db.add(ai_msg)
    await db.commit()
    
    return {"response": response}

@app_router.get("/chat/history")
async def get_chat_history(
    limit: int = 50,
    paciente: Paciente = Depends(get_current_paciente),
    db: AsyncSession = Depends(get_db)
):
    """Obter histórico do chat"""
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.paciente_id == paciente.id)
        .order_by(ChatMessage.created_at.asc()).limit(limit)
    )
    messages = result.scalars().all()
    
    return [{
        "id": str(m.id),
        "role": m.role,
        "content": m.content,
        "timestamp": m.created_at.isoformat() if m.created_at else None
    } for m in messages]

# ============================================
# ROTAS DE AUTENTICAÇÃO - PACIENTES
# ============================================

@auth_router.post("/paciente/register", status_code=status.HTTP_201_CREATED)
async def register_paciente(
    data: PacienteCreate,
    db: AsyncSession = Depends(get_db)
):
    """Registrar novo paciente"""
    # Validar CPF
    if not validate_cpf(data.cpf):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CPF inválido"
        )
    
    # Limpar CPF (remover caracteres não numéricos)
    cpf_clean = re.sub(r'[^0-9]', '', data.cpf)
    
    # Verificar se CPF já existe
    result = await db.execute(
        select(Paciente).where(Paciente.cpf == cpf_clean)
    )
    existing_cpf = result.scalar_one_or_none()
    if existing_cpf:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CPF já cadastrado"
        )
    
    # Verificar se email já existe (se fornecido)
    if data.email:
        result = await db.execute(
            select(Paciente).where(Paciente.email == data.email)
        )
        existing_email = result.scalar_one_or_none()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já cadastrado"
            )
    
    # Converter data de nascimento (formato DD/MM/AAAA)
    data_nascimento = None
    if data.data_nascimento:
        try:
            # Formato esperado: DD/MM/AAAA
            parts = data.data_nascimento.split('/')
            if len(parts) == 3:
                dia, mes, ano = parts
                data_nascimento = datetime(int(ano), int(mes), int(dia), tzinfo=timezone.utc)
        except (ValueError, IndexError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Data de nascimento inválida. Use o formato DD/MM/AAAA"
            )
    
    # Criar paciente
    paciente = Paciente(
        cpf=cpf_clean,
        nome=data.nome,
        email=data.email,
        senha_hash=get_password_hash(data.senha),
        telefone=data.telefone,
        data_nascimento=data_nascimento,
        sexo=data.sexo,
        objetivo=data.objetivo,
        status="novo",
        kanban_status="novos"
    )
    
    db.add(paciente)
    await db.commit()
    await db.refresh(paciente)
    
    # Criar token
    access_token = create_access_token(
        data={"sub": str(paciente.id), "type": "paciente"}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": paciente_to_dict(paciente)
    }

@auth_router.post("/paciente/login")
async def login_paciente(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login de paciente via CPF"""
    if not data.cpf:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CPF é obrigatório"
        )
    
    # Limpar CPF
    cpf_clean = re.sub(r'[^0-9]', '', data.cpf)
    
    # Buscar paciente
    result = await db.execute(
        select(Paciente).where(Paciente.cpf == cpf_clean)
    )
    paciente = result.scalar_one_or_none()
    
    if not paciente:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="CPF ou senha incorretos"
        )
    
    # Verificar senha
    if not verify_password(data.senha, paciente.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="CPF ou senha incorretos"
        )
    
    # Criar token
    access_token = create_access_token(
        data={"sub": str(paciente.id), "type": "paciente"}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": paciente_to_dict(paciente)
    }

