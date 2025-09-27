# models.py (MODIFICADO)

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime

# --- Imports do SQLAlchemy ORM ---
from sqlalchemy import Column, String, Integer, Float, Date, Text, ForeignKey
from sqlalchemy.orm import relationship
from .config import Base # Importamos a Base declarativa do config
from . import constants

# -----------------------------------------------------------------
# SEÇÃO 1: MODELOS ORM (MODIFICADOS)
# -----------------------------------------------------------------

class Projeto(Base):
    """
    Representa a tabela 'Projetos'.
    ADICIONAMOS 'project_type' para saber qual parser usar.
    """
    __tablename__ = "Projetos"
    
    project_code = Column(String(50), primary_key=True, index=True)
    project_name = Column(String(255), nullable=False)
    project_manager = Column(String(255))
    budget_total = Column(Float, default=0.0)
    
    # NOVO CAMPO: 'TI', 'Retalho', 'Saude', etc.
    # Isso é essencial para a Factory saber qual parser chamar.
    project_type = Column(String(50), nullable=False, default=constants.DEFAULT_TYPE)
    
    relatorios = relationship("RelatorioSprint", back_populates="projeto")

class RelatorioSprint(Base):
    """
    Representa a tabela 'Relatorios_Sprint'.
    REMOVEMOS os campos específicos de TI (custo, variação, etc.)
    """
    __tablename__ = "Relatorios_Sprint"
    
    report_id = Column(Integer, primary_key=True, index=True)
    sprint_number = Column(Integer, nullable=False) # Mantido por ser um "período" genérico
    report_date = Column(Date, default=datetime.utcnow)
    overall_status = Column(String(50))
    executive_summary = Column(Text, nullable=True)
    risks_and_impediments = Column(Text, nullable=True)
    next_steps = Column(Text, nullable=True)
    
    # --- CAMPOS REMOVIDOS ---
    # cost_realized = Column(Float, default=0.0) -> MOVEMOS PARA KPI
    # variance_text = Column(String(255), nullable=True) -> MOVEMOS PARA KPI
    # financial_narrative = Column(Text, nullable=True) -> MOVEMOS PARA KPI
    
    project_code_fk = Column(String(50), ForeignKey("Projetos.project_code"))
    
    projeto = relationship("Projeto", back_populates="relatorios")
    milestones = relationship("MilestoneHistorico", back_populates="relatorio")
    
    # NOVO RELACIONAMENTO: Um relatório agora tem uma lista de KPIs
    kpis = relationship("RelatorioKPI", back_populates="relatorio", cascade="all, delete-orphan")

class MilestoneHistorico(Base):
    """
    Esta tabela está perfeita, é genérica. NENHUMA MUDANÇA.
    """
    __tablename__ = "Milestones_Historico"
    
    milestone_history_id = Column(Integer, primary_key=True, index=True)
    description = Column(Text, nullable=False)
    status = Column(String(100))
    date_planned = Column(Date, nullable=True)
    date_actual_or_revised = Column(String(50), nullable=True)
    
    report_id_fk = Column(Integer, ForeignKey("Relatorios_Sprint.report_id"))
    
    relatorio = relationship("RelatorioSprint", back_populates="milestones")

class RelatorioKPI(Base):
    """
    NOVA TABELA: Armazena QUALQUER métrica (KPI) de forma genérica.
    """
    __tablename__ = "Relatorios_KPIs"
    
    kpi_id = Column(Integer, primary_key=True, index=True)
    kpi_name = Column(String(255), nullable=False)      # Ex: "Custo Realizado", "NPS", "App Downloads"
    kpi_value_numeric = Column(Float, nullable=True)   # Ex: 50000.0, 45.0, 10000.0
    kpi_value_text = Column(String(500), nullable=True) # Ex: "R$ 50.000,00", "Acima da Meta"
    kpi_category = Column(String(100), default="Geral") # Ex: "Financeiro", "Operacional", "Cliente"
    
    report_id_fk = Column(Integer, ForeignKey("Relatorios_Sprint.report_id"))
    
    relatorio = relationship("RelatorioSprint", back_populates="kpis")

# -----------------------------------------------------------------
# SEÇÃO 2: MODELOS PYDANTIC (MODIFICADOS)
# -----------------------------------------------------------------

class KPI(BaseModel):
    """ NOVO Pydantic model para um KPI genérico """
    kpi_name: str
    kpi_value_numeric: Optional[float] = None
    kpi_value_text: Optional[str] = None
    kpi_category: str = "Geral"
    
    class Config:
        from_attributes = True

class Milestone(BaseModel): # Nenhuma mudança, já era genérico
    description: str
    status: str
    date_planned: Optional[date] = None
    date_actual_or_revised: Optional[str] = None
    slippage: bool = False 
    
    class Config:
        from_attributes = True

class ReportData(BaseModel):
    """ Modelo de dados do Parser, agora genérico """
    project_code: str
    project_name: str
    project_manager: str
    sprint_number: int = Field(alias="last_sprint_reported") 
    overall_status_humano: Optional[str] = None 
    overall_status: str = "Em Dia" 
    executive_summary: Optional[str] = None
    risks_and_impediments: Optional[str] = None
    next_steps: Optional[str] = None

class ParsedReport(BaseModel):
    """ O objeto de transporte final do Parser """
    projeto: ReportData
    milestones: List[Milestone]
    kpis: List[KPI] # NOVO CAMPO: Lista de KPIs extraídos

# --- Modelos de Resposta da API (MODIFICADOS) ---

class DashboardStats(BaseModel): # Nenhuma mudança
    total_projetos: int
    projetos_em_dia: int
    projetos_em_risco: int
    projetos_atrasados: int
    # Este campo precisará de uma query mais complexa no Repository
    # (somar o KPI "Custo Realizado" de todos os projetos)
    investimento_total_executado: float

class ProjectListItem(BaseModel): # Nenhuma mudança
    code: str
    name: str
    class Config: from_attributes = True

class SprintListItem(BaseModel): # Nenhuma mudança
    report_id: int
    sprint_number: int
    class Config: from_attributes = True

class FinancialHistoryItem(BaseModel):
    # ESTE MODELO FICOU OBSOLETO.
    # O histórico agora é por KPI, não apenas financeiro.
    # Vamos removê-lo por enquanto para simplificar.
    pass

class ReportDetail(BaseModel):
    """ Modelo de detalhe do relatório, agora genérico """
    project_code: str
    project_name: str
    project_manager: str
    budget_total: float # Vem do Projeto "Pai"
    report_id: int
    sprint_number: int
    report_date: date
    overall_status: str
    executive_summary: Optional[str] = None
    risks_and_impediments: Optional[str] = None
    next_steps: Optional[str] = None
    status_anterior: Optional[str] = None
    
    # --- CAMPOS REMOVIDOS ---
    # cost_realized: float
    # variance_text: Optional[str] = None
    # financial_narrative: Optional[str] = None
    # cost_delta: float = 0.0
    
    class Config:
        from_attributes = True

class ReportDetailResponse(BaseModel):
    """ Resposta final da API de detalhe """
    projeto: ReportDetail
    milestones: List[Milestone]
    kpis: List[KPI] # NOVO CAMPO: Envia os KPIs para o front-end

class FinancialHistoryItem(BaseModel):
    """
    Este modelo volta a ser usado para o gráfico de histórico de KPI.
    """
    sprint_number: int
    cost_realized: float
    budget_total: float