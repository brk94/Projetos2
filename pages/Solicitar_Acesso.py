"""
Página Streamlit — Solicitar Acesso

Seções:
- Configuração da página e navegação
- Helpers de validação/sanitização
- UI do formulário e fluxo de submissão

Destaques dos comentários:
- Por que validar domínio do e‑mail (@mcsonae.com)
- Normalização de setor (inputs livres → valores canônicos)
- Regras mínimas para "nome completo"
- Encaminhamento da solicitação para o endpoint público `/auth/solicitar-acesso`
"""

# ======================================================================================
# Imports
# ======================================================================================
import re
import streamlit as st
from ui_nav import req_post  # wrapper com headers/refresh da sessão (mantido)

# ======================================================================================
# Configuração da página e pequenos ajustes de navegação
# ======================================================================================
st.set_page_config(
    page_title="Solicitar acesso",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded",
)
# Oculta a navegação padrão/ícones do Streamlit nesta página (apenas estética)
st.markdown(
    """
<style>
[data-testid="stSidebarNav"] { display: none !important; }
button[kind="header"] { display: none !important; }
</style>
""",
    unsafe_allow_html=True,
)

# Sidebar minimalista: atalho de volta à Home
with st.sidebar:
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page("Home.py")

st.title("Solicitar acesso")

# ======================================================================================
# Helpers de validação/sanitização (mantidos, apenas comentados)
# ======================================================================================
_ALLOWED_SETORS = {"RETALHO": "Retalho", "TI": "TI", "MARKETING": "Marketing", "RH": "RH"}
# Ordem aqui afeta o índice default do selectbox lá embaixo ("Visualizador")
cargos = ["Analista", "Gestor de Projetos", "Diretor", "Visualizador"]


def _eh_um_email_mcsonae(email: str) -> bool:
    """Aceita apenas e-mails corporativos da org (@mcsonae.com)."""
    return isinstance(email, str) and email.strip().lower().endswith("@mcsonae.com")


def _sanitizar_setor(raw: str) -> str | None:
    """Normaliza o setor para valores canônicos: Retalho, TI, Marketing ou RH.
    - Ignora caixa e espaços extras; retorna None se não casar.
    """
    if not isinstance(raw, str):
        return None
    key = raw.strip().upper()
    key = re.sub(r"\s+", " ", key)
    return _ALLOWED_SETORS.get(key, None)


def _validar_nome_completo(raw: str) -> bool:
    """Regra mínima: ao menos 2 palavras (nome e sobrenome) com >= 2 letras."""
    if not isinstance(raw, str):
        return False
    nome = raw.strip()
    partes = [p for p in nome.split() if p]
    return len(partes) >= 2 and all(len(p) >= 2 for p in partes[:2])


def _titlecase_nome(raw: str) -> str:
    """Titlecase simples para melhorar a apresentação do nome no backend/admin."""
    return " ".join(p.capitalize() for p in raw.strip().split())

# ======================================================================================
# UI do formulário (ordem é importante para Streamlit)
# ======================================================================================
with st.form("solicitar_acesso"):
    nome  = st.text_input("Nome completo", max_chars=255)
    email = st.text_input("E-mail corporativo", max_chars=255)
    senha = st.text_input("Senha desejada", type="password")

    # Cargo LOGO APÓS a senha (mantido)
    cargo = st.selectbox("Cargo desejado", cargos, index=cargos.index("Visualizador"))

    setor = st.text_input("Setor (Retalho, TI, Marketing ou RH)", max_chars=255)
    justificativa = st.text_area("Justificativa", max_chars=512)

    enviar = st.form_submit_button("Enviar solicitação")

    # ---------------------------------------------------------------------------------
    # Fluxo de submissão (validações → payload → POST). Mantido sem alterar lógica.
    # ---------------------------------------------------------------------------------
    if enviar:
        # Campos obrigatórios
        if not (nome and email and senha and setor and justificativa and cargo):
            st.error("Preencha todos os campos.")
            st.stop()

        # E-mail corporativo
        if not _eh_um_email_mcsonae(email):
            st.error("O e-mail deve ser @mcsonae.com.")
            st.stop()

        # Nome completo mínimo (evita cadastro com um único token)
        if not _validar_nome_completo(nome):
            st.error("Informe nome e sobrenome.")
            st.stop()
        nome_fmt = _titlecase_nome(nome)

        # Setor normalizado para o domínio esperado pelo backend
        setor_norm = _sanitizar_setor(setor)
        if not setor_norm:
            st.error("Setor inválido. Use Retalho, TI, Marketing ou RH.")
            st.stop()

        # Monta payload exatamente como esperado pela API pública
        payload = {
            "nome": nome_fmt,
            "email": email.strip().lower(),
            "senha": senha,
            "setor": setor_norm,
            "justificativa": justificativa.strip(),
            "cargo": cargo,
        }

        # Envia via wrapper que já cuida de headers e refresh de sessão
        try:
            r = req_post("/auth/solicitar-acesso", json=payload)
            if r.status_code == 201:
                st.success("Solicitação enviada! Aguarde a aprovação do administrador.")
            else:
                msg = r.json().get("detail") if "application/json" in r.headers.get("content-type","") else r.text
                st.error(msg or f"Falha ao enviar solicitação (HTTP {r.status_code}).")
        except Exception as e:
            st.error(f"Erro de rede: {e}")