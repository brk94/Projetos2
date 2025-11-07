import re
import streamlit as st
from ui_nav import req_post

# ======================================================================================
# Configuração da página
# ======================================================================================
st.set_page_config(
    page_title="Solicitar acesso",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Oculta a navegação padrão
st.markdown(
    """
<style>
[data-testid="stSidebarNav"] { display: none !important; }
button[kind="header"] { display: none !important; }

/* Estilização do botão de submit */
.stFormSubmitButton button {
    background: #2F5DE7 !important;
    color: white !important;
    border: 1px solid #2F5DE7 !important;
    border-radius: 8px !important;
    padding: 0.5rem 2rem !important;
    font-weight: 600 !important;
}

.stFormSubmitButton button:hover {
    filter: brightness(0.9) !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# Sidebar minimalista
with st.sidebar:
    if st.button("🏠 Voltar para Login", use_container_width=True):
        st.switch_page("Home.py")

# ======================================================================================
# Helpers de validação
# ======================================================================================
_ALLOWED_SETORS = {"RETALHO": "Retalho", "TI": "TI", "MARKETING": "Marketing", "RH": "RH"}
cargos = ["Analista", "Gestor de Projetos", "Diretor", "Visualizador"]

def _eh_um_email_mcsonae(email: str) -> bool:
    return isinstance(email, str) and email.strip().lower().endswith("@mcsonae.com")

def _sanitizar_setor(raw: str) -> str | None:
    if not isinstance(raw, str):
        return None
    key = raw.strip().upper()
    key = re.sub(r"\s+", " ", key)
    return _ALLOWED_SETORS.get(key, None)

def _validar_nome_completo(raw: str) -> bool:
    if not isinstance(raw, str):
        return False
    nome = raw.strip()
    partes = [p for p in nome.split() if p]
    return len(partes) >= 2 and all(len(p) >= 2 for p in partes[:2])

def _titlecase_nome(raw: str) -> str:
    return " ".join(p.capitalize() for p in raw.strip().split())

# ======================================================================================
# Header com Logo e Título
# ======================================================================================
logo_url = "https://mc.sonae.pt/wp-content/uploads/2019/01/novo-logo-mc.jpg"
st.markdown(f"""
    <div style="display:flex;justify-content:flex-start;align-items:center;margin-bottom:10px;">
        <img src="{logo_url}" alt="MC Sonae" style="max-width:120px;height:auto;" />
    </div>
""", unsafe_allow_html=True)

st.title("Solicitar Acesso")
st.markdown("**Preencha o formulário para solicitar acesso ao Dashboard MC Sonae**")

# ======================================================================================
# Seção de Dados do Solicitante
# ======================================================================================
st.header("Dados do Solicitante")
st.markdown("Preencha todos os campos obrigatórios. Sua solicitação será analisada pelo administrador.")

# Container principal do formulário
with st.container(border=True):
    with st.form("solicitar_acesso"):
        # Layout em colunas para melhor organização
        col1, col2 = st.columns(2)
        
        with col1:
            nome = st.text_input(
                "**Nome completo** *", 
                placeholder="Nome, Sobrenome",
                help="Informe nome e sobrenome completos"
            )
            
            email = st.text_input(
                "**E-mail corporativo** *", 
                placeholder="seu.email@mcsonae.com",
                help="Apenas e-mails @mcsonae.com são aceitos"
            )
            
            senha = st.text_input(
                "**Senha** *", 
                type="password",
                placeholder="Digite uma senha segura",
                help="Mínimo 6 caracteres"
            )
        
        with col2:
            cargo = st.selectbox(
                "**Cargo** *", 
                cargos,
                index=cargos.index("Visualizador"),
                help="Selecione seu cargo"
            )
            
            setor = st.selectbox(
                "**Setor** *", 
                ["TI", "Retalho", "Marketing", "RH"],
                help="Selecione seu setor"
            )
            
            # Espaçamento para alinhar com a coluna da esquerda
            st.markdown("<div style='height: 29px'></div>", unsafe_allow_html=True)
        
        # Justificativa - campo grande que ocupa largura total
        justificativa = st.text_area(
            "**Justificativa** *", 
            placeholder="Descreva o motivo da solicitação de acesso...",
            max_chars=512,
            help="Explique por que precisa de acesso ao sistema"
        )
        
        # Botão de submit
        col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 2])
        with col_btn2:
            enviar = st.form_submit_button(
                "Enviar solicitação", 
                use_container_width=True
            )

# ======================================================================================
# Processamento do formulário
# ======================================================================================
if enviar:
    # Validações
    errors = []
    
    # Campos obrigatórios
    if not nome:
        errors.append("Nome completo é obrigatório")
    if not email:
        errors.append("E-mail corporativo é obrigatório")
    if not senha:
        errors.append("Senha é obrigatória")
    if not justificativa:
        errors.append("Justificativa é obrigatória")
    
    # Validações específicas
    if nome and not _validar_nome_completo(nome):
        errors.append("Informe nome e sobrenome completos")
    
    if email and not _eh_um_email_mcsonae(email):
        errors.append("O e-mail deve ser @mcsonae.com")
    
    if senha and len(senha) < 6:
        errors.append("A senha deve ter no mínimo 6 caracteres")
    
    # Mostrar erros ou processar
    if errors:
        for error in errors:
            st.error(error)
    else:
        # Processar dados
        nome_fmt = _titlecase_nome(nome)
        setor_norm = _sanitizar_setor(setor)
        
        payload = {
            "nome": nome_fmt,
            "email": email.strip().lower(),
            "senha": senha,
            "setor": setor_norm,
            "justificativa": justificativa.strip(),
            "cargo": cargo,
        }
        
        # Enviar para API
        try:
            r = req_post("/auth/solicitar-acesso", json=payload)
            if r.status_code == 201:
                st.toast("Solicitação enviada com sucesso! Aguarde a aprovação do administrador.", icon="✅")
            else:
                if "application/json" in r.headers.get("content-type", ""):
                    msg = r.json().get("detail", "Erro desconhecido")
                else:
                    msg = r.text
                st.error(f"❌ Falha ao enviar: {msg}")
        except Exception as e:
            st.error(f"🔌 Erro de conexão: {e}")

# ======================================================================================
# Footer
# ======================================================================================
st.markdown(
    "<div style='text-align: center; color: #888; font-size: 0.9rem;'>"
    "Desenvolvido pelo Grupo 1 - Cesar School • Projeto Acadêmico - 2025"
    "</div>",
    unsafe_allow_html=True
)