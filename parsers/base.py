# parsers/base.py
import io
from abc import ABC, abstractmethod
from typing import List, Optional

from projeto_api_sonae.models import ParsedReport
from projeto_api_sonae.services import AIService, ReportData, Milestone, KPI
from projeto_api_sonae.utils import helper_limpar_financeiro

class ReportParser(ABC):
    """ Classe base abstrata para todos os parsers """
    def __init__(self, ai_service: AIService): 
        self.ai_service = ai_service
        
    @abstractmethod
    def parse(self, file_stream: io.BytesIO) -> Optional[ParsedReport]: 
        pass

    def _processar_ia(self, projeto_data_raw: dict, milestones_data_raw: list, kpis_data_raw: list) -> Optional[ParsedReport]:
        """
        Helper de IA genérico, modificado para aceitar KPIs.
        """
        try:
            # Valida os dados brutos com Pydantic
            report_obj = ReportData(**projeto_data_raw)
            milestone_objs = [Milestone(**m) for m in milestones_data_raw]
            kpi_objs = [KPI(**k) for k in kpis_data_raw]
            
            # IA Nível 2 - Cálculo de Status (genérico)
            status_calculado_ia = self.ai_service.calculate_status_nlp(report_obj)
            report_obj.overall_status = status_calculado_ia
            
            # IA Nível 3 - Resumo (modificado para ser mais genérico)
            resumo_gerado_ia = self.ai_service.generate_summary_gemini(report_obj, milestone_objs, kpi_objs)
            report_obj.executive_summary = resumo_gerado_ia
            
            # Retorna o pacote de dados completo
            return ParsedReport(projeto=report_obj, milestones=milestone_objs, kpis=kpi_objs)
        
        except Exception as e:
            print(f"ERRO AO VALIDAR DADOS Pydantic ou processar IA: {e}")
            print(f"Dados brutos do projeto: {projeto_data_raw}")
            return None