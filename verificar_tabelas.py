import sqlalchemy
import os
from dotenv import load_dotenv

print("Carregando variáveis de ambiente...")
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERRO: DATABASE_URL não encontrada.")
    exit()

print(f"Conectando ao banco de dados: {DATABASE_URL.split('@')[-1]}...")

try:
    engine = sqlalchemy.create_engine(DATABASE_URL)
    with engine.connect() as connection:
        print("Conexão bem-sucedida!")

        # Usar o "Inspector" do SQLAlchemy para listar tabelas
        inspector = sqlalchemy.inspect(engine)
        table_names = inspector.get_table_names()

        print("\n--- TABELAS ENCONTRADAS NO BANCO DE DADOS ---")
        if not table_names:
            print(">>> NENHUMA TABELA ENCONTRADA. <<<")
        else:
            for name in table_names:
                print(f"  - {name}")
        print("-------------------------------------------\n")
        print("Verificação concluída.")

except Exception as e:
    print(f"ERRO ao conectar ou inspecionar: {e}")