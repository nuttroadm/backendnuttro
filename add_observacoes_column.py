"""
Script para adicionar a coluna observacoes na tabela conversas
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def add_observacoes_column():
    """Adiciona a coluna observacoes na tabela conversas se não existir"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERRO: DATABASE_URL não encontrada no .env")
        return
    
    # Conectar ao banco - remover o sufixo +asyncpg se existir
    if "+asyncpg" in database_url:
        database_url = database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(database_url)
    
    try:
        # Verificar se a coluna já existe
        check_query = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'conversas' AND column_name = 'observacoes';
        """
        result = await conn.fetch(check_query)
        
        if result:
            print("✓ Coluna 'observacoes' já existe na tabela 'conversas'")
        else:
            # Adicionar a coluna
            alter_query = """
            ALTER TABLE conversas 
            ADD COLUMN IF NOT EXISTS observacoes TEXT;
            """
            await conn.execute(alter_query)
            print("✓ Coluna 'observacoes' adicionada com sucesso na tabela 'conversas'")
        
    except Exception as e:
        print(f"ERRO ao adicionar coluna: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(add_observacoes_column())

