# config.py
import os
from dotenv import load_dotenv
import sqlalchemy
from sqlalchemy.orm import sessionmaker, declarative_base
import spacy
import google.generativeai as genai

# Carrega as variáveis do arquivo .env para o ambiente
load_dotenv()

# --- Configurações de Aplicação e Segurança ---
# Lidas do ambiente e convertidas para os tipos corretos aqui.
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Inicialização da Conexão com o DB (COM ORM) ---
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

# --- Inicialização de Serviços Externos (IA e NLP) ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
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