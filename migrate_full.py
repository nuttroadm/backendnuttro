"""
Script para migrar/recriar tabelas no banco de dados
Resolve problemas de foreign keys
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:AoLcSmiQwJYUHltrLzhl@orderlymanatee-postgres.cloudfy.live:8856/db")

# Remover prefixo asyncpg para usar com asyncpg diretamente
DB_URL = DATABASE_URL.replace("+asyncpg", "")

async def run_migration():
    print("🔄 Conectando ao banco de dados...")
    conn = await asyncpg.connect(DB_URL)
    
    try:
        # Verificar se admin existe na tabela nutricionistas
        admin = await conn.fetchrow("""
            SELECT id, email FROM nutricionistas WHERE email = 'admin@nuttro.com';
        """)
        
        if admin:
            admin_id = admin['id']
            print(f"✅ Admin existe: {admin_id}")
        else:
            print("⚠️ Admin não existe - criando...")
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            senha_hash = pwd_context.hash("admin123")
            
            admin_id = await conn.fetchval("""
                INSERT INTO nutricionistas (email, nome, senha_hash, plano, ativo)
                VALUES ('admin@nuttro.com', 'Administrador', $1, 'enterprise', TRUE)
                RETURNING id;
            """, senha_hash)
            print(f"✅ Admin criado: {admin_id}")
        
        # Remover FK antiga
        print("\n🔧 Removendo FK antiga...")
        await conn.execute("""
            ALTER TABLE pacientes DROP CONSTRAINT IF EXISTS pacientes_nutricionista_id_fkey;
        """)
        print("✅ FK removida")
        
        # Atualizar pacientes com nutricionista_id inválido
        print("\n🔧 Atualizando pacientes com nutricionista_id inválido...")
        updated = await conn.execute(f"""
            UPDATE pacientes 
            SET nutricionista_id = '{admin_id}'
            WHERE nutricionista_id NOT IN (SELECT id FROM nutricionistas);
        """)
        print(f"✅ Pacientes atualizados: {updated}")
        
        # Adicionar FK correta para nutricionistas
        print("\n🔧 Adicionando FK correta para nutricionistas...")
        await conn.execute("""
            ALTER TABLE pacientes 
            ADD CONSTRAINT pacientes_nutricionista_id_fkey 
            FOREIGN KEY (nutricionista_id) REFERENCES nutricionistas(id) ON DELETE CASCADE;
        """)
        print("✅ FK adicionada com sucesso")
        
        # Verificar outras FKs que podem estar referenciando 'usuarios'
        print("\n📋 Verificando outras constraints...")
        
        tables_to_check = ['agendamentos', 'consultas', 'status_personalizados', 'whatsapp_sessions']
        
        for table in tables_to_check:
            try:
                constraints = await conn.fetch(f"""
                    SELECT conname, confrelid::regclass AS referenced_table
                    FROM pg_constraint 
                    WHERE conrelid = '{table}'::regclass 
                    AND contype = 'f';
                """)
                
                for c in constraints:
                    if 'usuarios' in str(c['referenced_table']):
                        print(f"  ⚠️ {table}: FK {c['conname']} -> usuarios (precisa corrigir)")
                        await conn.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {c['conname']};")
                        
                        # Atualizar nutricionista_id para o admin
                        await conn.execute(f"""
                            UPDATE {table} 
                            SET nutricionista_id = '{admin_id}'
                            WHERE nutricionista_id NOT IN (SELECT id FROM nutricionistas);
                        """)
                        
                        # Adicionar FK correta
                        await conn.execute(f"""
                            ALTER TABLE {table} 
                            ADD CONSTRAINT {table}_nutricionista_id_fkey 
                            FOREIGN KEY (nutricionista_id) REFERENCES nutricionistas(id) ON DELETE CASCADE;
                        """)
                        print(f"  ✅ {table}: FK corrigida")
                    else:
                        print(f"  ✅ {table}: {c['conname']} -> {c['referenced_table']} (OK)")
            except Exception as e:
                print(f"  ⚠️ {table}: {e}")
        
        print("\n✅ Migração concluída!")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(run_migration())
