import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, Float, Date, ForeignKey, DateTime, Boolean
import os
from dotenv import load_dotenv
import datetime

# Carrega a DATABASE_URL do seu arquivo .env
print("Carregando variáveis de ambiente do .env...")
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERRO: DATABASE_URL não encontrada no arquivo .env.")
    print("Verifique se o arquivo .env existe e tem a variável DATABASE_URL.")
    exit()

print(f"Conectando ao banco de dados na nuvem (Render)...")

try:
    # Criar a conexão com o banco de dados
    engine = sqlalchemy.create_engine(
    DATABASE_URL,
    connect_args={"sslmode": "require"}
    )

    Base = declarative_base()

    # --- DEFINIÇÃO DAS TABELAS (Baseado nas queries do main.py) ---

    # Tabela 'Projetos' (baseado no /processar-relatorios/ e /projetos/lista/)
    class Projetos(Base):
        __tablename__ = 'Projetos'
        project_code = Column(String(50), primary_key=True, unique=True, index=True)
        project_name = Column(String(255))
        project_manager = Column(String(255))
        budget_total = Column(Float)

    # Tabela 'Relatorios_Sprint' (baseado no /processar-relatorios/ e /relatorio/detalhe/)
    class Relatorios_Sprint(Base):
        __tablename__ = 'Relatorios_Sprint'
        report_id = Column(Integer, primary_key=True, autoincrement=True)
        project_code_fk = Column(String(50), ForeignKey('Projetos.project_code'))
        sprint_number = Column(Integer)
        report_date = Column(DateTime, default=datetime.datetime.utcnow)
        overall_status = Column(String(100))
        executive_summary = Column(Text)
        risks_and_impediments = Column(Text)
        next_steps = Column(Text)
        cost_realized = Column(Float)
        variance_text = Column(String(255))
        financial_narrative = Column(Text)

    # Tabela 'Milestones_Historico' (baseado no /processar-relatorios/ e /relatorio/detalhe/)
    class Milestones_Historico(Base):
        __tablename__ = 'Milestones_Historico'
        milestone_history_id = Column(Integer, primary_key=True, autoincrement=True)
        report_id_fk = Column(Integer, ForeignKey('Relatorios_Sprint.report_id'))
        description = Column(Text)
        status = Column(String(100))
        date_planned = Column(Date, nullable=True) # Permite nulo
        date_actual_or_revised = Column(String(100), nullable=True) # String para flexibilidade
        slippage = Column(Boolean, default=False) # Identificado no endpoint /relatorio/detalhe/

    # --- FIM DAS DEFINIÇÕES ---

    print("Criando todas as tabelas no banco de dados...")

    # Comando para criar as tabelas
    Base.metadata.create_all(engine)

    print("\nSUCESSO!")
    print("Tabelas 'Projetos', 'Relatorios_Sprint' e 'Milestones_Historico' criadas com sucesso no banco de dados do Render.")

except Exception as e:
    print(f"\n--- ERRO ---")
    print(f"Não foi possível conectar ou criar as tabelas: {e}")
    print("\nPossíveis causas:")
    print("1. A DATABASE_URL no seu .env está incorreta (verifique usuário, senha, host).")
    print("2. A biblioteca 'psycopg2-binary' não está instalada (Rode: pip install psycopg2-binary)")
    print("3. O banco de dados no Render não está 'Available'.")