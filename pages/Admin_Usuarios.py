"""
Página Streamlit — Admin • Gerenciar Usuários

Seções:
- Setup da página (visual) e Segurança/Navegação
- Utilities (wrappers para API + cache curto)
- Tab 1: Usuários (busca, edição de setor, modal “Gerenciar Acesso”)
- Tab 2: Solicitações de Acesso (listar e decidir)
"""

# ======================================================================================
# Imports e Setup visual
# ======================================================================================
import streamlit as st
from ui_nav import (
    garantir_sessao_e_permissoes,
    render_menu_lateral,
    req_get, req_put, req_post, req_delete,
)

from pathlib import Path
from base64 import b64encode

# ======================================================================================
# Utilitário de imagem (robusto)
# ======================================================================================
def _load_image_b64(filename: str) -> str | None:
    here = Path(__file__).resolve().parent
    candidates = [
        here / "images" / filename,                 # ./pages/images/<file>
        Path.cwd() / "pages" / "images" / filename, # raiz/pages/images/<file>
        here / filename,                            # fallback raro
    ]
    for p in candidates:
        if p.exists():
            try:
                return b64encode(p.read_bytes()).decode()
            except Exception:
                pass
    return None

# ======================================================================================
# Config de página + CSS (somente visual)
# ======================================================================================
st.set_page_config(page_title="Admin • Gerenciar Usuários", page_icon="👥", layout="wide")
st.markdown(
    """
<style>
[data-testid="stSidebarNav"]{display:none!important}
button[kind="header"]{display:none!important}

/* Altura/estilo dos botões para alinhar com o selectbox (44px) */
.stButton > button { height: 44px; padding: 0 16px; border-radius: 10px; }
/* Evita “pulo” visual */
.block-container button, .block-container .stButton { margin-top: 0 !important; }
</style>
""",
    unsafe_allow_html=True,
)

# Título com ícone
_icon_b64 = _load_image_b64("gerenciar.png")
st.markdown(
    f"""
<div style="display:flex;align-items:center;gap:8px;">
  {'<img src="data:image/png;base64,' + _icon_b64 + '" alt="Gerenciar icon" style="width:48px;height:48px;object-fit:contain;border-radius:4px;" />' if _icon_b64 else '👥'}
  <h1 style="margin:0;">Gerenciar Usuários</h1>
</div>
""",
    unsafe_allow_html=True,
)
st.caption("Gerencie usuários e solicitações de acesso ao sistema")

# ======================================================================================
# Segurança / Navegação (gate inicial)
# ======================================================================================
perms = garantir_sessao_e_permissoes()
render_menu_lateral(perms, current_page="admin_usuarios")
perms_lower = {p.lower() for p in (perms or [])}

# ✅ Correção: permite se tiver QUALQUER uma dessas permissões
tem_acesso = bool(
    {"gerenciar_usuarios", "gerenciar_papeis"} & perms_lower
    or "view_pagina_admin_usuarios" in perms_lower
)
if not tem_acesso:
    st.warning("Página não disponível para seu perfil.")
    st.stop()

# Toast de feedback pós-ação (via session_state)
if "flash_toast" in st.session_state:
    st.toast(st.session_state.pop("flash_toast"), icon="✅")

# ======================================================================================
# Utilities: helpers de API + cache curto (10s)
# ======================================================================================
@st.cache_data(ttl=10)
def _try_get(url: str, params: dict | None = None):
    r = req_get(url, params=params)
    return (r.status_code, r.json() if r and r.headers.get("content-type", "").startswith("application/json") else None)

@st.cache_data(ttl=10)
def _admin_listar_projetos():
    status, data = _try_get("/admin/projetos/lista")
    if status != 200 or not data:
        status2, data2 = _try_get("/projetos/lista/")
        data = data2 if (status2 == 200 and data2) else []

    norm = []
    for p in (data or []):
        codigo = (
            p.get("codigo_projeto")
            or p.get("codigo")
            or p.get("cod")
            or p.get("codigo_projeto_fk")
            or p.get("id")
        )
        nome = (
            p.get("nome_projeto")
            or p.get("nome")
            or p.get("titulo")
            or p.get("project_name")
        )
        area = (
            p.get("area_negocio")
            or p.get("setor")
            or p.get("departamento")
        )
        if codigo and nome:
            norm.append({
                "codigo_projeto": str(codigo),
                "nome_projeto": str(nome),
                "area_negocio": (str(area).strip() if area is not None else ""),
            })
    return norm

def _admin_listar_acessos_usuario(id_usuario: int):
    r = req_get(f"/admin/usuarios/{id_usuario}/acessos")
    return r.json() if r and r.status_code == 200 else []

def _admin_conceder_acesso(id_usuario: int, codigo_projeto: str, papel: str | None = None):
    payload = {"codigo_projeto": codigo_projeto}
    if papel is not None:
        payload["papel"] = papel
    return req_post(f"/admin/usuarios/{id_usuario}/acessos", json=payload)

def _admin_revogar_acesso(id_usuario: int, codigo_projeto: str):
    return req_delete(f"/admin/usuarios/{id_usuario}/acessos/{codigo_projeto}")

def _load_users(q_):
    try:
        r = req_get("/admin/usuarios", params={"q": q_} if q_ else None)
        if r.status_code == 200:
            return r.json()
        st.error(r.json().get("detail") if "application/json" in r.headers.get("content-type", "") else r.text)
    except Exception as e:
        st.error(f"Erro: {e}")
    return []

# ======================================================================================
# Modal compatível (st.dialog / experimental / fallback)
# ======================================================================================
def _open_modal_acesso(alvo: dict):
    """
    Mostra o modal de 'Gerenciar Acesso' com o melhor recurso disponível.
    """
    def _body():
        st.caption(alvo["email"])

        _admin_listar_projetos.clear()
        _try_get.clear()
        all_projs = _admin_listar_projetos()

        current = _admin_listar_acessos_usuario(alvo["id_usuario"])

        setor_state_key = f"setor_{alvo['id_usuario']}"
        setor_atual = st.session_state.get(setor_state_key, None)
        user_setor = (setor_atual if setor_atual is not None else (alvo.get("setor") or "")).strip()
        user_setor_norm = user_setor.upper()

        projs_filtrados = [
            p for p in (all_projs or [])
            if (p.get("area_negocio", "").strip().upper() == user_setor_norm)
        ]

        opts = {p["nome_projeto"]: p["codigo_projeto"] for p in projs_filtrados}
        atuais = {acc.get("codigo_projeto_fk") for acc in (current or []) if acc.get("codigo_projeto_fk")}
        defaults = [nome for nome, cod in opts.items() if cod in atuais]

        if not user_setor:
            st.warning("Usuário sem setor definido. Não é possível listar projetos para concessão de acesso.")
        elif not projs_filtrados:
            st.info(f"Não há projetos cadastrados para o setor **{user_setor}**.")
        else:
            st.caption(f"Somente projetos do setor **{user_setor}** podem ser atribuídos a este usuário.")

        selecionados = st.multiselect(
            "Projetos com acesso de visualização",
            options=list(opts.keys()),
            default=defaults,
            help="Selecione os projetos (do mesmo setor do usuário) que ele poderá visualizar no dashboard.",
            placeholder="Selecione os projetos...",
        )

        st.markdown("---")
        colx, coly = st.columns([1, 1])
        with colx:
            if st.button("Salvar alterações", type="primary", use_container_width=True, disabled=(not projs_filtrados)):
                selecionados_cod = {opts[n] for n in selecionados}
                atuais_filtrados = atuais.intersection(set(opts.values()))

                to_grant = selecionados_cod - atuais_filtrados
                to_revoke = atuais_filtrados - selecionados_cod

                ok = True
                for cod in sorted(to_grant):
                    r = _admin_conceder_acesso(alvo["id_usuario"], cod)
                    ok &= (r is not None and r.status_code in (200, 201))
                for cod in sorted(to_revoke):
                    r = _admin_revogar_acesso(alvo["id_usuario"], cod)
                    ok &= (r is not None and r.status_code in (200, 204))

                if ok:
                    st.session_state["flash_toast"] = "Acessos atualizados com sucesso."
                    st.session_state.pop("modal_user_acesso", None)
                    _admin_listar_projetos.clear()
                    _try_get.clear()
                    st.rerun()
                else:
                    st.error("Falha ao atualizar alguns acessos. Verifique o log do servidor.")

        with coly:
            if st.button("Cancelar", use_container_width=True):
                st.session_state.pop("modal_user_acesso", None)
                st.rerun()

    # Preferência: st.dialog → experimental_dialog → fallback
    if hasattr(st, "dialog"):
        @st.dialog(f"Gerenciar Acesso — {alvo['nome']}", width="large")
        def _dlg():
            _body()
        _dlg()
    elif hasattr(st, "experimental_dialog"):
        @st.experimental_dialog(f"Gerenciar Acesso — {alvo['nome']}")
        def _dlg2():
            _body()
        _dlg2()
    else:
        # Fallback simples (expander no topo)
        with st.expander(f"Gerenciar Acesso — {alvo['nome']} (fallback)", expanded=True):
            _body()

# ======================================================================================
# Tabs (Usuários / Solicitações)
# ======================================================================================
tab_usuarios, tab_solicitacoes = st.tabs(["Usuários", "Solicitações de Acesso"])

# ======================================================================================
# ABA 1 — USUÁRIOS
# ======================================================================================
with tab_usuarios:
    colf1, colf2 = st.columns([2, 1], vertical_alignment="bottom")
    with colf1:
        q = st.text_input("Buscar por nome ou e-mail", placeholder="ex.: joao@mcsonae.com")
    with colf2:
        if st.button("Atualizar lista", use_container_width=True):
            _admin_listar_projetos.clear()
            _try_get.clear()
            st.rerun()

    data_u = _load_users(q)

    if not data_u:
        st.info("Nenhum usuário encontrado.")
    else:
        opcoes_setor = ["Retalho", "TI", "Marketing", "RH"]

        # Abre modal se estiver agendado no session_state
        if st.session_state.get("modal_user_acesso"):
            _open_modal_acesso(st.session_state["modal_user_acesso"])

        for u in data_u:
            setor_str = (u.get("setor") or "")
            cargo_str = (u.get("cargo") or "")
            is_admin_user = (cargo_str or "").strip() == "Administrador"

            header = f"#{u['id_usuario']} • {u['nome']}  |  {u['email']}  |  {cargo_str}  |  {setor_str}"
            with st.expander(header, expanded=False):

                if is_admin_user:
                    c1, c3, c4 = st.columns([3, 1, 1], vertical_alignment="center")
                    with c1:
                        st.text_input(
                            "Nome",
                            value=u["nome"],
                            key=f"nome_{u['id_usuario']}",
                            label_visibility="collapsed",
                            disabled=True,
                        )
                    with c3: st.caption("Administrador")
                    with c4: st.caption(" ")
                else:
                    c1, c2, c3, c4 = st.columns([2, 2, 1, 1], vertical_alignment="center")

                    with c1:
                        st.text_input(
                            "Nome",
                            value=u["nome"],
                            key=f"nome_{u['id_usuario']}",
                            label_visibility="collapsed",
                            disabled=True,
                        )

                    with c2:
                        opcoes = [""] + opcoes_setor
                        idx = opcoes.index(setor_str) if setor_str in opcoes else 0
                        setor = st.selectbox(
                            "Setor",
                            opcoes,
                            index=idx,
                            key=f"setor_{u['id_usuario']}",
                            label_visibility="collapsed",
                        )

                    with c3:
                        if st.button("💾 Salvar", key=f"save_{u['id_usuario']}", use_container_width=True):
                            try:
                                prev_setor = setor_str or ""
                                new_setor  = setor or ""
                                changed_setor = (prev_setor != new_setor)
                                if not changed_setor:
                                    st.info("Nenhuma alteração a salvar.")
                                else:
                                    payload = {"setor": (setor or None)}
                                    r = req_put(f"/admin/usuarios/{u['id_usuario']}", json=payload)
                                    if r.status_code == 200:
                                        st.session_state["flash_toast"] = (
                                            f"Usuário {u['nome']} ({u['email']}): Setor alterado de "
                                            f"{prev_setor or '—'} para {new_setor or '—'}."
                                        )
                                        _admin_listar_projetos.clear()
                                        _try_get.clear()
                                        st.rerun()
                                    else:
                                        st.error(r.json().get("detail") if "application/json" in r.headers.get("content-type", "") else r.text)
                            except Exception as e:
                                st.error(f"Erro: {e}")

                    with c4:
                        if st.button("🔐 Gerenciar Acesso", key=f"acc_{u['id_usuario']}", use_container_width=True):
                            st.session_state["modal_user_acesso"] = u
                            st.rerun()

# ======================================================================================
# ABA 2 — SOLICITAÇÕES DE ACESSO
# ======================================================================================
with tab_solicitacoes:
    st.caption("Aprovar cria o usuário; rejeitar pode ter motivo (opcional).")

    STATUS_OPTS = ["aguardando", "aprovado", "rejeitado", "expirado"]
    default_val = st.session_state.get("admin_solic_status", "aguardando")
    status = st.selectbox(
        "Status",
        STATUS_OPTS,
        index=STATUS_OPTS.index(default_val),
        format_func=lambda s: s.title(),
        key="admin_solic_status",
    )

    def _carregar_solicitacao(_status: str):
        try:
            status_code, data = _try_get("/admin/solicitacoes", params={"status": _status})
            if status_code == 200:
                return data
            st.error(data.get("detail") if isinstance(data, dict) else "Falha ao listar solicitações.")
        except Exception as e:
            st.error(f"Erro: {e}")
        return []

    def _decidir(id_solic: int, decisao: str, motivo: str | None = None, label: str = ""):
        try:
            payload = {"decisao": decisao}
            if motivo:
                payload["motivo"] = motivo
            r = req_post(f"/admin/solicitacoes/{id_solic}/decidir", json=payload)
            if r.status_code == 200:
                acao = "Aprovada" if decisao == "aprovar" else "Rejeitada"
                st.session_state["flash_toast"] = f"Solicitação {acao}: {label}."
                st.rerun()
            else:
                st.error(r.json().get("detail") if "application/json" in r.headers.get("content-type","") else r.text)
        except Exception as e:
            st.error(f"Erro: {e}")

    data_s = _carregar_solicitacao(status)

    if not data_s:
        st.info("Nenhuma solicitação para o filtro selecionado.")
    else:
        for s in data_s:
            header = f"{s['nome']} | {s['email']} | {s.get('setor') or ''} | Cargo: {s.get('cargo')}"
            with st.expander(header, expanded=False):
                st.write("**Justificativa do solicitante:**")
                st.write((s.get("justificativa") or "").strip() or "—")

                if status == "aguardando":
                    motivo = st.text_area(
                        "Motivo (opcional) — será salvo tanto em aprovação quanto em rejeição",
                        key=f"motivo_{s['id_solicitacao']}",
                        placeholder="Explique sua decisão...",
                    )
                    colA, colB = st.columns(2, vertical_alignment="center")
                    with colA:
                        if st.button("✅ Aprovar", key=f"ap_{s['id_solicitacao']}", use_container_width=True):
                            _decidir(s["id_solicitacao"], "aprovar", motivo or None, label=f"{s['nome']} ({s['email']})")
                    with colB:
                        if st.button("❌ Rejeitar", key=f"rj_{s['id_solicitacao']}", use_container_width=True):
                            _decidir(s["id_solicitacao"], "rejeitar", motivo or None, label=f"{s['nome']} ({s['email']})")
                else:
                    motivo_txt = (s.get("motivo_decisao") or "").strip() or "Motivo não informado"
                    dec_por_nome = (s.get("decidido_por_nome") or "—")
                    dec_em_txt = s.get("decidido_em") or "—"
                    st.caption(f"Decidido por: {dec_por_nome} em {dec_em_txt} | Motivo: {motivo_txt}")
