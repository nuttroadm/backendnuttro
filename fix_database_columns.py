"""
Script para adicionar colunas faltantes nas tabelas
"""

import asyncio
import os
from dotenv import load_dotenv
import asyncpg

async def fix_database_columns():
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL não configurada no .env")
        return

    # asyncpg espera 'postgresql://' ou 'postgres://'
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = None
    try:
        conn = await asyncpg.connect(database_url)
        
        # 1. Adicionar duracao_minutos em consultas se não existir
        column_check = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'consultas' 
            AND column_name = 'duracao_minutos';
        """)
        
        if not column_check:
            print("Adicionando coluna 'duracao_minutos' em 'consultas'...")
            await conn.execute("""
                ALTER TABLE consultas
                ADD COLUMN duracao_minutos INTEGER DEFAULT 60;
            """)
            print("✓ Coluna 'duracao_minutos' adicionada em 'consultas'")
        else:
            print("✓ Coluna 'duracao_minutos' já existe em 'consultas'")
        
        # 2. Adicionar plano_alimentar_id em consultas se não existir
        column_check = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'consultas' 
            AND column_name = 'plano_alimentar_id';
        """)
        
        if not column_check:
            print("Adicionando coluna 'plano_alimentar_id' em 'consultas'...")
            await conn.execute("""
                ALTER TABLE consultas
                ADD COLUMN plano_alimentar_id UUID;
            """)
            print("✓ Coluna 'plano_alimentar_id' adicionada em 'consultas'")
        else:
            print("✓ Coluna 'plano_alimentar_id' já existe em 'consultas'")
        
        # 3. Adicionar link_videochamada em agendamentos se não existir
        column_check = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'agendamentos' 
            AND column_name = 'link_videochamada';
        """)
        
        if not column_check:
            print("Adicionando coluna 'link_videochamada' em 'agendamentos'...")
            await conn.execute("""
                ALTER TABLE agendamentos
                ADD COLUMN link_videochamada TEXT;
            """)
            print("✓ Coluna 'link_videochamada' adicionada em 'agendamentos'")
        else:
            print("✓ Coluna 'link_videochamada' já existe em 'agendamentos'")
        
        print("\n✅ Todas as colunas verificadas/criadas com sucesso!")
        
    except Exception as e:
        print(f"Erro ao corrigir colunas: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_database_columns())

