# services.py (MODIFICADO)

import io
import re
from datetime import datetime
from typing import List, Optional

from . import models
from . import utils

# Nossos módulos locais
from .models import (
    # Modelos ORM
    Projeto, RelatorioSprint, MilestoneHistorico, RelatorioKPI, # <- Adicionado RelatorioKPI
    # Modelos Pydantic
    ReportData, Milestone, KPI, ParsedReport, DashboardStats, ProjectListItem, 
    SprintListItem, ReportDetail, ReportDetailResponse
)
from .utils import helper_extrair_BLOCO_TEXTO, helper_extrair_VALOR_LINHA, helper_limpar_financeiro

# Libs de Banco de Dados
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case, desc

#
# AS CLASSES DE PARSER FORAM MOVIDAS PARA O DIRETÓRIO 'parsers/'
#

# --- CLASSE DE SERVIÇO DE IA (MODIFICADA) ---
class AIService:
    """
    Encapsula toda a lógica de IA (Nível 2 SpaCy e Nível 3 Gemini).
    """
    def __init__(self, nlp_model, gemini_model, gemini_config):
        self.nlp = nlp_model
        self.gemini_model = gemini_model
        self.gemini_config = gemini_config
        # ... (LEMMAS_DE_RISCO, etc. continuam iguais) ...
        print("AIService inicializado.")

    def calculate_status_nlp(self, report: ReportData) -> str:
        # Nenhuma mudança necessária aqui, já era genérico
        status_calculado = (report.overall_status_humano or "Em Dia").strip()
        # ... (lógica de NLP continua igual) ...
        return status_calculado

    def generate_summary_gemini(self, report: ReportData, milestones: List[Milestone], kpis: List[KPI]) -> str:
        """ Modificado para receber KPIs genéricos, não dados financeiros fixos """
        if not self.gemini_model:
            return report.executive_summary or "Falha ao gerar resumo de IA. Resumo original não encontrado."
        
        # Transforma a lista de KPIs em texto para o prompt
        kpis_texto_limpo = ""
        if kpis:
            for item in kpis:
                kpi_valor = item.kpi_value_text or f"{item.kpi_value_numeric:,.2f}"
                kpis_texto_limpo += f"- KPI: '{item.kpi_name}' ({item.kpi_category}), Valor: '{kpi_valor}'.\n"
        else:
            kpis_texto_limpo = "Nenhuma métrica (KPI) foi extraída."

        milestones_texto_limpo = ""
        if milestones:
            for item in milestones:
                milestones_texto_limpo += f"- Marco: '{item.description}', está com status: '{item.status}'.\n"
        else:
            milestones_texto_limpo = "Nenhum milestone detalhado foi extraído."
        
        prompt = f"""
        Você é um Diretor de Projetos (PMO) sênior. Escreva um resumo executivo curto (máximo 4 frases), 
        profissional e direto (em português do Brasil) com base NOS SEGUINTES DADOS BRUTOS de um projeto:

        - Nome do Projeto: {report.project_name}
        - Status Calculado (pela IA Nível 2): {report.overall_status}
        - Período (Sprint/Fase): {report.sprint_number}
        
        - Métricas Chave (KPIs) deste período:
          {kpis_texto_limpo}
          
        - Lista de Milestones (Metas do Projeto):
          {milestones_texto_limpo}

        Por favor, gere um "Sumário Executivo" que destaque os pontos principais.
        Use os KPIs para explicar o desempenho.
        Seja direto. NÃO inclua "Riscos e Impedimentos".
        """
        try:
            response = self.gemini_model.generate_content(prompt, generation_config=self.gemini_config)
            return response.text.replace("*", "").strip()
        except Exception as e:
            print(f"ERRO AO CHAMAR API GEMINI (NÍVEL 3): {e}")
            return report.executive_summary or 'Falha ao gerar resumo de IA. Resumo original não encontrado.'


# -----------------------------------------------------------------
# CLASSE DE REPOSITÓRIO DE BANCO de DADOS (MODIFICADA)
# -----------------------------------------------------------------

class DatabaseRepository:
    """
    Encapsula TODA a lógica de banco de dados usando o ORM.
    Agora é 100% genérico.
    """
    def __init__(self, session_factory):
        self.session_factory = session_factory
        print("DatabaseRepository (ORM) inicializado.")

    def _get_db(self) -> Session:
        return self.session_factory()

    def get_project_type(self, project_code: str) -> Optional[str]:
        """ NOVA FUNÇÃO: Busca o 'project_type' para a Factory """
        db: Session = self._get_db()
        try:
            projeto = db.query(Projeto.project_type).filter(Projeto.project_code == project_code).first()
            if projeto:
                return projeto.project_type
            return None
        finally:
            db.close()

    def save_parsed_report(self, report: ParsedReport, project_type: str) -> int:
        """
        Salva um relatório processado (projeto + milestones + kpis) no DB.
        Agora também recebe o project_type para criar novos projetos.
        """
        projeto_data = report.projeto
        milestones_data = report.milestones
        kpis_data = report.kpis
        
        db: Session = self._get_db()
        try:
            # PASSO A: UPSERT Projeto "Pai"
            projeto_orm = db.query(Projeto).get(projeto_data.project_code)
            
            if projeto_orm:
                # Atualiza o projeto existente
                projeto_orm.project_name = projeto_data.project_name
                projeto_orm.project_manager = projeto_data.project_manager
                # ... (lógica de atualização do budget_total via KPI) ...
                for kpi in kpis_data:
                    if kpi.kpi_name == "Orçamento Total":
                        projeto_orm.budget_total = kpi.kpi_value_numeric or 0.0
                        break
            else:
                # Cria um novo projeto
                new_budget = 0.0
                for kpi in kpis_data:
                    if kpi.kpi_name == "Orçamento Total":
                        new_budget = kpi.kpi_value_numeric or 0.0
                        break
                
                projeto_orm = Projeto(
                    project_code=projeto_data.project_code,
                    project_name=projeto_data.project_name,
                    project_manager=projeto_data.project_manager,
                    budget_total=new_budget,
                    project_type=project_type # <- USA O NOVO CAMPO
                )
                db.add(projeto_orm)
            
            # PASSO B: INSERT Relatório Histórico (agora genérico)
            # ... (o resto da função (Passos B, C, D) continua exatamente igual) ...
            relatorio_orm = RelatorioSprint(
                **projeto_data.dict(exclude={
                    'project_code', 'project_name', 'project_manager', 
                    'overall_status_humano'
                }),
                report_date=datetime.utcnow().date(),
                project_code_fk=projeto_data.project_code
            )
            db.add(relatorio_orm)
            db.flush() 
            new_report_id = relatorio_orm.report_id
            
            if milestones_data:
                milestones_orm = [
                    MilestoneHistorico(
                        **milestone.dict(exclude={'slippage'}),
                        report_id_fk=new_report_id
                    ) for milestone in milestones_data
                ]
                db.add_all(milestones_orm)
            
            if kpis_data:
                kpis_orm = [
                    RelatorioKPI(
                        **kpi.dict(), 
                        report_id_fk=new_report_id
                    ) for kpi in kpis_data
                ]
                db.add_all(kpis_orm)
            
            db.commit() 
            print(f"SUCESSO (ORM): Histórico do Sprint {projeto_data.sprint_number} salvo para o Projeto {projeto_data.project_code} (Report ID: {new_report_id}).")
            return new_report_id
        
        except Exception as e:
            db.rollback() 
            print(f"ERRO DE TRANSAÇÃO ORM NO BANCO DE DADOS: {e}")
            raise e
        finally:
            db.close()

    def get_dashboard_stats(self) -> DashboardStats:
        """ Busca os dados para o /dashboard-executivo/ """
        db: Session = self._get_db()
        try:
            # Subquery para o último sprint (sem mudança)
            subquery = db.query(
                RelatorioSprint.project_code_fk,
                func.max(RelatorioSprint.sprint_number).label('max_sprint')
            ).group_by(RelatorioSprint.project_code_fk).subquery()
            
            # Subquery para somar o Custo Realizado (KPI)
            # Esta é a parte mais complexa da refatoração
            kpi_subquery = db.query(
                RelatorioSprint.project_code_fk,
                func.sum(RelatorioKPI.kpi_value_numeric).label("total_investido")
            ).join(
                RelatorioKPI, RelatorioSprint.report_id == RelatorioKPI.report_id_fk
            ).filter(
                RelatorioKPI.kpi_name == "Custo Realizado" # Filtra apenas pelo KPI de custo
            ).group_by(RelatorioSprint.project_code_fk).subquery()

            # Query principal
            query = db.query(
                func.count().label("total_projetos"),
                func.sum(case((RelatorioSprint.overall_status == 'Em Dia', 1), else_=0)).label("projetos_em_dia"),
                func.sum(case((RelatorioSprint.overall_status == 'Em Risco', 1), else_=0)).label("projetos_em_risco"),
                func.sum(case((RelatorioSprint.overall_status == 'Atrasado', 1), else_=0)).label("projetos_atrasados"),
                # Opcional: Soma o total_investido da kpi_subquery
                # Por simplicidade, podemos buscar isso separado ou deixar em 0.0
            ).join(
                subquery,
                (RelatorioSprint.project_code_fk == subquery.c.project_code_fk) &
                (RelatorioSprint.sprint_number == subquery.c.max_sprint)
            )
            
            resultado = query.one()
            
            # Busca o investimento total separadamente
            investimento_total = db.query(func.sum(RelatorioKPI.kpi_value_numeric)).filter(
                RelatorioKPI.kpi_name == "Custo Realizado"
            ).scalar() or 0.0
            
            if resultado and resultado.total_projetos > 0:
                stats = resultado._mapping.copy()
                stats["investimento_total_executado"] = investimento_total
                return DashboardStats(**stats)
            
        except Exception as e:
            print(f"ERRO AO BUSCAR DADOS DO DASHBOARD (ORM): {e}")
        finally:
            db.close()
            
        return DashboardStats(total_projetos=0, projetos_em_dia=0, projetos_em_risco=0, projetos_atrasados=0, investimento_total_executado=0.0)

    def get_project_list(self) -> List[models.ProjectListItem]:
        """ Busca os dados para /projetos/lista/ usando o ORM. """
        db: Session = self._get_db()
        try:
            # Usamos 'models.Projeto' para sermos explícitos
            projetos_orm = db.query(models.Projeto).order_by(models.Projeto.project_name).all()

            # --- CORREÇÃO AQUI ---
            # Voltamos ao mapeamento manual, que funciona 100%
            return [
                models.ProjectListItem(code=p.project_code, name=p.project_name) 
                for p in projetos_orm
            ]

        except Exception as e:
            # O seu log de erro vai pegar o erro aqui
            print(f"ERRO AO BUSCAR LISTA DE PROJETOS (ORM): {e}")
            return []
        finally:
            db.close()

    def get_sprints_do_projeto(self, project_code: str) -> List[SprintListItem]:
        # Nenhuma mudança necessária
        db: Session = self._get_db()
        try:
            sprints_orm = db.query(RelatorioSprint).filter(
                RelatorioSprint.project_code_fk == project_code
            ).order_by(desc(RelatorioSprint.sprint_number)).all()
            return [SprintListItem.model_validate(s) for s in sprints_orm]
        except Exception as e:
            print(f"ERRO AO BUSCAR LISTA DE SPRINTS (ORM): {e}")
            return []
        finally:
            db.close()

    def get_detalhe_do_relatorio(self, report_id: int) -> Optional[ReportDetailResponse]:
        """ 
        Busca os dados para /relatorio/detalhe/{report_id} 
        Modificado para buscar KPIs genéricos
        """
        db: Session = self._get_db()
        try:
            # 1. Pega o relatório ATUAL (e seu projeto pai, milestones e KPIs)
            relatorio_atual = db.query(RelatorioSprint).options(
                joinedload(RelatorioSprint.projeto),
                joinedload(RelatorioSprint.milestones),
                joinedload(RelatorioSprint.kpis) # <- Carrega os KPIs junto
            ).get(report_id)
            
            if not relatorio_atual:
                return None
            
            projeto_pai = relatorio_atual.projeto
            
            status_anterior = None 
            prev_milestones_map = {} 

            # 2. Busca o relatório ANTERIOR (sem mudança)
            if relatorio_atual.sprint_number > 1: 
                prev_sprint_num = relatorio_atual.sprint_number - 1
                relatorio_anterior = db.query(RelatorioSprint).options(
                    joinedload(RelatorioSprint.milestones)
                ).filter(
                    RelatorioSprint.project_code_fk == relatorio_atual.project_code_fk,
                    RelatorioSprint.sprint_number == prev_sprint_num
                ).first()
                
                if relatorio_anterior:
                    status_anterior = relatorio_anterior.overall_status
                    prev_milestones_map = {
                        m.description: m for m in relatorio_anterior.milestones
                    }

            # 3. Pega os milestones e KPIs ATUAIS (já carregados)
            milestones_atuais_orm = relatorio_atual.milestones
            kpis_atuais_orm = relatorio_atual.kpis

            # 4. Converte KPIs ORM para Pydantic
            kpis_processados = [KPI.model_validate(k) for k in kpis_atuais_orm]

            # 5. Processa Milestones (Cálculo de Slippage) (sem mudança)
            milestones_processados = []
            for curr_m_orm in milestones_atuais_orm:
                curr_m = Milestone.model_validate(curr_m_orm)
                # ... (lógica de slippage continua a mesma) ...
                milestones_processados.append(curr_m)

            # 6. Monta o objeto de resposta final
            report_detail_obj = ReportDetail(
                **relatorio_atual.__dict__,
                project_code=projeto_pai.project_code,
                project_name=projeto_pai.project_name,
                project_manager=projeto_pai.project_manager,
                budget_total=projeto_pai.budget_total,
                status_anterior=status_anterior
            )
            
            return ReportDetailResponse(
                projeto=report_detail_obj,
                milestones=milestones_processados,
                kpis=kpis_processados # <- Envia os KPIs
            )

        except Exception as e:
            print(f"ERRO AO BUSCAR DETALHE DO RELATÓRIO (ORM) {report_id}: {e}")
            return None
        finally:
            db.close()

    def get_kpi_history(self, project_code: str, kpi_name: str) -> List[models.FinancialHistoryItem]:
        """
        NOVA FUNÇÃO: Busca o histórico de um KPI numérico específico 
        e o orçamento total do projeto.
        """
        db: Session = self._get_db()
        try:
            # 1. Busca o orçamento total do projeto (que é fixo)
            projeto = db.query(models.Projeto.budget_total).filter(models.Projeto.project_code == project_code).first()
            budget = projeto.budget_total if projeto else 0.0

            # 2. Busca o histórico do KPI especificado (ex: "Custo Realizado")
            kpi_history_orm = db.query(
                models.RelatorioSprint.sprint_number, 
                models.RelatorioKPI.kpi_value_numeric
            ).join(
                models.RelatorioKPI, 
                models.RelatorioSprint.report_id == models.RelatorioKPI.report_id_fk
            ).filter(
                models.RelatorioSprint.project_code_fk == project_code,
                models.RelatorioKPI.kpi_name == kpi_name
            ).order_by(
                models.RelatorioSprint.sprint_number
            ).all()

            # 3. Monta a lista de resposta no formato que o gráfico espera
            historico = [
                models.FinancialHistoryItem(
                    sprint_number=item.sprint_number,
                    cost_realized=item.kpi_value_numeric or 0.0,
                    budget_total=budget
                ) for item in kpi_history_orm
            ]
            
            return historico

        except Exception as e:
            print(f"ERRO AO BUSCAR HISTÓRICO DE KPI (ORM): {e}")
            return []
        finally:
            db.close()