# ui_nav.py  — navegação/segurança unificadas para todas as páginas Streamlit

from __future__ import annotations
import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000"

# Rotas (nomes usados em current_page)
ROUTES = {
    "home": "Home.py",
    "processar": "pages/2_Processar_Relatórios.py",
    "dash_projetos": "pages/3_Dashboard.py",
    "dash_retalho": "pages/4_Dashboard_Retalho.py",
    "dash_rh": "pages/5_Dashboard_RH.py",
    "dash_mkt": "pages/6_Dashboard_Marketing.py",
    "about": "pages/7_About.py",
}

SIDEBAR_CSS = """
<style>
/* Sidebar ocupa toda a altura e vira coluna flex */
[data-testid="stSidebar"] > div:first-child {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

/* Contêiner do menu (botões neutros só aqui) */
[data-testid="stSidebar"] .sidebar-menu .stButton > button {
  background: #ffffff !important;
  background-color: #ffffff !important;
  background-image: none !important;
  color: #111111 !important;
  border: 1px solid #d9d9d9 !important;
  box-shadow: none !important;
}
[data-testid="stSidebar"] .sidebar-menu .stButton > button:hover {
  background: #f2f2f2 !important;
  background-color: #f2f2f2 !important;
  background-image: none !important;
}

/* Espaçador empurra o logout para o rodapé */
.sidebar-spacer { flex-grow: 1; }

/* Zona fixa do logout no rodapé da sidebar */
.logout-zone { margin-top: auto; padding-top: .5rem; padding-bottom: .5rem; }

/* 🔴 Estilo EXCLUSIVO do botão "Sair" (especificidade alta) */
[data-testid="stSidebar"] .logout-zone .stButton > button {
  background: #d64545 !important;          /* vermelho suave */
  background-color: #d64545 !important;
  background-image: none !important;
  color: #ffffff !important;
  border: 1px solid #d64545 !important;
  box-shadow: none !important;
}
[data-testid="stSidebar"] .logout-zone .stButton > button:hover {
  background: #bf3b3b !important;          /* um tom mais escuro no hover */
  background-color: #bf3b3b !important;
  background-image: none !important;
  border-color: #bf3b3b !important;
}

/* (opcional) encostar mais no rodapé visual */
[data-testid="stSidebar"] > div:first-child { padding-bottom: .25rem; }
</style>
"""



# ----------------------
# Utilitários de sessão
# ----------------------
def api_headers() -> dict:
    tok = st.session_state.get("auth_token")
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def _switch(page_key: str):
    """Troca de página usando o caminho do ROUTES."""
    target = ROUTES.get(page_key)
    if not target:
        st.warning("Página de destino não encontrada.")
        return
    st.switch_page(target)


def _logout_and_rerun():
    for k in ("logged_in", "user_email", "auth_token", "perms"):
        st.session_state.pop(k, None)
    st.rerun()


def _fetch_perms_from_api() -> set[str]:
    """Busca permissões do backend e normaliza para minúsculas."""
    try:
        r = requests.get(f"{API_URL}/me/permissoes", headers=api_headers(), timeout=10)
        if r.status_code == 200:
            return {p.lower() for p in r.json()}
        # 401/403: sessão inválida
        return set()
    except requests.ConnectionError:
        return set()


def ensure_session_and_perms() -> set[str]:
    """
    Garante que o usuário está logado e retorna o set de permissões (minúsculas).
    Se não estiver logado ou sem token → volta para Home (login).
    """
    # Esconde navegação nativa do Streamlit em todas as páginas
    st.markdown(
        "<style>[data-testid='stSidebarNav']{display:none!important}</style>",
        unsafe_allow_html=True,
    )

    if not st.session_state.get("logged_in") or not st.session_state.get("auth_token"):
        _switch("home")
        st.stop()

    if not st.session_state.get("perms"):
        st.session_state["perms"] = list(_fetch_perms_from_api())

    return set(p.lower() for p in st.session_state.get("perms", []))


# ------------------------------------
# Sidebar (menu padronizado)
# ------------------------------------
def render_sidebar(perms: set[str], current_page: str | None = None):
    st.sidebar.markdown(SIDEBAR_CSS, unsafe_allow_html=True)

    # Header do usuário
    st.sidebar.success(f"Logado como: {st.session_state.get('user_email','')}")

    # Regras de permissão
    can_see_processar = (
        "view_pagina_processar_relatorios" in perms or
        "realizar_upload_relatorio" in perms
    )
    can_see_dashboards = "view_pagina_dashboards" in perms

    # ====== MENU NEUTRO (cinza/branco) ======
    st.sidebar.markdown('<div class="sidebar-menu">', unsafe_allow_html=True)

    if st.sidebar.button("🏠 Home", key=f"btn_home_{current_page or 'x'}", width="stretch"):
        if current_page != "home":
            _switch("home")

    if can_see_processar:
        if st.sidebar.button("📤 Processar Relatórios", key=f"btn_proc_{current_page or 'x'}", width="stretch"):
            if current_page != "processar":
                _switch("processar")

    if can_see_dashboards:
        st.sidebar.markdown("---")
        if st.sidebar.button("📊 Dashboard TI", key=f"btn_dash_proj_{current_page or 'x'}", width="stretch"):
            if current_page != "dash_projetos":
                _switch("dash_projetos")
        if st.sidebar.button("🛍️ Dashboard Retalho", key=f"btn_dash_retalho_{current_page or 'x'}", width="stretch"):
            if current_page != "dash_retalho":
                _switch("dash_retalho")
        if st.sidebar.button("👥 Dashboard RH", key=f"btn_dash_rh_{current_page or 'x'}", width="stretch"):
            if current_page != "dash_rh":
                _switch("dash_rh")
        if st.sidebar.button("📣 Dashboard Marketing", key=f"btn_dash_mkt_{current_page or 'x'}", width="stretch"):
            if current_page != "dash_mkt":
                _switch("dash_mkt")

    st.sidebar.markdown("---")
    if st.sidebar.button("ℹ️ About", key=f"btn_about_{current_page or 'x'}", width="stretch"):
        if current_page != "about":
            _switch("about")

    st.sidebar.markdown('</div>', unsafe_allow_html=True)
    # ====== FIM MENU NEUTRO ======

    # Empurra o logout para o rodapé
    st.sidebar.markdown('<div class="sidebar-spacer"></div>', unsafe_allow_html=True)

    # ====== ZONA DO LOGOUT (vermelho, no rodapé) ======
    st.sidebar.markdown('<div class="logout-zone">', unsafe_allow_html=True)
    try:
        clicked = st.sidebar.button("Sair", key=f"btn_logout_{current_page or 'x'}", width="stretch")
    except TypeError:
        clicked = st.sidebar.button("Sair", key=f"btn_logout_{current_page or 'x'}", use_container_width=True)
    st.sidebar.markdown('</div>', unsafe_allow_html=True)
    # ====== FIM LOGOUT ======

    if clicked:
        _logout_and_rerun()