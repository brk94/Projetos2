# parsers/retail_parser.py
import io
from typing import Optional
from parsers.base import ReportParser
from projeto_api_sonae.models import ParsedReport

class Retail_XLSXReportParser(ReportParser):
    def parse(self, file_stream: io.BytesIO) -> Optional[ParsedReport]:
        #
        # TODO: Implementar a lógica de parser para relatórios de Retalho.
        # Ex: ler um Excel e procurar por "NPS" ou "% Quebra"
        #
        print("Parser de Retalho ainda não implementado.")
        return None