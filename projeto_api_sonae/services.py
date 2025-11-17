"""
Serviços centrais do backend: Autenticação (JWT/senhas), IA (Gemini/SpaCy)
para sumários, e Repositório ORM (CRUD, RBAC, Refresh Tokens, Dashboard).

Seções
- Imports
- Configuração de Segurança (SECRET_KEY/ALGORITHM/expirações)
- AuthService — senhas (bcrypt) e JWT (access/refresh)
- Helpers de tempo (UTC)
- AIService — geração e sanitização de resumo (Gemini)
- DatabaseRepository — acesso ao banco (ORM) + regras de negócio
    - Usuários e RBAC
    - Refresh Tokens (hash + rotate + revoke)
    - Relatórios/Dashboard
    - Solicitações de acesso
    - Soft delete e restauração de projetos
    - Acessos por projeto/usuário
"""

# ======================================================================================
# Imports
# ======================================================================================
import os
import secrets
import hashlib
import hmac
from typing import List, Optional
from datetime import datetime, timedelta, timezone

# --- Imports de Segurança e Autenticação ---
from passlib.context import CryptContext
from jose import JWTError, jwt
import bcrypt

# --- Utilidades ---
import re
import unicodedata

# --- ORM / DB ---
from . import models
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case, desc, delete
from sqlalchemy import and_

# ======================================================================================
# Config de segurança (JWT)
# ======================================================================================
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM  = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS   = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ======================================================================================
# AuthService — hash de senha e JWT
# ======================================================================================
class AuthService:
    @staticmethod
    def eh_bcrypt_hash(value: Optional[str]) -> bool:
        if not isinstance(value, str):
            return False
        return value.startswith("$2a$") or value.startswith("$2b$") or value.startswith("$2y$")

    def get_hash_senha(self, plain_password: str) -> str:
        return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()

    def verificar_senha(self, plain_password: str, hashed_password: str) -> bool:
        if not self.eh_bcrypt_hash(hashed_password):
            return False
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())

    def verificar_senha_ou_texto_puro(self, plain_password: str, stored_value: str) -> bool:
        if self.eh_bcrypt_hash(stored_value):
            return bcrypt.checkpw(plain_password.encode(), stored_value.encode())
        return hmac.compare_digest(plain_password, stored_value)

    def precisa_atualizar_senha(self, stored_value: str) -> bool:
        return not self.eh_bcrypt_hash(stored_value)

    def criar_access_token(self, data: dict, expires_delta=None) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    def criar_refresh_token_texto_puro() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def refresh_token_expirado(rt: models.RefreshToken) -> bool:
        exp = rt.data_expiracao
        if exp is None:
            return True
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp < datetime.now(timezone.utc)

# ======================================================================================
# AIService — opcional (Gemini)
# ======================================================================================
class AIService:
    def __init__(self, nlp_model, gemini_model, gemini_config):
        self.nlp = nlp_model
        self.gemini_model = gemini_model
        self.gemini_config = gemini_config
        print("AIService inicializado.")

    def _sanitizar_resumo_ptbr(self, s: str) -> str:
        if not isinstance(s, str):
            return ""
        s = unicodedata.normalize("NFC", s).replace("\u00A0", " ")
        s = re.sub(r"\s+", " ", s).strip()
        s = re.sub(
            r"R\s*\$?\s*([0-9]{1,3}(?:\.[0-9]{3})*,\s*[0-9]{2})",
            lambda m: "R$ " + m.group(1).replace(" ", ""),
            s, flags=re.IGNORECASE,
        )
        s = re.sub(
            r"R\s*\$?\s*([0-9]{1,3}(?:\.[0-9]{3})+)(?!,)",
            lambda m: "R$ " + m.group(1),
            s, flags=re.IGNORECASE,
        )
        s = re.sub(r"([A-Za-zÁ-ú])(\d)", r"\1 \2", s)
        s = re.sub(r"(\d)([A-Za-zÁ-ú])", r"\1 \2", s)
        s = re.sub(r"(?i)\bdeum\b", "de um", s)
        s = re.sub(r"([*_~`])", r"\\\1", s)
        return s

    def gerar_resumo_gemini(self, report_data, milestones, kpis) -> str:
        if not self.gemini_model:
            return report_data.resumo_executivo or ""
        prompt = f"""(texto do prompt mantido)"""
        try:
            resp = self.gemini_model.generate_content(prompt, generation_config=self.gemini_config)
            raw = (getattr(resp, "text", None) or str(resp) or "").strip()
            return self._sanitizar_resumo_ptbr(raw) or (report_data.resumo_executivo or "")
        except Exception:
            return report_data.resumo_executivo or "Resumo original não disponível."
        
    def resumir_aries_relatorio(self, texto: str) -> str:
        """
        Gera um resumo em PT-BR do relatório ARIES (em inglês),
        organizado em seções de markdown. Não persiste nada, só
        devolve uma string grande para o frontend.
        """
        if not isinstance(texto, str):
            if isinstance(texto, (bytes, bytearray)):
                texto = texto.decode("utf-8", errors="ignore")
            else:
                texto = str(texto)

        # Para não estourar o contexto do modelo, recorta se for gigante
        max_chars = 30000
        trecho = texto[:max_chars]

        prompt = f"""
        Você é um especialista em projetos de identidade digital e privacidade na Europa.

        A seguir está um trecho de um relatório do projeto ARIES (em inglês).
        Gere um resumo em **português do Brasil**, organizado com markdown simples, usando
        as seções abaixo (use títulos `##`):

        ## Visão geral do projeto ARIES
        - Contexto e objetivo geral do projeto

        ## Papel da SONAE / SONAE MC
        - Qual o papel da SONAE no piloto / cenário descrito
        - Principais responsabilidades e atividades

        ## Principais atividades e resultados
        - Work packages ou tarefas relevantes
        - Demonstrações / pilotos / experimentos realizados
        - Resultados alcançados (quando descritos)

        ## Riscos, desafios e lições aprendidas
        - Riscos mencionados, dificuldades, limitações
        - Lições aprendidas ou recomendações

        ## Pontos que podem inspirar o MC Sonae (projeto acadêmico)
        - 3 a 5 bullets conectando o que aparece no ARIES com ideias
        que poderiam ser aplicadas numa plataforma de dashboards
        e monitoramento de projetos

        INSTRUÇÕES:
        - Não invente informação. Use apenas o que aparecer no texto.
        - Se alguma seção não tiver informação, escreva uma frase curta
        dizendo que o relatório não traz detalhes suficientes.
        - Não use código, não use blocos ```; apenas markdown simples.

        TRECHO DO RELATÓRIO (em inglês):
        \"\"\"{trecho}\"\"\"
        """.strip()

        try:
            resp = self.gemini_model.generate_content(
                prompt,
                generation_config=self.gemini_config,
            )
            raw = (getattr(resp, "text", None) or str(resp) or "").strip()
            return self._sanitizar_resumo_ptbr(raw)
        except Exception as e:
            print(f"AVISO: Falha ao resumir relatório ARIES: {e}")
            return "Não foi possível gerar o resumo automático do relatório ARIES."

    def gerar_insights_aries(self, texto: str) -> dict:
        """
        Interpreta um relatório ARIES e devolve um dicionário estruturado
        em termos de Work Packages (WP1..WP7), pilotos/cenários e tabelas
        relevantes. Não mexe em banco de dados.
        """
        if not isinstance(texto, str):
            if isinstance(texto, (bytes, bytearray)):
                texto = texto.decode("utf-8", errors="ignore")
            else:
                texto = str(texto)

        max_chars = 30000
        trecho = texto[:max_chars]

        prompt = f"""
        Você é um especialista em projetos europeus de I&D e em documentação de Work Packages.

        A seguir está um trecho de um relatório do projeto ARIES (em inglês).
        O documento menciona Work Packages (WP1, WP2, ..., WP7), pilotos/cenários (por ex. e-commerce, aeroporto)
        e várias tabelas (por exemplo: cronogramas, KPIs, parceiros, resultados).

        Sua tarefa é analisar o texto (incluindo o conteúdo das tabelas, quando for descrito em texto)
        e devolver um JSON ESTRUTURADO em português do Brasil, exatamente no formato abaixo:

        {{
        "visao_geral": "Texto curto explicando o contexto e objetivo geral do projeto ARIES.",
        "papel_sonae": "Explicação específica do papel da SONAE / SONAE MC no projeto e nos pilotos.",
        "work_packages": [
            {{
            "id": "WP1",
            "titulo": "Título resumido do WP1 (em português, se possível).",
            "objetivo": "Objetivo principal do WP1.",
            "status": "planejado ou em_andamento ou concluido ou atrasado ou nao_mencionado",
            "principais_atividades": [
                "Atividade relevante do WP1 descrita no relatório.",
                "Outra atividade relevante do WP1."
            ],
            "principais_resultados": [
                "Resultado importante do WP1, se mencionado.",
                "Outro resultado importante do WP1."
            ]
            }},
            {{
            "id": "WP2",
            "titulo": "...",
            "objetivo": "...",
            "status": "...",
            "principais_atividades": [],
            "principais_resultados": []
            }}
        ],
        "pilotos": [
            {{
            "nome": "Nome do piloto/cenário (ex.: e-commerce cross-border)",
            "descricao": "Descrição resumida do que é testado nesse piloto.",
            "work_packages_relacionados": ["WP2", "WP4"],
            "status": "em_andamento ou concluido ou planejado ou nao_mencionado",
            "principais_resultados": [
                "Resultado ou evidência relevante mencionada para esse piloto."
            ],
            "kpis": [
                "KPIs, métricas ou indicadores que aparecem no relatório."
            ]
            }}
        ],
        "tabelas_relevantes": [
            {{
            "titulo": "Título resumido da tabela (se houver).",
            "tema": "Tema da tabela (ex.: cronograma, KPIs, parceiros).",
            "descricao": "Resumo em 1-3 frases do que a tabela mostra."
            }}
        ],
        "riscos": [
            "Riscos ou desafios relevantes mencionados no texto."
        ],
        "licoes": [
            "Lições aprendidas ou recomendações mencionadas."
        ],
        "ideias_mc_sonae": [
            "Ideia 1 de como aproveitar algo do ARIES no projeto MC Sonae.",
            "Ideia 2...",
            "Ideia 3..."
        ]
        }}

        INSTRUÇÕES IMPORTANTES:
        - Preencha o máximo de campos possível COM BASE NO TEXTO.
        - Não invente informações que não estejam claramente implícitas ou explícitas.
        - Se algum campo não tiver informação suficiente, deixe listas vazias ou use
          valores genéricos como "nao_mencionado" para status.
        - Use IDs de WPs reais que aparecerem no texto (WP1, WP2, ..., WP7).
        - Tudo deve estar em português do Brasil, mas você pode manter nomes próprios
          e siglas em inglês.
        - Respeite ESTRITAMENTE a estrutura do JSON acima.
        - Não coloque comentários, não coloque texto fora do JSON.
        - Não retorne ``` nem blocos de código, apenas JSON puro.

        TRECHO DO RELATÓRIO (em inglês):
        \"\"\"{trecho}\"\"\"
        """.strip()

        try:
            resp = self.gemini_model.generate_content(
                prompt,
                generation_config=self.gemini_config,
            )
            raw = (getattr(resp, "text", None) or str(resp) or "").strip()
            parsed = self._tentar_parse_json(raw)
            return parsed or {}
        except Exception as e:
            print(f"AVISO: Falha ao gerar insights estruturados do ARIES: {e}")
            return {}


# ======================================================================================
# DatabaseRepository — todas as operações ORM
# ======================================================================================
class DatabaseRepository:
    def __init__(self, session_factory, ai_service: AIService):
        self.session_factory = session_factory
        self.ai_service = ai_service
        print("DatabaseRepository (ORM) inicializado.")

    def _get_db(self) -> Session:
        return self.session_factory()

    # --------------------------- RBAC / Usuários ---------------------------
    def usuario_tem_papel(self, email: str, role_name: str) -> bool:
        with self.session_factory() as session:
            q = (
                session.query(models.Papel)
                .join(models.UsuarioPapel, models.Papel.id_papel == models.UsuarioPapel.id_papel_fk)
                .join(models.Usuario, models.UsuarioPapel.id_usuario_fk == models.Usuario.id_usuario)
                .filter(models.Usuario.email == email, models.Papel.nome == role_name)
            )
            return session.query(q.exists()).scalar()

    def get_usuario_por_email(self, email: str) -> Optional[models.Usuario]:
        db = self._get_db()
        try:
            return db.query(models.Usuario).filter(models.Usuario.email == email).first()
        finally:
            db.close()

    def set_senha_hash_usuario(self, email: str, new_hash: str) -> None:
        db = self._get_db()
        try:
            u = db.query(models.Usuario).filter(models.Usuario.email == email).first()
            if not u:
                return
            u.senha_hash = new_hash
            db.commit()
        finally:
            db.close()

    def get_permissoes_usuario(self, email: str) -> List[str]:
        db = self._get_db()
        try:
            q = (
                db.query(models.Permissao.nome_permissao)
                .join(models.PapelPermissao, models.Permissao.id_permissao == models.PapelPermissao.id_permissao_fk)
                .join(models.Papel, models.Papel.id_papel == models.PapelPermissao.id_papel_fk)
                .join(models.UsuarioPapel, models.Papel.id_papel == models.UsuarioPapel.id_papel_fk)
                .join(models.Usuario, models.Usuario.id_usuario == models.UsuarioPapel.id_usuario_fk)
                .filter(models.Usuario.email == email)
                .distinct()
            )
            return [r[0] for r in q.all()]
        finally:
            db.close()

    def get_perfil_usuario(self, email: str) -> dict:
        db = self._get_db()
        try:
            u = db.query(models.Usuario).filter(models.Usuario.email == email).first()
            if not u:
                return {}
            cargos = (
                db.query(models.Papel.nome)
                .join(models.UsuarioPapel, models.Papel.id_papel == models.UsuarioPapel.id_papel_fk)
                .filter(models.UsuarioPapel.id_usuario_fk == u.id_usuario)
                .all()
            )
            return {"nome": u.nome, "email": u.email, "setor": u.setor, "cargos": [c[0] for c in cargos]}
        finally:
            db.close()

    # --------------------------- Refresh Tokens ---------------------------
    @staticmethod
    def _hash_refresh_token(plain_token: str) -> str:
        pepper = os.getenv("REFRESH_TOKEN_PEPPER", "")
        return hashlib.sha256((pepper + plain_token).encode("utf-8")).hexdigest()

    def criar_refresh_token(self, db: Session, user_id: int) -> str:
        plain = AuthService.criar_refresh_token_texto_puro()
        hashed = self._hash_refresh_token(plain)
        exp = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        db.add(models.RefreshToken(id_usuario_fk=user_id, token_hash=hashed, data_expiracao=exp))
        db.commit()
        return plain

    def get_refresh_token(self, db: Session, plain_token: str) -> Optional[models.RefreshToken]:
        hashed = self._hash_refresh_token(plain_token)
        now = datetime.now(timezone.utc)
        return (
            db.query(models.RefreshToken)
            .filter(models.RefreshToken.token_hash == hashed, models.RefreshToken.data_expiracao >= now)
            .first()
        )

    def get_refresh_token_dono_email(self, db: Session, plain_token: str) -> Optional[str]:
        rt = self.get_refresh_token(db, plain_token)
        if not rt:
            return None
        u = db.query(models.Usuario).filter(models.Usuario.id_usuario == rt.id_usuario_fk).first()
        return u.email if u else None

    def rotate_refresh_token(self, db: Session, old_plain: str, new_plain: str) -> bool:
        rt = self.get_refresh_token(db, old_plain)
        if not rt:
            return False
        try:
            rt.token_hash = self._hash_refresh_token(new_plain)
            rt.data_expiracao = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False

    def revogar_refresh_token_para_texto_puro(self, db: Session, plain: str) -> int:
        rt = self.get_refresh_token(db, plain)
        if not rt:
            return 0
        db.delete(rt)
        db.commit()
        return 1

    def revogar_todos_refresh_tokens_do_usuario(self, user_id: int) -> int:
        db = self._get_db()
        try:
            res = db.execute(delete(models.RefreshToken).where(models.RefreshToken.id_usuario_fk == user_id))
            db.commit()
            return int(res.rowcount or 0)
        finally:
            db.close()

    # --------------------------- Relatórios / Dashboard ---------------------------
    def salvar_relatorio_processado(self, report: models.ParsedReport, author_id: int | None = None) -> int:
        db = self._get_db()
        try:
            if self.ai_service.gemini_model:
                resumo = self.ai_service.gerar_resumo_gemini(report, report.milestones, report.kpis)
                report.resumo_executivo = resumo

            gerente_fk = self._buscar_fk_gerente_por_nome(db, report.gerente_projeto)

            if gerente_fk is not None:
                papel = self._papel_acesso_por_usuario(db, gerente_fk)
                self._grant_acesso_projeto(db, report.codigo_projeto, gerente_fk, papel)

            orc_kpi = next((k for k in report.kpis if k.nome_kpi == "Orçamento Total"), None)

            projeto = db.get(models.Projeto, report.codigo_projeto)
            if projeto:
                projeto.nome_projeto = report.nome_projeto
                projeto.gerente_projeto = report.gerente_projeto
                if gerente_fk is not None:
                    projeto.id_gerente_fk = gerente_fk
                if orc_kpi and orc_kpi.valor_numerico_kpi is not None:
                    projeto.orcamento_total = orc_kpi.valor_numerico_kpi
            else:
                new_budget = orc_kpi.valor_numerico_kpi if (orc_kpi and orc_kpi.valor_numerico_kpi is not None) else 0.0
                projeto = models.Projeto(
                    codigo_projeto=report.codigo_projeto,
                    nome_projeto=report.nome_projeto,
                    gerente_projeto=report.gerente_projeto,
                    id_gerente_fk=gerente_fk,
                    orcamento_total=new_budget,
                    area_negocio=report.area_negocio,
                )
                db.add(projeto)

            rel = models.RelatorioSprint(
                numero_sprint=report.numero_sprint,
                status_geral=report.status_geral,
                resumo_executivo=report.resumo_executivo,
                riscos_e_impedimentos=report.riscos_e_impedimentos,
                proximos_passos=report.proximos_passos,
                codigo_projeto_fk=report.codigo_projeto,
                story_points_planejados=report.story_points_planejados,
                story_points_entregues=report.story_points_entregues,
                id_autor_fk=author_id,
            )
            if report.milestones:
                rel.milestones = [models.MilestoneHistorico(**m.model_dump()) for m in report.milestones]
            if report.kpis:
                rel.kpis = [models.RelatorioKPI(**k.model_dump()) for k in report.kpis]

            db.add(rel)
            db.commit()
            return rel.id_relatorio
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _papel_acesso_por_usuario(self, db, id_usuario: int) -> str:
        rows = (
            db.query(models.Papel.nome)
            .join(models.UsuarioPapel, models.UsuarioPapel.id_papel_fk == models.Papel.id_papel)
            .filter(models.UsuarioPapel.id_usuario_fk == id_usuario)
            .all()
        )
        nomes = {r[0] for r in rows}
        ordem = ["Administrador", "Diretor", "Gestor de Projetos", "Analista", "Visualizador"]
        for c in ordem:
            if c in nomes: return c
        return "Visualizador"

    def _grant_acesso_projeto(self, db, codigo_projeto: str, id_usuario: int, papel: str) -> None:
        vinc = (
            db.query(models.ProjetoUsuarioAcesso)
            .filter(
                models.ProjetoUsuarioAcesso.codigo_projeto_fk == codigo_projeto,
                models.ProjetoUsuarioAcesso.id_usuario_fk == id_usuario,
            ).first()
        )
        if vinc:
            if papel and vinc.papel_acesso != papel:
                vinc.papel_acesso = papel
            return
        db.add(models.ProjetoUsuarioAcesso(
            codigo_projeto_fk=codigo_projeto, id_usuario_fk=id_usuario, papel_acesso=papel or "Visualizador"
        ))

    def _buscar_fk_gerente_por_nome(self, db: Session, nome_gerente: str | None) -> int | None:
        if not nome_gerente or not nome_gerente.strip():
            return None
        row = (
            db.query(models.Usuario.id_usuario)
            .join(models.UsuarioPapel, models.UsuarioPapel.id_usuario_fk == models.Usuario.id_usuario)
            .join(models.Papel, models.Papel.id_papel == models.UsuarioPapel.id_papel_fk)
            .filter(func.lower(models.Usuario.nome) == func.lower(nome_gerente.strip()))
            .filter(models.Papel.nome == "Gestor de Projetos")
            .first()
        )
        return row.id_usuario if row else None

    def get_estatisticas_dashboard(self) -> Optional[models.DashboardStats]:
        db = self._get_db()
        try:
            sub = (
                db.query(
                    models.RelatorioSprint.codigo_projeto_fk,
                    func.max(models.RelatorioSprint.numero_sprint).label("max_sprint"),
                )
                .group_by(models.RelatorioSprint.codigo_projeto_fk)
                .subquery()
            )
            base = (
                db.query(models.RelatorioSprint)
                .join(sub, and_(
                    models.RelatorioSprint.codigo_projeto_fk == sub.c.codigo_projeto_fk,
                    models.RelatorioSprint.numero_sprint == sub.c.max_sprint,
                ))
                .join(models.Projeto, models.Projeto.codigo_projeto == models.RelatorioSprint.codigo_projeto_fk)
                .filter(models.Projeto.is_deletado.is_(False))  # <<< PG-friendly
            )
            query = db.query(
                func.count().label("total_projetos"),
                func.sum(case((models.RelatorioSprint.status_geral == "Em Dia", 1), else_=0)).label("projetos_em_dia"),
                func.sum(case((models.RelatorioSprint.status_geral == "Em Risco", 1), else_=0)).label("projetos_em_risco"),
                func.sum(case((models.RelatorioSprint.status_geral == "Atrasado", 1), else_=0)).label("projetos_atrasados"),
            ).select_from(base)
            res = query.one()

            investimento_total = (
                db.query(func.sum(models.RelatorioKPI.valor_numerico_kpi))
                .join(models.RelatorioSprint, models.RelatorioSprint.id_relatorio == models.RelatorioKPI.id_relatorio_fk)
                .join(models.Projeto, models.Projeto.codigo_projeto == models.RelatorioSprint.codigo_projeto_fk)
                .filter(models.RelatorioKPI.nome_kpi == "Custo Realizado", models.Projeto.is_deletado.is_(False))  # <<<
                .scalar() or 0.0
            )
            stats = res._asdict()
            stats["investimento_total_executado"] = investimento_total
            return models.DashboardStats(**stats)
        finally:
            db.close()

    def get_lista_projetos(self) -> List[models.ProjectListItem]:
        db = self._get_db()
        try:
            projetos = (
                db.query(models.Projeto)
                .filter(models.Projeto.is_deletado.is_(False))  # <<< PG-friendly
                .order_by(models.Projeto.nome_projeto)
                .all()
            )
            def _area(p):
                a = getattr(p, "area_negocio", None)
                return (a.value if hasattr(a, "value") else a) or ""
            return [
                models.ProjectListItem(codigo_projeto=p.codigo_projeto, nome_projeto=p.nome_projeto, area_negocio=_area(p))
                for p in projetos
            ]
        finally:
            db.close()

    def get_sprints_do_projeto(self, codigo_projeto: str) -> List[models.SprintListItem]:
        db = self._get_db()
        try:
            rows = (
                db.query(models.RelatorioSprint)
                .filter(models.RelatorioSprint.codigo_projeto_fk == codigo_projeto)
                .order_by(desc(models.RelatorioSprint.numero_sprint))
                .all()
            )
            return [models.SprintListItem.model_validate(s) for s in rows]
        finally:
            db.close()

    def get_detalhe_do_relatorio(self, id_relatorio: int) -> Optional[models.ReportDetailResponse]:
        db = self._get_db()
        try:
            rel = (
                db.query(models.RelatorioSprint)
                .options(
                    joinedload(models.RelatorioSprint.projeto),
                    joinedload(models.RelatorioSprint.milestones),
                    joinedload(models.RelatorioSprint.kpis),
                )
                .get(id_relatorio)
            )
            if not rel:
                return None

            data = rel.__dict__.copy()
            if rel.projeto:
                data["codigo_projeto"] = rel.projeto.codigo_projeto
                data["nome_projeto"] = rel.projeto.nome_projeto
                data["gerente_projeto"] = rel.projeto.gerente_projeto
                data["orcamento_total"] = rel.projeto.orcamento_total

            detail = models.ReportDetail(**data)
            milestones = [models.Milestone.model_validate(m) for m in rel.milestones]
            kpis = [models.KPI.model_validate(k) for k in rel.kpis]
            return models.ReportDetailResponse(detalhe_relatorio=detail, milestones=milestones, kpis=kpis)
        finally:
            db.close()

    def get_historico_kpi(self, codigo_projeto: str, nome_kpi: str) -> List[models.FinancialHistoryItem]:
        db = self._get_db()
        try:
            proj = db.query(models.Projeto.orcamento_total).filter(models.Projeto.codigo_projeto == codigo_projeto).first()
            orc = proj.orcamento_total if proj else 0.0
            rows = (
                db.query(models.RelatorioSprint.numero_sprint, models.RelatorioKPI.valor_numerico_kpi)
                .join(models.RelatorioKPI, models.RelatorioSprint.id_relatorio == models.RelatorioKPI.id_relatorio_fk)
                .filter(models.RelatorioSprint.codigo_projeto_fk == codigo_projeto, models.RelatorioKPI.nome_kpi == nome_kpi)
                .order_by(models.RelatorioSprint.numero_sprint)
                .all()
            )
            return [
                models.FinancialHistoryItem(sprint_number=r.numero_sprint, cost_realized=r.valor_numerico_kpi or 0.0, budget_total=orc)
                for r in rows
            ]
        finally:
            db.close()

    # --------------------------- Solicitações de acesso ---------------------------
    def criar_solicitacao_acesso(self, *, nome: str, email: str, senha: str, setor: str, justificativa: str, cargo: str) -> None:
        db = self._get_db()
        try:
            email_norm = (email or "").strip().lower()
            nome_norm  = (nome or "").strip()
            setor_norm = (setor or "").strip()
            just_norm  = (justificativa or "").strip()
            cargo_norm = (cargo or "").strip()

            CARGOS_VALIDOS = {"Administrador","Analista","Gestor de Projetos","Diretor","Visualizador"}
            if cargo_norm not in CARGOS_VALIDOS:
                raise RuntimeError("Cargo inválido.")

            if db.query(models.Usuario.id_usuario).filter(models.Usuario.email == email_norm).first():
                raise RuntimeError("E-mail já cadastrado.")

            pend = (
                db.query(models.UsuarioSolicitacaoAcesso.id_solicitacao)
                .filter(models.UsuarioSolicitacaoAcesso.email == email_norm,
                        models.UsuarioSolicitacaoAcesso.status == "aguardando")
                .first()
            )
            if pend:
                raise RuntimeError("Já existe solicitação pendente para este e-mail.")

            auth = AuthService()
            senha_hash = auth.get_hash_senha(senha)

            sol = models.UsuarioSolicitacaoAcesso(
                nome=nome_norm, email=email_norm, senha_hash=senha_hash,
                setor=setor_norm, justificativa=just_norm, cargo=cargo_norm,
                status="aguardando", criado_em=datetime.utcnow(),
            )
            db.add(sol)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def listar_solicitacoes(self, *, status: str = "aguardando"):
        db = self._get_db()
        try:
            rows = (
                db.query(models.UsuarioSolicitacaoAcesso, models.Usuario.nome.label("decidido_por_nome"))
                .outerjoin(models.Usuario, models.Usuario.id_usuario == models.UsuarioSolicitacaoAcesso.decidido_por)
                .filter(models.UsuarioSolicitacaoAcesso.status == status)
                .order_by(models.UsuarioSolicitacaoAcesso.criado_em.asc())
                .all()
            )
            out = []
            for sol, admin_nome in rows:
                d = {k: v for k, v in sol.__dict__.items() if k != "_sa_instance_state"}
                d["decidido_por_nome"] = admin_nome
                out.append(d)
            return out
        finally:
            db.close()

    def decidir_solicitacao(self, id_solic: int, admin_id: int, decisao: str, motivo: Optional[str] = None):
        """Aprova/Rejeita solicitação de acesso."""
        db: Session = self._get_db()
        try:
            sol = db.get(models.UsuarioSolicitacaoAcesso, id_solic)
            if not sol:
                raise RuntimeError("Solicitação não encontrada.")
            if sol.status != "aguardando":
                raise RuntimeError("Solicitação já foi decidida.")

            decisao_norm = (decisao or "").strip().lower()
            if decisao_norm not in {"aprovar", "rejeitar"}:
                raise RuntimeError("Decisão inválida.")

            # Rejeição simples
            if decisao_norm == "rejeitar":
                sol.status = "rejeitado"
                sol.motivo_decisao = (motivo or None)
                sol.decidido_por = admin_id
                sol.decidido_em = datetime.utcnow()
                db.commit()
                return

            # === Aprovação ===
            # 1) Resolve papel (fallback para Visualizador)
            cargo = (sol.cargo or "").strip()
            papel = db.query(models.Papel).filter(models.Papel.nome == cargo).first()
            if not papel:
                papel = db.query(models.Papel).filter(models.Papel.nome == "Visualizador").first()
                if not papel:
                    raise RuntimeError("Papel/cargo não encontrado (nem fallback Visualizador).")

            # 2) E-mail normalizado + checagem de duplicidade
            email_norm = (sol.email or "").strip().lower()
            if not email_norm:
                raise RuntimeError("E-mail da solicitação é inválido.")

            if db.query(models.Usuario.id_usuario).filter(models.Usuario.email == email_norm).first():
                raise RuntimeError("Já existe um usuário com este e-mail.")

            # 3) Cria usuário (reusa o hash que veio na solicitação)
            novo = models.Usuario(
                nome=(sol.nome or "").strip(),
                email=email_norm,
                senha_hash=sol.senha_hash,  # já está em bcrypt
                setor=(sol.setor or None),
            )
            db.add(novo)
            db.flush()  # obtém novo.id_usuario

            # 4) Vincula papel (sem campos extras)
            existe = (
                db.query(models.UsuarioPapel)
                .filter(
                    models.UsuarioPapel.id_usuario_fk == novo.id_usuario,
                    models.UsuarioPapel.id_papel_fk == papel.id_papel,
                )
                .first()
            )
            if not existe:
                db.add(models.UsuarioPapel(
                    id_usuario_fk=novo.id_usuario,
                    id_papel_fk=papel.id_papel,
                ))

            # 5) Finaliza decisão da solicitação
            sol.status = "aprovado"
            sol.motivo_decisao = (motivo or None)
            sol.decidido_por = admin_id
            sol.decidido_em = datetime.utcnow()

            db.commit()

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


    def atualizar_usuario_limitado(self, *, id_usuario: int, nome: str | None, setor: str | None) -> None:
        db = self._get_db()
        try:
            u = db.get(models.Usuario, id_usuario)
            if not u:
                raise RuntimeError("Usuário não encontrado.")
            changed = False
            if nome is not None and nome.strip() and nome.strip() != u.nome:
                u.nome = nome.strip(); changed = True
            if setor is not None and setor.strip() and setor.strip() != (u.setor or ""):
                u.setor = setor.strip(); changed = True
            if changed:
                u.data_atualizacao = datetime.utcnow()
                db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def listar_usuarios(self, q: str | None = None) -> list[dict]:
        db = self._get_db()
        try:
            CARGO_ORDER = case(
                (models.Papel.nome == "Administrador",        5),
                (models.Papel.nome == "Gestor de Projetos",   4),
                (models.Papel.nome == "Analista",             3),
                (models.Papel.nome == "Diretor",              2),
                (models.Papel.nome == "Visualizador",         1),
                else_=0,
            ).label("cargo_rank")

            qry = (
                db.query(
                    models.Usuario.id_usuario,
                    models.Usuario.nome,
                    models.Usuario.email,
                    models.Usuario.setor,
                    models.Papel.nome.label("cargo"),
                    CARGO_ORDER,
                )
                .outerjoin(models.UsuarioPapel, models.Usuario.id_usuario == models.UsuarioPapel.id_usuario_fk)
                .outerjoin(models.Papel, models.Papel.id_papel == models.UsuarioPapel.id_papel_fk)
            )
            if q:
                qnorm = f"%{q.strip().lower()}%"
                qry = qry.filter((models.Usuario.nome.ilike(qnorm)) | (models.Usuario.email.ilike(qnorm)))

            rows = qry.order_by(models.Usuario.id_usuario.asc(), CARGO_ORDER.desc()).all()
            out: dict[int, dict] = {}
            for r in rows:
                if r.id_usuario not in out:
                    out[r.id_usuario] = {
                        "id_usuario": r.id_usuario,
                        "nome": r.nome,
                        "email": r.email,
                        "setor": r.setor,
                        "cargo": r.cargo or "",
                    }
            return list(out.values())
        finally:
            db.close()

    # --------------------------- Filtros utilitários ---------------------------
    def _somente_ativos(self, query):
        return query.filter(models.Projeto.is_deletado.is_(False))  # <<< PG-friendly

    def eh_admin(self, email: str) -> bool:
        return self.usuario_tem_papel(email, "Administrador")

    def eh_gestor(self, email: str) -> bool:
        return self.usuario_tem_papel(email, "Gestor de Projetos")

    def _norm(self, s: str | None) -> str:
        return (s or "").strip().lower()

    # --------------------------- Projetos: visibilidade ---------------------------
    def get_projeto(self, codigo_projeto: str) -> Optional[models.Projeto]:
        db = self._get_db()
        try:
            return db.get(models.Projeto, codigo_projeto)
        finally:
            db.close()

    def permissao_deletar_projeto(self, *, email: str, codigo_projeto: str) -> bool:
        if self.eh_admin(email):
            return True
        if not self.eh_gestor(email):
            return False
        user = self.get_usuario_por_email(email)
        if not user:
            return False
        proj = self.get_projeto(codigo_projeto)
        if not proj:
            return False
        # antes: proj.is_deletado == 0
        return self._norm(proj.gerente_projeto) == self._norm(user.nome) and (proj.is_deletado is False)

    def listar_projetos_deletados(self) -> list[dict]:
        db = self._get_db()
        try:
            rows = (
                db.query(
                    models.Projeto.codigo_projeto,
                    models.Projeto.nome_projeto,
                    models.Projeto.area_negocio,
                    models.Projeto.deletado_em,
                    models.Projeto.motivo_exclusao,
                    models.Usuario.nome.label("deletado_por_nome"),
                )
                .outerjoin(models.Usuario, models.Usuario.id_usuario == models.Projeto.deletado_por)
                .filter(models.Projeto.is_deletado.is_(True))   # <<< PG-friendly
                .order_by(models.Projeto.deletado_em.desc())
                .all()
            )
            return [
                dict(
                    codigo_projeto=r.codigo_projeto,
                    nome_projeto=r.nome_projeto,
                    area_negocio=r.area_negocio,
                    deletado_em=r.deletado_em,
                    motivo=r.motivo_exclusao or "",
                    deletado_por_nome=r.deletado_por_nome or "—",
                ) for r in rows
            ]
        finally:
            db.close()

    def listar_projetos_visiveis(self, *, email: str) -> list[dict]:
        db = self._get_db()
        try:
            u = db.query(models.Usuario).filter(models.Usuario.email == email).first()
            if not u:
                return []
            uid = u.id_usuario
            is_admin = self.eh_admin(email)
            projmap: dict[str, str] = {}

            if is_admin:
                for r in (db.query(models.Projeto.codigo_projeto, models.Projeto.nome_projeto)
                          .filter(models.Projeto.is_deletado.is_(False))
                          .order_by(models.Projeto.nome_projeto.asc()).all()):
                    projmap[r.codigo_projeto] = r.nome_projeto

            for r in (db.query(models.Projeto.codigo_projeto, models.Projeto.nome_projeto)
                      .filter(models.Projeto.is_deletado.is_(False), models.Projeto.id_gerente_fk == uid).all()):
                projmap[r.codigo_projeto] = r.nome_projeto

            for r in (db.query(models.Projeto.codigo_projeto, models.Projeto.nome_projeto)
                      .join(models.ProjetoUsuarioAcesso,
                            models.ProjetoUsuarioAcesso.codigo_projeto_fk == models.Projeto.codigo_projeto)
                      .filter(models.Projeto.is_deletado.is_(False),
                              models.ProjetoUsuarioAcesso.id_usuario_fk == uid).all()):
                projmap[r.codigo_projeto] = r.nome_projeto

            for r in (db.query(models.Projeto.codigo_projeto, models.Projeto.nome_projeto)
                      .join(models.RelatorioSprint, models.RelatorioSprint.codigo_projeto_fk == models.Projeto.codigo_projeto)
                      .filter(models.Projeto.is_deletado.is_(False),
                              models.RelatorioSprint.id_autor_fk == uid).all()):
                projmap[r.codigo_projeto] = r.nome_projeto

            return [dict(codigo_projeto=c, nome_projeto=n) for c, n in sorted(projmap.items(), key=lambda kv: kv[1].lower())]
        finally:
            db.close()

    def listar_projetos_gerenciados(self, *, email: str) -> list[dict]:
        db = self._get_db()
        try:
            u = db.query(models.Usuario.id_usuario, models.Usuario.nome, models.Usuario.email).filter(models.Usuario.email == email).first()
            if not u:
                return []
            uid, nome = u.id_usuario, u.nome

            is_admin = (
                db.query(models.Papel.id_papel)
                .join(models.UsuarioPapel, models.Papel.id_papel == models.UsuarioPapel.id_papel_fk)
                .filter(models.UsuarioPapel.id_usuario_fk == uid, models.Papel.nome == "Administrador")
                .first() is not None
            )

            projmap: dict[str, str] = {}
            if is_admin:
                for r in (db.query(models.Projeto.codigo_projeto, models.Projeto.nome_projeto)
                          .filter(models.Projeto.is_deletado.is_(False))
                          .order_by(models.Projeto.nome_projeto.asc()).all()):
                    projmap[r.codigo_projeto] = r.nome_projeto

            for r in (db.query(models.Projeto.codigo_projeto, models.Projeto.nome_projeto)
                      .filter(models.Projeto.is_deletado.is_(False), models.Projeto.id_gerente_fk == uid)
                      .order_by(models.Projeto.nome_projeto.asc()).all()):
                projmap[r.codigo_projeto] = r.nome_projeto

            for r in (db.query(models.Projeto.codigo_projeto, models.Projeto.nome_projeto)
                      .join(models.RelatorioSprint, models.RelatorioSprint.codigo_projeto_fk == models.Projeto.codigo_projeto)
                      .filter(models.Projeto.is_deletado.is_(False), models.RelatorioSprint.id_autor_fk == uid)
                      .group_by(models.Projeto.codigo_projeto, models.Projeto.nome_projeto)
                      .order_by(models.Projeto.nome_projeto.asc()).all()):
                projmap[r.codigo_projeto] = r.nome_projeto

            if not projmap:
                # fallback por nome (compat)
                qtd = db.query(func.count(models.Usuario.id_usuario)).filter(models.Usuario.nome == nome).scalar()
                if qtd == 1:
                    for r in (db.query(models.Projeto.codigo_projeto, models.Projeto.nome_projeto)
                              .filter(models.Projeto.is_deletado.is_(False),
                                      models.Projeto.id_gerente_fk.is_(None),
                                      models.Projeto.gerente_projeto == nome)
                              .order_by(models.Projeto.nome_projeto.asc()).all()):
                        projmap[r.codigo_projeto] = r.nome_projeto

            out = [{"codigo_projeto": c, "nome_projeto": n} for c, n in projmap.items()]
            out.sort(key=lambda x: x["nome_projeto"].lower())
            return out
        finally:
            db.close()

    def garantir_acesso_projeto(self, *, codigo_projeto: str, id_usuario: int, papel: str | None = None) -> dict:
        db = self._get_db()
        try:
            papel_final = (papel or self._papel_acesso_por_usuario(db, id_usuario) or "Visualizador")
            vinc = (
                db.query(models.ProjetoUsuarioAcesso)
                .filter(models.ProjetoUsuarioAcesso.codigo_projeto_fk == codigo_projeto,
                        models.ProjetoUsuarioAcesso.id_usuario_fk == id_usuario).first()
            )
            if vinc:
                if vinc.papel_acesso != papel_final:
                    vinc.papel_acesso = papel_final
            else:
                db.add(models.ProjetoUsuarioAcesso(
                    codigo_projeto_fk=codigo_projeto, id_usuario_fk=id_usuario, papel_acesso=papel_final
                ))
            db.commit()
            return {"message": "Acesso garantido."}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def revogar_acesso_projeto(self, *, codigo_projeto: str, id_usuario: int) -> dict:
        db = self._get_db()
        try:
            db.query(models.ProjetoUsuarioAcesso).filter(
                models.ProjetoUsuarioAcesso.codigo_projeto_fk == codigo_projeto,
                models.ProjetoUsuarioAcesso.id_usuario_fk == id_usuario,
            ).delete(synchronize_session=False)
            db.commit()
            return {"message": "Acesso removido."}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # --------------------------- HARD DELETE de usuário ---------------------------
    def hard_delete_usuario(self, *, id_usuario: int) -> bool:
        db = self._get_db()
        try:
            u = db.get(models.Usuario, id_usuario)
            if not u:
                return False

            db.query(models.RefreshToken).filter(models.RefreshToken.id_usuario_fk == id_usuario)\
              .delete(synchronize_session=False)

            db.query(models.UsuarioPapel).filter(models.UsuarioPapel.id_usuario_fk == id_usuario)\
              .delete(synchronize_session=False)

            db.query(models.ProjetoUsuarioAcesso).filter(models.ProjetoUsuarioAcesso.id_usuario_fk == id_usuario)\
              .delete(synchronize_session=False)

            db.query(models.Projeto).filter(models.Projeto.id_gerente_fk == id_usuario)\
              .update({models.Projeto.id_gerente_fk: None}, synchronize_session=False)

            db.delete(u)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
