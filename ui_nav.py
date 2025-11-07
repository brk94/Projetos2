import os
import json
import html
from pathlib import Path
from typing import Optional, List, Set

import requests
import streamlit as st

# ============================
# Config & Persistência Local
# ============================
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
_SESSION_FILE = Path.home() / ".mc_sonae_session.json"

def _clear_session_local():
    try:
        if _SESSION_FILE.exists():
            _SESSION_FILE.unlink()
    except Exception:
        pass

# Persistência local de sessão
def _persist_session_local(rt: str | None, email: str | None):
    """Salva refresh token e e-mail localmente para reabrir sessão depois."""
    try:
        data = {"rt": rt or "", "u": email or ""}
        _SESSION_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        # Falha silenciosa para não quebrar a UI
        pass

def _load_session_local() -> tuple[str, str]:
    """Carrega refresh token e e-mail salvos localmente (se existirem)."""
    try:
        data = json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
        return (data.get("rt") or "", data.get("u") or "")
    except Exception:
        return "", ""

# ============================
# Helpers de Sessão / HTTP
# ============================
def _auth_headers() -> dict:
    token = st.session_state.get("auth_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}

def _metodo_http(method, path, **kw):
    url = path if path.startswith("http") else f"{API_URL}{path}"
    extra_headers = kw.pop("headers", {}) or {}
    headers = {**_auth_headers(), **extra_headers}
    if "timeout" not in kw:
        kw["timeout"] = 10

    resp = requests.request(method, url, headers=headers, **kw)
    if resp.status_code != 401:
        return resp

    if _atualizar_token_se_necessario():
        headers = {**_auth_headers(), **extra_headers}
        return requests.request(method, url, headers=headers, **kw)
    return resp

def req_get(path, **kw): return _metodo_http("GET", path, **kw)
def req_post(path, **kw): return _metodo_http("POST", path, **kw)
def req_put(path: str, **kwargs): return _metodo_http("PUT", path, **kwargs)
def req_delete(path, **kw): return _metodo_http("DELETE", path, **kw)

def api_headers() -> dict:
    return _auth_headers()

def _limpar_session():
    for k in ("logged_in", "user_email", "auth_token", "refresh_token", "perms"):
        if k in st.session_state:
            del st.session_state[k]
    qp = dict(st.query_params)
    for k in ("rt", "u", "logout"):
        if k in qp:
            qp.pop(k, None)
    st.query_params = qp

def _atualizar_token_se_necessario() -> bool:
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
        st.session_state["refresh_token"] = data.get("refresh_token", rt)
        st.session_state["logged_in"] = True

        qp = dict(st.query_params)
        qp["rt"] = st.session_state["refresh_token"]
        if st.session_state.get("user_email"):
            qp["u"] = st.session_state["user_email"]
        st.query_params = qp
        return True
    return False

# =========================================================
# Bootstrap silencioso
# =========================================================
def _inicializar_sessao_por_query_e_refresh() -> bool:
    def _qp_first(value):
        if isinstance(value, list):
            return value[0] if value else ""
        return value or ""

    qp = dict(st.query_params)
    rt = _qp_first(qp.get("rt"))
    u  = _qp_first(qp.get("u"))

    if rt and not st.session_state.get("refresh_token"):
        st.session_state["refresh_token"] = rt
    if u and not st.session_state.get("user_email"):
        st.session_state["user_email"] = u
    if st.session_state.get("refresh_token") and not st.session_state.get("logged_in"):
        st.session_state["logged_in"] = True

    if st.session_state.get("auth_token"):
        return False

    if not (st.session_state.get("logged_in") and st.session_state.get("refresh_token")):
        return False

    try:
        resp = requests.post(f"{API_URL}/token/refresh",
                             json={"refresh_token": st.session_state["refresh_token"]},
                             timeout=10)
        if resp.status_code == 200:
            data = resp.json() or {}
            st.session_state["auth_token"]    = data.get("access_token", "")
            st.session_state["refresh_token"] = data.get("refresh_token", st.session_state["refresh_token"])
            qp = dict(st.query_params)
            qp["rt"] = st.session_state["refresh_token"]
            if st.session_state.get("user_email"):
                qp["u"] = st.session_state["user_email"]
            st.query_params = qp
            return True
    except requests.RequestException:
        pass
    return False

# =========================================================
# Permissões (fatal)
# =========================================================
def garantir_sessao_e_permissoes(force_reload: bool = False, require_perm: Optional[str] = None) -> List[str]:
    _inicializar_sessao_por_query_e_refresh()

    if not st.session_state.get("logged_in"):
        try:
            st.switch_page("Home.py")
        except Exception:
            st.query_params.clear()
            st.experimental_set_query_params(pagina="home")
            st.stop()

    cached: List[str] = st.session_state.get("perms") or []
    if cached and not force_reload:
        if require_perm:
            perms_lower_cached = {p.lower() for p in cached}
            is_admin_cached = (
                "view_pagina_admin_usuarios" in perms_lower_cached
                or {"gerenciar_usuarios", "gerenciar_papeis"}.issubset(perms_lower_cached)
            )
            if (not is_admin_cached) and (require_perm.lower() not in perms_lower_cached):
                st.warning("Página não disponível para seu perfil.")
                st.stop()
        return cached

    def _headers() -> dict:
        token = st.session_state.get("auth_token", "")
        return {"Authorization": f"Bearer {token}"} if token else {}

    def _buscar_permissoes() -> Optional[List[str]]:
        try:
            r = requests.get(f"{API_URL}/me/permissoes", headers=_headers(), timeout=10)
            if r.status_code == 200:
                return r.json() or []
            if r.status_code == 401:
                return None
        except requests.RequestException:
            pass
        return []

    perms = _buscar_permissoes()
    if perms is None:
        refreshed = _inicializar_sessao_por_query_e_refresh()
        perms = _buscar_permissoes() if refreshed else []
    if not perms:
        perms = cached

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
            st.warning("Página não disponível para seu perfil.")
            st.stop()

    return perms

# =========================================================
# Versão NÃO-FATAL — Home
# =========================================================
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
        return st.session_state["perms"]
    except requests.RequestException:
        return st.session_state["perms"]

# ============================
# Backend — logout
# ============================
def _logout_backend():
    rt = st.session_state.get("refresh_token", "")
    if not rt:
        return
    try:
        requests.post(f"{API_URL}/logout",
                      json={"refresh_token": rt},
                      headers=_auth_headers(),
                      timeout=10)
    except requests.RequestException:
        pass
    _clear_session_local()

# ============================
# Utils de Navegação Pública
# ============================
def _set_qp(**pairs):
    qp = dict(st.query_params)
    for k, v in pairs.items():
        if v is None:
            qp.pop(k, None)
        else:
            qp[k] = v
    st.query_params = qp

def ir_para_solicitar_acesso():
    """Mantido para compatibilidade com Home.py"""
    candidates = (
        "pages/Solicitar_Acesso.py",
        "pages/solicitar_acesso.py",
        "Solicitar_Acesso",
        "Solicitar Acesso",
    )
    for c in candidates:
        try:
            st.switch_page(c)
            return
        except Exception:
            pass
    qp = dict(st.query_params)
    qp["page"] = "Solicitar_Acesso"
    qp.pop("rt", None); qp.pop("u", None)
    st.query_params = qp
    st.rerun()

def ir_para_pagina_publica(page_slug: str):
    """Mantido para compatibilidade se for usado em algum lugar"""
    _set_qp(page=page_slug, rt=None, u=None)
    st.session_state.pop("auth_token", None)
    st.session_state.pop("logged_in", None)
    st.rerun()

# ============================
# Visual helpers (Sidebar Skin)
# ============================
def _menu_lateral_layout():
    st.markdown("""
    <style>
      [data-testid="stSidebarNav"] { display:none !important; }

      section[data-testid="stSidebar"], [data-testid="stSidebar"]{
        background:#fff!important; min-width:280px!important; max-width:280px!important; padding:0!important;
      }
      [data-testid="stSidebar"] > div:first-child{ padding:0!important; }

      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
      * { font-family:'Inter', system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }

      .sidebar-header{ padding:16px 16px 12px; border-bottom:0 !important; box-shadow:none !important; }
      .sidebar-logo{ display:flex; align-items:center; gap:10px; margin-bottom:12px; }
      .sidebar-logo-img{
        width:34px; height:34px; border-radius:7px; display:flex; align-items:center; justify-content:center;
        background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); color:#fff; font-weight:700; font-size:14px;
      }
      .sidebar-logo-text h3{ margin:0 0 2px 0; font-size:14px; font-weight:600; color:#1a1a1a; line-height:0.1; }
      .sidebar-logo-text p{ margin:0; font-size:12px; color:#6b7280; line-height:0.1; }

      .sidebar-user{
        display:block !important;
        padding:10px !important;
        background:#f8f9fa !important;
        border-radius:8px !important;
      }
      .sidebar-user-avatar{ display:none !important; }

      /* --- novos estilos para rótulos/valores --- */
      .meta-label{
        margin:0 0 4px 0 !important;
        font-size:10.5px !important;
        color:#6b7280 !important;
        text-transform:uppercase !important;
        letter-spacing:.02em !important;
        line-height:1.1 !important;
      }
      .value-email{
        margin:0 0 6px 0 !important;
        font-size:13px !important;
        font-weight:600 !important;
        color:#1a1a1a !important;
        line-height:1.15 !important;
        word-break:break-all;
      }
      .value-setor{
        margin:0 !important;
        font-size:11.5px !important;
        color:#374151 !important;
        line-height:1.1 !important;
      }

      section[data-testid="stSidebar"]{ --nav-gap: 12px; --nav-gap-first: 12px; }
      section[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{ gap:0 !important; }
      section[data-testid="stSidebar"] [data-testid="element-container"]{ margin:0 !important; padding:0 !important; }
      .sidebar-nav{ padding:0 !important; }
      .sidebar-nav .nav-spacer{ height: var(--nav-gap-first); }

      section[data-testid="stSidebar"] [data-testid="stPageLink"]{
        display:block !important; margin: var(--nav-gap) 0 !important;
      }
      .sidebar-nav [data-testid="stPageLink"] > a{
        display:block !important; width:100% !important;
        text-decoration:none !important; background:transparent !important; border:none !important;
        border-radius:6px !important; min-height:28px !important; padding:4px 8px !important;
        font-size:13px !important; font-weight:500 !important; color:#111827 !important;
        line-height:20px !important; text-align:left !important;
      }
      .sidebar-nav [data-testid="stPageLink"] > a:hover{ background:#f5f6f8 !important; }

      .nav-row{ margin:0 !important; padding:0 !important; }
      .nav-row.active [data-testid="stPageLink"] > a{ background:#2563eb !important; color:#fff !important; }

      .logout-btn button{
        background:transparent !important; border:none !important; box-shadow:none !important; outline:none !important;
        display:block !important; width:100% !important; text-align:left !important;
        border-radius:6px !important; min-height:28px !important; padding:4px 8px !important;
        font-size:13px !important; font-weight:500 !important; color:#111827 !important;
        line-height:20px !important; cursor:pointer !important;
      }
      .logout-btn button:hover{ background:#f5f6f8 !important; }
    </style>
    """, unsafe_allow_html=True)


def _cabecalho_menu_lateral():
    perfil = st.session_state.get("me_perfil") or {}
    email  = st.session_state.get("user_email") or "—"
    setor  = (perfil.get("setor") or "Administrador")

    # Para evitar que qualquer caractere especial quebre o HTML
    email_safe = html.escape(str(email))
    setor_safe = html.escape(str(setor))

    st.markdown(
        f"""
        <div class="sidebar-header">
        <div class="sidebar-logo">
            <div class="sidebar-logo-img">MC</div>
            <div class="sidebar-logo-text">
            <h3>MC Sonae</h3>
            <p>Dashboard</p>
            </div>
        </div>

        <div class="sidebar-user">
            <div class="sidebar-user-info">
            <div class="meta-label">Usuário conectado</div>
            <div class="value-email">{email_safe}</div>
            <div class="meta-label">Setor</div>
            <div class="value-setor">{setor_safe}</div>
            </div>
        </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def _nav_link_pagina_navegacao(label: str, icon: str, page: str, active: bool=False):
    st.markdown(f'<div class="nav-row{" active" if active else ""}">', unsafe_allow_html=True)
    st.page_link(page, label=f"{icon} {label}", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

def _nav_logout(label: str = "Sair"):
    # Botão estilizado igual aos links
    st.markdown('<div class="nav-row logout-btn">', unsafe_allow_html=True)
    if st.button(f"↩ {label}", key="logout_link_btn", use_container_width=True):
        try:
            _logout_backend()
        finally:
            _limpar_session()
            try:
                st.switch_page("Home.py")
            except Exception:
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ============================
# Sidebar / navegação (visual)
# ============================
def render_menu_lateral(perms: list[str] | None, current_page: str | None = None):
    perms_lower = {p.lower() for p in (perms or [])}
    is_admin = (
        "view_pagina_admin_usuarios" in perms_lower
        or {"gerenciar_usuarios", "gerenciar_papeis"}.issubset(perms_lower)
    )

    perfil = st.session_state.get("me_perfil") or _buscar_me_perfil() or {}
    setor = (perfil.get("setor") or "").strip().upper()
    eh_usuario_ti = (setor == "TI")

    with st.sidebar:
        _menu_lateral_layout()
        _cabecalho_menu_lateral()

        st.markdown('<div class="sidebar-nav">', unsafe_allow_html=True)
        st.markdown('<div class="nav-spacer"></div>', unsafe_allow_html=True)

        _nav_link_pagina_navegacao("Home", "🏠", "Home.py", active=(current_page == "home"))

        can_view_dash_ti = (is_admin or ("view_dashboard_ti" in perms_lower)) and (is_admin or eh_usuario_ti)
        if can_view_dash_ti:
            _nav_link_pagina_navegacao("Dashboard (TI)", "📊", "pages/3_Dashboard.py",
                           active=(current_page in {"dashboard", "dash_ti"}))

        if "realizar_upload_relatorio" in perms_lower:
            _nav_link_pagina_navegacao("Processar Relatórios", "📤", "pages/2_Processar_Relatórios.py",
                           active=(current_page == "processar"))

        if is_admin:
            _nav_link_pagina_navegacao("Gerenciar Usuários", "👥", "pages/Admin_Usuarios.py",
                           active=(current_page == "admin_usuarios"))
            _nav_link_pagina_navegacao("Gerenciar Exclusões", "🗑️", "pages/Gerenciar_Exclusoes.py",
                           active=(current_page == "admin_exclusoes"))

        _nav_link_pagina_navegacao("About", "ℹ️", "pages/7_About.py", active=(current_page == "about"))

        # Sair (igual aos demais, mas executa logout)
        _nav_logout("Sair")

        st.markdown('</div>', unsafe_allow_html=True)

# ============================
# Outros helpers
# ============================
def render_texto_literal(text: str | None):
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    safe = html.escape(text)
    st.markdown(f"<div style='white-space:pre-wrap'>{safe}</div>", unsafe_allow_html=True)

def _buscar_me_perfil() -> dict:
    try:
        r = requests.get(f"{API_URL}/me/perfil", headers=_auth_headers(), timeout=10)
        if r.status_code == 200:
            return r.json() or {}
    except requests.RequestException:
        pass
    return {}