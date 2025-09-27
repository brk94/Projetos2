# parsers/factory.py
from typing import Optional

# Nossos módulos
from projeto_api_sonae.services import AIService # A factory precisa do AIService para injetar nos parsers
from parsers.base import ReportParser
from parsers.parser_ti import IT_PDFReportParser, IT_DocxReportParser, IT_XLSXReportParser
from parsers.retail_parser import Retail_XLSXReportParser
from projeto_api_sonae.constants import ProjectTypes

class ReportParserFactory:
    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service
        print("ReportParserFactory (Refatorada) inicializada.")
    
    def get_parser(self, filename: str, project_type: str) -> Optional[ReportParser]:
        """
        Retorna o parser correto com base no TIPO DE PROJETO e extensão do arquivo.
        """
        
        if project_type == ProjectTypes.TECH:
            if filename.endswith(".pdf"): 
                return IT_PDFReportParser(self.ai_service)
            elif filename.endswith(".docx"): 
                return IT_DocxReportParser(self.ai_service)
            elif filename.endswith((".xlsx", ".xls")): 
                return IT_XLSXReportParser(self.ai_service)
        
        elif project_type == ProjectTypes.RETAIL:
            if filename.endswith((".xlsx", ".xls")):
                # Supomos que relatórios de retalho venham em Excel
                return Retail_XLSXReportParser(self.ai_service)
            
        # Adicione outros 'elif project_type == ...' aqui no futuro

        print(f"Aviso: Nenhum parser encontrado para project_type='{project_type}' e filename='{filename}'")
        return None