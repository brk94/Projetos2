""" 
Modelos de domínio: ORM (SQLAlchemy) + Esquemas (Pydantic).

⚠️ Revisão **apenas** com organização e comentários. **Nomes, tipos e lógica
permanecem inalterados**. A ideia é facilitar a leitura/entendimento sem
mudar o comportamento.

Seções:
- Imports e Base
- Enums / Domínios
- ORM: Projetos e Relatórios
- ORM: Usuários / RBAC / Tokens
- ORM: Solicitações de Acesso
- ORM: Acesso por Projeto
- Pydantic: DTOs de entrada/saída
"""
# ======================================================================================
# Imports e Base
# ======================================================================================
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Literal
from datetime import date, datetime
import enum

# --- SQLAlchemy ORM ---
from sqlalchemy import (
    Column, String, BigInteger, Integer, Float, Date, Text, ForeignKey,
    DateTime, Enum, Boolean, Index, UniqueConstraint, Computed, text
)
from sqlalchemy.orm import relationship
from .config import Base

# ======================================================================================
# Enums / Domínios
# ======================================================================================
CargoLiteral = Literal["Administrador", "Analista", "Gestor de Projetos", "Diretor", "Visualizador"]

class AreaNegocioEnum(str, enum.Enum):
    TI        = "TI"
    RETALHO   = "Retalho"
    RH        = "RH"
    MARKETING = "Marketing"

# ======================================================================================
# ORM — Projetos e Relatórios
# ======================================================================================
class Projeto(Base):
    __tablename__ = "projetos"

    codigo_projeto   = Column(String(50), primary_key=True, index=True)
    nome_projeto     = Column(String(255), nullable=False)
    gerente_projeto  = Column(String(255))
    orcamento_total  = Column(Float, default=0.0)
    area_negocio     = Column(Enum(AreaNegocioEnum), nullable=False, default=AreaNegocioEnum.TI)
    data_criacao     = Column(DateTime, default=datetime.utcnow)
    data_atualizacao = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Soft delete / auditoria
    is_deletado     = Column(Boolean, nullable=False, default=False)
    deletado_em     = Column(DateTime, nullable=True)
    deletado_por    = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    motivo_exclusao = Column(String(255), nullable=True)

    id_gerente_fk = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True, index=True)

    gerente = relationship(
        "Usuario",
        back_populates="projetos_gerenciados",
        foreign_keys=[id_gerente_fk],
        primaryjoin="Projeto.id_gerente_fk == Usuario.id_usuario",
        lazy="joined",
    )
    relatorios = relationship("RelatorioSprint", back_populates="projeto", passive_deletes=True)

class RelatorioSprint(Base):
    __tablename__ = "relatorios_sprint"

    id_relatorio        = Column(Integer, primary_key=True, index=True)
    numero_sprint       = Column(Integer, nullable=False)
    data_relatorio      = Column(Date, default=date.today)

    status_geral        = Column(String(50))
    resumo_executivo    = Column(Text, nullable=True)
    riscos_e_impedimentos = Column(Text, nullable=True)
    proximos_passos     = Column(Text, nullable=True)

    codigo_projeto_fk = Column(String(50), ForeignKey("projetos.codigo_projeto", ondelete="CASCADE"), nullable=False, index=True)
    id_autor_fk       = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True, index=True)

    data_criacao     = Column(DateTime, default=datetime.utcnow)
    data_atualizacao = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    story_points_planejados = Column(Integer, nullable=True)
    story_points_entregues  = Column(Integer, nullable=True)

    projeto    = relationship("Projeto", back_populates="relatorios")
    autor      = relationship("Usuario", back_populates="relatorios")
    milestones = relationship("MilestoneHistorico", back_populates="relatorio", cascade="all, delete-orphan")
    kpis       = relationship("RelatorioKPI",       back_populates="relatorio", cascade="all, delete-orphan")

class MilestoneHistorico(Base):
    __tablename__ = "milestones_historico"

    id_historico_marco    = Column(Integer, primary_key=True, index=True)
    descricao             = Column(Text, nullable=False)
    status                = Column(String(100))
    data_planejada        = Column(Date, nullable=True)
    data_real_ou_revisada = Column(Date, nullable=True)
    id_relatorio_fk       = Column(Integer, ForeignKey("relatorios_sprint.id_relatorio", ondelete="CASCADE"), nullable=False, index=True)

    relatorio = relationship("RelatorioSprint", back_populates="milestones")

class RelatorioKPI(Base):
    __tablename__ = "relatorios_kpis"

    id_kpi             = Column(Integer, primary_key=True, index=True)
    nome_kpi           = Column(String(255), nullable=False)
    valor_numerico_kpi = Column(Float, nullable=True)
    valor_texto_kpi    = Column(String(500), nullable=True)
    categoria_kpi      = Column(String(100), default="Geral")
    id_relatorio_fk    = Column(Integer, ForeignKey("relatorios_sprint.id_relatorio", ondelete="CASCADE"), nullable=False, index=True)

    relatorio = relationship("RelatorioSprint", back_populates="kpis")

# ======================================================================================
# ORM — Usuários / RBAC / Tokens
# ======================================================================================
class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario       = Column(Integer, primary_key=True, autoincrement=True)
    nome             = Column(String(255), nullable=False)
    email            = Column(String(255), nullable=False, unique=True)
    senha_hash       = Column(String(255), nullable=False)
    data_criacao     = Column(DateTime, default=datetime.utcnow)
    data_atualizacao = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    data_exclusao    = Column(DateTime, nullable=True)
    setor            = Column(String(32), nullable=True)

    projetos_gerenciados = relationship(
        "Projeto",
        back_populates="gerente",
        foreign_keys="Projeto.id_gerente_fk",
        primaryjoin="Projeto.id_gerente_fk == Usuario.id_usuario",
        lazy="selectin",
    )
    papeis         = relationship("Papel", secondary="usuario_papeis", back_populates="usuarios")
    relatorios     = relationship("RelatorioSprint", back_populates="autor")
    refresh_tokens = relationship("RefreshToken", back_populates="usuario")

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id_token       = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario_fk  = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    token_hash     = Column(String(255), nullable=False)
    data_expiracao = Column(DateTime, nullable=False)
    data_criacao   = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="refresh_tokens")

class Escopo(Base):
    __tablename__ = "escopos"

    id_escopo = Column(Integer, primary_key=True, autoincrement=True)
    tipo      = Column(String(50), nullable=False, unique=True)
    descricao = Column(Text)

class Papel(Base):
    __tablename__ = "papeis"

    id_papel        = Column(Integer, primary_key=True, autoincrement=True)
    nome            = Column(String(100), nullable=False, unique=True)
    id_escopo_fk    = Column(Integer, ForeignKey("escopos.id_escopo"), nullable=False)
    data_criacao     = Column(DateTime, default=datetime.utcnow)
    data_atualizacao = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    escopo     = relationship("Escopo")
    usuarios   = relationship("Usuario",   secondary="usuario_papeis",   back_populates="papeis")
    permissoes = relationship("Permissao", secondary="papel_permissoes", back_populates="papeis")

class Permissao(Base):
    __tablename__ = "permissoes"

    id_permissao   = Column(Integer, primary_key=True, autoincrement=True)
    nome_permissao = Column(String(255), nullable=False, unique=True)
    descricao      = Column(Text)

    papeis = relationship("Papel", secondary="papel_permissoes", back_populates="permissoes")

class UsuarioPapel(Base):
    __tablename__ = "usuario_papeis"

    id_usuario_fk   = Column(Integer, ForeignKey("usuarios.id_usuario"), primary_key=True)
    id_papel_fk     = Column(Integer, ForeignKey("papeis.id_papel"),     primary_key=True)
    data_atribuicao = Column(DateTime, default=datetime.utcnow)

class PapelPermissao(Base):
    __tablename__ = "papel_permissoes"

    id_papel_fk     = Column(Integer, ForeignKey("papeis.id_papel"),         primary_key=True)
    id_permissao_fk = Column(Integer, ForeignKey("permissoes.id_permissao"), primary_key=True)  # noqa: E999 (mantém igual ao seu)
    data_atribuicao = Column(DateTime, default=datetime.utcnow)

# ======================================================================================
# ORM — Solicitações de Acesso
# ======================================================================================
class UsuarioSolicitacaoAcesso(Base):
    __tablename__ = "usuarios_solicitacoes_acesso"

    id_solicitacao = Column(BigInteger, primary_key=True, autoincrement=True)
    nome           = Column(String(255), nullable=False)
    email          = Column(String(255), nullable=False, index=True)
    senha_hash     = Column(String(255), nullable=False)
    setor          = Column(String(255), nullable=False)
    cargo          = Column(String(64),  nullable=False)
    justificativa  = Column(String(512), nullable=False)

    status = Column(
        Enum('aguardando', 'aprovado', 'rejeitado', 'expirado', name='status_solic'),
        nullable=False,
        default='aguardando'
    )

    decidido_por   = Column(BigInteger, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    decidido_em    = Column(DateTime, nullable=True)
    motivo_decisao = Column(String(512), nullable=True)

    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow)
    expira_em = Column(DateTime, nullable=True)

    decisor = relationship("Usuario", foreign_keys=[decidido_por])

    __table_args__ = (
        # Índice único PARCIAL (PostgreSQL) — apenas enquanto status = 'aguardando'
        Index(
            'uq_solic_email_aguardando',
            'email',
            unique=True,
            postgresql_where=(text("status = 'aguardando'"))
        ),
        Index('idx_status_email', 'status', 'email'),
        Index('idx_criado_em', 'criado_em'),
    )


# ======================================================================================
# ORM — Acesso por Projeto
# ======================================================================================
class ProjetoUsuarioAcesso(Base):
    __tablename__ = "projetos_usuarios_acesso"

    id_acesso         = Column(Integer, primary_key=True, autoincrement=True)
    codigo_projeto_fk = Column(String(50), ForeignKey("projetos.codigo_projeto", ondelete="CASCADE"), index=True, nullable=False)
    id_usuario_fk     = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), index=True, nullable=False)
    papel_acesso      = Column(String(32), nullable=False, default="Visualizador")
    criado_em         = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("codigo_projeto_fk", "id_usuario_fk", name="uq_projeto_usuario"),
    )

# ======================================================================================
# Pydantic — DTOs de entrada/saída (mantidos)
# ======================================================================================
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
    data_real_ou_revisada: Optional[date] = None
    class Config: from_attributes = True

class ParsedReport(BaseModel):
    codigo_projeto: str
    nome_projeto: str
    gerente_projeto: str
    area_negocio: AreaNegocioEnum
    numero_sprint: int
    status_geral: str
    resumo_executivo: Optional[str] = None
    riscos_e_impedimentos: Optional[str] = None
    proximos_passos: Optional[str] = None
    story_points_planejados: Optional[int] = None
    story_points_entregues: Optional[int] = None
    milestones: List[Milestone]
    kpis: List[KPI]

class ReportDetail(BaseModel):
    codigo_projeto: str
    nome_projeto: str
    gerente_projeto: Optional[str] = None
    orcamento_total: Optional[float] = None
    id_relatorio: int
    numero_sprint: int
    data_relatorio: date
    status_geral: Optional[str] = None
    resumo_executivo: Optional[str] = None
    riscos_e_impedimentos: Optional[str] = None
    proximos_passos: Optional[str] = None
    story_points_planejados: Optional[int] = None
    story_points_entregues: Optional[int] = None
    class Config: from_attributes = True

class ReportDetailResponse(BaseModel):
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
    area_negocio: Optional[str] = None
    class Config: from_attributes = True

class SprintListItem(BaseModel):
    id_relatorio: int
    numero_sprint: int
    class Config: from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshIn(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None

class AccessRequestIn(BaseModel):
    nome: str
    email: str
    senha: str
    setor: str
    justificativa: str
    cargo: CargoLiteral

class DecisaoIn(BaseModel):
    decisao: str
    motivo: Optional[str] = None

class SolicitacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_solicitacao: int
    nome: str
    email: str
    setor: Optional[str] = None
    justificativa: Optional[str] = None
    status: str
    criado_em: Optional[datetime] = None
    decidido_por: Optional[int] = None
    decidido_em: Optional[datetime] = None
    motivo_decisao: Optional[str] = None
    decidido_por_nome: Optional[str] = None
    cargo: str

class UsuarioAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_usuario: int
    nome: str
    email: str
    setor: Optional[str] = None
    cargo: Optional[str] = None
    data_criacao: Optional[datetime] = None
    data_atualizacao: Optional[datetime] = None

class UsuarioUpdateIn(BaseModel):
    nome: Optional[str] = None
    setor: Optional[str] = None

class UsuarioPerfilOut(BaseModel):
    nome: str
    email: str
    setor: Optional[str] = None
    cargos: List[str] = []
