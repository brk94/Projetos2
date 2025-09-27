# parsers/it_parser.py
import io
import re
from datetime import datetime
from typing import Optional, List

# Libs de Scraper
from pdfminer.high_level import extract_text
import docx
import pandas as pd

# Nossos módulos locais
from projeto_api_sonae.models import ParsedReport
from projeto_api_sonae.utils import helper_extrair_BLOCO_TEXTO, helper_extrair_VALOR_LINHA, helper_limpar_financeiro
from .base import ReportParser # Isto continua correto

#
# A PARTIR DAQUI, SÃO SUAS CLASSES DE PARSER ANTIGAS,
# MAS RENOMEADAS E MODIFICADAS PARA GERAR UMA LISTA DE KPIs
#

class IT_PDFReportParser(ReportParser):
    def parse(self, file_stream: io.BytesIO) -> Optional[ParsedReport]:
        texto_bruto = extract_text(file_stream)
        
        orcamento = helper_extrair_VALOR_LINHA(texto_bruto, r"Orçamento Total do Projeto:\s*(.*?)\n")
        custo = helper_extrair_VALOR_LINHA(texto_bruto, r"Custo Realizado até a Data:\s*(.*?)\n")
        variacao = helper_extrair_VALOR_LINHA(texto_bruto, r"Variação \(Burn Rate\):\s*(.*?)\n")
        
        projeto_data_raw = {
            "project_code": helper_extrair_VALOR_LINHA(texto_bruto, r"ID do Projeto:\s*(PROJ-\d+)"),
            "project_name": helper_extrair_VALOR_LINHA(texto_bruto, r"Relatório de Status Semanal - (.*?)\n"),
            "project_manager": helper_extrair_VALOR_LINHA(texto_bruto, r"Gerente do Projeto:\s*(.*?)\s+Sprint:"),
            "last_sprint_reported": int(helper_extrair_VALOR_LINHA(texto_bruto, r"Sprint:\s*Sprint\s*(\d+)") or 0),
            "overall_status_humano": helper_extrair_VALOR_LINHA(texto_bruto, r"Status Geral \(Saúde\):\s*(.*?)\n"),
            "executive_summary": helper_extrair_BLOCO_TEXTO(texto_bruto, r"Sumário Executivo:\s*([\s\S]*?)(?=3\. Principais Impedimentos e Riscos|$)"),
            "risks_and_impediments": helper_extrair_BLOCO_TEXTO(texto_bruto, r"Principais Impedimentos e Riscos:\s*([\s\S]*?)(?=4\. Próximos Passos|$)"),
            "next_steps": helper_extrair_BLOCO_TEXTO(texto_bruto, r"Próximos Passos:\s*([\s\S]*?)(?=5\. Acompanhamento Financeiro|$)") 
        }
        
        # --- MUDANÇA PRINCIPAL: Criando a lista de KPIs ---
        kpis_data_raw = []
        kpis_data_raw.append({
            "kpi_name": "Orçamento Total", "kpi_category": "Financeiro",
            "kpi_value_numeric": helper_limpar_financeiro(orcamento),
            "kpi_value_text": orcamento
        })
        kpis_data_raw.append({
            "kpi_name": "Custo Realizado", "kpi_category": "Financeiro",
            "kpi_value_numeric": helper_limpar_financeiro(custo),
            "kpi_value_text": custo
        })
        kpis_data_raw.append({
            "kpi_name": "Variação (Burn Rate)", "kpi_category": "Financeiro",
            "kpi_value_numeric": None, # Variação é um texto
            "kpi_value_text": variacao
        })
        
        # Extração de Milestones (sem mudança)
        bloco_tabela = helper_extrair_BLOCO_TEXTO(texto_bruto, r"6\. Acompanhamento de Marcos \(Milestones\):\s*([\s\S]*?)(?=\Z)")
        milestones_data_raw = []
        if bloco_tabela:
            padrao_linha_tabela = re.compile(
                r"^(.*?)\s+(Concluído|Atrasado|Em\s+Andamento|Pendente)\s+(\d{2}/\d{2}/\d{4})\s+(.*?)$", 
                re.IGNORECASE | re.MULTILINE
            )
            for match in padrao_linha_tabela.finditer(bloco_tabela):
                try: data_obj = datetime.strptime(match.group(3), '%d/%m/%Y').date()
                except ValueError: data_obj = None
                milestones_data_raw.append({
                    "description": match.group(1).strip().replace('\n', ' '),
                    "status": match.group(2).strip().replace('\n', ''),
                    "date_planned": data_obj,
                    "date_actual_or_revised": match.group(4).strip()
                })
                
        # Chama o helper genérico com os 3 pacotes de dados
        return self._processar_ia(projeto_data_raw, milestones_data_raw, kpis_data_raw)


class IT_DocxReportParser(ReportParser):
    def parse(self, file_stream: io.BytesIO) -> Optional[ParsedReport]:
        doc = docx.Document(file_stream)
        full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip() != ""]) 
        
        orcamento = helper_extrair_VALOR_LINHA(full_text, r"Orçamento Total do Projeto:\s*(.*?)\n")
        custo = helper_extrair_VALOR_LINHA(full_text, r"Custo Realizado até a Data:\s*(.*?)\n")
        variacao = helper_extrair_VALOR_LINHA(full_text, r"Variação \(Burn Rate\):\s*(.*?)\n")
        
        projeto_data_raw = {
            "project_code": helper_extrair_VALOR_LINHA(full_text, r"ID do Projeto:\s*(PROJ-\d+)"),
            "project_name": helper_extrair_VALOR_LINHA(full_text, r"Relatório de Status Semanal - (.*?)\n"), 
            "project_manager": helper_extrair_VALOR_LINHA(full_text, r"Gerente do Projeto:\s*(.*?)\s+Sprint:"),
            "last_sprint_reported": int(helper_extrair_VALOR_LINHA(full_text, r"Sprint:\s*Sprint\s*(\d+)") or 0),
            "overall_status_humano": helper_extrair_VALOR_LINHA(full_text, r"Status Geral \(Saúde\):\s*(.*?)\n"),
            "executive_summary": helper_extrair_BLOCO_TEXTO(full_text, r"Sumário Executivo:\s*([\s\S]*?)(?=3\. Principais Impedimentos e Riscos|$)"),
            "risks_and_impediments": helper_extrair_BLOCO_TEXTO(full_text, r"Principais Impedimentos e Riscos:\s*([\s\S]*?)(?=4\. Próximos Passos|$)"),
            "next_steps": helper_extrair_BLOCO_TEXTO(full_text, r"Próximos Passos:\s*([\s\S]*?)(?=5\. Acompanhamento Financeiro|$)"),
        }
        
        # --- MUDANÇA PRINCIPAL: Criando a lista de KPIs ---
        kpis_data_raw = []
        kpis_data_raw.append({
            "kpi_name": "Orçamento Total", "kpi_category": "Financeiro",
            "kpi_value_numeric": helper_limpar_financeiro(orcamento),
            "kpi_value_text": orcamento
        })
        kpis_data_raw.append({
            "kpi_name": "Custo Realizado", "kpi_category": "Financeiro",
            "kpi_value_numeric": helper_limpar_financeiro(custo),
            "kpi_value_text": custo
        })
        kpis_data_raw.append({
            "kpi_name": "Variação (Burn Rate)", "kpi_category": "Financeiro",
            "kpi_value_numeric": None,
            "kpi_value_text": variacao
        })
        
        # Extração de Milestones (sem mudança)
        milestones_data_raw = []
        try:
            tabela = doc.tables[0] 
            for row in tabela.rows[1:]: 
                try: data_planned_obj = datetime.strptime(row.cells[2].text.strip(), '%d/%m/%Y').date()
                except ValueError: data_planned_obj = None
                data_rev_str = row.cells[3].text.strip()
                data_revisada_final = None
                if data_rev_str.lower() not in ["(pendente)", ""]:
                    try: data_revisada_final = datetime.strptime(data_rev_str, '%d/%m/%Y').date().isoformat()
                    except ValueError: data_revisada_final = data_rev_str
                milestones_data_raw.append({
                    "description": row.cells[0].text.strip(),
                    "status": row.cells[1].text.strip(),
                    "date_planned": data_planned_obj,
                    "date_actual_or_revised": data_revisada_final
                })
        except IndexError: pass
        
        return self._processar_ia(projeto_data_raw, milestones_data_raw, kpis_data_raw)


class IT_XLSXReportParser(ReportParser):
    def parse(self, file_stream: io.BytesIO) -> Optional[ParsedReport]:
        df_resumo = pd.read_excel(file_stream, sheet_name="Resumo_Executivo", header=None)
        resumo_dict = df_resumo.set_index(0)[1].to_dict()
        
        orcamento = str(resumo_dict.get("Orçamento Total:"))
        custo = str(resumo_dict.get("Custo Realizado:"))
        
        projeto_data_raw = {
            "project_code": resumo_dict.get("ID do Projeto:"),
            "project_name": resumo_dict.get("Nome do Projeto:"),
            "project_manager": resumo_dict.get("Gerente do Projeto:"),
            "last_sprint_reported": int(resumo_dict.get("Sprint:", 0)),
            "overall_status_humano": resumo_dict.get("Status Geral (Saúde):"),
            "executive_summary": resumo_dict.get("Resumo:"),
            "risks_and_impediments": None, "next_steps": None
        }
        
        # --- MUDANÇA PRINCIPAL: Criando a lista de KPIs ---
        kpis_data_raw = []
        kpis_data_raw.append({
            "kpi_name": "Orçamento Total", "kpi_category": "Financeiro",
            "kpi_value_numeric": helper_limpar_financeiro(orcamento),
            "kpi_value_text": orcamento
        })
        kpis_data_raw.append({
            "kpi_name": "Custo Realizado", "kpi_category": "Financeiro",
            "kpi_value_numeric": helper_limpar_financeiro(custo),
            "kpi_value_text": custo
        })
        
        # Extração de Milestones (sem mudança)
        df_milestones = pd.read_excel(file_stream, sheet_name="Cronograma_Milestones")
        milestones_data_raw_dict = df_milestones.to_dict('records')
        milestones_data_raw = []
        for row in milestones_data_raw_dict:
            milestones_data_raw.append({
                "description": row.get('Descrição do Marco (Milestone)'),
                "status": row.get('Status do Marco'),
                "date_planned": pd.to_datetime(row.get('Data Prevista')).date() if pd.notna(row.get('Data Prevista')) else None,
                "date_actual_or_revised": None
            })
            
        return self._processar_ia(projeto_data_raw, milestones_data_raw, kpis_data_raw)