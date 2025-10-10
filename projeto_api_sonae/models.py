# models.py

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime
import enum

# --- Imports do SQLAlchemy ORM ---
from sqlalchemy import Column, String, Integer, Float, Date, Text, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from .config import Base # Supondo que a Base declarativa venha de um arquivo config.py

# -----------------------------------------------------------------
# SEÇÃO 1: MODELOS ORM (SQLAlchemy)
# -----------------------------------------------------------------

class AreaNegocioEnum(str, enum.Enum):
    TI = "TI"
    RETALHO = "Retalho"
    RH = "RH"
    MARKETING = "Marketing"

# --- Tabelas de Domínio (Projetos e Relatórios) ---

class Projeto(Base):
    __tablename__ = "Projetos"
    
    codigo_projeto = Column(String(50), primary_key=True, index=True)
    nome_projeto = Column(String(255), nullable=False)
    gerente_projeto = Column(String(255))
    orcamento_total = Column(Float, default=0.0)
    
    # Este campo foi removido para evitar confusão com 'area_negocio'
    # tipo_projeto = Column(String(50), nullable=False, default='Geral')
    
    area_negocio = Column(Enum(AreaNegocioEnum), nullable=False, default=AreaNegocioEnum.TI)
    data_criacao = Column(DateTime, default=datetime.utcnow)
    data_atualizacao = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    relatorios = relationship("RelatorioSprint", back_populates="projeto")

class RelatorioSprint(Base):
    __tablename__ = "Relatorios_Sprint"
    
    id_relatorio = Column(Integer, primary_key=True, index=True)
    numero_sprint = Column(Integer, nullable=False)
    data_relatorio = Column(Date, default=date.today)
    status_geral = Column(String(50))
    resumo_executivo = Column(Text, nullable=True)
    riscos_e_impedimentos = Column(Text, nullable=True)
    proximos_passos = Column(Text, nullable=True)
    codigo_projeto_fk = Column(String(50), ForeignKey("Projetos.codigo_projeto"))
    id_autor_fk = Column(Integer, ForeignKey("Usuarios.id_usuario"), nullable=True)
    data_criacao = Column(DateTime, default=datetime.utcnow)
    data_atualizacao = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Campos específicos de TI que voltaram para esta tabela
    story_points_planejados = Column(Integer, nullable=True)
    story_points_entregues = Column(Integer, nullable=True)
    
    projeto = relationship("Projeto", back_populates="relatorios")
    autor = relationship("Usuario", back_populates="relatorios")
    milestones = relationship("MilestoneHistorico", back_populates="relatorio", cascade="all, delete-orphan")
    kpis = relationship("RelatorioKPI", back_populates="relatorio", cascade="all, delete-orphan")

class MilestoneHistorico(Base):
    __tablename__ = "Milestones_Historico"
    
    id_historico_marco = Column(Integer, primary_key=True, index=True)
    descricao = Column(Text, nullable=False)
    status = Column(String(100))
    data_planejada = Column(Date, nullable=True)
    data_real_ou_revisada = Column(String(50), nullable=True)
    id_relatorio_fk = Column(Integer, ForeignKey("Relatorios_Sprint.id_relatorio"))
    
    relatorio = relationship("RelatorioSprint", back_populates="milestones")

class RelatorioKPI(Base):
    __tablename__ = "Relatorios_KPIs"
    
    id_kpi = Column(Integer, primary_key=True, index=True)
    nome_kpi = Column(String(255), nullable=False)
    valor_numerico_kpi = Column(Float, nullable=True)
    valor_texto_kpi = Column(String(500), nullable=True)
    categoria_kpi = Column(String(100), default="Geral")
    id_relatorio_fk = Column(Integer, ForeignKey("Relatorios_Sprint.id_relatorio"))
    
    relatorio = relationship("RelatorioSprint", back_populates="kpis")

# --- Classes de RBAC (Controle de Acesso) ---

class Usuario(Base):
    __tablename__ = "Usuarios"
    id_usuario = Column(Integer, primary_key=True)
    nome = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    senha_hash = Column(String(255), nullable=False)
    data_criacao = Column(DateTime, default=datetime.utcnow)
    data_atualizacao = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    data_exclusao = Column(DateTime, nullable=True)
    setor = Column(String(32), nullable=True)

    papeis = relationship("Papel", secondary="Usuario_Papeis", back_populates="usuarios")
    relatorios = relationship("RelatorioSprint", back_populates="autor")
    refresh_tokens = relationship("RefreshToken", back_populates="usuario")

class Papel(Base):
    __tablename__ = "Papeis"
    id_papel = Column(Integer, primary_key=True)
    nome = Column(String(100), nullable=False, unique=True)
    id_escopo_fk = Column(Integer, ForeignKey("Escopos.id_escopo"))
    
    usuarios = relationship("Usuario", secondary="Usuario_Papeis", back_populates="papeis")
    permissoes = relationship("Permissao", secondary="Papel_Permissoes", back_populates="papeis")
    escopo = relationship("Escopo")

class Permissao(Base):
    __tablename__ = "Permissoes"
    id_permissao = Column(Integer, primary_key=True)
    nome_permissao = Column(String(255), nullable=False, unique=True)
    descricao = Column(Text)
    
    papeis = relationship("Papel", secondary="Papel_Permissoes", back_populates="permissoes")
    
class Escopo(Base):
    __tablename__ = "Escopos"
    id_escopo = Column(Integer, primary_key=True)
    tipo = Column(String(50), nullable=False, unique=True)
    descricao = Column(Text)

class RefreshToken(Base):
    __tablename__ = "Refresh_Tokens"
    id_token = Column(Integer, primary_key=True)
    id_usuario_fk = Column(Integer, ForeignKey("Usuarios.id_usuario"))
    token_hash = Column(String(255), nullable=False)
    data_expiracao = Column(DateTime, nullable=False)
    data_criacao = Column(DateTime, default=datetime.utcnow)
    
    usuario = relationship("Usuario", back_populates="refresh_tokens")

# --- Tabelas de Junção ---
class UsuarioPapel(Base):
    __tablename__ = "Usuario_Papeis"
    id_usuario_fk = Column(Integer, ForeignKey("Usuarios.id_usuario"), primary_key=True)
    id_papel_fk = Column(Integer, ForeignKey("Papeis.id_papel"), primary_key=True)
    data_atribuicao = Column(DateTime, default=datetime.utcnow)

class PapelPermissao(Base):
    __tablename__ = "Papel_Permissoes"
    id_papel_fk = Column(Integer, ForeignKey("Papeis.id_papel"), primary_key=True)
    id_permissao_fk = Column(Integer, ForeignKey("Permissoes.id_permissao"), primary_key=True)
    data_atribuicao = Column(DateTime, default=datetime.utcnow)

# -----------------------------------------------------------------
# SEÇÃO 2: MODELOS DE DADOS (Pydantic)
# -----------------------------------------------------------------

class KPI(BaseModel):
    nome_kpi: str
    valor_numerico_kpi: Optional[float] = None
    valor_texto_kpi: Optional[str] = None
    categoria_kpi: str = "Geral"
    
    class Config: from_attributes = True

class Milestone(BaseModel):
    descricao: str
    status: Optional[str] = None
    data_planejada: Optional[date] = None
    data_real_ou_revisada: Optional[str] = None
    
    class Config: from_attributes = True

class ParsedReport(BaseModel):
    # Informações genéricas do projeto e do relatório
    codigo_projeto: str
    nome_projeto: str
    gerente_projeto: str
    area_negocio: AreaNegocioEnum
    numero_sprint: int
    status_geral: str
    resumo_executivo: Optional[str] = None
    riscos_e_impedimentos: Optional[str] = None
    proximos_passos: Optional[str] = None
    
    # Informações específicas de TI (agora no nível principal)
    story_points_planejados: Optional[int] = None
    story_points_entregues: Optional[int] = None
    
    # Listas de entidades relacionadas
    milestones: List[Milestone]
    kpis: List[KPI]
    
class ReportDetail(BaseModel):
    # Dados do Projeto
    codigo_projeto: str
    nome_projeto: str
    gerente_projeto: Optional[str] = None
    orcamento_total: Optional[float] = None
    
    # Dados do Relatório
    id_relatorio: int
    numero_sprint: int
    data_relatorio: date
    status_geral: Optional[str] = None
    resumo_executivo: Optional[str] = None
    riscos_e_impedimentos: Optional[str] = None
    proximos_passos: Optional[str] = None
    
    # Adicionando campos de TI que podem vir do BD
    story_points_planejados: Optional[int] = None
    story_points_entregues: Optional[int] = None

    class Config: from_attributes = True

class ReportDetailResponse(BaseModel):
    # Simplificado: Não há mais 'detalhes_especificos'
    detalhe_relatorio: ReportDetail
    milestones: List[Milestone]
    kpis: List[KPI]

class FinancialHistoryItem(BaseModel):
    sprint_number: int
    cost_realized: float
    budget_total: float

class DashboardStats(BaseModel):
    total_projetos: int
    projetos_em_dia: int
    projetos_em_risco: int
    projetos_atrasados: int
    investimento_total_executado: float

class ProjectListItem(BaseModel):
    codigo_projeto: str
    nome_projeto: str
    
    class Config: 
        from_attributes = True
        # O alias pode ser usado se você quiser que o JSON final
        # tenha nomes diferentes, mas vamos manter simples por enquanto.

class SprintListItem(BaseModel):
    id_relatorio: int
    numero_sprint: int
    class Config: from_attributes = True

class Token(BaseModel):
    """ Modelo de resposta para o endpoint de login. """
    access_token: str
    token_type: str