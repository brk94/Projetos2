from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form, Depends
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from typing import List, Annotated, Iterable, Set
import io
import uuid
import os
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from .models import AreaNegocioEnum
from .constants import AREAS_NEGOCIO as AREAS_PADRAO  # ["TI", "Retalho", "RH", "Marketing"]

# Nossos módulos locais
from . import config
from . import models
from . import services
from . import constants
from .config import SessionLocal  # já existe no seu projeto

# Segurança / Auth
from .auth import require_permission  # mantém seu decorator
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
AUTH_DEBUG = os.getenv("AUTH_DEBUG", "0") == "1"

app = FastAPI(title="API Projeto MC Sonae")

# --- INICIALIZAÇÃO DOS SERVIÇOS ---
try:
    ai_service = services.AIService(
        nlp_model=config.nlp,
        gemini_model=config.gemini_model,
        gemini_config=config.gemini_generation_config,
    )
    parser_factory = services.ReportParserFactory(ai_service=ai_service) if hasattr(services, "ReportParserFactory") else None
    # Você já usa a factory do pacote parsers:
    if parser_factory is None:
        from parsers.factory import ReportParserFactory
        parser_factory = ReportParserFactory(ai_service=ai_service)

    repository = services.DatabaseRepository(
        session_factory=config.SessionLocal,
        ai_service=ai_service,
    )
    auth_service = services.AuthService()
    print("\n--- Todos os serviços (ORM) foram inicializados com sucesso! ---")
except Exception as e:
    print(f"\n--- FALHA CRÍTICA NA INICIALIZAÇÃO: {e} ---")
    raise

# --- DB session dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- User dependency (retorna o e-mail do usuário do token) ---
def require_user(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Não autorizado (token sem 'sub').")
        return sub  # e-mail
    except JWTError:
        raise HTTPException(status_code=401, detail="Não autorizado")

# =========================
# RBAC: utilitários comuns
# =========================

def _get_perms_lower(email: str) -> Set[str]:
    perms = repository.get_user_permissions(email)  # já existe no seu services.py
    return {p.lower() for p in perms}

def _is_admin(email: str, perms_lower: Set[str]) -> bool:
    # Admin por papel OU por “poderes” de gestão
    return repository.user_has_role(email, "Administrador") or \
           {"gerenciar_usuarios", "gerenciar_papeis"}.issubset(perms_lower)

def compute_allowed_upload_types(email: str) -> List[str]:
    """
    Regras por papel:
      - precisa ter 'realizar_upload_relatorio' (senão 403).
      - Admin: todos os tipos.
      - Gestor: todos os tipos (desde que tenha upload genérico).
      - Analista: apenas o setor do usuário (Usuarios.setor).
      - Diretor/Visualizador: sem upload por padrão → 403.
    """
    user = repository.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado.")

    perms_lower = _get_perms_lower(email)

    # Sem permissão genérica → 403
    if "realizar_upload_relatorio" not in perms_lower:
        raise HTTPException(status_code=403, detail="Sem permissões de upload para nenhum tipo de projeto.")

    # Admin → todos
    if _is_admin(email, perms_lower):
        return list(AREAS_PADRAO)  # ["TI","Retalho","RH","Marketing"]

    # Papel do usuário
    is_gestor       = repository.user_has_role(email, "Gestor de Projetos")
    is_analista     = repository.user_has_role(email, "Analista")
    is_diretor      = repository.user_has_role(email, "Diretor")
    is_visualizador = repository.user_has_role(email, "Visualizador")

    # Gestor com permissão de upload → todos
    if is_gestor:
        return list(AREAS_PADRAO)

    # Analista → apenas setor
    if is_analista:
        setor = getattr(user, "setor", None)
        # setor pode vir como Enum (AreaNegocioEnum) ou string; normalize para string
        if isinstance(setor, AreaNegocioEnum):
            setor = setor.value
        if setor in AREAS_PADRAO:
            return [setor]
        raise HTTPException(status_code=403, detail="Sem setor associado para upload.")

    # Diretor / Visualizador (ou quaisquer outros) → por padrão não sobem
    if is_diretor or is_visualizador:
        raise HTTPException(status_code=403, detail="Perfil sem direito de upload.")

    # Padrão conservador
    raise HTTPException(status_code=403, detail="Perfil sem direito de upload.")

# ===========================================
# API: Perfil/Permissões e Tipos de Projeto
# ===========================================

@app.get("/me/permissoes")
def minhas_permissoes(_user_email: str = Depends(require_user)):
    return repository.get_user_permissions(_user_email)

@app.get("/projetos/tipos")
def listar_tipos_upload(_user_email: str = Depends(require_user)) -> List[str]:
    """
    Lista os tipos de projeto que o usuário PODE enviar, de acordo com:
      - permissão 'realizar_upload_relatorio'
      - papel (Admin/Gestor → todos; Analista → seu setor)
    """
    return compute_allowed_upload_types(_user_email)

# ===========================
# Tarefas assíncronas (in-mem)
# ===========================
tasks = {}

def run_save_task(task_id: str, parsed_data: models.ParsedReport):
    try:
        tasks[task_id] = {"status": "processando"}
        repository.save_parsed_report(parsed_data)
        tasks[task_id] = {"status": "concluido", "detail": "Relatório processado e salvo com sucesso."}
    except Exception as e:
        tasks[task_id] = {"status": "falhou", "detail": str(e)}

# ===========================
# Auth: Login (token)
# ===========================

@app.post("/token", response_model=models.Token)
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    email = (form_data.username or "").strip()
    # ... (seus logs) ...

    user = repository.get_user_by_email(email=email)
    if not user:
        raise HTTPException(status_code=401, detail="Email ou senha incorretos", headers={"WWW-Authenticate": "Bearer"})

    # 1) Aceita bcrypt OU texto puro (para migração)
    if not auth_service.verify_password_or_plain(form_data.password, user.senha_hash):
        raise HTTPException(status_code=401, detail="Email ou senha incorretos", headers={"WWW-Authenticate": "Bearer"})

    # 2) Se estava em texto puro, migra agora para bcrypt
    if auth_service.needs_update(user.senha_hash):
        try:
            new_hash = auth_service.get_password_hash(form_data.password)
            repository.set_user_password_hash(user.email, new_hash)
            print(f"[AUTH] Hash de '{user.email}' migrado para bcrypt.")
        except Exception as e:
            print(f"[AUTH] Erro ao migrar hash: {e}")

    # 3) Gera o token normalmente
    access_token = auth_service.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

# ===================================
# Upload de Relatórios (protegido)
# ===================================

@app.post("/processar-relatorios/")
async def processar_relatorios(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    # Aceita tanto 'project_type' quanto 'tipo_projeto' (retrocompat.
    # e para casar com o front atual)
    project_type: str | None = Form(None),
    tipo_projeto: str | None = Form(None),
    _user_email: str = Depends(require_user),
    # Protegido: precisa ter a permissão genérica de upload
    _perm_check: models.Usuario = Depends(require_permission("realizar_upload_relatorio")),
):
    if not files:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado.")

    # Normaliza o tipo escolhido
    chosen_type = project_type or tipo_projeto
    if not chosen_type:
        raise HTTPException(status_code=422, detail="Campo de tipo do projeto é obrigatório.")

    # Confere se o tipo é permitido para este usuário (regra única)
    allowed = compute_allowed_upload_types(_user_email)
    if chosen_type not in allowed:
        raise HTTPException(status_code=403, detail="Sem permissão para enviar relatório desse tipo.")

    # Prepara task
    file = files[0]  # você permite múltiplos, mas processa um por vez aqui
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "pendente"}
    file_stream = io.BytesIO(await file.read())

    try:
        parser = parser_factory.get_parser(file.filename, chosen_type)
        if not parser:
            detail = f"Nenhum parser compatível encontrado para o arquivo '{file.filename}' e tipo '{chosen_type}'."
            tasks[task_id] = {"status": "falhou", "detail": detail}
            raise HTTPException(status_code=400, detail=detail)

        parsed_data = parser.parse(file_stream)
        if not parsed_data:
            detail = f"O parser não conseguiu extrair dados do arquivo '{file.filename}'."
            tasks[task_id] = {"status": "falhou", "detail": detail}
            raise HTTPException(status_code=400, detail=detail)

        background_tasks.add_task(run_save_task, task_id, parsed_data)
        return {"status": "processamento_iniciado", "task_id": task_id, "filename": file.filename}
    except Exception as e:
        error_detail = str(e.detail) if isinstance(e, HTTPException) else str(e)
        tasks[task_id] = {"status": "falhou", "detail": f"Erro inesperado: {error_detail}"}
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=tasks[task_id]["detail"])

# ===========================
# Status da tarefa (protegido)
# ===========================

@app.get("/tasks/status/{task_id}")
async def get_task_status(
    task_id: str,
    _perm_check: models.Usuario = Depends(require_permission("realizar_upload_relatorio")),
    _user_email: str = Depends(require_user),
):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    return task

# ===========================
# Endpoints de leitura (RBAC)
# ===========================

@app.get("/dashboard-executivo/", response_model=models.DashboardStats)
async def get_dashboard_data(
    _perm_check: models.Usuario = Depends(require_permission("view_pagina_home")),
):
    return repository.get_dashboard_stats()

@app.get("/projetos/lista/", response_model=List[models.ProjectListItem])
async def get_projetos_lista(
    _perm_check: models.Usuario = Depends(require_permission("view_pagina_home")),
):
    return repository.get_project_list()

@app.get("/projeto/{project_code}/lista-sprints/", response_model=List[models.SprintListItem])
async def get_sprints_do_projeto(
    project_code: str,
    _perm_check: models.Usuario = Depends(require_permission("view_pagina_dashboards")),
):
    return repository.get_sprints_do_projeto(project_code)

@app.get("/relatorio/detalhe/{report_id}", response_model=models.ReportDetailResponse)
async def get_detalhe_do_relatorio(
    report_id: int,
    _perm_check: models.Usuario = Depends(require_permission("view_pagina_dashboards")),
):
    data = repository.get_detalhe_do_relatorio(report_id)
    if not data:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    return data

@app.get("/projeto/{project_code}/historico-kpi/{kpi_name}", response_model=List[models.FinancialHistoryItem])
async def get_historico_de_kpi(
    project_code: str,
    kpi_name: str,
    _perm_check: models.Usuario = Depends(require_permission("view_pagina_dashboards")),
):
    return repository.get_kpi_history(project_code, kpi_name)