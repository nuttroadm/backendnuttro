"""
Script para adicionar a coluna duracao_minutos na tabela consultas
"""

import asyncio
import os
from dotenv import load_dotenv
import asyncpg

async def add_duracao_minutos():
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
        
        # Verificar se a coluna já existe
        column_check = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'consultas' 
            AND column_name = 'duracao_minutos';
        """)
        
        if column_check:
            print("✓ Coluna 'duracao_minutos' já existe na tabela 'consultas'")
            return
        
        # Adicionar coluna
        await conn.execute("""
            ALTER TABLE consultas
            ADD COLUMN duracao_minutos INTEGER DEFAULT 60;
        """)
        
        print("✓ Coluna 'duracao_minutos' adicionada com sucesso na tabela 'consultas'")
        
    except Exception as e:
        print(f"Erro ao adicionar coluna: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            await conn.close()

if __name__ == "__main__":
    asyncio.run(add_duracao_minutos())

