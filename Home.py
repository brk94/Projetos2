import streamlit as st
import os
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
/* Somente o botão de SUBMIT do formulário */
[data-testid="stForm"] .stFormSubmitButton button,
[data-testid="stForm"] button[type="submit"]{
  background:#2F5DE7 !important;
  color:#FFFFFF !important;
  border:1px solid #2F5DE7 !important;
  border-radius:10px !important;
  box-shadow:none !important;
}
[data-testid="stForm"] .stFormSubmitButton button:hover,
[data-testid="stForm"] button[type="submit"]:hover{
  filter:brightness(0.92);
}
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

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

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
        resp = requests.post(
            f"{API_URL}/token",
            data={"username": email, "password": senha},
            timeout=10,
        )
    except requests.ConnectionError:
        st.error("Não foi possível conectar à API. O servidor backend está online?")
        return

    if resp.status_code != 200:
        st.error("Email ou senha incorretos.")
        return

    data = resp.json() or {}
    access_token = data.get("access_token") or ""
    refresh_token = data.get("refresh_token") or ""

    if not access_token or not refresh_token:
        st.error("Erro ao receber tokens de autenticação.")
        return

    # guarda tudo no estado
    st.session_state["logged_in"] = True
    st.session_state["user_email"] = email
    st.session_state["auth_token"] = access_token
    st.session_state["refresh_token"] = refresh_token

    # persiste o refresh na URL para sobreviver ao F5
    qp = dict(st.query_params)
    qp["rt"] = refresh_token
    qp["u"] = email
    st.query_params = qp

    # carrega/força recarregar permissões e segue
    garantir_sessao_e_permissoes(force_reload=True)
    st.rerun()

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
        logo_url = "https://mc.sonae.pt/wp-content/uploads/2019/01/novo-logo-mc.jpg"
        st.markdown(f"""
            <div style="display:flex;justify-content:center;margin-bottom:6px">
            <img src="{logo_url}" alt="MC Sonae" style="max-width:200px;height:auto;" />
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown(
            "<h3 style='text-align:center; font-weight:600; margin:0px 0 12px;'>Dashboard de automação de projetos</h3>",
            unsafe_allow_html=True
        )
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

        # Botão centralizado que chama a função correta ---
        st.markdown("""
        <style>
        .center-access {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            margin: 1rem 0;
            width: 100%;
        }

        .help-text {
            font-size: 16px;
            color: #6B7280;
            margin-bottom: -15px;
            text-align: center;
            width: 100%;
        }

        /* Estilização do botão para parecer um link */
        .stButton button {
            background: transparent !important;
            color: #2F5DE7 !important;
            border: none !important;
            box-shadow: none !important;
            font-weight: 600;
            font-size: 16px;
            padding: 4px 8px;
        }

        .stButton button:hover {
            background-color: rgba(47, 93, 231, 0.05) !important;
        }
        </style>

        <div class="center-access">
            <div class="help-text">Não tem uma conta?</div>
        </div>
        """, unsafe_allow_html=True)

        # Container para centralizar o botão
        col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
        with col_btn2:
            if st.button("Solicitar acesso", use_container_width=True, key="solicitar_acesso"):
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
render_menu_lateral(perms, current_page="home")

# --- Casca visual da Home ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');

/* Fundo e container principal */
[data-testid="stAppViewContainer"] {
    background-color:#FFFFFF !important;
}
.main .block-container{
    padding-top:2rem;
    padding-left:3rem;
    padding-right:3rem;
    padding-bottom:2rem;
    min-height:100vh;
    background-color:transparent !important;
}

/* Cabeçalho da página */
.main-header h3{
    font-weight:700;
    color:#333 !important;
    margin-bottom:0;
    font-size:2.8rem;
}
.main-header p{
    color:#0072C6 !important;
    font-weight:500;
    font-size:1rem;
    margin-bottom:2rem;
}

/* Cartões */
.white-card{
    background-color:#FFFFFF !important;
    border-radius:12px;
    padding:24px;
    margin-bottom:24px;
    box-shadow:0 4px 12px rgba(0,0,0,0.05);
    border:1px solid #E0E0E0;
}
.center-card{ text-align:center; padding:40px 24px; }
.center-card .icon-placeholder{
    width:80px; height:80px; border-radius:50%;
    background-color:#E7F3FE;
    display:flex; align-items:center; justify-content:center;
    margin:0 auto 20px auto; font-size:40px; color:#0072C6;
}

/* Cabeçalho de seção dentro do cartão */
.card-header{ display:flex; align-items:center; margin-bottom:20px; }
.card-header .header-icon{ font-size:1.5rem; margin-right:12px; }
.card-header h4{ margin:0; font-weight:700; color:#333 !important; font-size:1.1rem; }

.info-card{ border-left:4px solid #0072C6; }
.info-text{ color:#555 !important; font-size:1rem; line-height:1.6; }

/* Cartões da equipe */
.team-card{ border-radius:12px; padding:24px; text-align:center; height:100%; }
.team-card-blue{  background-color:#E7F3FE; }
.team-card-green{ background-color:#E6F7E9; }
.team-card-purple{background-color:#F3E8FD; }

.team-icon{
    width:70px; height:70px; border-radius:50%;
    display:flex; align-items:center; justify-content:center;
    margin:0 auto 16px auto; font-size:30px;
}
.icon-bg-blue{   background-color:#D0E7FD; color:#0072C6; }
.icon-bg-green{  background-color:#CFF0D6; color:#28A745; }
.icon-bg-purple{ background-color:#E8D3FB; color:#7E1AFB; }
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
    <div class="main-header">
        <h3>Dashboard de Automação de Projetos MC Sonae</h3>
        <p>Desenvolvido pelo Grupo 1 | CESAR School - Projetos 2</p>
    </div>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="white-card center-card">
        <div class="icon-placeholder">🎯</div>
        <h2>Dashboard de Projetos em Tempo Real</h2>
        <p>Acompanhe o progresso dos seus projetos</p>
    </div>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="white-card info-card">
        <div class="card-header">
            <span class="header-icon">ℹ️</span>
            <h4>O que esse Dashboard faz?</h4>
        </div>
        <p class="info-text">
            Este dashboard foi desenvolvido para automatizar a comunicação e gestão de projetos na MC Sonae.
            Ele centraliza informações de status, métricas financeiras, marcos importantes e riscos, proporcionando
            uma visão completa e em tempo real do progresso dos projetos.
        </p>
    </div>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="white-card info-card">
        <div class="card-header">
            <span class="header-icon">🔧</span>
            <h4>Recursos do Sistema</h4>
        </div>
        <p class="info-text" style="margin-bottom:0;">
            Integra <strong>automação inteligente</strong> para reduzir trabalho manual,
            <strong>controle de acesso</strong> por usuário e projeto, e
            <strong>sincronização em tempo real</strong> de dados para todos os usuários.
        </p>
    </div>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("""
        <div class="team-card team-card-blue">
            <div class="team-icon icon-bg-blue">👥</div>
            <h5>Equipe de Desenvolvimento</h5>
            <p>Grupo 1 - Cesar School</p>
        </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown("""
        <div class="team-card team-card-green">
            <div class="team-icon icon-bg-green">🎯</div>
            <h5>Gestão de Projetos</h5>
            <p>MC Sonae</p>
        </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown("""
        <div class="team-card team-card-purple">
            <div class="team-icon icon-bg-purple">🔧</div>
            <h5>Automação</h5>
            <p>Tecnologia &amp; Inovação</p>
        </div>
    """, unsafe_allow_html=True)