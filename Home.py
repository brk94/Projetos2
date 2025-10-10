# Home.py
import streamlit as st
import requests
from ui_nav import ensure_session_and_perms, render_sidebar

st.set_page_config(
    page_title="MC Sonae",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Esconde a navegação nativa
st.markdown("""
<style>
[data-testid="stSidebarNav"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# Estado básico
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("user_email", "")
st.session_state.setdefault("auth_token", "")
st.session_state.setdefault("perms", [])

API_URL = "http://127.0.0.1:8000"

def do_login(email: str, senha: str):
    try:
        r = requests.post(f"{API_URL}/token", data={"username": email, "password": senha}, timeout=10)
        if r.status_code == 200:
            tok = r.json().get("access_token")
            st.session_state["logged_in"] = True
            st.session_state["user_email"] = email
            st.session_state["auth_token"] = tok
            # carrega permissões
            ensure_session_and_perms()
            st.rerun()
        else:
            st.error("Email ou senha incorretos.")
    except requests.ConnectionError:
        st.error("Não foi possível conectar à API. O servidor backend está online?")

# Se não estiver logado: tela de login e sai
if not st.session_state["logged_in"] or not st.session_state["auth_token"]:
    col1, col2, col3 = st.columns([1, 1.2, 1])
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
                if st.form_submit_button("Entrar", width='stretch'):
                    if email and senha:
                        do_login(email, senha)
                    else:
                        st.warning("Informe email e senha.")

        st.markdown(
            "<div style='text-align: center; margin-top: 1rem; color: #888;'>"
            "Desenvolvido pelo Grupo 1 - Cesar School<br>Projeto Acadêmico - 2025"
            "</div>",
            unsafe_allow_html=True,
        )
    st.stop()

# A partir daqui: logado
perms = ensure_session_and_perms()
render_sidebar(perms, current_page="home")

st.title("Bem-vindo ao Dashboard de Automação de Projetos MC Sonae")
st.markdown("### 🚀 Desenvolvido pelo **Grupo 1** | **CESAR School - Projetos 2**")
st.markdown("---")
st.image(
    "https://images.pexels.com/photos/3183150/pexels-photo-3183150.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=1",
    caption="Desafio CESAR School & MC Sonae: Automação da Comunicação de Projetos",
)
st.header("O que este dashboard faz?")
st.markdown("""
Esta aplicação automatiza a comunicação de resultados de projetos na MC Sonae.
Ela transforma relatórios dispersos (`.docx`, `.pdf`) em insights visuais e centralizados.
""")
st.subheader("Como navegar:")
st.info("👈 Use **os botões da barra lateral**. Eles já respeitam suas permissões.")