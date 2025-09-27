import sqlalchemy
from sqlalchemy.orm import sessionmaker, declarative_base
import spacy
import google.generativeai as genai

# --- Configurações de API e DB ---
GEMINI_API_KEY = "AIzaSyDy8A-SnXeHoXz8TdhMTFTMZyZSH_nw5gs" 
DATABASE_URL = "mysql+mysqlconnector://root:-MySQL1596@localhost:3306/mc_sonae_db"

# --- Inicialização da Conexão com o DB (COM ORM) ---
try:
    engine = sqlalchemy.create_engine(DATABASE_URL)
    
    # Criamos uma "fábrica" de sessões de DB
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Criamos uma classe Base para nossos modelos ORM
    Base = declarative_base()

    with engine.connect() as conn:
        print("Conexão com o Banco de Dados MySQL local estabelecida com sucesso!")
except Exception as e:
    print(f"ERRO: Não foi possível conectar ao Banco de Dados MySQL: {e}")
    exit()

try:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.5-pro')
    gemini_generation_config = genai.types.GenerationConfig(temperature=0.0)
    print("Configuração da API Gemini (Nível 3) carregada com sucesso!")
except Exception as e:
    print(f"ERRO AO CONFIGURAR API GEMINI: {e}")
    gemini_model = None
    gemini_generation_config = None

try:
    nlp = spacy.load("pt_core_news_md")
    print("Modelo de NLP (SpaCy Nível 2) carregado com sucesso!")
except OSError:
    print("ERRO: Modelo 'pt_core_news_md' do SpaCy não encontrado.")
    print("Rode: python -m spacy download pt_core_news_md")
    nlp = None