"""
FastAPI — API Projeto MC Sonae

Seções:
- Imports e Config
- Inicialização de Serviços (AI, ParserFactory, Repository, Auth)
- Dependências (DB e usuário do token)
- RBAC utilitários
- Perfil/Permissões & Tipos de Projeto
- Tarefas em memória (status)
- Auth: Login / Refresh / Logout
- Upload de Relatórios (protegido)
- Endpoints de Leitura (dashboard e relatórios)
- Admin: Solicitações de acesso e Usuários
- Admin: Projetos (lixeira, restore, hard delete)
- User-facing: Gerenciamento e soft delete
"""

# ======================================================================================
# Imports e Config
# ======================================================================================
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form, Depends, Body
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from typing import List, Annotated, Set, Optional
from pydantic import BaseModel
import io
import uuid
import os
from jose import jwt, JWTError

from .models import AreaNegocioEnum
from .constants import AREAS_NEGOCIO as AREAS_PADRAO  # ["TI", "Retalho", "RH", "Marketing"]

# Nossos módulos locais
from . import config
from . import models
from . import services
from .config import SessionLocal
from .models import (
    AccessRequestIn,
    SolicitacaoOut,
    DecisaoIn,
    UsuarioAdminOut,
    UsuarioUpdateIn,
    UsuarioPerfilOut,
)
# Segurança / Auth
from .auth import solicitar_permissao

# OAuth2 Bearer para extrair o token do header Authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Chaves/JWT param (mantidos via ENV)
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
AUTH_DEBUG = os.getenv("AUTH_DEBUG", "0") == "1"
REFRESH_TOKEN_PEPPER = os.getenv("REFRESH_TOKEN_PEPPER", "")

# Instância FastAPI
app = FastAPI(title="API Projeto MC Sonae")


# ======================================================================================
# Pydantic: Payload auxiliar
# ======================================================================================
class AcessoIn(BaseModel):
    codigo_projeto: str
    papel: str | None = None


# ======================================================================================
# Inicialização de Serviços (AI, ParserFactory, Repository, Auth)
# ======================================================================================
try:
    ai_service = services.AIService(
        nlp_model=config.nlp,
        gemini_model=config.gemini_model,
        gemini_config=config.gemini_generation_config,
    )

    # Factory de parsers — compat com fallback para `parsers.factory`
    parser_factory = services.ReportParserFactory(ai_service=ai_service) if hasattr(services, "ReportParserFactory") else None
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


# ======================================================================================
# Dependências (DB e usuário do token)
# ======================================================================================

def get_db():
    """Cria/fecha sessão de DB por requisição (usado com Depends)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_user(token: str = Depends(oauth2_scheme)) -> str:
    """Extrai e valida JWT Bearer; retorna o `sub` (e‑mail) do usuário.
    - 401 se token inválido, sem `sub` ou sem assinatura válida.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Não autorizado (token sem 'sub').")
        return sub
    except JWTError:
        raise HTTPException(status_code=401, detail="Não autorizado")


# ======================================================================================
# RBAC: Utilitários comuns
# ======================================================================================

def _get_permissoes_lower(email: str) -> Set[str]:
    perms = repository.get_permissoes_usuario(email)
    return {p.lower() for p in perms}


def _eh_admin(email: str, perms_lower: Set[str]) -> bool:
    """Admin por papel OU por poderes agregados de gestão (compat)."""
    return repository.usuario_tem_papel(email, "Administrador") or \
           {"gerenciar_usuarios", "gerenciar_papeis"}.issubset(perms_lower)


def verificar_tipos_upload_permitidos(email: str) -> List[str]:
    """
    Regras por papel para envio de relatórios:
      - requer permissão genérica: 'realizar_upload_relatorio' (senão 403).
      - Admin: todos os tipos.
      - Gestor: todos os tipos (se tiver permissão de upload).
      - Analista: apenas o **setor** do usuário (Usuarios.setor).
      - Diretor/Visualizador: sem upload por padrão.
    """
    user = repository.get_usuario_por_email(email)
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado.")

    perms_lower = _get_permissoes_lower(email)

    if "realizar_upload_relatorio" not in perms_lower:
        raise HTTPException(status_code=403, detail="Sem permissões de upload para nenhum tipo de projeto.")

    if _eh_admin(email, perms_lower):
        return list(AREAS_PADRAO)

    is_gestor       = repository.usuario_tem_papel(email, "Gestor de Projetos")
    is_analista     = repository.usuario_tem_papel(email, "Analista")
    is_diretor      = repository.usuario_tem_papel(email, "Diretor")
    is_visualizador = repository.usuario_tem_papel(email, "Visualizador")

    if is_gestor:
        return list(AREAS_PADRAO)

    if is_analista:
        setor = getattr(user, "setor", None)
        if isinstance(setor, AreaNegocioEnum):
            setor = setor.value
        if setor in AREAS_PADRAO:
            return [setor]
        raise HTTPException(status_code=403, detail="Sem setor associado para upload.")

    if is_diretor or is_visualizador:
        raise HTTPException(status_code=403, detail="Perfil sem direito de upload.")

    raise HTTPException(status_code=403, detail="Perfil sem direito de upload.")


# ======================================================================================
# Perfil/Permissões & Tipos de Projeto
# ======================================================================================
@app.get("/me/permissoes")
def minhas_permissoes(_user_email: str = Depends(require_user)):
    return repository.get_permissoes_usuario(_user_email)


@app.get("/me/perfil", response_model=UsuarioPerfilOut, tags=["me"])
def me_perfil(_user_email: str = Depends(require_user)):
    data = repository.get_perfil_usuario(_user_email)
    if not data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return data


@app.get("/projetos/tipos")
def listar_tipos_upload(_user_email: str = Depends(require_user)) -> List[str]:
    """Lista os tipos de projeto que o usuário PODE enviar (aplica RBAC)."""
    return verificar_tipos_upload_permitidos(_user_email)


# ======================================================================================
# Tarefas assíncronas (in‑mem)
# ======================================================================================
tasks = {}


def run_tarefa_save(task_id: str, parsed_data: models.ParsedReport, author_id: int | None = None):
    try:
        tasks[task_id] = {"status": "processando"}
        repository.salvar_relatorio_processado(parsed_data, author_id=author_id)
        tasks[task_id] = {"status": "concluido", "detail": "Relatório processado e salvo com sucesso."}
    except Exception as e:
        tasks[task_id] = {"status": "falhou", "detail": str(e)}


# ======================================================================================
# Auth: Login (access + refresh) / Refresh / Logout
# ======================================================================================
@app.post("/token", response_model=models.TokenPair)
async def login_por_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db=Depends(get_db)):
    email = (form_data.username or "").strip()
    user = repository.get_usuario_por_email(email=email)
    if not user:
        raise HTTPException(status_code=401, detail="Email ou senha incorretos", headers={"WWW-Authenticate": "Bearer"})

    if not auth_service.verificar_senha_ou_texto_puro(form_data.password, user.senha_hash):
        raise HTTPException(status_code=401, detail="Email ou senha incorretos", headers={"WWW-Authenticate": "Bearer"})

    # Migração transparente: se senha em texto/legado, rehash para bcrypt
    if auth_service.precisa_atualizar_senha(user.senha_hash):
        try:
            new_hash = auth_service.get_hash_senha(form_data.password)
            repository.set_senha_hash_usuario(user.email, new_hash)
        except Exception:
            pass

    access_token = auth_service.criar_access_token(data={"sub": user.email})
    refresh_plain = repository.criar_refresh_token(db, user_id=user.id_usuario)

    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_plain}


@app.post("/token/refresh", response_model=models.TokenPair)
async def refresh_access_token(payload: models.RefreshIn, db=Depends(get_db)):
    rt = repository.get_refresh_token(db, plain_token=payload.refresh_token)
    if not rt:
        raise HTTPException(status_code=401, detail="Refresh token inválido.")
    if services.AuthService.refresh_token_expirado(rt):
        repository.revogar_refresh_token_para_texto_puro(db, plain_token=payload.refresh_token)
        raise HTTPException(status_code=401, detail="Refresh token expirado.")

    email_usuario = repository.get_refresh_token_dono_email(db, plain_token=payload.refresh_token)
    if not email_usuario:
        repository.revogar_refresh_token_para_texto_puro(db, plain_token=payload.refresh_token)
        raise HTTPException(status_code=401, detail="Refresh token inválido.")

    new_access = auth_service.criar_access_token(data={"sub": email_usuario})
    new_refresh_plain = auth_service.criar_refresh_token_texto_puro()
    ok = repository.rotate_refresh_token(db, old_plain_token=payload.refresh_token, new_plain_token=new_refresh_plain)
    if not ok:
        repository.revogar_refresh_token_para_texto_puro(db, plain_token=payload.refresh_token)
        raise HTTPException(status_code=401, detail="Refresh token inválido.")

    return {"access_token": new_access, "refresh_token": new_refresh_plain, "token_type": "bearer"}


@app.post("/logout")
async def logout(
    _user_email: str = Depends(require_user),
    _body: Optional[dict] = Body(default=None)  # ignoramos qualquer RT específico; revogamos todos do usuário
):
    user = repository.get_usuario_por_email(_user_email)
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado.")

    # Purga global: apaga todos os refresh tokens deste usuário
    count = repository.revogar_todos_refresh_tokens_do_usuario(user.id_usuario)
    return {"revoked": count, "mode": "all"}


# ======================================================================================
# Upload de Relatórios
# ======================================================================================
@app.post("/processar-relatorios/")
async def processar_relatorios(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    # Aceita tanto 'project_type' quanto 'tipo_projeto' (retrocompat. com front)
    project_type: str | None = Form(None),
    tipo_projeto: str | None = Form(None),
    _user_email: str = Depends(require_user),
    # Protegido: precisa ter a permissão genérica de upload
    _perm_check: models.Usuario = Depends(solicitar_permissao("realizar_upload_relatorio")),
):
    if not files:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado.")

    chosen_type = project_type or tipo_projeto
    if not chosen_type:
        raise HTTPException(status_code=422, detail="Campo de tipo do projeto é obrigatório.")

    # Confere se o tipo é permitido para este usuário
    allowed = verificar_tipos_upload_permitidos(_user_email)
    if chosen_type not in allowed:
        raise HTTPException(status_code=403, detail="Sem permissão para enviar relatório desse tipo.")

    file = files[0]  # processa um por vez
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "pendente"}
    file_stream = io.BytesIO(await file.read())

    # Resolve o autor pelo e‑mail do token (grava em Relatorios_Sprint.id_autor_fk)
    uploader = repository.get_usuario_por_email(_user_email)
    author_id = uploader.id_usuario if uploader else None

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

        # Observação: o vínculo do gerente (id_gerente_fk) é resolvido dentro do repository
        background_tasks.add_task(run_tarefa_save, task_id, parsed_data, author_id)
        return {"status": "processamento_iniciado", "task_id": task_id, "filename": file.filename}
    except Exception as e:
        error_detail = str(e.detail) if isinstance(e, HTTPException) else str(e)
        tasks[task_id] = {"status": "falhou", "detail": f"Erro inesperado: {error_detail}"}
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=tasks[task_id]["detail"])


# ======================================================================================
# Status da tarefa
# ======================================================================================
@app.get("/tasks/status/{task_id}")
async def get_status_tarefa(
    task_id: str,
    _perm_check: models.Usuario = Depends(solicitar_permissao("realizar_upload_relatorio")),
    _user_email: str = Depends(require_user),
):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    return task


# ======================================================================================
# Endpoints de leitura (RBAC)
# ======================================================================================
@app.get("/dashboard-executivo/", response_model=models.DashboardStats)
async def get_dados_dashboard(_perm_check: models.Usuario = Depends(solicitar_permissao("view_pagina_home")),):
    return repository.get_estatisticas_dashboard()


@app.get("/projetos/lista/", response_model=List[models.ProjectListItem])
async def get_projetos_lista(_perm_check: models.Usuario = Depends(solicitar_permissao("view_pagina_home")),):
    return repository.get_lista_projetos()


@app.get("/projeto/{project_code}/lista-sprints/", response_model=List[models.SprintListItem])
async def get_sprints_do_projeto(project_code: str, _perm_check: models.Usuario = Depends(solicitar_permissao("view_pagina_dashboards")),):
    return repository.get_sprints_do_projeto(project_code)


@app.get("/relatorio/detalhe/{report_id}", response_model=models.ReportDetailResponse)
async def get_detalhe_do_relatorio(report_id: int, _perm_check: models.Usuario = Depends(solicitar_permissao("view_pagina_dashboards")),):
    data = repository.get_detalhe_do_relatorio(report_id)
    if not data:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    return data


@app.get("/projeto/{project_code}/historico-kpi/{kpi_name}", response_model=List[models.FinancialHistoryItem])
async def get_historico_kpi(project_code: str, kpi_name: str, _perm_check: models.Usuario = Depends(solicitar_permissao("view_pagina_dashboards")),):
    return repository.get_historico_kpi(project_code, kpi_name)


# ======================================================================================
# Admin: Utilitário require_admin
# ======================================================================================

def require_admin(_user_email: str = Depends(require_user)):
    perms_lower = _get_permissoes_lower(_user_email)
    if not _eh_admin(_user_email, perms_lower):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")
    user = repository.get_usuario_por_email(_user_email)
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado.")
    return user


# ======================================================================================
# Solicitação de Acesso (público) e Admin (listar/decidir/usuarios)
# ======================================================================================
@app.post("/auth/solicitar-acesso", status_code=201, tags=["auth"])
def solicitar_acesso(body: AccessRequestIn):
    try:
        repository.criar_solicitacao_acesso(
            nome=body.nome,
            email=body.email,
            senha=body.senha,
            setor=body.setor,
            justificativa=body.justificativa,
            cargo=body.cargo,
        )
        return {"message": "Solicitação registrada com sucesso."}
    except RuntimeError as re:
        raise HTTPException(status_code=409, detail=str(re))


@app.get("/admin/solicitacoes", response_model=List[SolicitacaoOut], tags=["admin"])
def admin_listar_solicitacoes(
    status: str = "aguardando",
    _admin = Depends(require_admin),
):
    return repository.listar_solicitacoes(status=status)


@app.post("/admin/solicitacoes/{id_solic}/decidir", tags=["admin"])
def admin_decidir_solicitacao(id_solic: int, body: DecisaoIn, admin = Depends(require_admin)):
    try:
        repository.decidir_solicitacao(
            id_solic=id_solic,
            admin_id=admin.id_usuario,
            decisao=body.decisao,
            motivo=body.motivo,
        )
        return {"message": "Decisão registrada."}
    except RuntimeError as re:
        raise HTTPException(status_code=409, detail=str(re))
    except Exception:
        raise HTTPException(status_code=500, detail="Falha ao decidir a solicitação.")


@app.get("/admin/usuarios", response_model=List[UsuarioAdminOut], tags=["admin"])
def admin_listar_usuarios(q: str | None = None, _admin = Depends(require_admin)):
    return repository.listar_usuarios(q=q)


@app.put("/admin/usuarios/{id_usuario}", tags=["admin"])
def admin_atualizar_usuario(id_usuario: int, body: UsuarioUpdateIn, _admin = Depends(require_admin)):
    try:
        repository.atualizar_usuario_limitado(
            id_usuario=id_usuario,
            nome=body.nome,
            setor=body.setor
        )
        return {"message": "Usuário atualizado."}
    except RuntimeError as re:
        raise HTTPException(status_code=404, detail=str(re))
    except Exception:
        raise HTTPException(status_code=500, detail="Falha ao atualizar usuário.")


@app.get("/admin/usuarios/{id_usuario}/acessos", tags=["admin"])
def admin_listar_acessos_usuario(id_usuario: int, _admin = Depends(require_admin)):
    return repository.listar_acessos_por_usuario(id_usuario=id_usuario)


@app.post("/admin/usuarios/{id_usuario}/acessos", status_code=201, tags=["admin"])
def admin_conceder_acesso_usuario(id_usuario: int, body: AcessoIn, _admin = Depends(require_admin)):
    # reaproveita o serviço que JÁ COMMITA
    return repository.garantir_acesso_projeto(
        codigo_projeto=body.codigo_projeto,
        id_usuario=id_usuario,
        papel=body.papel,
    )


@app.delete("/admin/usuarios/{id_usuario}/acessos/{codigo_projeto}", status_code=204, tags=["admin"])
def admin_revogar_acesso_usuario(id_usuario: int, codigo_projeto: str, _admin = Depends(require_admin)):
    repository.revogar_acesso_projeto(
        codigo_projeto=codigo_projeto,
        id_usuario=id_usuario,
    )
    return None


@app.get("/admin/projetos/lista", response_model=List[models.ProjectListItem], tags=["admin"])
def admin_listar_projetos(_=Depends(require_admin)):
    return repository.get_lista_projetos()


# ======================================================================================
# Admin: Soft Delete / Lixeira / Restore / Hard Delete
# ======================================================================================
@app.get("/admin/projetos/excluidos", tags=["admin"])
def listar_excluidos(admin = Depends(require_admin)):
    # RBAC garantido por Depends(require_admin)
    return repository.listar_projetos_deletados()


@app.post("/admin/projetos/{codigo}/soft-delete", tags=["admin"])
def soft_delete_projeto(
    codigo: str,
    body: dict | None = Body(None),   # {"motivo": "..."}
    admin = Depends(require_admin),
):
    motivo = (body or {}).get("motivo")
    ok = repository.soft_delete_projeto(
        codigo_projeto=codigo,
        admin_id=admin.id_usuario,
        motivo=motivo,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return {"message": "Projeto enviado para a lixeira."}


@app.post("/admin/projetos/{codigo}/restaurar", tags=["admin"])
def restore_projeto(
    codigo: str,
    admin = Depends(require_admin),
):
    ok = repository.restaurar_projeto(
        codigo_projeto=codigo,
        user_id=admin.id_usuario,   
        is_admin=True               
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return {"message": "Projeto restaurado."}


@app.delete("/admin/projetos/{codigo}", tags=["admin"])
def delete_projeto(
    codigo: str,
    admin = Depends(require_admin),
):
    ok = repository.remover_projeto_definitivo(codigo_projeto=codigo)
    if not ok:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return {"message": "Projeto excluído definitivamente."}


# ======================================================================================
# User‑facing: projetos gerenciados/visíveis e soft delete
# ======================================================================================
@app.get("/me/projetos/gerenciados", response_model=List[models.ProjectListItem])
def meus_projetos_gerenciados(_user_email: str = Depends(require_user)):
    return repository.listar_projetos_gerenciados(email=_user_email)


@app.post("/projetos/{codigo}/soft-delete")
def user_soft_delete_projeto(
    codigo: str,
    body: dict | None = Body(None),
    _user_email: str = Depends(require_user),
):
    motivo = (body or {}).get("motivo")
    if not repository.can_soft_delete_projeto(email=_user_email, codigo_projeto=codigo):
        raise HTTPException(status_code=403, detail="Sem permissão para excluir este projeto.")

    # pega id do usuário para auditoria
    user = repository.get_usuario_por_email(_user_email)
    ok = repository.soft_delete_projeto(
        codigo_projeto=codigo,
        admin_id=user.id_usuario if user else None,
        motivo=motivo,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return {"message": "Projeto enviado para a lixeira."}


@app.get("/me/projetos/visiveis", response_model=List[models.ProjectListItem])
def meus_projetos_visiveis(_user_email: str = Depends(require_user)):
    return repository.listar_projetos_visiveis(email=_user_email)


@app.get("/admin/projetos/{codigo}/acessos", tags=["admin"])
def admin_list_acessos(codigo: str, _admin = Depends(require_admin)):
    return repository.listar_acessos_por_projeto(codigo_projeto=codigo)


@app.post("/admin/projetos/{codigo}/acessos", tags=["admin"])
def admin_grant_acesso(codigo: str, id_usuario: int = Body(...), papel: str = Body("Visualizador"), _admin = Depends(require_admin)):
    repository.garantir_acesso_projeto(codigo_projeto=codigo, id_usuario=id_usuario, papel=papel)
    return {"message": "Acesso concedido."}


@app.delete("/admin/projetos/{codigo}/acessos/{id_usuario}", tags=["admin"])
def admin_revoke_acesso(codigo: str, id_usuario: int, _admin = Depends(require_admin)):
    repository.revogar_acesso_projeto(codigo_projeto=codigo, id_usuario=id_usuario)
    return {"message": "Acesso removido."}