# parsers/factory.py
from .base import ReportParser
from .parser_ti import IT_PDFReportParser, IT_DocxReportParser, IT_XLSXReportParser  # se não usar XLSX, pode remover
from projeto_api_sonae.models import AreaNegocioEnum

class ReportParserFactory:
    def __init__(self, ai_service):
        self.ai_service = ai_service

    def _normalize_project_type(self, project_type):
        if isinstance(project_type, AreaNegocioEnum):
            return project_type.value  # "TI", "Retalho", "RH", "Marketing"
        if isinstance(project_type, str):
            s = project_type.strip().lower()
            if s in ("ti", "retalho", "rh", "marketing"):
                return s.capitalize() if s != "ti" else "TI"
        return None

    def get_parser(self, filename: str, project_type) -> ReportParser | None:
        pt = self._normalize_project_type(project_type)
        if pt != "TI":
            # Tudo que não é TI fica desativado por enquanto
            return None

        name = filename.lower()
        if name.endswith(".pdf"):
            return IT_PDFReportParser(ai_service=self.ai_service)
        if name.endswith(".docx"):
            return IT_DocxReportParser(ai_service=self.ai_service)
        # Se quiser, mantenha XLSX para TI; senão, retorne None
        # if name.endswith(".xlsx"):
        #     return IT_XLSXReportParser(ai_service=self.ai_service)

        return None
