import os
import streamlit as st
import requests

# --- Renderização de texto "puro" (sem Markdown/LaTeX) ---
import html

from typing import Optional

# Base da API (permite sobrescrever via env)
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

import json
from pathlib import Path

# Persistência local (fallback) — evita usar URL para sobreviver a F5/novas sessões do Streamlit.
_SESSION_FILE = Path.home() / ".mc_sonae_session.json"

def _persist_session_local(rt: str | None, email: str | None):
    try:
        data = {"rt": rt or "", "u": email or ""}
        _SESSION_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass

def _load_session_local():
    try:
        data = json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
        return (data.get("rt") or ""), (data.get("u") or "")
    except Exception:
        return "", ""

def _clear_session_local():
    try:
        if _SESSION_FILE.exists():
            _SESSION_FILE.unlink()
    except Exception:
        pass

# -----------------------
# Helpers de sessão/HTTP
# -----------------------
def _auth_headers() -> dict:
    token = st.session_state.get("auth_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}

def _metodo_http(method, path, **kw):
    url = path if path.startswith("http") else f"{API_URL}{path}"

    # Mescla headers do caller com os de auth, sem perder Authorization
    extra_headers = kw.pop("headers", {}) or {}
    headers = {**_auth_headers(), **extra_headers}

    # Timeout padrão só se o caller não passou
    if "timeout" not in kw:
        kw["timeout"] = 10

    # 1ª tentativa
    resp = requests.request(method, url, headers=headers, **kw)
    if resp.status_code != 401:
        return resp

    # Tenta renovar access de forma silenciosa
    if _atualizar_token_se_necessario():
        # Recalcula headers com o novo access
        headers = {**_auth_headers(), **extra_headers}
        return requests.request(method, url, headers=headers, **kw)

    # Mantém o 401 original se não deu para renovar
    return resp

def req_get(path, **kw):    
    return _metodo_http("GET", path, **kw)

def req_post(path, **kw):   
    return _metodo_http("POST", path, **kw)

def req_put(path: str, **kwargs):
    return _metodo_http("PUT", path, **kwargs)

def req_delete(path, **kw): 
    return _metodo_http("DELETE", path, **kw)

# Alias público usado pelas páginas (ex.: 3_Dashboard.py)
def api_headers() -> dict:
    """Headers HTTP com Authorization atual (se houver)."""
    return _auth_headers()

def _limpar_session():
    # limpa estado
    for k in ("logged_in", "user_email", "auth_token", "refresh_token", "perms"):
        if k in st.session_state:
            del st.session_state[k]

    # >>> NOVO: limpar a querystring (remove 'rt' e 'u') <<<
    qp = dict(st.query_params)
    changed = False
    if "rt" in qp:
        qp.pop("rt", None)
        changed = True
    if "u" in qp:
        qp.pop("u", None)
        changed = True
    if changed:
        st.query_params = qp

def _atualizar_token_se_necessario() -> bool:
    """
    Tenta renovar o access token usando /token/refresh.
    Retorna True se renovou com sucesso.
    """
    rt = st.session_state.get("refresh_token", "")
    if not rt:
        return False
    try:
        rr = requests.post(f"{API_URL}/token/refresh", json={"refresh_token": rt}, timeout=10)
    except requests.RequestException:
        return False

    if rr.status_code == 200:
        data = rr.json() or {}
        st.session_state["auth_token"] = data.get("access_token", "")
        # se backend devolver novo refresh, atualiza (rotação)
        st.session_state["refresh_token"] = data.get("refresh_token", rt)
        # importante: garantir flag de login true ao renovar silenciosamente
        st.session_state["logged_in"] = True
        return True

    # refresh inválido → não limpa aqui; quem chamou decide
    return False

# -----------------------------------------------------------------
# Carrega/garante permissões do usuário (modo "fatal", usado nas páginas)
# -----------------------------------------------------------------

# --- BOOTSTRAP SILENCIOSO (centralizado) ---
import os
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

# ui_nav.py (trecho a adicionar/atualizar)

import os
import requests
import streamlit as st
from typing import List, Optional, Set

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

# ------------------------------------------------------------
# 1) Bootstrap silencioso (reidrata sessão e faz refresh)
# ------------------------------------------------------------
def _inicializar_sessao_por_query_e_refresh() -> bool:
    """
    1) Reidrata sessão a partir de ?rt=<refresh>&u=<email> se a sessão perdeu estado no F5.
    2) Se não há access_token mas há refresh_token, chama /token/refresh e atualiza sessão + URL.
    Retorna True se renovou o access com sucesso, False caso contrário.
    """
    # Reidratar via query params
    qp = dict(st.query_params)
    rt = qp.get("rt")
    u  = qp.get("u")

    if rt and not st.session_state.get("refresh_token"):
        st.session_state["refresh_token"] = rt
    if u and not st.session_state.get("user_email"):
        st.session_state["user_email"] = u
    if st.session_state.get("refresh_token") and not st.session_state.get("logged_in"):
        st.session_state["logged_in"] = True  # temos refresh => usuário logado

    # Se já temos access token, nada a fazer
    if st.session_state.get("auth_token"):
        return False

    # Sem logged_in ou sem refresh -> não dá pra renovar
    if not (st.session_state.get("logged_in") and st.session_state.get("refresh_token")):
        return False

    # Tenta renovar
    try:
        resp = requests.post(
            f"{API_URL}/token/refresh",
            json={"refresh_token": st.session_state["refresh_token"]},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json() or {}
            st.session_state["auth_token"]    = data.get("access_token", "")
            st.session_state["refresh_token"] = data.get("refresh_token", st.session_state["refresh_token"])

            # Mantém rt/u na URL (e atualiza em caso de rotação)
            qp = dict(st.query_params)
            qp["rt"] = st.session_state["refresh_token"]
            if st.session_state.get("user_email"):
                qp["u"] = st.session_state["user_email"]
            st.query_params = qp
            return True
    except requests.RequestException:
        pass

    return False


# ------------------------------------------------------------
# 2) Verificação de sessão + carregamento/retentativa de permissões
#    (com fallback no cache para evitar falso "sem permissão")
# ------------------------------------------------------------
def garantir_sessao_e_permissoes(force_reload: bool = False, require_perm: Optional[str] = None) -> List[str]:
    """
    - Garante que a sessão esteja reidratada/renovada antes de consultar permissões.
    - Busca permissões do backend. Se 401, tenta 1x refresh e repete.
    - Se ainda falhar, mantém o cache anterior (evita "sem permissão" falso).
    - Se require_perm for passado, só bloqueia caso as permissões estejam carregadas
      e o usuário REALMENTE não tenha a permissão (admin sempre passa).
    """
    # 1) Bootstrap antes de qualquer coisa (sobrevive a F5)
    _inicializar_sessao_por_query_e_refresh()

    # 2) Se não estiver logado de jeito nenhum, devolve para o Home.py (tela de login)
    if not st.session_state.get("logged_in"):
        try:
            st.switch_page("Home.py")
        except Exception:
            st.query_params.clear()
            st.experimental_set_query_params(pagina="home")
            st.stop()  # interrompe o render da página atual

    # 3) Se temos permissões em cache e não pediram force_reload, devolve o cache
    cached: List[str] = st.session_state.get("perms") or []
    if cached and not force_reload:
        if require_perm:
            perms_lower_cached = {p.lower() for p in cached}
            is_admin_cached = (
                "view_pagina_admin_usuarios" in perms_lower_cached
                or {"gerenciar_usuarios", "gerenciar_papeis"}.issubset(perms_lower_cached)
            )
            if (not is_admin_cached) and (require_perm.lower() not in perms_lower_cached):
                st.warning("Página não encontrada ou não disponível para seu perfil.")
                st.stop()
        return cached

    # 4) Precisamos buscar do backend
    def _headers() -> dict:
        token = st.session_state.get("auth_token", "")
        return {"Authorization": f"Bearer {token}"} if token else {}

    def _buscar_permissoes() -> Optional[List[str]]:
        try:
            r = requests.get(f"{API_URL}/me/permissoes", headers=_headers(), timeout=10)
            if r.status_code == 200:
                return r.json() or []
            if r.status_code == 401:
                return None  # sinaliza para tentar refresh
        except requests.RequestException:
            pass
        return []

    perms = _buscar_permissoes()

    # 5) Se 401/None, tenta um refresh e re-tenta UMA vez
    if perms is None:
        refreshed = _inicializar_sessao_por_query_e_refresh()
        if refreshed:
            perms = _buscar_permissoes()
        else:
            perms = []

    # 6) Se falhou de novo, NÃO apague o cache; use-o como fallback
    if not perms:
        perms = cached  # fallback suave evita falso "sem permissão"

    # 7) Atualiza estado e faz o gate se pediram require_perm
    st.session_state["perms"] = perms

    perfil = _buscar_me_perfil()
    if perfil:
        st.session_state["me_perfil"] = perfil
    else:
        st.session_state.setdefault("me_perfil", {})

    if require_perm:
        perms_lower: Set[str] = {p.lower() for p in perms}
        is_admin = (
            "view_pagina_admin_usuarios" in perms_lower
            or {"gerenciar_usuarios", "gerenciar_papeis"}.issubset(perms_lower)
        )
        if (not is_admin) and (require_perm.lower() not in perms_lower):
            st.warning("Página não encontrada ou não disponível para seu perfil.")
            st.stop()

    return perms

# -----------------------------------------------------------------
# Versão NÃO-FATAL para a Home:
# - Nunca dá logout automático.
# - Tenta /me/permissoes; se falhar, retorna o que tiver em cache (ou [])
# -----------------------------------------------------------------
def garantir_sessao_e_permissoes_nao_fatal(force_reload: bool = False):
    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("user_email", "")
    st.session_state.setdefault("auth_token", "")
    st.session_state.setdefault("refresh_token", "")
    st.session_state.setdefault("perms", [])

    if not st.session_state["auth_token"]:
        return st.session_state["perms"]

    if st.session_state["perms"] and not force_reload:
        return st.session_state["perms"]

    try:
        r = requests.get(f"{API_URL}/me/permissoes", headers=_auth_headers(), timeout=10)
        if r.status_code == 200:
            st.session_state["perms"] = r.json()
            return st.session_state["perms"]
        if r.status_code == 401:
            if _atualizar_token_se_necessario():
                r2 = requests.get(f"{API_URL}/me/permissoes", headers=_auth_headers(), timeout=10)
                if r2.status_code == 200:
                    st.session_state["perms"] = r2.json()
                    return st.session_state["perms"]
        # qualquer outro status → não limpa sessão aqui
        return st.session_state["perms"]
    except requests.RequestException:
        return st.session_state["perms"]

# -----------------
# Logout (backend)
# -----------------
def _logout_backend():
    """
    Chama /logout no backend informando o refresh_token atual.
    Mesmo que falhe, limpamos a sessão local para o usuário sair.
    """
    rt = st.session_state.get("refresh_token", "")
    if not rt:
        return

    try:
        # Envia o refresh para revogar no banco; Authorization com access atual
        requests.post(
            f"{API_URL}/logout",
            json={"refresh_token": rt},
            headers=_auth_headers(),
            timeout=10,
        )
    except requests.RequestException:
        # não faz nada: melhor esforço
        pass

    # Limpa persistência local
    _clear_session_local()

# ---------------------------
# Sidebar / navegação simples
# ---------------------------
def render_menu_lateral(perms: list[str] | None, current_page: str | None = None):
    perms_lower = {p.lower() for p in (perms or [])}
    is_admin = (
        "view_pagina_admin_usuarios" in perms_lower
        or {"gerenciar_usuarios", "gerenciar_papeis"}.issubset(perms_lower)
    )

     # >>> NOVO: setor do usuário (usa o que já está na sessão ou busca do backend)
    perfil = st.session_state.get("me_perfil") or _buscar_me_perfil() or {}
    setor = (perfil.get("setor") or "").strip().upper()
    eh_usuario_ti = (setor == "TI")

    with st.sidebar:
        st.markdown("### Navegação")

        # Home
        if st.sidebar.button(("🏠 " if current_page == "home" else "🏠 ") + "Home", use_container_width=True):
            st.switch_page("Home.py")

        # --- Dashboard de TI (SOMENTE se tiver permissão explícita ou for admin ou usuário do setor TI) ---
        can_view_dash_ti = (is_admin or ("view_dashboard_ti" in perms_lower)) and (is_admin or eh_usuario_ti)
        if can_view_dash_ti:
            active = current_page in {"dashboard", "dash_ti"}
            label = ("📊 " if active else "📊 ") + "Dashboard (TI)"
            if st.sidebar.button(label, use_container_width=True):
                st.switch_page("pages/3_Dashboard.py")

        # Processar Relatórios (perm específica)
        if "realizar_upload_relatorio" in perms_lower:
            if st.sidebar.button(("📤 " if current_page == "processar" else "📤 ") + "Processar Relatórios",
                                 use_container_width=True):
                st.switch_page("pages/2_Processar_Relatórios.py")

        # Admin
        if is_admin:
            if st.sidebar.button(("👥 " if current_page == "admin_usuarios" else "👥 ") + "Gerenciar Usuários",
                                 use_container_width=True):
                st.switch_page("pages/Admin_Usuarios.py")
            if st.sidebar.button(("🗑️ " if current_page == "admin_exclusoes" else "🗑️ ") + "Gerenciar Exclusões",
                                 use_container_width=True):
                st.switch_page("pages/Gerenciar_Exclusoes.py")

        # About — sempre
        if st.sidebar.button(("ℹ️ " if current_page == "about" else "ℹ️ ") + "About", use_container_width=True):
            st.switch_page("pages/7_About.py")

        st.divider()
        st.caption(f"Conectado como: {st.session_state.get('user_email') or 'usuário'}")
        if st.sidebar.button("🚪 Logout", key="logout_btn", use_container_width=True):
            try:
                _logout_backend()
            finally:
                _limpar_session()
                st.switch_page("Home.py")

def render_texto_literal(text: str | None):
    """
    Renderiza texto literal (ex.: 'R$ 750.000,00') sem que o Streamlit aplique Markdown/LaTeX.
    Mantém quebras de linha (white-space: pre-wrap).
    """
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    safe = html.escape(text)  # escapa < > & e afins
    st.markdown(f"<div style='white-space:pre-wrap'>{safe}</div>", unsafe_allow_html=True)

def _buscar_me_perfil() -> dict:
    try:
        r = requests.get(f"{API_URL}/me/perfil", headers=_auth_headers(), timeout=10)
        if r.status_code == 200:
            return r.json() or {}
    except requests.RequestException:
        pass
    return {}

def _is_admin(perms_lower: set[str]) -> bool:
    return (
        "view_pagina_admin_usuarios" in perms_lower
        or {"gerenciar_usuarios", "gerenciar_papeis"}.issubset(perms_lower)
    )


# ---------------------------
# Solicitação de Acesso
# ---------------------------

def _set_qp(**pairs):
    qp = dict(st.query_params)
    for k, v in pairs.items():
        if v is None:
            qp.pop(k, None)
        else:
            qp[k] = v
    st.query_params = qp

def ir_para_solicitar_acesso():
    # Tenta por caminho e por rótulo (Streamlit transforma "_" em espaço no menu)
    candidates = (
        "pages/Solicitar_Acesso.py",  # seu arquivo com underscore e maiúsculas
        "pages/solicitar_acesso.py",  # tudo minúsculo (se mudar no futuro)
        "Solicitar_Acesso",           # rótulo igual ao nome do arquivo
        "Solicitar Acesso",           # rótulo com espaço (mais comum no menu)
    )
    for c in candidates:
        try:
            st.switch_page(c)
            return
        except Exception:
            pass
    # Fallback por querystring (ainda funciona se você roteia no Home)
    qp = dict(st.query_params)
    qp["page"] = "Solicitar_Acesso"
    qp.pop("rt", None); qp.pop("u", None)
    st.query_params = qp
    st.rerun()

def ir_para_pagina_publica(page_slug: str):
    _set_qp(page=page_slug, rt=None, u=None)
    st.session_state.pop("auth_token", None)
    st.session_state.pop("logged_in", None)
    st.rerun()