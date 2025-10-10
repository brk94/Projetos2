# parsers/base.py
import io
from abc import ABC, abstractmethod
from typing import Optional

from projeto_api_sonae.models import ParsedReport
from projeto_api_sonae.services import AIService

class ReportParser(ABC):
    """ Classe base abstrata para todos os parsers. """
    def __init__(self, ai_service: AIService): 
        # O ai_service ainda pode ser útil no futuro para enriquecer
        # os dados dentro de um parser específico.
        self.ai_service = ai_service
        
    @abstractmethod
    def parse(self, file_stream: io.BytesIO) -> Optional[ParsedReport]: 
        pass