"""
Script para adicionar colunas faltantes nas tabelas consultas e agendamentos
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/nuttro")

async def fix_missing_columns():
    # Remover o prefixo asyncpg se presente
    db_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    
    conn = await asyncpg.connect(db_url)
    try:
        print("Verificando e adicionando colunas faltantes...")
        
        # Verificar e adicionar observacoes em consultas
        check_obs = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='consultas' AND column_name='observacoes';
        """
        exists_obs = await conn.fetchval(check_obs)
        
        if not exists_obs:
            await conn.execute("""
                ALTER TABLE consultas 
                ADD COLUMN observacoes TEXT;
            """)
            print("✓ Coluna observacoes adicionada em consultas")
        else:
            print("✓ Coluna observacoes já existe em consultas")
        
        # Verificar e adicionar lembrete_enviado em agendamentos
        check_lembrete = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='agendamentos' AND column_name='lembrete_enviado';
        """
        exists_lembrete = await conn.fetchval(check_lembrete)
        
        if not exists_lembrete:
            await conn.execute("""
                ALTER TABLE agendamentos 
                ADD COLUMN lembrete_enviado BOOLEAN DEFAULT FALSE;
            """)
            print("✓ Coluna lembrete_enviado adicionada em agendamentos")
        else:
            print("✓ Coluna lembrete_enviado já existe em agendamentos")
        
        # Verificar e adicionar confirmacao_paciente em agendamentos
        check_confirmacao = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='agendamentos' AND column_name='confirmacao_paciente';
        """
        exists_confirmacao = await conn.fetchval(check_confirmacao)
        
        if not exists_confirmacao:
            await conn.execute("""
                ALTER TABLE agendamentos 
                ADD COLUMN confirmacao_paciente BOOLEAN DEFAULT FALSE;
            """)
            print("✓ Coluna confirmacao_paciente adicionada em agendamentos")
        else:
            print("✓ Coluna confirmacao_paciente já existe em agendamentos")
        
        # Verificar e adicionar proximos_passos em consultas
        check_proximos = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='consultas' AND column_name='proximos_passos';
        """
        exists_proximos = await conn.fetchval(check_proximos)
        
        if not exists_proximos:
            await conn.execute("""
                ALTER TABLE consultas 
                ADD COLUMN proximos_passos JSONB DEFAULT '[]'::jsonb;
            """)
            print("✓ Coluna proximos_passos adicionada em consultas")
        else:
            print("✓ Coluna proximos_passos já existe em consultas")
        
        # Verificar e adicionar insights_ia em consultas
        check_insights = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='consultas' AND column_name='insights_ia';
        """
        exists_insights = await conn.fetchval(check_insights)
        
        if not exists_insights:
            await conn.execute("""
                ALTER TABLE consultas 
                ADD COLUMN insights_ia JSONB;
            """)
            print("✓ Coluna insights_ia adicionada em consultas")
        else:
            print("✓ Coluna insights_ia já existe em consultas")
        
        # Verificar e adicionar recomendacoes_ia em consultas
        check_recomendacoes = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='consultas' AND column_name='recomendacoes_ia';
        """
        exists_recomendacoes = await conn.fetchval(check_recomendacoes)
        
        if not exists_recomendacoes:
            await conn.execute("""
                ALTER TABLE consultas 
                ADD COLUMN recomendacoes_ia JSONB;
            """)
            print("✓ Coluna recomendacoes_ia adicionada em consultas")
        else:
            print("✓ Coluna recomendacoes_ia já existe em consultas")
        
        print("\n✅ Todas as colunas foram verificadas e adicionadas!")
        
    except Exception as e:
        print(f"❌ Erro ao adicionar colunas: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_missing_columns())

