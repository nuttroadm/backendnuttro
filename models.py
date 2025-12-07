"""
Modelos SQLAlchemy para Backend Solo Nuttro
Tabelas separadas para Nutricionistas e Pacientes
Com comunicação integrada entre ambos
"""

from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey, JSON, Float, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime, timezone
import uuid
import enum

Base = declarative_base()

# ============================================
# ENUMS
# ============================================

class TipoUsuario(str, enum.Enum):
    NUTRICIONISTA = "nutricionista"
    PACIENTE = "paciente"
    ADMIN = "admin"

class StatusPaciente(str, enum.Enum):
    ATIVO = "ativo"
    INATIVO = "inativo"
    PAUSADO = "pausado"

class NivelAdesao(str, enum.Enum):
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"

class TipoConsulta(str, enum.Enum):
    PRIMEIRA = "primeira_consulta"
    RETORNO = "retorno"
    ACOMPANHAMENTO = "acompanhamento"

class StatusAgendamento(str, enum.Enum):
    AGENDADO = "agendado"
    CONFIRMADO = "confirmado"
    REALIZADO = "realizado"
    CANCELADO = "cancelado"
    REMARCADO = "remarcado"

# ============================================
# TABELA: NUTRICIONISTAS (Usuários Web)
# ============================================

class Nutricionista(Base):
    __tablename__ = "nutricionistas"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    nome = Column(String(255), nullable=False)
    senha_hash = Column(String(255))
    
    # Dados profissionais
    crn = Column(String(20), unique=True, index=True)  # Registro profissional
    especialidades = Column(JSON, default=list)  # ["esportiva", "clinica", etc]
    telefone = Column(String(50))
    foto_url = Column(Text)
    bio = Column(Text)
    
    # OAuth
    google_id = Column(String(255), index=True)
    
    # Status
    ativo = Column(Boolean, default=True)
    plano = Column(String(50), default='free')  # free, pro, enterprise
    
    # Configurações
    config_notificacoes = Column(JSON, default=dict)
    config_ia = Column(JSON, default=dict)  # Preferências da IA
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login_at = Column(DateTime(timezone=True))
    
    # Relationships
    pacientes = relationship("Paciente", back_populates="nutricionista", cascade="all, delete-orphan")
    whatsapp_session = relationship("WhatsAppSession", back_populates="nutricionista", uselist=False, cascade="all, delete-orphan")
    agendamentos = relationship("Agendamento", back_populates="nutricionista", cascade="all, delete-orphan")
    consultas = relationship("Consulta", back_populates="nutricionista", cascade="all, delete-orphan")
    status_personalizados = relationship("StatusPersonalizado", back_populates="nutricionista", cascade="all, delete-orphan")

# ============================================
# TABELA: PACIENTES (Usuários Mobile)
# ============================================

class Paciente(Base):
    __tablename__ = "pacientes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nutricionista_id = Column(UUID(as_uuid=True), ForeignKey("nutricionistas.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Credenciais do app
    cpf = Column(String(11), unique=True, nullable=False, index=True)
    email = Column(String(255), index=True)
    senha_hash = Column(String(255))
    
    # Dados pessoais
    nome = Column(String(255), nullable=False)
    telefone = Column(String(50), index=True)
    data_nascimento = Column(DateTime)
    sexo = Column(String(10))  # M, F, O
    endereco = Column(Text)
    foto_url = Column(Text)
    
    # Dados nutricionais
    objetivo = Column(String(100))  # emagrecimento, hipertrofia, etc
    altura_cm = Column(Float)
    peso_atual_kg = Column(Float)
    peso_meta_kg = Column(Float)
    restricoes_alimentares = Column(JSON, default=list)  # ["lactose", "gluten"]
    alergias = Column(JSON, default=list)
    preferencias = Column(JSON, default=dict)
    
    # Status e engajamento
    status = Column(String(50), default=StatusPaciente.ATIVO.value)
    nivel_adesao = Column(String(50), default=NivelAdesao.MEDIA.value)
    kanban_status = Column(String(50), default='novo')
    dias_jornada = Column(Integer, default=0)
    
    # Configurações do app
    config_notificacoes = Column(JSON, default=dict)
    lembretes_ativos = Column(Boolean, default=True)
    
    # Observações
    observacoes = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login_at = Column(DateTime(timezone=True))
    last_checkin_at = Column(DateTime(timezone=True))
    
    # Relationships
    nutricionista = relationship("Nutricionista", back_populates="pacientes")
    checkins = relationship("CheckIn", back_populates="paciente", cascade="all, delete-orphan", order_by="desc(CheckIn.created_at)")
    refeicoes = relationship("Refeicao", back_populates="paciente", cascade="all, delete-orphan", order_by="desc(Refeicao.created_at)")
    metas = relationship("Meta", back_populates="paciente", cascade="all, delete-orphan")
    consultas = relationship("Consulta", back_populates="paciente", cascade="all, delete-orphan")
    agendamentos = relationship("Agendamento", back_populates="paciente")
    chat_messages = relationship("ChatMessage", back_populates="paciente", cascade="all, delete-orphan", order_by="desc(ChatMessage.created_at)")
    planos_alimentares = relationship("PlanoAlimentar", back_populates="paciente", cascade="all, delete-orphan", order_by="desc(PlanoAlimentar.created_at)")

# ============================================
# TABELA: CHECK-INS DIÁRIOS (Mobile)
# ============================================

class CheckIn(Base):
    __tablename__ = "checkins"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paciente_id = Column(UUID(as_uuid=True), ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Data do check-in
    data = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Métricas (1-3: baixo, médio, alto)
    consistencia_plano = Column(Integer)  # Seguiu o plano?
    frequencia_refeicoes = Column(Integer)  # Quantidade de refeições
    tempo_refeicao = Column(Integer)  # Tempo dedicado às refeições
    vegetais_frutas = Column(Integer)  # Consumo de vegetais/frutas
    ingestao_liquido = Column(Integer)  # Água e líquidos
    energia_fisica = Column(Integer)  # Nível de energia
    atividade_fisica = Column(Integer)  # Realizou atividade?
    qualidade_sono = Column(Integer)  # Qualidade do sono
    confianca_jornada = Column(Integer)  # Confiança no progresso
    satisfacao_corpo = Column(Integer)  # Satisfação corporal
    
    # Dados adicionais
    comportamental = Column(JSON, default=dict)  # Dados comportamentais extras
    humor = Column(String(50))  # feliz, neutro, triste, ansioso
    notas = Column(Text)  # Observações do paciente
    
    # Análise da IA
    analise_ia = Column(JSON)  # Feedback e insights da IA
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    paciente = relationship("Paciente", back_populates="checkins")

# ============================================
# TABELA: REFEIÇÕES (Mobile)
# ============================================

class Refeicao(Base):
    __tablename__ = "refeicoes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paciente_id = Column(UUID(as_uuid=True), ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Tipo e horário
    tipo = Column(String(50), nullable=False)  # cafe, lanche_manha, almoco, lanche_tarde, jantar, ceia
    data_hora = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Imagem
    foto_base64 = Column(Text)
    foto_url = Column(Text)  # URL se armazenado externamente
    
    # Descrição manual
    descricao = Column(Text)
    
    # Análise da IA
    itens_identificados = Column(JSON, default=list)  # ["arroz", "feijão", "frango"]
    porcoes = Column(JSON, default=dict)  # {"arroz": "2 colheres", ...}
    macros = Column(JSON)  # {proteinas_g, carboidratos_g, gorduras_g, fibras_g}
    calorias_estimadas = Column(Integer)
    feedback_ia = Column(Text)
    sugestoes_ia = Column(JSON, default=list)
    alinhamento_plano = Column(String(20))  # excelente, bom, atencao
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    paciente = relationship("Paciente", back_populates="refeicoes")

# ============================================
# TABELA: METAS (Mobile + Web)
# ============================================

class Meta(Base):
    __tablename__ = "metas"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paciente_id = Column(UUID(as_uuid=True), ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False, index=True)
    nutricionista_id = Column(UUID(as_uuid=True), ForeignKey("nutricionistas.id", ondelete="SET NULL"), index=True)
    
    # Meta
    tipo = Column(String(50), nullable=False)  # comportamental, fisica, bem_estar, nutricional
    titulo = Column(String(255), nullable=False)
    descricao = Column(Text)
    
    # Valores
    meta_valor = Column(Float)
    valor_atual = Column(Float, default=0)
    unidade = Column(String(50))  # kg, %, dias, etc
    
    # Período
    periodo = Column(String(50))  # diario, semanal, mensal
    data_inicio = Column(DateTime(timezone=True))
    data_fim = Column(DateTime(timezone=True))
    
    # Status
    status = Column(String(50), default='ativa')  # ativa, concluida, pausada
    progresso_percentual = Column(Float, default=0)
    
    # Criada por
    criada_por = Column(String(50))  # nutricionista, paciente, ia
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    paciente = relationship("Paciente", back_populates="metas")

# ============================================
# TABELA: CONSULTAS (Web)
# ============================================

class Consulta(Base):
    __tablename__ = "consultas"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paciente_id = Column(UUID(as_uuid=True), ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False, index=True)
    nutricionista_id = Column(UUID(as_uuid=True), ForeignKey("nutricionistas.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Tipo e data
    tipo = Column(String(50), default=TipoConsulta.PRIMEIRA.value)
    data_consulta = Column(DateTime(timezone=True), nullable=False, index=True)
    duracao_minutos = Column(Integer, default=60)
    status = Column(String(50), default='em_andamento')
    
    # Dados da consulta
    anamnese = Column(JSON)
    avaliacao_fisica = Column(JSON)  # peso, medidas, etc
    avaliacao_emocional = Column(JSON)
    avaliacao_comportamental = Column(JSON)
    avaliacao_bem_estar = Column(JSON)
    
    # Plano e metas
    plano_alimentar_id = Column(UUID(as_uuid=True), ForeignKey("planos_alimentares.id", ondelete="SET NULL"))
    metas_definidas = Column(JSON, default=list)
    
    # Observações
    observacoes = Column(Text)
    proximos_passos = Column(JSON, default=list)
    
    # Análise da IA
    insights_ia = Column(JSON)
    recomendacoes_ia = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    paciente = relationship("Paciente", back_populates="consultas")
    nutricionista = relationship("Nutricionista", back_populates="consultas")
    plano_alimentar = relationship("PlanoAlimentar")

# ============================================
# TABELA: PLANOS ALIMENTARES
# ============================================

class PlanoAlimentar(Base):
    __tablename__ = "planos_alimentares"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paciente_id = Column(UUID(as_uuid=True), ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False, index=True)
    nutricionista_id = Column(UUID(as_uuid=True), ForeignKey("nutricionistas.id", ondelete="SET NULL"), index=True)
    
    # Info
    titulo = Column(String(255), nullable=False)
    descricao = Column(Text)
    objetivo = Column(String(100))
    
    # Dados do plano
    calorias_diarias = Column(Integer)
    macros_alvo = Column(JSON)  # {proteinas_g, carboidratos_g, gorduras_g}
    refeicoes = Column(JSON)  # Estrutura do plano de refeições
    substitucoes = Column(JSON)  # Opções de substituição
    observacoes = Column(Text)
    
    # Status
    ativo = Column(Boolean, default=True)
    data_inicio = Column(DateTime(timezone=True))
    data_fim = Column(DateTime(timezone=True))
    
    # Gerado por
    gerado_por_ia = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    paciente = relationship("Paciente", back_populates="planos_alimentares")

# ============================================
# TABELA: AGENDAMENTOS (Web)
# ============================================

class Agendamento(Base):
    __tablename__ = "agendamentos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nutricionista_id = Column(UUID(as_uuid=True), ForeignKey("nutricionistas.id", ondelete="CASCADE"), nullable=False, index=True)
    paciente_id = Column(UUID(as_uuid=True), ForeignKey("pacientes.id", ondelete="SET NULL"), index=True)
    
    # Dados
    titulo = Column(String(255), nullable=False)
    data_hora = Column(DateTime(timezone=True), nullable=False, index=True)
    duracao_minutos = Column(Integer, default=60)
    tipo = Column(String(50), default='consulta')  # consulta, retorno, avaliacao
    
    # Status
    status = Column(String(50), default=StatusAgendamento.AGENDADO.value)
    
    # Observações
    observacoes = Column(Text)
    link_videochamada = Column(Text)
    
    # Notificações
    lembrete_enviado = Column(Boolean, default=False)
    confirmacao_paciente = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    nutricionista = relationship("Nutricionista", back_populates="agendamentos")
    paciente = relationship("Paciente", back_populates="agendamentos")

# ============================================
# TABELA: CHAT MESSAGES (IA - Mobile)
# ============================================

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paciente_id = Column(UUID(as_uuid=True), ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Mensagem
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    
    # Contexto
    contexto = Column(JSON)  # Dados de contexto usados pela IA
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationships
    paciente = relationship("Paciente", back_populates="chat_messages")

# ============================================
# TABELA: WHATSAPP SESSIONS (Web)
# ============================================

class WhatsAppSession(Base):
    __tablename__ = "whatsapp_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nutricionista_id = Column(UUID(as_uuid=True), ForeignKey("nutricionistas.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    # Instance Evolution API
    instance_name = Column(String(255), unique=True, nullable=False, index=True)
    instance_id = Column(String(255))
    
    # Status
    status = Column(String(50), default='disconnected')  # disconnected, pending, connected
    phone = Column(String(50))
    phone_name = Column(String(255))
    
    # QR Code
    qr_code = Column(Text)
    qr_code_expires_at = Column(DateTime(timezone=True))
    
    # Timestamps
    last_connection_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    nutricionista = relationship("Nutricionista", back_populates="whatsapp_session")

# ============================================
# TABELA: STATUS PERSONALIZADOS (Web)
# ============================================

class StatusPersonalizado(Base):
    __tablename__ = "status_personalizados"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nutricionista_id = Column(UUID(as_uuid=True), ForeignKey("nutricionistas.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Dados
    nome = Column(String(100), nullable=False)
    cor = Column(String(7), default='#6B2FFF')
    icone = Column(String(50))
    ordem = Column(Integer, default=0)
    ativo = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    nutricionista = relationship("Nutricionista", back_populates="status_personalizados")

# ============================================
# TABELA: CONVERSAS (WhatsApp - Web)
# ============================================

class Conversa(Base):
    __tablename__ = "conversas"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nutricionista_id = Column(UUID(as_uuid=True), ForeignKey("nutricionistas.id", ondelete="CASCADE"), nullable=False, index=True)
    paciente_id = Column(UUID(as_uuid=True), ForeignKey("pacientes.id", ondelete="SET NULL"), index=True)
    
    # Dados do contato
    telefone = Column(String(50), nullable=False, index=True)
    nome_contato = Column(String(255))
    foto_contato = Column(Text)
    
    # Status e marcação
    status_personalizado = Column(String(100), index=True)
    marcacao = Column(String(100), index=True)
    
    # Observações da conversa
    observacoes = Column(Text)
    
    # Mensagens
    unread_count = Column(Integer, default=0)
    last_message_at = Column(DateTime(timezone=True), index=True)
    last_message_preview = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    nutricionista = relationship("Nutricionista")
    paciente = relationship("Paciente")
    mensagens = relationship("Mensagem", back_populates="conversa", cascade="all, delete-orphan", order_by="desc(Mensagem.created_at)")

# ============================================
# TABELA: MENSAGENS (WhatsApp - Web)
# ============================================

class Mensagem(Base):
    __tablename__ = "mensagens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversa_id = Column(UUID(as_uuid=True), ForeignKey("conversas.id", ondelete="CASCADE"), nullable=False, index=True)
    nutricionista_id = Column(UUID(as_uuid=True), ForeignKey("nutricionistas.id", ondelete="CASCADE"), nullable=False, index=True)
    paciente_id = Column(UUID(as_uuid=True), ForeignKey("pacientes.id", ondelete="SET NULL"), index=True)
    
    # Conteúdo
    remetente = Column(String(50), nullable=False)  # paciente, nutricionista
    conteudo = Column(Text, nullable=False)
    tipo = Column(String(50), default='texto')  # texto, imagem, audio, video, documento
    midia_url = Column(Text)
    
    # WhatsApp
    whatsapp_id = Column(String(255), index=True)
    whatsapp_timestamp = Column(DateTime(timezone=True))
    
    # Status
    lida = Column(Boolean, default=False)
    lida_em = Column(DateTime(timezone=True))
    
    # Marcação individual da mensagem
    marcacao = Column(String(100), index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationships
    conversa = relationship("Conversa", back_populates="mensagens")
    paciente = relationship("Paciente")

# ============================================
# TABELA: HISTÓRICO DE IA (Logs e memória)
# ============================================

class IAHistorico(Base):
    __tablename__ = "ia_historico"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Contexto
    paciente_id = Column(UUID(as_uuid=True), ForeignKey("pacientes.id", ondelete="CASCADE"), index=True)
    nutricionista_id = Column(UUID(as_uuid=True), ForeignKey("nutricionistas.id", ondelete="SET NULL"), index=True)
    
    # Tipo de interação
    tipo = Column(String(50), nullable=False)  # analise_refeicao, chat, checkin_analysis, consulta_insight
    
    # Dados
    input_data = Column(JSON)
    output_data = Column(JSON)
    modelo_usado = Column(String(100))
    tokens_usados = Column(Integer)
    tempo_resposta_ms = Column(Integer)
    
    # Status
    sucesso = Column(Boolean, default=True)
    erro = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

