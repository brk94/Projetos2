# services.py

import os
from typing import List, Optional
from datetime import datetime, timedelta, timezone

# --- Imports de Segurança e Autenticação ---
from passlib.context import CryptContext
from jose import JWTError, jwt
import bcrypt
import hmac

# --- Imports do SQLAlchemy ---
from . import models
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case, desc

# --- Configuração de Segurança ---
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))

# Cria um contexto que sabe como hashear e verificar senhas usando o algoritmo bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    @staticmethod
    def is_bcrypt_hash(value: Optional[str]) -> bool:
        """Retorna True se o valor parece ser um hash bcrypt ($2a/$2b/$2y)."""
        if not isinstance(value, str):
            return False
        return value.startswith("$2a$") or value.startswith("$2b$") or value.startswith("$2y$")

    def get_password_hash(self, plain_password: str) -> str:
        return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verifica apenas quando hashed_password é de fato bcrypt."""
        if not self.is_bcrypt_hash(hashed_password):
            return False
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())

    def verify_password_or_plain(self, plain_password: str, stored_value: str) -> bool:
        """
        Aceita tanto hash bcrypt quanto texto puro (para migração).
        - Se 'stored_value' for bcrypt → valida com bcrypt
        - Se for texto puro → compara em tempo constante
        """
        if self.is_bcrypt_hash(stored_value):
            return bcrypt.checkpw(plain_password.encode(), stored_value.encode())
        # Comparação constante para evitar timing leaks (mesmo sendo migração)
        return hmac.compare_digest(plain_password, stored_value)

    def needs_update(self, stored_value: str) -> bool:
        """Pedir migração quando NÃO for bcrypt."""
        return not self.is_bcrypt_hash(stored_value)

    def create_access_token(self, data: dict, expires_delta=None) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

class AIService:
    def __init__(self, nlp_model, gemini_model, gemini_config):
        self.nlp = nlp_model
        self.gemini_model = gemini_model
        self.gemini_config = gemini_config
        print("AIService inicializado.")

    def generate_summary_gemini(self, report_data, milestones, kpis) -> str:
        prompt = f"""
        Você é um Diretor de Projetos (PMO) sênior. Escreva um resumo executivo curto (máximo 4 frases), 
        profissional e direto (em português do Brasil) com base NOS SEGUINTES DADOS BRUTOS de um projeto:
        - Nome do Projeto: {report_data.nome_projeto}
        - Status do Período: {report_data.status_geral}
        - Período (Sprint/Fase): {report_data.numero_sprint}
        - Métricas Chave (KPIs): {[k.model_dump() for k in kpis]}
        - Marcos (Milestones): {[m.model_dump() for m in milestones]}
        Por favor, gere um "Sumário Executivo" que destaque os pontos principais.
        Use os KPIs para explicar o desempenho. Seja direto.
        """
        try:
            response = self.gemini_model.generate_content(prompt, generation_config=self.gemini_config)
            return response.text.replace("*", "").strip()
        except Exception as e:
            print(f"AVISO: Falha ao gerar resumo com Gemini: {e}")
            return report_data.resumo_executivo or "Resumo original não disponível."


class DatabaseRepository:
    def __init__(self, session_factory, ai_service: AIService):
        self.session_factory = session_factory
        self.ai_service = ai_service
        print("DatabaseRepository (ORM) inicializado.")

    def _get_db(self) -> Session:
        return self.session_factory()

    # --- Métodos de Usuário ---
    
    def user_has_role(self, email: str, role_name: str) -> bool:
        """
        Retorna True se o usuário com 'email' possuir o papel cujo nome é 'role_name'.
        Ex.: user_has_role('admin@mcsonae.com', 'Administrador') -> True/False
        """
        with self.session_factory() as session:
            q = (
                session.query(models.Papel)
                .join(models.UsuarioPapel, models.Papel.id_papel == models.UsuarioPapel.id_papel_fk)
                .join(models.Usuario, models.UsuarioPapel.id_usuario_fk == models.Usuario.id_usuario)
                .filter(models.Usuario.email == email, models.Papel.nome == role_name)
            )
            # Existe alguma linha que satisfaça?
            return session.query(q.exists()).scalar()
        
    def get_user_by_email(self, email: str) -> Optional[models.Usuario]:
        """Busca um usuário no banco de dados pelo seu e-mail."""
        db: Session = self._get_db()
        try:
            return db.query(models.Usuario).filter(models.Usuario.email == email).first()
        finally:
            db.close()

    def set_user_password_hash(self, email: str, new_hash: str) -> None:
        from sqlalchemy.orm import Session
        from . import models
        db: Session = self._get_db()
        try:
            user = db.query(models.Usuario).filter(models.Usuario.email == email).first()
            if not user:
                return
            user.senha_hash = new_hash
            db.commit()
        finally:
            db.close()

    def get_user_permissions(self, email: str) -> List[str]:
        db: Session = self._get_db()
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
            return [row[0] for row in q.all()]
        finally:
            db.close()

    # --- Métodos de Relatório ---

    def save_parsed_report(self, report: models.ParsedReport) -> int:
        db: Session = self._get_db()
        try:
            if self.ai_service.gemini_model:
                print("Gerando resumo com IA (Gemini)...")
                resumo_ia = self.ai_service.generate_summary_gemini(report, report.milestones, report.kpis)
                report.resumo_executivo = resumo_ia

            projeto_orm = db.query(models.Projeto).get(report.codigo_projeto)
            orcamento_total_kpi = next((kpi for kpi in report.kpis if kpi.nome_kpi == "Orçamento Total"), None)
            
            if projeto_orm:
                # ## CORREÇÃO APLICADA AQUI ##
                # Agora atualiza todos os campos do projeto, não apenas o orçamento.
                projeto_orm.nome_projeto = report.nome_projeto
                projeto_orm.gerente_projeto = report.gerente_projeto
                if orcamento_total_kpi and orcamento_total_kpi.valor_numerico_kpi is not None:
                    projeto_orm.orcamento_total = orcamento_total_kpi.valor_numerico_kpi
            else:
                new_budget = orcamento_total_kpi.valor_numerico_kpi if orcamento_total_kpi and orcamento_total_kpi.valor_numerico_kpi is not None else 0.0
                projeto_orm = models.Projeto(
                    codigo_projeto=report.codigo_projeto,
                    nome_projeto=report.nome_projeto,
                    gerente_projeto=report.gerente_projeto,
                    orcamento_total=new_budget,
                    area_negocio=report.area_negocio
                )
                db.add(projeto_orm)
            
            relatorio_orm = models.RelatorioSprint(
                numero_sprint=report.numero_sprint,
                status_geral=report.status_geral,
                resumo_executivo=report.resumo_executivo,
                riscos_e_impedimentos=report.riscos_e_impedimentos,
                proximos_passos=report.proximos_passos,
                codigo_projeto_fk=report.codigo_projeto,
                story_points_planejados=report.story_points_planejados,
                story_points_entregues=report.story_points_entregues
            )
            
            if report.milestones:
                relatorio_orm.milestones = [models.MilestoneHistorico(**m.model_dump()) for m in report.milestones]
            if report.kpis:
                relatorio_orm.kpis = [models.RelatorioKPI(**k.model_dump()) for k in report.kpis]
            
            db.add(relatorio_orm)
            db.commit()
            
            print(f"SUCESSO: Relatório salvo para o Projeto {report.codigo_projeto} (ID: {relatorio_orm.id_relatorio}).")
            return relatorio_orm.id_relatorio
        
        except Exception as e:
            db.rollback() 
            raise e
        finally:
            db.close()

    def get_dashboard_stats(self) -> Optional[models.DashboardStats]:
        db: Session = self._get_db()
        try:
            subquery = db.query(models.RelatorioSprint.codigo_projeto_fk, func.max(models.RelatorioSprint.numero_sprint).label('max_sprint')).group_by(models.RelatorioSprint.codigo_projeto_fk).subquery()
            query = db.query(
                func.count().label("total_projetos"),
                func.sum(case((models.RelatorioSprint.status_geral == 'Em Dia', 1), else_=0)).label("projetos_em_dia"),
                func.sum(case((models.RelatorioSprint.status_geral == 'Em Risco', 1), else_=0)).label("projetos_em_risco"),
                func.sum(case((models.RelatorioSprint.status_geral == 'Atrasado', 1), else_=0)).label("projetos_atrasados")
            ).join(subquery, (models.RelatorioSprint.codigo_projeto_fk == subquery.c.codigo_projeto_fk) & (models.RelatorioSprint.numero_sprint == subquery.c.max_sprint))
            resultado = query.one()
            investimento_total = db.query(func.sum(models.RelatorioKPI.valor_numerico_kpi)).filter(models.RelatorioKPI.nome_kpi == "Custo Realizado").scalar() or 0.0
            stats = resultado._asdict()
            stats["investimento_total_executado"] = investimento_total
            return models.DashboardStats(**stats)
        finally:
            db.close()

    def get_project_list(self) -> List[models.ProjectListItem]:
        db: Session = self._get_db()
        try:
            projetos_orm = db.query(models.Projeto).order_by(models.Projeto.nome_projeto).all()
            return [models.ProjectListItem(codigo_projeto=p.codigo_projeto, nome_projeto=p.nome_projeto) for p in projetos_orm]
        except Exception as e:
            print(f"ERRO AO BUSCAR LISTA DE PROJETOS (ORM): {e}")
            return []
        finally:
            db.close()

    def get_sprints_do_projeto(self, codigo_projeto: str) -> List[models.SprintListItem]:
        db: Session = self._get_db()
        try:
            sprints_orm = db.query(models.RelatorioSprint).filter(models.RelatorioSprint.codigo_projeto_fk == codigo_projeto).order_by(desc(models.RelatorioSprint.numero_sprint)).all()
            return [models.SprintListItem.model_validate(s) for s in sprints_orm]
        finally:
            db.close()

    def get_detalhe_do_relatorio(self, id_relatorio: int) -> Optional[models.ReportDetailResponse]:
        db: Session = self._get_db()
        try:
            relatorio_atual = db.query(models.RelatorioSprint).options(
                joinedload(models.RelatorioSprint.projeto),
                joinedload(models.RelatorioSprint.milestones),
                joinedload(models.RelatorioSprint.kpis)
            ).get(id_relatorio)
            
            if not relatorio_atual: return None
            
            dados_para_detalhe = relatorio_atual.__dict__
            if relatorio_atual.projeto:
                dados_para_detalhe['codigo_projeto'] = relatorio_atual.projeto.codigo_projeto
                dados_para_detalhe['nome_projeto'] = relatorio_atual.projeto.nome_projeto
                dados_para_detalhe['gerente_projeto'] = relatorio_atual.projeto.gerente_projeto
                dados_para_detalhe['orcamento_total'] = relatorio_atual.projeto.orcamento_total

            report_detail_obj = models.ReportDetail(**dados_para_detalhe)
            milestones = [models.Milestone.model_validate(m) for m in relatorio_atual.milestones]
            kpis = [models.KPI.model_validate(k) for k in relatorio_atual.kpis]
            
            return models.ReportDetailResponse(
                detalhe_relatorio=report_detail_obj,
                milestones=milestones,
                kpis=kpis
            )
        finally:
            db.close()

    def get_kpi_history(self, codigo_projeto: str, nome_kpi: str) -> List[models.FinancialHistoryItem]:
        db: Session = self._get_db()
        try:
            projeto = db.query(models.Projeto.orcamento_total).filter(models.Projeto.codigo_projeto == codigo_projeto).first()
            orcamento = projeto.orcamento_total if projeto else 0.0
            kpi_history_orm = db.query(models.RelatorioSprint.numero_sprint, models.RelatorioKPI.valor_numerico_kpi).join(models.RelatorioKPI, models.RelatorioSprint.id_relatorio == models.RelatorioKPI.id_relatorio_fk).filter(models.RelatorioSprint.codigo_projeto_fk == codigo_projeto, models.RelatorioKPI.nome_kpi == nome_kpi).order_by(models.RelatorioSprint.numero_sprint).all()
            historico = [models.FinancialHistoryItem(sprint_number=item.numero_sprint, cost_realized=item.valor_numerico_kpi or 0.0, budget_total=orcamento) for item in kpi_history_orm]
            return historico
        except Exception as e:
            print(f"ERRO AO BUSCAR HISTÓRICO DE KPI (ORM): {e}")
            return []
        finally:
            db.close()