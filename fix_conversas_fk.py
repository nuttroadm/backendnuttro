"""
Script para corrigir a foreign key constraint da tabela conversas
Remove a constraint antiga que aponta para 'usuarios' e cria nova apontando para 'nutricionistas'
"""

import asyncio
import os
from dotenv import load_dotenv
import asyncpg

async def fix_conversas_fk():
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
        
        # Verificar se a constraint antiga existe
        constraint_check = await conn.fetch("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'conversas' 
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name LIKE '%nutricionista%';
        """)
        
        print(f"Constraints encontradas: {[c['constraint_name'] for c in constraint_check]}")
        
        # Remover todas as constraints de foreign key relacionadas a nutricionista_id
        constraints_to_drop = await conn.fetch("""
            SELECT tc.constraint_name 
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_name = 'conversas' 
            AND tc.constraint_type = 'FOREIGN KEY'
            AND kcu.column_name = 'nutricionista_id';
        """)
        
        for constraint in constraints_to_drop:
            constraint_name = constraint['constraint_name']
            print(f"Removendo constraint: {constraint_name}")
            await conn.execute(f"ALTER TABLE conversas DROP CONSTRAINT IF EXISTS {constraint_name};")
        
        # Verificar se a tabela nutricionistas existe
        table_check = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name = 'nutricionistas';
        """)
        
        if not table_check:
            print("⚠️ Tabela 'nutricionistas' não existe! Execute a migração completa primeiro.")
            return
        
        # Buscar o primeiro nutricionista (admin) para usar como referência
        admin_nutricionista = await conn.fetchrow("""
            SELECT id FROM nutricionistas ORDER BY created_at ASC LIMIT 1;
        """)
        
        if not admin_nutricionista:
            print("⚠️ Nenhum nutricionista encontrado! Crie um nutricionista primeiro.")
            return
        
        admin_id = admin_nutricionista['id']
        print(f"✅ Nutricionista admin encontrado: {admin_id}")
        
        # Verificar conversas com nutricionista_id inválido
        invalid_conversas = await conn.fetch("""
            SELECT id, nutricionista_id 
            FROM conversas 
            WHERE nutricionista_id NOT IN (SELECT id FROM nutricionistas);
        """)
        
        if invalid_conversas:
            print(f"⚠️ Encontradas {len(invalid_conversas)} conversas com nutricionista_id inválido")
            print("Atualizando para apontar para o nutricionista admin...")
            
            # Atualizar todas as conversas inválidas para apontar para o admin
            await conn.execute("""
                UPDATE conversas 
                SET nutricionista_id = $1
                WHERE nutricionista_id NOT IN (SELECT id FROM nutricionistas);
            """, admin_id)
            
            print(f"✅ {len(invalid_conversas)} conversas atualizadas")
        
        # Criar nova constraint apontando para nutricionistas
        print("Criando nova constraint apontando para 'nutricionistas'...")
        await conn.execute("""
            ALTER TABLE conversas
            ADD CONSTRAINT conversas_nutricionista_id_fkey
            FOREIGN KEY (nutricionista_id)
            REFERENCES nutricionistas(id)
            ON DELETE CASCADE;
        """)
        
        print("✅ Constraint corrigida com sucesso!")
        
        # Verificar se funcionou
        final_check = await conn.fetch("""
            SELECT tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_name = 'conversas' 
            AND tc.constraint_type = 'FOREIGN KEY'
            AND kcu.column_name = 'nutricionista_id';
        """)
        
        print(f"Constraints finais: {[c['constraint_name'] for c in final_check]}")
        
    except Exception as e:
        print(f"Erro ao corrigir constraint: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_conversas_fk())

