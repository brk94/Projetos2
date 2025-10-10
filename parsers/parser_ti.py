# parsers/parser_ti.py
import io
import re
from datetime import datetime
from typing import Optional

# Libs de Scraper
from pdfminer.high_level import extract_text
import docx
import pandas as pd

# Nossos módulos locais
from projeto_api_sonae.models import ParsedReport, Milestone, KPI, AreaNegocioEnum
from projeto_api_sonae.utils import helper_extrair_BLOCO_TEXTO, helper_extrair_VALOR_LINHA, helper_limpar_financeiro
from .base import ReportParser

class IT_PDFReportParser(ReportParser):
    def parse(self, file_stream: io.BytesIO) -> Optional[ParsedReport]:
        texto_bruto = extract_text(file_stream)
        
        # --- Extração de Dados Genéricos ---
        projeto_data = {
            "codigo_projeto": helper_extrair_VALOR_LINHA(texto_bruto, r"ID do Projeto:\s*(PROJ-\d+)"),
            "nome_projeto": helper_extrair_VALOR_LINHA(texto_bruto, r"Relatório de Status Semanal - (.*?)\n"),
            "gerente_projeto": helper_extrair_VALOR_LINHA(texto_bruto, r"Gerente do Projeto:\s*(.*?)\s+Sprint:"),
            "numero_sprint": int(helper_extrair_VALOR_LINHA(texto_bruto, r"Sprint:\s*Sprint\s*(\d+)") or 0),
            "status_geral": helper_extrair_VALOR_LINHA(texto_bruto, r"Status Geral \(Saúde\):\s*(.*?)\n"),
            "resumo_executivo": helper_extrair_BLOCO_TEXTO(texto_bruto, r"Sumário Executivo:\s*([\s\S]*?)(?=3\. Principais Impedimentos e Riscos|$)"),
            "riscos_e_impedimentos": helper_extrair_BLOCO_TEXTO(texto_bruto, r"Principais Impedimentos e Riscos:\s*([\s\S]*?)(?=4\. Próximos Passos|$)"),
            "proximos_passos": helper_extrair_BLOCO_TEXTO(texto_bruto, r"Próximos Passos:\s*([\s\S]*?)(?=5\. Acompanhamento Financeiro|$)") 
        }

        # --- Extração de KPIs ---
        orcamento = helper_extrair_VALOR_LINHA(texto_bruto, r"Orçamento Total do Projeto:\s*(.*?)\n")
        custo = helper_extrair_VALOR_LINHA(texto_bruto, r"Custo Realizado até a Data:\s*(.*?)\n")
        kpis_data = [
            KPI(nome_kpi="Orçamento Total", categoria_kpi="Financeiro", valor_numerico_kpi=helper_limpar_financeiro(orcamento), valor_texto_kpi=orcamento),
            KPI(nome_kpi="Custo Realizado", categoria_kpi="Financeiro", valor_numerico_kpi=helper_limpar_financeiro(custo), valor_texto_kpi=custo)
        ]

        # --- Extração de Dados Específicos de TI (agora no nível principal) ---
        # ATENÇÃO: Adicione aqui o regex para extrair os story points do seu relatório
        story_points_planejados = None 
        story_points_entregues = None
        
        # --- Extração de Milestones ---
        bloco_tabela = helper_extrair_BLOCO_TEXTO(texto_bruto, r"6\. Acompanhamento de Marcos \(Milestones\):\s*([\s\S]*?)(?=\Z)")
        milestones_data = []
        if bloco_tabela:
            padrao_linha_tabela = re.compile(r"^(.*?)\s+(Concluído|Atrasado|Em\s+Andamento|Pendente|Em Risco)\s+(\d{2}/\d{2}/\d{4})\s+(.*?)$", re.IGNORECASE | re.MULTILINE)
            for match in padrao_linha_tabela.finditer(bloco_tabela):
                try: data_obj = datetime.strptime(match.group(3), '%d/%m/%Y').date()
                except ValueError: data_obj = None
                milestones_data.append(Milestone(
                    descricao=match.group(1).strip().replace('\n', ' '),
                    status=match.group(2).strip().replace('\n', ''),
                    data_planejada=data_obj,
                    data_real_ou_revisada=match.group(4).strip()
                ))
        
        # Monta e retorna o objeto ParsedReport simplificado
        return ParsedReport(
            **projeto_data,
            area_negocio=AreaNegocioEnum.TI,
            milestones=milestones_data,
            kpis=kpis_data,
            story_points_planejados=story_points_planejados,
            story_points_entregues=story_points_entregues
        )


class IT_DocxReportParser(ReportParser):
    def parse(self, file_stream: io.BytesIO) -> Optional[ParsedReport]:
        doc = docx.Document(file_stream)
        full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip() != ""]) 

        projeto_data = {
            "codigo_projeto": helper_extrair_VALOR_LINHA(full_text, r"ID do Projeto:\s*(PROJ-\d+)"),
            "nome_projeto": helper_extrair_VALOR_LINHA(full_text, r"Relatório de Status Semanal - (.*?)\n"), 
            "gerente_projeto": helper_extrair_VALOR_LINHA(full_text, r"Gerente do Projeto:\s*(.*?)\s+Sprint:"),
            "numero_sprint": int(helper_extrair_VALOR_LINHA(full_text, r"Sprint:\s*Sprint\s*(\d+)") or 0),
            "status_geral": helper_extrair_VALOR_LINHA(full_text, r"Status Geral \(Saúde\):\s*(.*?)\n"),
            "resumo_executivo": helper_extrair_BLOCO_TEXTO(full_text, r"Sumário Executivo:\s*([\s\S]*?)(?=3\. Principais Impedimentos e Riscos|$)"),
            "riscos_e_impedimentos": helper_extrair_BLOCO_TEXTO(full_text, r"Principais Impedimentos e Riscos:\s*([\s\S]*?)(?=4\. Próximos Passos|$)"),
            "proximos_passos": helper_extrair_BLOCO_TEXTO(full_text, r"Próximos Passos:\s*([\s\S]*?)(?=5\. Acompanhamento Financeiro|$)"),
        }
        
        orcamento = helper_extrair_VALOR_LINHA(full_text, r"Orçamento Total do Projeto:\s*(.*?)\n")
        custo = helper_extrair_VALOR_LINHA(full_text, r"Custo Realizado até a Data:\s*(.*?)\n")
        
        kpis_data = [
            KPI(nome_kpi="Orçamento Total", categoria_kpi="Financeiro", valor_numerico_kpi=helper_limpar_financeiro(orcamento), valor_texto_kpi=orcamento),
            KPI(nome_kpi="Custo Realizado", categoria_kpi="Financeiro", valor_numerico_kpi=helper_limpar_financeiro(custo), valor_texto_kpi=custo)
        ]

        # ATENÇÃO: Adicione aqui o regex para extrair os story points
        story_points_planejados = None
        story_points_entregues = None
        
        milestones_data = []
        try:
            tabela = doc.tables[0] 
            for row in tabela.rows[1:]: 
                try: data_planned_obj = datetime.strptime(row.cells[2].text.strip(), '%d/%m/%Y').date()
                except ValueError: data_planned_obj = None
                
                milestones_data.append(Milestone(
                    descricao=row.cells[0].text.strip(),
                    status=row.cells[1].text.strip(),
                    data_planejada=data_planned_obj,
                    data_real_ou_revisada=row.cells[3].text.strip()
                ))
        except IndexError: pass
        
        return ParsedReport(
            **projeto_data,
            area_negocio=AreaNegocioEnum.TI,
            milestones=milestones_data,
            kpis=kpis_data,
            story_points_planejados=story_points_planejados,
            story_points_entregues=story_points_entregues
        )


class IT_XLSXReportParser(ReportParser):
    def parse(self, file_stream: io.BytesIO) -> Optional[ParsedReport]:
        df_resumo = pd.read_excel(file_stream, sheet_name="Resumo_Executivo", header=None)
        resumo_dict = df_resumo.set_index(0)[1].to_dict()
        
        projeto_data = {
            "codigo_projeto": resumo_dict.get("ID do Projeto:"),
            "nome_projeto": resumo_dict.get("Nome do Projeto:"),
            "gerente_projeto": resumo_dict.get("Gerente do Projeto:"),
            "numero_sprint": int(resumo_dict.get("Sprint:", 0)),
            "status_geral": resumo_dict.get("Status Geral (Saúde):"),
            "resumo_executivo": resumo_dict.get("Resumo:"),
            "riscos_e_impedimentos": None, "proximos_passos": None
        }
        
        orcamento = str(resumo_dict.get("Orçamento Total:"))
        custo = str(resumo_dict.get("Custo Realizado:"))
        
        kpis_data = [
            KPI(nome_kpi="Orçamento Total", categoria_kpi="Financeiro", valor_numerico_kpi=helper_limpar_financeiro(orcamento), valor_texto_kpi=orcamento),
            KPI(nome_kpi="Custo Realizado", categoria_kpi="Financeiro", valor_numerico_kpi=helper_limpar_financeiro(custo), valor_texto_kpi=custo)
        ]

        # ATENÇÃO: Adicione aqui a lógica para buscar estes dados no seu Excel
        story_points_planejados = None
        story_points_entregues = None
        
        df_milestones = pd.read_excel(file_stream, sheet_name="Cronograma_Milestones")
        milestones_data = []
        for index, row in df_milestones.iterrows():
            milestones_data.append(Milestone(
                descricao=row.get('Descrição do Marco (Milestone)'),
                status=row.get('Status do Marco'),
                data_planejada=pd.to_datetime(row.get('Data Prevista')).date() if pd.notna(row.get('Data Prevista')) else None,
                data_real_ou_revisada=None
            ))
            
        return ParsedReport(
            **projeto_data,
            area_negocio=AreaNegocioEnum.TI,
            milestones=milestones_data,
            kpis=kpis_data,
            story_points_planejados=story_points_planejados,
            story_points_entregues=story_points_entregues
        )