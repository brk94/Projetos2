from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Annotated
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from datetime import timedelta

# Imports de módulos locais
from . import models, config, services 
from .services import DatabaseRepository # Para tipagem
from . import main # Importar para acessar as instâncias globais

# Configurações de segurança
SECRET_KEY = config.SECRET_KEY
ALGORITHM = config.ALGORITHM

# Oauth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Router Initialization ---
router = APIRouter()

# --- DEPENDÊNCIAS (Injection Factories) ---

def get_db():
    """Dependência que fornece uma sessão de DB para a requisição."""
    db = config.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_auth_service() -> services.AuthService:
    """Dependência para obter a instância global do AuthService."""
    return main.auth_service 

def get_repository(db: Annotated[Session, Depends(get_db)]) -> DatabaseRepository:
    # antes: return DatabaseRepository(session=db, ai_service=main.ai_service)
    return main.repository

# --- ENDPOINT DE LOGIN (/token) ---
@router.post("/token", response_model=models.Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    repository: Annotated[DatabaseRepository, Depends(get_repository)],
    auth_service: Annotated[services.AuthService, Depends(get_auth_service)]
):
    """
    Endpoint de login que gera o token JWT.
    """
    user = repository.get_user_by_email(email=form_data.username)
    
    if not user or not auth_service.verify_password(form_data.password, user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = auth_service.create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- LÓGICA DE SEGURANÇA (Para Proteger Rotas) ---

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    repository: Annotated[DatabaseRepository, Depends(get_repository)]
) -> models.Usuario:
    """Dependência que decodifica o token e retorna o usuário do DB."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = repository.get_user_by_email(email=email) 
    if user is None:
        raise credentials_exception
    return user

def require_permission(required_permission: str):
    """
    Fábrica de dependências que verifica se o usuário logado possui
    uma permissão específica.
    """
    # A ORDEM AQUI FOI MANTIDA, mas o aviso geralmente some ao garantir a sintaxe correta do Depends
    # Se o aviso persistir no seu ambiente VS Code/Pylance, a única solução é desativá-lo
    # localmente, pois o código está semanticamente correto para o FastAPI.
    async def permission_checker(
        # Note que a ordem posicional não tem valor padrão explícito, o Depends é injetado.
        current_user: Annotated[models.Usuario, Depends(get_current_user)],
        repository: Annotated[DatabaseRepository, Depends(get_repository)]
    ) -> models.Usuario:
        user_permissions = repository.get_user_permissions(current_user.email) 
        
        if required_permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para executar esta ação."
            )
        return current_user
        
    return permission_checker