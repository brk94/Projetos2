import streamlit as st
import requests
from ui_nav import garantir_sessao_e_permissoes, render_menu_lateral, ir_para_solicitar_acesso, _persist_session_local

st.set_page_config(
    page_title="MC Sonae",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Esconde a navegação nativa
st.markdown(
    """
<style>
[data-testid="stSidebarNav"] { display: none !important; }
</style>
""",
    unsafe_allow_html=True,
)

# Estado básico
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("user_email", "")
st.session_state.setdefault("auth_token", "")
st.session_state.setdefault("refresh_token", "")
st.session_state.setdefault("perms", [])

API_URL = "http://127.0.0.1:8000"

def _inicializar_refresh_silencioso() -> bool:
    """
    Se há refresh_token (em sessão ou URL) e não há access_token,
    tenta renovar o access de forma silenciosa ANTES de mostrar a tela de login.
    Retorna True se conseguiu renovar; False caso contrário.
    """
    if st.session_state.get("auth_token"):
        return True  # já tem access

    rt = st.session_state.get("refresh_token", "")
    if not rt:
        return False  # sem refresh, não há o que fazer

    try:
        r = requests.post(f"{API_URL}/token/refresh", json={"refresh_token": rt}, timeout=10)
        if r.status_code == 200:
            data = r.json() or {}
            st.session_state["auth_token"] = data.get("access_token", "")
            # em caso de rotação do refresh, atualiza sessão e URL
            st.session_state["refresh_token"] = data.get("refresh_token", rt)
            # Persiste localmente para sobreviver a F5/novas sessões
            _persist_session_local(st.session_state["refresh_token"], st.session_state.get("user_email"))

            # Persiste localmente (sem usar URL) para sobreviver a F5/novas sessões do Streamlit
            _persist_session_local(st.session_state["refresh_token"], st.session_state.get("user_email"))

            # Atualiza a querystring com o refresh (rotacionado) e email se já tiver
            qp = dict(st.query_params)
            qp["rt"] = st.session_state["refresh_token"]
            if st.session_state.get("user_email"):
                qp["u"] = st.session_state["user_email"]
            st.query_params = qp

            st.session_state["logged_in"] = True
            return True
    except requests.RequestException:
        pass
    return False

def fazer_login(email: str, senha: str):
    try:
        r = requests.post(f"{API_URL}/token", data={"username": email, "password": senha}, timeout=10)
        if r.status_code == 200:
            data = r.json() or {}
            # guarda tudo no estado
            st.session_state["logged_in"] = True
            st.session_state["user_email"] = email
            st.session_state["auth_token"] = data.get("access_token", "")
            st.session_state["refresh_token"] = data.get("refresh_token", "")

            # persiste o refresh na URL para sobreviver ao F5
            qp = dict(st.query_params)
            qp["rt"] = st.session_state["refresh_token"]
            qp["u"] = st.session_state["user_email"]
            st.query_params = qp

            # carrega permissões e segue
            garantir_sessao_e_permissoes(force_reload=True)
            st.rerun()
        else:
            st.error("Email ou senha incorretos.")
    except requests.ConnectionError:
        st.error("Não foi possível conectar à API. O servidor backend está online?")

# --- Recupera refresh token da URL para sobreviver ao F5 ---
# Ex.: http://localhost:8501/?rt=<refresh_token>&u=<email>
_rt = st.query_params.get("rt", [""])[0] if isinstance(st.query_params.get("rt"), list) else st.query_params.get("rt", "")
_u  = st.query_params.get("u",  [""])[0] if isinstance(st.query_params.get("u"),  list) else st.query_params.get("u",  "")

# Se vier na URL e o estado estiver vazio, grava no session_state
if _rt and not st.session_state.get("refresh_token"):
    st.session_state["refresh_token"] = _rt
# (o email é opcional; ajuda só em sinalização)
if _u and not st.session_state.get("user_email"):
    st.session_state["user_email"] = _u

# TENTA REFRESH SILENCIOSO ANTES DE MOSTRAR LOGIN
_inicializar_refresh_silencioso()

# Tela de login (só aparece se ainda não houver access token válido)
if not st.session_state["logged_in"] or not st.session_state["auth_token"]:
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with st.spinner("Carregando..."):
        pass
    with col2:
        st.image(
            "https://media.licdn.com/dms/image/D4D0BAQFchI-y3s2b-A/company-logo_200_200/0/1715019805988/mc_sonae_logo?e=1732320000&v=beta&t=M8-jIup_tTTGOq4Wk1cqzC_mK6hQYd-E7aA6xY1yGcU",
            width=120,
        )
        st.title("MC Sonae")
        st.subheader("Dashboard de Automação de Projetos")

        with st.container(border=True):
            st.header("Fazer Login")
            st.markdown("Entre com suas credenciais para acessar o dashboard")

            with st.form("login_form"):
                email = st.text_input("Email", placeholder="seu.email@mcsonae.com")
                senha = st.text_input("Senha", type="password", placeholder="Digite sua senha")
                entrar = st.form_submit_button("Entrar", use_container_width=True)
                if entrar:
                    if email and senha:
                        fazer_login(email, senha)
                    else:
                        st.warning("Informe email e senha.")

        # ---- ÚNICO BOTÃO INFERIOR: Solicitar acesso (fora do form) ----
        st.markdown("<div style='height: 0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Solicitar acesso", use_container_width=True):
            ir_para_solicitar_acesso()

        st.markdown(
            "<div style='text-align: center; margin-top: 1rem; color: #888;'>"
            "Desenvolvido pelo Grupo 1 - Cesar School<br>Projeto Acadêmico - 2025"
            "</div>",
            unsafe_allow_html=True,
        )
    st.stop()

# A partir daqui: logado
perms = garantir_sessao_e_permissoes()
#st.caption(f"DEBUG perms: {st.session_state.get('perms')}")
render_menu_lateral(perms, current_page="home")

st.title("Bem-vindo ao Dashboard de Automação de Projetos MC Sonae")
st.markdown("### 🚀 Desenvolvido pelo **Grupo 1** | **CESAR School - Projetos 2**")
st.markdown("---")
st.image(
    "https://images.pexels.com/photos/3183150/pexels-photo-3183150.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=1",
    caption="Desafio CESAR School & MC Sonae: Automação da Comunicação de Projetos",
)
st.header("O que este dashboard faz?")
st.markdown(
    """
Esta aplicação automatiza a comunicação de resultados de projetos na MC Sonae.
Ela transforma relatórios dispersos (`.docx`, `.pdf`) em insights visuais e centralizados.
"""
)
st.subheader("Como navegar:")
st.info("👈 Use **os botões da barra lateral**. Eles já respeitam suas permissões.")