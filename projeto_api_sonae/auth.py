"""
Módulo de Autenticação e Autorização (FastAPI)

Seções:
- Fluxo: /token (login) emite JWT; dependências validam e extraem usuário
- Método 'solicitar_permissao' protege rotas por permissão
- JWT decode, injeção de dependência, verificação de permissão
"""

# ======================================================================================
# Imports
# ======================================================================================

from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Annotated
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from datetime import timedelta

# Imports de módulos locais
from . import models, config, services
from .services import DatabaseRepository  # Para tipagem
from . import main  # Acessa instâncias globais inicializadas em main

# ======================================================================================
# Configurações e OAuth2
# ======================================================================================
# Secret/algoritmo definidos em config
SECRET_KEY = config.SECRET_KEY
ALGORITHM = config.ALGORITHM

# OAuth2 com fluxo password (tokenUrl deve coincidir com o endpoint /token)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Router local deste módulo
auth_router_description = "Endpoints e dependências de autenticação/autorizações"
router = APIRouter()

# ======================================================================================
# DEPENDÊNCIAS (Factories de Injeção)
# ======================================================================================

def get_db():
    """Fornece uma sessão de DB por requisição (abre/fecha).
    Uso: Depend(get_db) -> Session.
    """
    db = config.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_auth_service() -> services.AuthService:
    """Retorna a instância global de AuthService criada em main.
    Importante para centralizar política de senha/JWT.
    """
    return main.auth_service


def get_repository(db: Annotated[Session, Depends(get_db)]) -> DatabaseRepository:
    """Retorna o repositório global (padrão Unit of Work/Repository).
    Obs.: Mantém compatibilidade com o restante do projeto.
    """
    return main.repository

# ======================================================================================
# ENDPOINT DE LOGIN (/token)
# ======================================================================================
@router.post("/token", response_model=models.Token)
async def login_para_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    repository: Annotated[DatabaseRepository, Depends(get_repository)],
    auth_service: Annotated[services.AuthService, Depends(get_auth_service)],
):
    """Autentica usuário e retorna **access_token** (JWT Bearer).

    - Valida credenciais via `repository` + `auth_service`.
    - Em caso de falha, retorna 401 com `WWW-Authenticate: Bearer`.
    - Em sucesso, assina um JWT contendo `sub = user.email` com expiração
      definida em `config.ACCESS_TOKEN_EXPIRE_MINUTES`.
    """
    user = repository.get_usuario_por_email(email=form_data.username)

    if not user or not auth_service.verificar_senha(form_data.password, user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth_service.criar_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}

# ======================================================================================
# LÓGICA DE SEGURANÇA (Dependências para proteger rotas)
# ======================================================================================
async def get_usuario_atual(
    token: Annotated[str, Depends(oauth2_scheme)],
    repository: Annotated[DatabaseRepository, Depends(get_repository)],
) -> models.Usuario:
    """Decodifica o JWT do Authorization: Bearer e retorna o usuário do DB.

    - `oauth2_scheme` extrai o token do header.
    - Decodifica JWT (sub = email). Se inválido/ausente -> 401.
    - Busca usuário pelo email. Se não encontrado -> 401.
    """
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
        # Inclui expiração, assinatura inválida, token malformado, etc.
        raise credentials_exception

    user = repository.get_usuario_por_email(email=email)
    if user is None:
        raise credentials_exception
    return user


def solicitar_permissao(required_permission: str):
    """Fábrica de dependências para **autorização** por permissão específica.

    Exemplo de uso em rota protegida:
    ```python
    @router.get("/admin-only")
    async def admin_only(current_user: Annotated[models.Usuario, Depends(solicitar_permissao("ADMIN"))]):
        return {"ok": True}
    ```
    """

    async def verificar_permissao(
        # Ordem posicional mantida; Depends injeta o usuário autenticado
        current_user: Annotated[models.Usuario, Depends(get_usuario_atual)],
        repository: Annotated[DatabaseRepository, Depends(get_repository)],
    ) -> models.Usuario:
        """Valida se `required_permission` está na lista do usuário.
        Se ausente, retorna 403; caso contrário, repassa o `current_user`.
        """
        user_permissions = repository.get_permissoes_usuario(current_user.email)

        if required_permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para executar esta ação.",
            )
        return current_user

    return verificar_permissao
