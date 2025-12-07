"""
Script de migração para adicionar colunas do Backend Solo
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:AoLcSmiQwJYUHltrLzhl@orderlymanatee-postgres.cloudfy.live:8856/db')

# Remover asyncpg prefix se existir
if '+asyncpg' in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace('+asyncpg', '')

async def migrate():
    print("🔄 Conectando ao banco de dados...")
    conn = await asyncpg.connect(DATABASE_URL)
    
    migrations = [
        # Nutricionistas (nova tabela)
        """
        CREATE TABLE IF NOT EXISTS nutricionistas (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email VARCHAR(255) UNIQUE NOT NULL,
            nome VARCHAR(255) NOT NULL,
            senha_hash VARCHAR(255),
            crn VARCHAR(20) UNIQUE,
            especialidades JSONB DEFAULT '[]',
            telefone VARCHAR(50),
            foto_url TEXT,
            bio TEXT,
            google_id VARCHAR(255),
            ativo BOOLEAN DEFAULT true,
            plano VARCHAR(50) DEFAULT 'free',
            config_notificacoes JSONB DEFAULT '{}',
            config_ia JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            last_login_at TIMESTAMPTZ
        )
        """,
        
        # Colunas extras em pacientes
        "ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS cpf VARCHAR(11) UNIQUE",
        "ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS senha_hash VARCHAR(255)",
        "ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS sexo VARCHAR(10)",
        "ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS altura_cm FLOAT",
        "ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS peso_atual_kg FLOAT",
        "ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS peso_meta_kg FLOAT",
        "ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS restricoes_alimentares JSONB DEFAULT '[]'",
        "ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS alergias JSONB DEFAULT '[]'",
        "ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS preferencias JSONB DEFAULT '{}'",
        "ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS dias_jornada INTEGER DEFAULT 0",
        "ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS config_notificacoes JSONB DEFAULT '{}'",
        "ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS lembretes_ativos BOOLEAN DEFAULT true",
        "ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ",
        "ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS last_checkin_at TIMESTAMPTZ",
        
        # Check-ins
        """
        CREATE TABLE IF NOT EXISTS checkins (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
            data TIMESTAMPTZ NOT NULL,
            consistencia_plano INTEGER,
            frequencia_refeicoes INTEGER,
            tempo_refeicao INTEGER,
            vegetais_frutas INTEGER,
            ingestao_liquido INTEGER,
            energia_fisica INTEGER,
            atividade_fisica INTEGER,
            qualidade_sono INTEGER,
            confianca_jornada INTEGER,
            satisfacao_corpo INTEGER,
            comportamental JSONB DEFAULT '{}',
            humor VARCHAR(50),
            notas TEXT,
            analise_ia JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        
        # Refeições
        """
        CREATE TABLE IF NOT EXISTS refeicoes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
            tipo VARCHAR(50) NOT NULL,
            data_hora TIMESTAMPTZ NOT NULL,
            foto_base64 TEXT,
            foto_url TEXT,
            descricao TEXT,
            itens_identificados JSONB DEFAULT '[]',
            porcoes JSONB DEFAULT '{}',
            macros JSONB,
            calorias_estimadas INTEGER,
            feedback_ia TEXT,
            sugestoes_ia JSONB DEFAULT '[]',
            alinhamento_plano VARCHAR(20),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        
        # Metas
        """
        CREATE TABLE IF NOT EXISTS metas (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
            nutricionista_id UUID REFERENCES nutricionistas(id) ON DELETE SET NULL,
            tipo VARCHAR(50) NOT NULL,
            titulo VARCHAR(255) NOT NULL,
            descricao TEXT,
            meta_valor FLOAT,
            valor_atual FLOAT DEFAULT 0,
            unidade VARCHAR(50),
            periodo VARCHAR(50),
            data_inicio TIMESTAMPTZ,
            data_fim TIMESTAMPTZ,
            status VARCHAR(50) DEFAULT 'ativa',
            progresso_percentual FLOAT DEFAULT 0,
            criada_por VARCHAR(50),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        
        # Planos Alimentares
        """
        CREATE TABLE IF NOT EXISTS planos_alimentares (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
            nutricionista_id UUID REFERENCES nutricionistas(id) ON DELETE SET NULL,
            titulo VARCHAR(255) NOT NULL,
            descricao TEXT,
            objetivo VARCHAR(100),
            calorias_diarias INTEGER,
            macros_alvo JSONB,
            refeicoes JSONB,
            substitucoes JSONB,
            observacoes TEXT,
            ativo BOOLEAN DEFAULT true,
            data_inicio TIMESTAMPTZ,
            data_fim TIMESTAMPTZ,
            gerado_por_ia BOOLEAN DEFAULT false,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        
        # Chat Messages
        """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            contexto JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        
        # IA Histórico
        """
        CREATE TABLE IF NOT EXISTS ia_historico (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            paciente_id UUID REFERENCES pacientes(id) ON DELETE CASCADE,
            nutricionista_id UUID REFERENCES nutricionistas(id) ON DELETE SET NULL,
            tipo VARCHAR(50) NOT NULL,
            input_data JSONB,
            output_data JSONB,
            modelo_usado VARCHAR(100),
            tokens_usados INTEGER,
            tempo_resposta_ms INTEGER,
            sucesso BOOLEAN DEFAULT true,
            erro TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        
        # Indices
        "CREATE INDEX IF NOT EXISTS idx_checkins_paciente ON checkins(paciente_id)",
        "CREATE INDEX IF NOT EXISTS idx_refeicoes_paciente ON refeicoes(paciente_id)",
        "CREATE INDEX IF NOT EXISTS idx_metas_paciente ON metas(paciente_id)",
        "CREATE INDEX IF NOT EXISTS idx_chat_paciente ON chat_messages(paciente_id)",
        "CREATE INDEX IF NOT EXISTS idx_pacientes_cpf ON pacientes(cpf)",
    ]
    
    for sql in migrations:
        try:
            await conn.execute(sql)
            print(f"✅ Executado: {sql[:60]}...")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                print(f"ℹ️ Já existe: {sql[:60]}...")
            else:
                print(f"⚠️ Aviso: {str(e)[:100]}")
    
    await conn.close()
    print("\n✅ Migração concluída!")

if __name__ == "__main__":
    asyncio.run(migrate())

