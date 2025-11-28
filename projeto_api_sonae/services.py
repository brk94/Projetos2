"""
Serviços centrais do backend: Autenticação (JWT/senhas), IA (Gemini/SpaCy)
para sumários, e Repositório ORM (CRUD, RBAC, Refresh Tokens, Dashboard).

Seções
- Imports
- Configuração de Segurança (SECRET_KEY/ALGORITHM/expirações)
- AuthService — senhas (bcrypt) e JWT (access/refresh)
- Helpers de tempo (UTC)
- AIService — geração e sanitização de resumo (Gemini)
- DatabaseRepository — acesso ao banco (ORM) + regras de negócio
    - Usuários e RBAC
    - Refresh Tokens (hash + rotate + revoke)
    - Relatórios/Dashboard
    - Solicitações de acesso
    - Soft delete e restauração de projetos
    - Acessos por projeto/usuário
"""

# ======================================================================================
# Imports
# ======================================================================================
import os
import secrets
import hashlib
import hmac
from typing import List, Optional
from datetime import datetime, timedelta, timezone

# --- Imports de Segurança e Autenticação ---
from passlib.context import CryptContext
from jose import JWTError, jwt
import bcrypt
import re
import unicodedata
import json

# --- Imports do SQLAlchemy ---
from . import models
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case, desc, delete

# ======================================================================================
# Configuração de Segurança (via variáveis de ambiente)
# ======================================================================================
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))

# Contexto para hashing/verificação com bcrypt (mantido)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ======================================================================================
# AuthService (responsável por senhas e access tokens JWT)
# ======================================================================================
class AuthService:
    @staticmethod
    def eh_bcrypt_hash(value: Optional[str]) -> bool:
        """Retorna True se o valor parece ser um hash bcrypt ($2a/$2b/$2y)."""
        if not isinstance(value, str):
            return False
        return value.startswith("$2a$") or value.startswith("$2b$") or value.startswith("$2y$")

    def get_hash_senha(self, plain_password: str) -> str:
        """Gera hash bcrypt para `plain_password` (salt aleatório via gensalt)."""
        return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()

    def verificar_senha(self, plain_password: str, hashed_password: str) -> bool:
        """Verifica apenas quando `hashed_password` é de fato bcrypt.
        Em outros formatos (texto puro/legado), retorna False por segurança.
        """
        if not self.eh_bcrypt_hash(hashed_password):
            return False
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())

    def verificar_senha_ou_texto_puro(self, plain_password: str, stored_value: str) -> bool:
        """Compat: aceita hash bcrypt **ou** valor em texto puro (legado)."""
        if self.eh_bcrypt_hash(stored_value):
            return bcrypt.checkpw(plain_password.encode(), stored_value.encode())
        return hmac.compare_digest(plain_password, stored_value)

    def precisa_atualizar_senha(self, stored_value: str) -> bool:
        """Sinaliza necessidade de migração quando não for bcrypt."""
        return not self.eh_bcrypt_hash(stored_value)

    def criar_access_token(self, data: dict, expires_delta=None) -> str:
        """Assina um JWT com `sub` e expiração (default: ACCESS_TOKEN_EXPIRE_MINUTES)."""
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    @staticmethod
    def criar_refresh_token_texto_puro() -> str:
        """Gera token opaco (plaintext) para refresh; salvo como **hash** no BD."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def refresh_token_expirado(rt: models.RefreshToken) -> bool:
        """Confere expiração (normalizando timezone). Ausência de expiração = expirado."""
        exp_aware = _converter_para_utc(rt.data_expiracao)
        if exp_aware is None:
            return True
        return exp_aware < _utc_agora()

# ======================================================================================
# Helpers de tempo (UTC)
# ======================================================================================

def _utc_agora():
    """Sempre devolve 'agora' com timezone UTC (aware)."""
    return datetime.now(timezone.utc)


def _converter_para_utc(dt: datetime | None) -> datetime | None:
    """Converte datetime do BD (frequentemente *naive*) para aware/UTC, **sem** alterar o instante.
    - Se já for aware, apenas normaliza para UTC.
    - Se vier naive, anexa tz UTC (assumindo que o instante foi gravado como UTC).
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

# ======================================================================================
# AIService — geração e sanitização de resumo via Gemini
# ======================================================================================
class AIService:
    def __init__(self, nlp_model, gemini_model, gemini_config):
        self.nlp = nlp_model
        self.gemini_model = gemini_model
        self.gemini_config = gemini_config
        print("AIService inicializado.")

    def _sanitizar_resumo_ptbr(self, s: str) -> str:
        """Pós-processa a resposta para garantir texto limpo e formatos PT-BR de moeda.
        - Normaliza Unicode e espaços (inclui NBSP) e colapsa quebras.
        - Corrige padrões de moeda: sempre "R$ 1.234,56" (com espaço após R$).
        - Separa letras coladas a números (ex.: "a50" → "a 50").
        - Pequenos fixes de tokens colados e *escape* de markdown acidental.
        """
        if not isinstance(s, str):
            return ""
        s = unicodedata.normalize("NFC", s).replace("\u00A0", " ")
        s = re.sub(r"\s+", " ", s).strip()

        # 1) com centavos
        s = re.sub(
            r"R\s*\$?\s*([0-9]{1,3}(?:\.[0-9]{3})*,\s*[0-9]{2})",
            lambda m: "R$ " + m.group(1).replace(" ", ""),
            s,
            flags=re.IGNORECASE,
        )
        # 2) sem centavos (mantém milhar)
        s = re.sub(
            r"R\s*\$?\s*([0-9]{1,3}(?:\.[0-9]{3})+)(?!,)",
            lambda m: "R$ " + m.group(1),
            s,
            flags=re.IGNORECASE,
        )

        s = re.sub(r"([A-Za-zÁ-ú])(\d)", r"\1 \2", s)
        s = re.sub(r"(\d)([A-Za-zÁ-ú])", r"\1 \2", s)
        s = re.sub(r"(?i)\bdeum\b", "de um", s)
        s = re.sub(r"([*_~`])", r"\\\1", s)  # escape
        return s

    def gerar_resumo_gemini(self, report_data, milestones, kpis) -> str:
        """Gera um único parágrafo (máx. 4 frases) de resumo executivo PT-BR.
        - Regras rígidas de formatação de moeda e saída **texto puro**.
        - Em falha, faz *fallback* para `report_data.resumo_executivo`.
        """
        prompt = f"""
        Você é um PMO sênior. Produza um ÚNICO parágrafo (no máximo 4 frases), em português-BR,
        apenas com texto plano.

        REGRAS E FORMATAÇÃO (OBRIGATÓRIAS):
        - Não use Markdown/HTML: nada de '#', '*', '_', '~', '`', listas, títulos.
        - Não escreva frases introdutórias como "Claro", "Segue", "Aqui está".
        - Não quebre números no meio nem insira espaços ou quebras de linha dentro de valores.
        - Para dinheiro use SEMPRE este formato PT-BR: R$ 1.234.567,89 (com espaço após R$).
        Exemplos VÁLIDOS:
            R$ 750.000,00
            R$ 1.500.000,00
        Exemplos INVÁLIDOS (NÃO use):
            R $ 750.000 , 00
            R$750.000,00
            R 750.000,00
        - Foque em: status, riscos/impactos, orçamento executado e próximos passos (se houver).

        DADOS:
        - Projeto: {report_data.nome_projeto}
        - Status: {report_data.status_geral}
        - Sprint/Fase: {report_data.numero_sprint}
        - KPIs: {[k.model_dump() for k in kpis]}
        - Milestones: {[m.model_dump() for m in milestones]}

        Responda APENAS com o parágrafo final, sem rótulos ou cabeçalhos.
        """.strip()

        try:
            resp = self.gemini_model.generate_content(prompt, generation_config=self.gemini_config)
            raw = (getattr(resp, "text", None) or str(resp) or "").strip()
            clean = self._sanitizar_resumo_ptbr(raw)
            return clean or (report_data.resumo_executivo or "")
        except Exception as e:
            print(f"AVISO: Falha ao gerar resumo com Gemini: {e}")
            return report_data.resumo_executivo or "Resumo original não disponível."
        
    def resumir_aries_relatorio(self, texto: str) -> str:
        """
        Gera um resumo em PT-BR do relatório ARIES (em inglês),
        organizado em seções de markdown. Não persiste nada, só
        devolve uma string grande para o frontend.
        """
        if not isinstance(texto, str):
            if isinstance(texto, (bytes, bytearray)):
                texto = texto.decode("utf-8", errors="ignore")
            else:
                texto = str(texto)

        # Para não estourar o contexto do modelo, recorta se for gigante
        max_chars = 30000
        trecho = texto[:max_chars]

        prompt = f"""
        Você é um especialista em projetos de identidade digital e privacidade na Europa.

        A seguir está um trecho de um relatório do projeto ARIES (em inglês).
        Gere um resumo em **português do Brasil**, organizado com markdown simples, usando
        as seções abaixo (use títulos `##`):

        ## Visão geral do projeto ARIES
        - Contexto e objetivo geral do projeto

        ## Papel da SONAE / SONAE MC
        - Qual o papel da SONAE no piloto / cenário descrito
        - Principais responsabilidades e atividades

        ## Principais atividades e resultados
        - Work packages ou tarefas relevantes
        - Demonstrações / pilotos / experimentos realizados
        - Resultados alcançados (quando descritos)

        ## Riscos, desafios e lições aprendidas
        - Riscos mencionados, dificuldades, limitações
        - Lições aprendidas ou recomendações

        ## Pontos que podem inspirar o MC Sonae (projeto acadêmico)
        - 3 a 5 bullets conectando o que aparece no ARIES com ideias
        que poderiam ser aplicadas numa plataforma de dashboards
        e monitoramento de projetos

        INSTRUÇÕES:
        - Não invente informação. Use apenas o que aparecer no texto.
        - Se alguma seção não tiver informação, escreva uma frase curta
        dizendo que o relatório não traz detalhes suficientes.
        - Não use código, não use blocos ```; apenas markdown simples.

        TRECHO DO RELATÓRIO (em inglês):
        \"\"\"{trecho}\"\"\"
        """.strip()

        try:
            resp = self.gemini_model.generate_content(
                prompt,
                generation_config=self.gemini_config,
            )
            raw = (getattr(resp, "text", None) or str(resp) or "").strip()
            return self._sanitizar_resumo_ptbr(raw)
        except Exception as e:
            print(f"AVISO: Falha ao resumir relatório ARIES: {e}")
            return "Não foi possível gerar o resumo automático do relatório ARIES."

    def gerar_insights_aries(self, texto: str) -> dict:
        """
        Interpreta um relatório ARIES e devolve um dicionário estruturado
        em termos de Work Packages (WP1..WP7), pilotos/cenários e tabelas
        relevantes. Não mexe em banco de dados.
        """
        if not isinstance(texto, str):
            if isinstance(texto, (bytes, bytearray)):
                texto = texto.decode("utf-8", errors="ignore")
            else:
                texto = str(texto)

        max_chars = 30000
        trecho = texto[:max_chars]

        prompt = f"""
        Você é um especialista em projetos europeus de I&D e em documentação de Work Packages.

        A seguir está um trecho de um relatório do projeto ARIES (em inglês).
        O documento menciona Work Packages (WP1, WP2, ..., WP7), pilotos/cenários (por ex. e-commerce, aeroporto)
        e várias tabelas (por exemplo: cronogramas, KPIs, parceiros, resultados).

        Sua tarefa é analisar o texto (incluindo o conteúdo das tabelas, quando for descrito em texto)
        e devolver um JSON ESTRUTURADO em português do Brasil, exatamente no formato abaixo:

        {{
        "visao_geral": "Texto curto explicando o contexto e objetivo geral do projeto ARIES.",
        "papel_sonae": "Explicação específica do papel da SONAE / SONAE MC no projeto e nos pilotos.",
        "work_packages": [
            {{
            "id": "WP1",
            "titulo": "Título resumido do WP1 (em português, se possível).",
            "objetivo": "Objetivo principal do WP1.",
            "status": "planejado ou em_andamento ou concluido ou atrasado ou nao_mencionado",
            "principais_atividades": [
                "Atividade relevante do WP1 descrita no relatório.",
                "Outra atividade relevante do WP1."
            ],
            "principais_resultados": [
                "Resultado, entrega ou output concreto atribuído ao WP1.",
                "Outro resultado relevante."
            ]
            }},
            {{
            "id": "WP2",
            "titulo": "...",
            "objetivo": "...",
            "status": "...",
            "principais_atividades": [...],
            "principais_resultados": [...]
            }}
            // Repita para WP3..WP7, somente se houver informações no relatório.
        ],
        "pilotos": [
            {{
            "nome": "Piloto de e-commerce SONAE",
            "descricao": "Resumo do que foi feito nesse piloto.",
            "status": "planejado ou em_andamento ou concluido ou atrasado",
            "work_packages_relacionados": ["WP4", "WP5"],
            "principais_kpis": [
                "Ex: 16 utilizadores no primeiro piloto em 2017.",
                "Ex: piloto ampliado em 2018 com versão 2 do demonstrador."
            ]
            }},
            {{
            "nome": "Piloto de aeroporto",
            "descricao": "Se houver informações sobre esse cenário.",
            "status": "planejado ou em_andamento ou concluido ou atrasado",
            "work_packages_relacionados": ["WP4", "WP6"],
            "principais_kpis": [
                "Descreva KPIs se existirem, senão explique que não estão detalhados."
            ]
            }}
        ],
        "tabelas_relevantes": [
            {{
            "titulo": "Título ou identificação aproximada da tabela (ex.: Tabela 1 – Overview of pilots).",
            "tema": "tema da tabela (ex.: pilotos, cronograma, KPIs, parceiros, riscos, etc.)",
            "descricao": "Resumo em 1–2 frases do que essa tabela mostra (sem copiar números)."
            }}
        ],
        "riscos": [
            "Riscos, desafios ou problemas mencionados no relatório.",
            "Inclua atrasos, dependências de parceiros, limitações técnicas, etc."
        ],
        "licoes": [
            "Lições aprendidas, recomendações ou boas práticas identificadas.",
            "Inclua aprendizados sobre gestão de piloto, requisitos legais, privacidade, etc."
        ],
        "ideias_mc_sonae": [
            "Ideia de como algo do ARIES pode inspirar o projeto acadêmico MC Sonae.",
            "Conecte com dashboards, KPIs, gestão de continuidade, privacidade, etc."
        ]
        }}

        Regras importantes:
        - NÃO escreva nada fora do JSON acima.
        - NÃO use markdown no conteúdo dos campos (sem **negrito**, sem bullets markdown).
        - Use strings simples, listas simples.
        - Se alguma informação não existir no relatório, use frases curtas indicando que não há detalhes suficientes.
        - Considere também as tabelas descritas no texto para preencher os campos.
        - Não invente Work Packages ou pilotos que não existam no texto; apenas resuma o que estiver mencionado.

        TRECHO DO RELATÓRIO (em inglês):
        \"\"\"{trecho}\"\"\"
        """.strip()

        base = {
            "visao_geral": "",
            "papel_sonae": "",
            "work_packages": [],
            "pilotos": [],
            "tabelas_relevantes": [],
            "riscos": [],
            "licoes": [],
            "ideias_mc_sonae": [],
        }

        try:
            resp = self.gemini_model.generate_content(
                prompt,
                generation_config=self.gemini_config,
            )
            raw = (getattr(resp, "text", None) or str(resp) or "").strip()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                # Plano B: tentar achar o bloco entre { ... }
                if "{" in raw and "}" in raw:
                    sub = raw[raw.find("{"): raw.rfind("}") + 1]
                    data = json.loads(sub)
                else:
                    raise

            # Garante apenas as chaves que esperamos
            for k in base.keys():
                if k in data:
                    base[k] = data[k]

            return base

        except Exception as e:
            print(f"AVISO: Falha ao gerar insights ARIES: {e}")
            return base
        
# ======================================================================================
# DatabaseRepository (ORM + Refresh Tokens + Regras)
# ======================================================================================
class DatabaseRepository:
    def __init__(self, session_factory, ai_service: AIService):
        """`session_factory` cria sessões (scoped) e `ai_service` suporta resumos.
        Não muda a forma de inicialização nem efeitos colaterais (prints).
        """
        self.session_factory = session_factory
        self.ai_service = ai_service
        print("DatabaseRepository (ORM) inicializado.")

    # ------------- Utils -------------
    def _get_db(self) -> Session:
        """Abre uma sessão por chamada; *sempre* fechar em finally quando abrir manualmente."""
        return self.session_factory()

    # ------------- Usuários / RBAC -------------
    def usuario_tem_papel(self, email: str, role_name: str) -> bool:
        """Retorna True se o usuário possui o papel informado (join pelos vínculos)."""
        with self.session_factory() as session:
            q = (
                session.query(models.Papel)
                .join(models.UsuarioPapel, models.Papel.id_papel == models.UsuarioPapel.id_papel_fk)
                .join(models.Usuario, models.UsuarioPapel.id_usuario_fk == models.Usuario.id_usuario)
                .filter(models.Usuario.email == email, models.Papel.nome == role_name)
            )
            return session.query(q.exists()).scalar()

    def get_usuario_por_email(self, email: str) -> Optional[models.Usuario]:
        db: Session = self._get_db()
        try:
            return db.query(models.Usuario).filter(models.Usuario.email == email).first()
        finally:
            db.close()

    def set_senha_hash_usuario(self, email: str, new_hash: str) -> None:
        db: Session = self._get_db()
        try:
            user = db.query(models.Usuario).filter(models.Usuario.email == email).first()
            if not user:
                return
            user.senha_hash = new_hash
            db.commit()
        finally:
            db.close()

    def get_permissoes_usuario(self, email: str) -> List[str]:
        """Retorna permissões efetivas (distinct) agregando por papéis do usuário."""
        db: Session = self._get_db()
        try:
            q = (
                db.query(models.Permissao.nome_permissao)
                .join(models.PapelPermissao, models.Permissao.id_permissao == models.PapelPermissao.id_permissao_fk)
                .join(models.Papel, models.Papel.id_papel == models.PapelPermissao.id_papel_fk)
                .join(models.UsuarioPapel, models.Papel.id_papel == models.UsuarioPapel.id_papel_fk)
                .join(models.Usuario, models.Usuario.id_usuario == models.UsuarioPapel.id_usuario_fk)
                .filter(models.Usuario.email == email)
                .distinct()
            )
            return [row[0] for row in q.all()]
        finally:
            db.close()

    def get_perfil_usuario(self, email: str) -> dict:
        """Dados básicos + lista de cargos (nomes de papéis vinculados)."""
        db = self._get_db()
        try:
            u = db.query(models.Usuario).filter(models.Usuario.email == email).first()
            if not u:
                return {}
            cargos = (
                db.query(models.Papel.nome)
                .join(models.UsuarioPapel, models.Papel.id_papel == models.UsuarioPapel.id_papel_fk)
                .filter(models.UsuarioPapel.id_usuario_fk == u.id_usuario)
                .all()
            )
            return {
                "nome": u.nome,
                "email": u.email,
                "setor": u.setor,
                "cargos": [c[0] for c in cargos],
            }
        finally:
            db.close()

    # ------------- Refresh Tokens -------------
    @staticmethod
    def _hash_refresh_token(plain_token: str) -> str:
        """Hash SHA‑256 do refresh token **com pepper** (REFRESH_TOKEN_PEPPER).
        Armazena apenas o hash no BD para busca/rotação/revogação.
        """
        pepper = os.getenv("REFRESH_TOKEN_PEPPER", "")
        return hashlib.sha256((pepper + plain_token).encode("utf-8")).hexdigest()

    # === CREATE ===
    def criar_refresh_token(self, db: Session, user_id: int) -> str:
        """Cria refresh token (plaintext devolvido ao cliente; hash no BD)."""
        plain_token = AuthService.criar_refresh_token_texto_puro()
        token_hash = self._hash_refresh_token(plain_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        db.add(models.RefreshToken(
            id_usuario_fk=user_id,
            token_hash=token_hash,
            data_expiracao=expires_at
        ))
        db.commit()
        return plain_token

    # === READ ===
    def get_refresh_token(self, db: Session, plain_token: str) -> Optional[models.RefreshToken]:
        """Busca refresh token por **hash** e valida expiração >= agora (UTC)."""
        token_hash = self._hash_refresh_token(plain_token)
        now = datetime.now(timezone.utc)
        return (
            db.query(models.RefreshToken)
            .filter(
                models.RefreshToken.token_hash == token_hash,
                models.RefreshToken.data_expiracao >= now
            )
            .first()
        )

    def get_refresh_token_dono_email(self, db: Session, plain_token: str) -> Optional[str]:
        rt = self.get_refresh_token(db, plain_token)
        if not rt:
            return None
        user = db.query(models.Usuario).filter(models.Usuario.id_usuario == rt.id_usuario_fk).first()
        return user.email if user else None

    # === ROTATE ===
    def rotate_refresh_token(self, db: Session, old_plain_token: str, new_plain_token: str) -> bool:
        """Troca o hash armazenado (rotate) e renova expiração (idempotente por busca)."""
        rt = self.get_refresh_token(db, old_plain_token)
        if not rt:
            return False
        try:
            rt.token_hash = self._hash_refresh_token(new_plain_token)
            rt.data_expiracao = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False

    # === REVOKE ===
    def revogar_refresh_token_para_texto_puro(self, db: Session, plain_token: str) -> int:
        """Revoga um refresh token específico (busca por plaintext → hash interno)."""
        rt = self.get_refresh_token(db, plain_token)
        if not rt:
            return 0
        db.delete(rt)
        db.commit()
        return 1

    def revogar_todos_refresh_tokens_do_usuario(self, user_id: int) -> int:
        db: Session = self._get_db()
        try:
            result = db.execute(
                delete(models.RefreshToken).where(models.RefreshToken.id_usuario_fk == user_id)
            )
            db.commit()
            return int(result.rowcount or 0)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # ------------- Relatórios / Dashboards -------------
    def salvar_relatorio_processado(self, report: models.ParsedReport, author_id: int | None = None) -> int:
        """Persiste Projeto (upsert parcial), Relatório, Milestones e KPIs.
        - Se Gemini está configurado, sobrescreve `resumo_executivo` com resumo IA.
        - Resolve FK do gerente por nome (apenas se existir e tiver papel compatível).
        - Garante acesso do gerente ao projeto (papel conforme `_papel_acesso_por_usuario`).
        """
        db: Session = self._get_db()
        try:
            if self.ai_service.gemini_model:
                print("Gerando resumo com IA (Gemini)...")
                resumo_ia = self.ai_service.gerar_resumo_gemini(report, report.milestones, report.kpis)
                report.resumo_executivo = resumo_ia

            # Procura a FK do gerente pelo nome vindo no relatório
            gerente_fk = self._buscar_fk_gerente_por_nome(db, report.gerente_projeto)

            # Garante acesso do gerente com papel vindo do banco
            if gerente_fk is not None:
                papel_acesso_gerente = self._papel_acesso_por_usuario(db, gerente_fk)
                self._grant_acesso_projeto(
                    db,
                    codigo_projeto=report.codigo_projeto,
                    id_usuario=gerente_fk,
                    papel=papel_acesso_gerente,
                )

            # Orçamento total a partir dos KPIs
            orcamento_total_kpi = next((kpi for kpi in report.kpis if kpi.nome_kpi == "Orçamento Total"), None)

            projeto_orm = db.query(models.Projeto).get(report.codigo_projeto)
            if projeto_orm:
                projeto_orm.nome_projeto = report.nome_projeto
                projeto_orm.gerente_projeto = report.gerente_projeto
                if gerente_fk is not None:
                    projeto_orm.id_gerente_fk = gerente_fk  # << preencher/atualizar FK
                if orcamento_total_kpi and orcamento_total_kpi.valor_numerico_kpi is not None:
                    projeto_orm.orcamento_total = orcamento_total_kpi.valor_numerico_kpi
            else:
                new_budget = (
                    orcamento_total_kpi.valor_numerico_kpi
                    if orcamento_total_kpi and orcamento_total_kpi.valor_numerico_kpi is not None
                    else 0.0
                )
                projeto_orm = models.Projeto(
                    codigo_projeto=report.codigo_projeto,
                    nome_projeto=report.nome_projeto,
                    gerente_projeto=report.gerente_projeto,
                    id_gerente_fk=gerente_fk,
                    orcamento_total=new_budget,
                    area_negocio=report.area_negocio,
                )
                db.add(projeto_orm)

            # Cria o relatório
            relatorio_orm = models.RelatorioSprint(
                numero_sprint=report.numero_sprint,
                status_geral=report.status_geral,
                resumo_executivo=report.resumo_executivo,
                riscos_e_impedimentos=report.riscos_e_impedimentos,
                proximos_passos=report.proximos_passos,
                codigo_projeto_fk=report.codigo_projeto,
                story_points_planejados=report.story_points_planejados,
                story_points_entregues=report.story_points_entregues,
                id_autor_fk=author_id,
            )

            if report.milestones:
                relatorio_orm.milestones = [models.MilestoneHistorico(**m.model_dump()) for m in report.milestones]
            if report.kpis:
                relatorio_orm.kpis = [models.RelatorioKPI(**k.model_dump()) for k in report.kpis]

            db.add(relatorio_orm)
            db.commit()

            print(f"SUCESSO: Relatório salvo para o Projeto {report.codigo_projeto} (ID: {relatorio_orm.id_relatorio}).")
            return relatorio_orm.id_relatorio

        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def _papel_acesso_por_usuario(self, db, id_usuario: int) -> str:
        """Dado um usuário, retorna o **papel mais prioritário** entre seus vínculos.
        Ordem (alta→baixa): Administrador > Diretor > Gestor de Projetos > Analista > Visualizador
        """
        rows = (
            db.query(models.Papel.nome)
            .join(models.UsuarioPapel, models.UsuarioPapel.id_papel_fk == models.Papel.id_papel)
            .filter(models.UsuarioPapel.id_usuario_fk == id_usuario)
            .all()
        )
        nomes = {r[0] for r in rows}

        prioridade = [
            "Administrador",
            "Diretor",
            "Gestor de Projetos",
            "Analista",
            "Visualizador",
        ]
        for cargo in prioridade:
            if cargo in nomes:
                return cargo
        return "Visualizador"

    def _grant_acesso_projeto(self, db, codigo_projeto: str, id_usuario: int, papel: str) -> None:
        """Garante (idempotente) um vínculo de acesso ao projeto com o papel informado."""
        vinc = (
            db.query(models.ProjetoUsuarioAcesso)
            .filter(
                models.ProjetoUsuarioAcesso.codigo_projeto_fk == codigo_projeto,
                models.ProjetoUsuarioAcesso.id_usuario_fk == id_usuario,
            )
            .first()
        )
        if vinc:
            if papel and vinc.papel_acesso != papel:
                vinc.papel_acesso = papel
            return

        db.add(models.ProjetoUsuarioAcesso(
            codigo_projeto_fk=codigo_projeto,
            id_usuario_fk=id_usuario,
            papel_acesso=papel or "Visualizador",
        ))

    def _buscar_fk_gerente_por_nome(self, db: Session, nome_gerente: str | None) -> int | None:
        """Resolve a FK do gerente *apenas* se houver um usuário com papel "Gestor de Projetos".
        Caso não encontre, retorna `None` (o nome string continua salvo no Projeto).
        """
        if not nome_gerente or not nome_gerente.strip():
            return None

        nome_norm = nome_gerente.strip()
        row = (
            db.query(models.Usuario.id_usuario)
            .join(models.UsuarioPapel, models.UsuarioPapel.id_usuario_fk == models.Usuario.id_usuario)
            .join(models.Papel, models.Papel.id_papel == models.UsuarioPapel.id_papel_fk)
            .filter(func.lower(models.Usuario.nome) == func.lower(nome_norm))
            .filter(models.Papel.nome == "Gestor de Projetos")
            .first()
        )
        return row.id_usuario if row else None

    def get_estatisticas_dashboard(self) -> Optional[models.DashboardStats]:
        """Agrega métricas do *último relatório de cada projeto* ativo.
        - Conta projetos em Dia/Risco/Atrasado.
        - Soma investimento total executado (KPI "Custo Realizado").
        """
        db: Session = self._get_db()
        try:
            # Subconsulta: última sprint por projeto
            subquery = (
                db.query(
                    models.RelatorioSprint.codigo_projeto_fk,
                    func.max(models.RelatorioSprint.numero_sprint).label("max_sprint"),
                )
                .group_by(models.RelatorioSprint.codigo_projeto_fk)
                .subquery()
            )

            # Base: último relatório por projeto + join com Projetos (apenas ativos)
            base = (
                db.query(models.RelatorioSprint)
                .join(
                    subquery,
                    (models.RelatorioSprint.codigo_projeto_fk == subquery.c.codigo_projeto_fk)
                    & (models.RelatorioSprint.numero_sprint == subquery.c.max_sprint),
                )
                .join(
                    models.Projeto,
                    models.Projeto.codigo_projeto == models.RelatorioSprint.codigo_projeto_fk,
                )
                .filter(models.Projeto.is_deletado == 0)   # <<--- só ativos
            )

            # Agregados do quadro-resumo
            query = db.query(
                func.count().label("total_projetos"),
                func.sum(
                    case((models.RelatorioSprint.status_geral == "Em Dia", 1), else_=0)
                ).label("projetos_em_dia"),
                func.sum(
                    case((models.RelatorioSprint.status_geral == "Em Risco", 1), else_=0)
                ).label("projetos_em_risco"),
                func.sum(
                    case((models.RelatorioSprint.status_geral == "Atrasado", 1), else_=0)
                ).label("projetos_atrasados"),
            ).select_from(base)

            resultado = query.one()

            # Investimento total (somente projetos ativos)
            investimento_total = (
                db.query(func.sum(models.RelatorioKPI.valor_numerico_kpi))
                .join(
                    models.RelatorioSprint,
                    models.RelatorioSprint.id_relatorio == models.RelatorioKPI.id_relatorio_fk,
                )
                .join(
                    models.Projeto,
                    models.Projeto.codigo_projeto == models.RelatorioSprint.codigo_projeto_fk,
                )
                .filter(
                    models.RelatorioKPI.nome_kpi == "Custo Realizado",
                    models.Projeto.is_deletado == 0,  # <<--- só ativos
                )
                .scalar()
                or 0.0
            )

            stats = resultado._asdict()
            stats["investimento_total_executado"] = investimento_total
            return models.DashboardStats(**stats)
        finally:
            db.close()

    def get_lista_projetos(self) -> List[models.ProjectListItem]:
        """Lista de projetos **ativos** (nome/código/área) ordenada alfabeticamente."""
        db: Session = self._get_db()
        try:
            base = db.query(models.Projeto)
            base = self._somente_ativos(base)  # <<--- filtro atual
            projetos_orm = base.order_by(models.Projeto.nome_projeto).all()

            def _area_as_str(p):
                a = getattr(p, "area_negocio", None)
                return (a.value if hasattr(a, "value") else a) or ""

            return [
                models.ProjectListItem(
                    codigo_projeto=p.codigo_projeto,
                    nome_projeto=p.nome_projeto,
                    area_negocio=_area_as_str(p),
                )
                for p in projetos_orm
            ]
        except Exception as e:
            print(f"ERRO AO BUSCAR LISTA DE PROJETOS (ORM): {e}")
            return []
        finally:
            db.close()

    def get_sprints_do_projeto(self, codigo_projeto: str) -> List[models.SprintListItem]:
        db: Session = self._get_db()
        try:
            sprints_orm = (
                db.query(models.RelatorioSprint)
                .filter(models.RelatorioSprint.codigo_projeto_fk == codigo_projeto)
                .order_by(desc(models.RelatorioSprint.numero_sprint))
                .all()
            )
            return [models.SprintListItem.model_validate(s) for s in sprints_orm]
        finally:
            db.close()

    def get_detalhe_do_relatorio(self, id_relatorio: int) -> Optional[models.ReportDetailResponse]:
        """Carrega relatório + joins (projeto, milestones, kpis) e medeia p/ DTOs Pydantic."""
        db: Session = self._get_db()
        try:
            relatorio_atual = (
                db.query(models.RelatorioSprint)
                .options(
                    joinedload(models.RelatorioSprint.projeto),
                    joinedload(models.RelatorioSprint.milestones),
                    joinedload(models.RelatorioSprint.kpis),
                )
                .get(id_relatorio)
            )

            if not relatorio_atual:
                return None

            dados_para_detalhe = relatorio_atual.__dict__
            if relatorio_atual.projeto:
                dados_para_detalhe["codigo_projeto"] = relatorio_atual.projeto.codigo_projeto
                dados_para_detalhe["nome_projeto"] = relatorio_atual.projeto.nome_projeto
                dados_para_detalhe["gerente_projeto"] = relatorio_atual.projeto.gerente_projeto
                dados_para_detalhe["orcamento_total"] = relatorio_atual.projeto.orcamento_total

            report_detail_obj = models.ReportDetail(**dados_para_detalhe)
            milestones = [models.Milestone.model_validate(m) for m in relatorio_atual.milestones]
            kpis = [models.KPI.model_validate(k) for k in relatorio_atual.kpis]

            return models.ReportDetailResponse(
                detalhe_relatorio=report_detail_obj,
                milestones=milestones,
                kpis=kpis,
            )
        finally:
            db.close()

    def get_historico_kpi(self, codigo_projeto: str, nome_kpi: str) -> List[models.FinancialHistoryItem]:
        """Série temporal do KPI por sprint, com orçamento total do projeto para contexto."""
        db: Session = self._get_db()
        try:
            projeto = (
                db.query(models.Projeto.orcamento_total)
                .filter(models.Projeto.codigo_projeto == codigo_projeto)
                .first()
            )
            orcamento = projeto.orcamento_total if projeto else 0.0
            kpi_history_orm = (
                db.query(models.RelatorioSprint.numero_sprint, models.RelatorioKPI.valor_numerico_kpi)
                .join(models.RelatorioKPI, models.RelatorioSprint.id_relatorio == models.RelatorioKPI.id_relatorio_fk)
                .filter(
                    models.RelatorioSprint.codigo_projeto_fk == codigo_projeto,
                    models.RelatorioKPI.nome_kpi == nome_kpi,
                )
                .order_by(models.RelatorioSprint.numero_sprint)
                .all()
            )
            historico = [
                models.FinancialHistoryItem(
                    sprint_number=item.numero_sprint,
                    cost_realized=item.valor_numerico_kpi or 0.0,
                    budget_total=orcamento,
                )
                for item in kpi_history_orm
            ]
            return historico
        except Exception as e:
            print(f"ERRO AO BUSCAR HISTÓRICO DE KPI (ORM): {e}")
            return []
        finally:
            db.close()

    # --- Solicitações de Acesso (CRUD + aprovação) ---
    def criar_solicitacao_acesso(
        self, * , nome: str, email: str, senha: str, setor: str, justificativa: str, cargo: str,) -> None:
        """Registra solicitação 'aguardando' (com `senha_hash`) se não houver conflito.
        - Valida cargo permitido e ausência de usuário/pendência.
        - Mantém todos os campos e validações do original.
        """
        db: Session = self._get_db()
        try:
            email_norm = (email or "").strip().lower()
            nome_norm  = (nome or "").strip()
            setor_norm = (setor or "").strip()
            just_norm  = (justificativa or "").strip()
            cargo_norm = (cargo or "").strip()

            CARGOS_VALIDOS = {
                "Administrador",
                "Analista",
                "Gestor de Projetos",
                "Diretor",
                "Visualizador",
            }
            if cargo_norm not in CARGOS_VALIDOS:
                raise RuntimeError("Cargo inválido.")

            exists_user = (
                db.query(models.Usuario.id_usuario)
                .filter(models.Usuario.email == email_norm)
                .first()
            )
            if exists_user:
                raise RuntimeError("E-mail já cadastrado.")

            exists_pending = (
                db.query(models.UsuarioSolicitacaoAcesso.id_solicitacao)
                .filter(
                    models.UsuarioSolicitacaoAcesso.email == email_norm,
                    models.UsuarioSolicitacaoAcesso.status == "aguardando",
                )
                .first()
            )
            if exists_pending:
                raise RuntimeError("Já existe solicitação pendente para este e-mail.")

            auth = AuthService()
            senha_hash = auth.get_hash_senha(senha)

            solic = models.UsuarioSolicitacaoAcesso(
                nome=nome_norm,
                email=email_norm,
                senha_hash=senha_hash,
                setor=setor_norm,
                justificativa=just_norm,
                cargo=cargo_norm,                 
                status="aguardando",
                criado_em=datetime.utcnow(),
            )
            db.add(solic)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def listar_solicitacoes(self, *, status: str = "aguardando"):
        db: Session = self._get_db()
        try:
            q = (
                db.query(models.UsuarioSolicitacaoAcesso, models.Usuario.nome.label("decidido_por_nome"))
                .outerjoin(
                    models.Usuario,
                    models.Usuario.id_usuario == models.UsuarioSolicitacaoAcesso.decidido_por
                )
                .filter(models.UsuarioSolicitacaoAcesso.status == status)
                .order_by(models.UsuarioSolicitacaoAcesso.criado_em.asc())
            )
            rows = q.all()

            out = []
            for sol, admin_nome in rows:
                d = {k: v for k, v in sol.__dict__.items() if k != "_sa_instance_state"}
                d["decidido_por_nome"] = admin_nome
                out.append(d)
            return out
        finally:
            db.close()

    def decidir_solicitacao(self, id_solic: int, admin_id: int, decisao: str, motivo: Optional[str] = None):
        """Aprova ou rejeita a solicitação **sem deletar o registro**.
        - rejeitar  -> status='rejeitado', mantém linha
        - aprovar   -> cria usuário + vínculo de papel, status='aprovado'
        """
        db: Session = self._get_db()
        try:
            sol = db.get(models.UsuarioSolicitacaoAcesso, id_solic)
            if not sol:
                raise RuntimeError("Solicitação não encontrada.")
            if sol.status != "aguardando":
                raise RuntimeError("Solicitação já foi decidida.")

            decisao_norm = (decisao or "").strip().lower()
            if decisao_norm not in {"aprovar", "rejeitar"}:
                raise RuntimeError("Decisão inválida.")

            # ===== REJEITAR (não deleta) =====
            if decisao_norm == "rejeitar":
                sol.status = "rejeitado"
                sol.motivo_decisao = (motivo or None)
                sol.decidido_por = admin_id
                sol.decidido_em = datetime.utcnow()
                db.commit()
                return {"message": "Solicitação rejeitada."}

            # ===== APROVAR =====
            cargo = (sol.cargo or "").strip()
            papel = db.query(models.Papel).filter(models.Papel.nome == cargo).first()
            if not papel:
                raise RuntimeError("Papel/cargo não encontrado no sistema.")

            email_norm = (sol.email or "").strip().lower()
            if not email_norm:
                raise RuntimeError("E-mail da solicitação é inválido.")
            if db.query(models.Usuario).filter(models.Usuario.email == email_norm).first():
                raise RuntimeError("Já existe um usuário com este e-mail.")

            novo = models.Usuario(
                nome=(sol.nome or "").strip(),
                email=email_norm,
                senha_hash=sol.senha_hash,
                setor=(sol.setor or None),
            )
            db.add(novo)
            db.flush()  # obtém novo.id_usuario

            # Vincula papel se ainda não tiver
            ja_tem = (
                db.query(models.UsuarioPapel)
                .filter(
                    models.UsuarioPapel.id_usuario_fk == novo.id_usuario,
                    models.UsuarioPapel.id_papel_fk == papel.id_papel,
                )
                .first()
            )
            if not ja_tem:
                db.add(models.UsuarioPapel(
                    id_usuario_fk=novo.id_usuario,
                    id_papel_fk=papel.id_papel,
                    # se teu modelo NÃO tem esse campo, não passe 'criado_em'
                ))

            # Marca decisão (mantém a linha; não deleta)
            sol.status = "aprovado"
            sol.motivo_decisao = (motivo or None)
            sol.decidido_por = admin_id
            sol.decidido_em = datetime.utcnow()

            db.commit()
            return {"message": "Solicitação aprovada."}

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()



    def atualizar_usuario_limitado(self, *, id_usuario: int, nome: str | None, setor: str | None) -> None:
        db: Session = self._get_db()
        try:
            user = db.query(models.Usuario).get(id_usuario)
            if not user:
                raise RuntimeError("Usuário não encontrado.")

            changed = False
            if nome is not None and nome.strip() and nome.strip() != user.nome:
                user.nome = nome.strip()
                changed = True
            if setor is not None and setor.strip() and setor.strip() != (user.setor or ""):
                user.setor = setor.strip()
                changed = True

            if not changed:
                return

            user.data_atualizacao = datetime.utcnow()
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def listar_usuarios(self, q: str | None = None) -> list[dict]:
        """Lista usuários + **um** cargo prioritário (colapsado) por usuário.
        - Usa `CARGO_ORDER` para priorizar: Admin > Gestor > Analista > Diretor > Visualizador.
        - Ordena por `id_usuario` e, por usuário, cargo de maior prioridade.
        """
        db: Session = self._get_db()
        try:
            CARGO_ORDER = case(
                (models.Papel.nome == "Administrador",        5),
                (models.Papel.nome == "Gestor de Projetos",   4),
                (models.Papel.nome == "Analista",             3),
                (models.Papel.nome == "Diretor",              2),
                (models.Papel.nome == "Visualizador",         1),
                else_=0,
            ).label("cargo_rank")

            qry = (
                db.query(
                    models.Usuario.id_usuario,
                    models.Usuario.nome,
                    models.Usuario.email,
                    models.Usuario.setor,
                    models.Papel.nome.label("cargo"),
                    CARGO_ORDER,
                )
                .outerjoin(
                    models.UsuarioPapel,
                    models.Usuario.id_usuario == models.UsuarioPapel.id_usuario_fk,
                )
                .outerjoin(
                    models.Papel,
                    models.Papel.id_papel == models.UsuarioPapel.id_papel_fk,
                )
            )

            if q:
                qnorm = f"%{q.strip().lower()}%"
                qry = qry.filter(
                    (models.Usuario.nome.ilike(qnorm))
                    | (models.Usuario.email.ilike(qnorm))
                )

            rows = qry.order_by(models.Usuario.id_usuario.asc(), CARGO_ORDER.desc()).all()

            out: dict[int, dict] = {}
            for r in rows:
                if r.id_usuario not in out:
                    out[r.id_usuario] = {
                        "id_usuario": r.id_usuario,
                        "nome": r.nome,
                        "email": r.email,
                        "setor": r.setor,
                        "cargo": r.cargo or "",
                    }

            return list(out.values())
        finally:
            db.close()

    def _garantir_acesso_gerente(db, codigo_projeto: str, id_gerente: int):
        """(Compat) Cria vínculo de acesso de 'Gestor de Projetos' se não existir."""
        exists = (
            db.query(models.ProjetoUsuarioAcesso.id_acesso)
            .filter(models.ProjetoUsuarioAcesso.codigo_projeto_fk == codigo_projeto,
                    models.ProjetoUsuarioAcesso.id_usuario_fk == id_gerente)
            .first()
        )
        if not exists:
            db.add(models.ProjetoUsuarioAcesso(
                codigo_projeto_fk=codigo_projeto,
                id_usuario_fk=id_gerente,
                papel_acesso="Gestor de Projetos"
            ))

    # -------- SOFT DELETE  --------
    def _somente_ativos(self, query):
        """Filtra para considerar apenas projetos com is_deletado = 0."""
        return query.filter(models.Projeto.is_deletado == 0)

    def _pode_gerir_projeto(self, *, projeto, user_id: int, is_admin: bool) -> bool:
        """Regra: admin sempre pode; senão, precisa ser o gerente (FK)."""
        if is_admin:
            return True
        return (projeto.id_gerente_fk is not None) and (projeto.id_gerente_fk == user_id)

    def can_soft_delete_projeto(self, *, email: str, codigo_projeto: str) -> bool:
        """Pode enviar à lixeira se: Admin **ou** Gerente do projeto (via FK)."""
        db = self._get_db()
        try:
            user = db.query(models.Usuario).filter(models.Usuario.email == email).first()
            if not user:
                return False

            is_admin = self.usuario_tem_papel(email, "Administrador")

            proj = db.query(models.Projeto).filter(models.Projeto.codigo_projeto == codigo_projeto).first()
            if not proj:
                return False

            return self._pode_gerir_projeto(projeto=proj, user_id=user.id_usuario, is_admin=is_admin)
        finally:
            db.close()

    def soft_delete_projeto(self, *, codigo_projeto: str, admin_id: int | None = None, motivo: str | None = None) -> bool:
        """Marca `is_deletado=1` sem apagar filhos (idempotente se já estiver na lixeira)."""
        db = self._get_db()
        try:
            proj = (
                db.query(models.Projeto)
                .filter(models.Projeto.codigo_projeto == codigo_projeto)
                .first()
            )
            if not proj:
                return False

            if bool(proj.is_deletado):
                return True

            proj.is_deletado = 1
            proj.deletado_em = datetime.utcnow()
            proj.deletado_por = admin_id
            proj.motivo_exclusao = (motivo or None)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def restaurar_projeto(self, *, codigo_projeto: str, user_id: int, is_admin: bool = False) -> bool:
        """Restaura projeto da lixeira. Admin sempre pode; senão, apenas o gerente (FK)."""
        db: Session = self._get_db()
        try:
            prj = db.query(models.Projeto).get(codigo_projeto)
            if not prj or prj.is_deletado == 0:
                return False

            if not self._pode_gerir_projeto(projeto=prj, user_id=user_id, is_admin=is_admin):
                raise RuntimeError("Sem permissão para restaurar este projeto.")

            prj.is_deletado = 0
            prj.deletado_em = None
            prj.deletado_por = None
            prj.motivo_exclusao = None
            db.commit()
            return True
        except:
            db.rollback()
            raise
        finally:
            db.close()

    def remover_projeto_definitivo(self, codigo_projeto: str) -> bool:
        """Hard delete (DELETE FROM Projetos …). Cascatas cuidam das filhas."""
        db: Session = self._get_db()
        try:
            proj = db.query(models.Projeto).get(codigo_projeto)
            if not proj:
                return False
            db.delete(proj)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def listar_projetos_deletados(self) -> list[dict]:
        """Tela 'Gerenciar Exclusões': lista projetos com `is_deletado=1` (join com autor)."""
        db: Session = self._get_db()
        try:
            rows = (
                db.query(
                    models.Projeto.codigo_projeto,
                    models.Projeto.nome_projeto,
                    models.Projeto.area_negocio,
                    models.Projeto.deletado_em,
                    models.Projeto.motivo_exclusao,
                    models.Usuario.nome.label("deletado_por_nome"),
                )
                .outerjoin(models.Usuario, models.Usuario.id_usuario == models.Projeto.deletado_por)
                .filter(models.Projeto.is_deletado == 1)
                .order_by(models.Projeto.deletado_em.desc())
                .all()
            )
            return [
                dict(
                    codigo_projeto=r.codigo_projeto,
                    nome_projeto=r.nome_projeto,
                    area_negocio=r.area_negocio,
                    deletado_em=r.deletado_em,
                    motivo=r.motivo_exclusao or "",
                    deletado_por_nome=r.deletado_por_nome or "—",
                ) for r in rows
            ]
        finally:
            db.close()

    def listar_projetos_visiveis(self, *, email: str) -> list[dict]:
        """Mapeia todos os projetos que o usuário **pode ver** (Admin, Gerente FK, Acesso, Autor)."""
        db = self._get_db()
        try:
            u = db.query(models.Usuario).filter(models.Usuario.email == email).first()
            if not u:
                return []

            uid = u.id_usuario
            is_admin = self.eh_admin(email)
            projetos_map: dict[str, str] = {}

            if is_admin:
                rows = (db.query(models.Projeto.codigo_projeto, models.Projeto.nome_projeto)
                        .filter(models.Projeto.is_deletado == 0)
                        .order_by(models.Projeto.nome_projeto.asc())
                        .all())
                for r in rows: projetos_map[r.codigo_projeto] = r.nome_projeto

            rows_fk = (db.query(models.Projeto.codigo_projeto, models.Projeto.nome_projeto)
                        .filter(models.Projeto.is_deletado == 0,
                                models.Projeto.id_gerente_fk == uid).all())
            for r in rows_fk: projetos_map[r.codigo_projeto] = r.nome_projeto

            rows_acc = (db.query(models.Projeto.codigo_projeto, models.Projeto.nome_projeto)
                        .join(models.ProjetoUsuarioAcesso,
                                models.ProjetoUsuarioAcesso.codigo_projeto_fk == models.Projeto.codigo_projeto)
                        .filter(models.Projeto.is_deletado == 0,
                                models.ProjetoUsuarioAcesso.id_usuario_fk == uid).all())
            for r in rows_acc: projetos_map[r.codigo_projeto] = r.nome_projeto

            rows_autor = (db.query(models.Projeto.codigo_projeto, models.Projeto.nome_projeto)
                            .join(models.RelatorioSprint,
                                models.RelatorioSprint.codigo_projeto_fk == models.Projeto.codigo_projeto)
                            .filter(models.Projeto.is_deletado == 0,
                                    models.RelatorioSprint.id_autor_fk == uid).all())
            for r in rows_autor: projetos_map[r.codigo_projeto] = r.nome_projeto

            return [
                dict(codigo_projeto=cod, nome_projeto=nome)
                for cod, nome in sorted(projetos_map.items(), key=lambda kv: kv[1].lower())
            ]
        finally:
            db.close()

    # --- Helpers RBAC para soft delete ---
    def eh_admin(self, email: str) -> bool:
        return self.usuario_tem_papel(email, "Administrador")

    def eh_gestor(self, email: str) -> bool:
        return self.usuario_tem_papel(email, "Gestor de Projetos")

    def _norm(self, s: str | None) -> str:
        return (s or "").strip().lower()

    def get_projeto(self, codigo_projeto: str) -> Optional[models.Projeto]:
        db: Session = self._get_db()
        try:
            return db.query(models.Projeto).get(codigo_projeto)
        finally:
            db.close()

    def permissao_deletar_projeto(self, *, email: str, codigo_projeto: str) -> bool:
        """Admin sempre pode. Gestor pode se for gerente (comparação por **nome** string)."""
        if self.eh_admin(email):
            return True
        if not self.eh_gestor(email):
            return False

        user = self.get_usuario_por_email(email)
        if not user:
            return False

        proj = self.get_projeto(codigo_projeto)
        if not proj:
            return False

        # Comparação por NOME (modelo guarda string em `gerente_projeto`)
        return self._norm(proj.gerente_projeto) == self._norm(user.nome)

    def listar_projetos_gerenciados(self, *, email: str) -> list[dict]:
        """Projetos onde o usuário é gerente (FK), admin, autor, ou (fallback) por nome único.
        Mantém a mesma ordem e deduplicação por mapa.
        """
        db = self._get_db()
        try:
            u = (
                db.query(models.Usuario.id_usuario, models.Usuario.nome, models.Usuario.email)
                .filter(models.Usuario.email == email)
                .first()
            )
            if not u:
                return []

            uid = u.id_usuario
            nome = u.nome

            is_admin = (
                db.query(models.Papel.id_papel)
                .join(models.UsuarioPapel, models.Papel.id_papel == models.UsuarioPapel.id_papel_fk)
                .filter(models.UsuarioPapel.id_usuario_fk == uid, models.Papel.nome == "Administrador")
                .first()
                is not None
            )

            projetos_map: dict[str, str] = {}

            if is_admin:
                rows_all = (
                    db.query(models.Projeto.codigo_projeto, models.Projeto.nome_projeto)
                    .filter(models.Projeto.is_deletado == 0)
                    .order_by(models.Projeto.nome_projeto.asc())
                    .all()
                )
                for r in rows_all:
                    projetos_map[r.codigo_projeto] = r.nome_projeto

            rows_fk = (
                db.query(models.Projeto.codigo_projeto, models.Projeto.nome_projeto)
                .filter(models.Projeto.is_deletado == 0)
                .filter(models.Projeto.id_gerente_fk == uid)
                .order_by(models.Projeto.nome_projeto.asc())
                .all()
            )
            for r in rows_fk:
                projetos_map[r.codigo_projeto] = r.nome_projeto

            rows_author = (
                db.query(models.Projeto.codigo_projeto, models.Projeto.nome_projeto)
                .join(models.RelatorioSprint, models.RelatorioSprint.codigo_projeto_fk == models.Projeto.codigo_projeto)
                .filter(models.Projeto.is_deletado == 0)
                .filter(models.RelatorioSprint.id_autor_fk == uid)
                .group_by(models.Projeto.codigo_projeto, models.Projeto.nome_projeto)
                .order_by(models.Projeto.nome_projeto.asc())
                .all()
            )
            for r in rows_author:
                projetos_map[r.codigo_projeto] = r.nome_projeto

            # Fallback temporário por nome (compatibilidade) — apenas se nada foi encontrado
            if not projetos_map:
                from sqlalchemy import func
                qtd = (
                    db.query(func.count(models.Usuario.id_usuario))
                    .filter(models.Usuario.nome == nome)
                    .scalar()
                )
                if qtd == 1:
                    rows_name = (
                        db.query(models.Projeto.codigo_projeto, models.Projeto.nome_projeto)
                        .filter(models.Projeto.is_deletado == 0)
                        .filter(models.Projeto.id_gerente_fk.is_(None))
                        .filter(models.Projeto.gerente_projeto == nome)
                        .order_by(models.Projeto.nome_projeto.asc())
                        .all()
                    )
                    for r in rows_name:
                        projetos_map[r.codigo_projeto] = r.nome_projeto

            out = [{"codigo_projeto": c, "nome_projeto": n} for c, n in projetos_map.items()]
            out.sort(key=lambda x: x["nome_projeto"].lower())
            return out

        finally:
            db.close()

    def listar_acessos_por_projeto(self, *, codigo_projeto: str) -> list[dict]:
        """Lista vínculos de acesso e dados básicos do usuário (join) ordenados por nome."""
        db = self._get_db()
        try:
            rows = (
                db.query(
                    models.ProjetoUsuarioAcesso.id_acesso,
                    models.ProjetoUsuarioAcesso.codigo_projeto_fk,
                    models.ProjetoUsuarioAcesso.id_usuario_fk,
                    models.ProjetoUsuarioAcesso.papel_acesso,
                    models.Usuario.nome.label("usuario_nome"),
                    models.Usuario.email.label("usuario_email"),
                )
                .join(models.Usuario, models.Usuario.id_usuario == models.ProjetoUsuarioAcesso.id_usuario_fk)
                .filter(models.ProjetoUsuarioAcesso.codigo_projeto_fk == codigo_projeto)
                .order_by(models.Usuario.nome.asc())
                .all()
            )
            return [
                dict(
                    id_acesso=r.id_acesso,
                    codigo_projeto_fk=r.codigo_projeto_fk,
                    id_usuario_fk=r.id_usuario_fk,
                    papel_acesso=r.papel_acesso,
                    usuario_nome=r.usuario_nome,
                    usuario_email=r.usuario_email,
                )
                for r in rows
            ]
        finally:
            db.close()

    def listar_acessos_por_usuario(self, *, id_usuario: int) -> list[dict]:
        """Lista códigos de projeto e papéis de acesso associados a um usuário."""
        db = self._get_db()
        try:
            rows = (
                db.query(
                    models.ProjetoUsuarioAcesso.codigo_projeto_fk,
                    models.ProjetoUsuarioAcesso.papel_acesso,
                )
                .filter(models.ProjetoUsuarioAcesso.id_usuario_fk == id_usuario)
                .all()
            )
            return [
                {"codigo_projeto_fk": r.codigo_projeto_fk, "papel_acesso": r.papel_acesso}
                for r in rows
            ]
        finally:
            db.close()

    def garantir_acesso_projeto(self, *, codigo_projeto: str, id_usuario: int, papel: str | None = None) -> dict:
        """Idempotente: garante um vínculo com `papel_final` (param ou deduzido por prioridade)."""
        db = self._get_db()
        try:
            papel_final = (papel or self._papel_acesso_por_usuario(db, id_usuario) or "Visualizador")
            vinc = (
                db.query(models.ProjetoUsuarioAcesso)
                .filter(
                    models.ProjetoUsuarioAcesso.codigo_projeto_fk == codigo_projeto,
                    models.ProjetoUsuarioAcesso.id_usuario_fk == id_usuario,
                ).first()
            )
            if vinc:
                if vinc.papel_acesso != papel_final:
                    vinc.papel_acesso = papel_final
            else:
                db.add(models.ProjetoUsuarioAcesso(
                    codigo_projeto_fk=codigo_projeto,
                    id_usuario_fk=id_usuario,
                    papel_acesso=papel_final,
                ))
            db.commit()
            return {"message": "Acesso garantido."}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def revogar_acesso_projeto(self, *, codigo_projeto: str, id_usuario: int) -> dict:
        """Remove vínculo de acesso ao projeto (se existir)."""
        db = self._get_db()
        try:
            db.query(models.ProjetoUsuarioAcesso).filter(
                models.ProjetoUsuarioAcesso.codigo_projeto_fk == codigo_projeto,
                models.ProjetoUsuarioAcesso.id_usuario_fk == id_usuario,
            ).delete(synchronize_session=False)
            db.commit()
            return {"message": "Acesso removido."}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def hard_delete_usuario(self, *, id_usuario: int) -> bool:
        """
        Hard delete (MySQL/ORM): remove DEFINITIVAMENTE o usuário e dependências,
        usando .query(...).filter(...).update(...) / .delete(...), sem update().where().values().
        """
        db = self._get_db()
        try:
            u = db.query(models.Usuario).get(id_usuario)
            if not u:
                return False

            # 1) Refresh tokens do usuário
            (
                db.query(models.RefreshToken)
                .filter(models.RefreshToken.id_usuario_fk == id_usuario)
                .delete(synchronize_session=False)
            )

            # 2) Papéis do usuário (tabela ponte)
            (
                db.query(models.UsuarioPapel)
                .filter(models.UsuarioPapel.id_usuario_fk == id_usuario)
                .delete(synchronize_session=False)
            )

            # 3) Acessos do usuário aos projetos (tabela ponte)
            (
                db.query(models.ProjetoUsuarioAcesso)
                .filter(models.ProjetoUsuarioAcesso.id_usuario_fk == id_usuario)
                .delete(synchronize_session=False)
            )

            # 4) Desassociar como gerente de projetos (FK -> NULL)
            (
                db.query(models.Projeto)
                .filter(models.Projeto.id_gerente_fk == id_usuario)
                .update({models.Projeto.id_gerente_fk: None}, synchronize_session=False)
            )

            # 5) Desassociar como autor de relatórios (FK -> NULL)
            (
                db.query(models.RelatorioSprint)
                .filter(models.RelatorioSprint.id_autor_fk == id_usuario)
                .update({models.RelatorioSprint.id_autor_fk: None}, synchronize_session=False)
            )

            # 6) Remover usuário
            db.delete(u)

            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()