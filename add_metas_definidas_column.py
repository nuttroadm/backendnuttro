"""
Script para adicionar a coluna metas_definidas na tabela consultas
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/nuttro")

async def add_metas_definidas_column():
    # Remover o prefixo asyncpg se presente
    db_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    
    conn = await asyncpg.connect(db_url)
    try:
        # Verificar se a coluna já existe
        check_query = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='consultas' AND column_name='metas_definidas';
        """
        exists = await conn.fetchval(check_query)
        
        if exists:
            print("Coluna metas_definidas já existe!")
            return
        
        # Adicionar a coluna
        await conn.execute("""
            ALTER TABLE consultas 
            ADD COLUMN IF NOT EXISTS metas_definidas JSONB DEFAULT '[]'::jsonb;
        """)
        
        print("Coluna metas_definidas adicionada com sucesso!")
        
    except Exception as e:
        print(f"Erro ao adicionar coluna: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(add_metas_definidas_column())

