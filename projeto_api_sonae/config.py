"""
Configuração de ambiente, segurança, banco de dados e serviços externos.

Seções:
- Imports
- .env (carregamento de variáveis)
- Configurações de aplicação/segurança
- Banco de Dados (ORM)
- Serviços Externos (Gemini / SpaCy)
"""

# ======================================================================================
# Imports
# ======================================================================================

import os
from dotenv import load_dotenv
import sqlalchemy
from sqlalchemy.orm import sessionmaker, declarative_base
import spacy
import google.generativeai as genai

# ======================================================================================
# .env — Carregamento de variáveis de ambiente
# ======================================================================================
# Observação: não altera como as variáveis são lidas; apenas documenta.
load_dotenv()

# ======================================================================================
# Configurações de Aplicação e Segurança (mantidas)
# ======================================================================================
# Lidas do ambiente e convertidas para os tipos corretos aqui.
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# ======================================================================================
# Banco de Dados — Inicialização da conexão ORM (mantido)
# ======================================================================================
# Notas:
# - Usa `DATABASE_URL` do .env.
# - Mantemos prints e fallbacks (engine=None, Base=object) exatamente como no original.
try:
    engine = sqlalchemy.create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    with engine.connect() as conn:
        print("Conexão com o Banco de Dados MySQL local estabelecida com sucesso!")
except Exception as e:
    print(f"ERRO: Não foi possível conectar ao Banco de Dados MySQL: {e}")
    engine = None
    SessionLocal = None
    Base = object

# ======================================================================================
# Serviços Externos — IA (Gemini) e NLP (SpaCy) (mantido)
# ======================================================================================
# Notas:
# - Mantém exatamente a mesma forma de configuração e tratamento de erro.
# - Em caso de problema, os objetos continuam virando None.
try:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.5-pro')
    gemini_generation_config = genai.types.GenerationConfig(temperature=0.0)
    print("Configuração da API Gemini carregada com sucesso!")
except Exception as e:
    print(f"ERRO AO CONFIGURAR API GEMINI: {e}")
    gemini_model = None
    gemini_generation_config = None

try:
    nlp = spacy.load("pt_core_news_md")
    print("Modelo de NLP (SpaCy) carregado com sucesso!")
except OSError:
    print("ERRO: Modelo 'pt_core_news_md' do SpaCy não encontrado.")
    print("Rode: python -m spacy download pt_core_news_md")
    nlp = None