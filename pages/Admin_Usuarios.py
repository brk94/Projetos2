"""
Página Streamlit — Admin • Gerenciar Usuários

Seções:
- Setup da página (visual) e Segurança/Navegação
- Utilities (wrappers para API + cache curto)
- Tab 1: Usuários (busca, edição de setor, modal “Gerenciar Acesso”)
- Tab 2: Solicitações de Acesso (listar e decidir)

Destaques de leitura:
- **Mapeamento de chaves**: normaliza respostas do backend (cód/nome/área) para o multiselect.
- **Filtro por Setor** no modal: lista apenas projetos do mesmo setor do usuário alvo.
- **Cache & Rerun**: `@st.cache_data(ttl=10)` + `clear()` + `st.rerun()` ao salvar/cancelar.
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

# Config de página + CSS (só visual; mantém comportamento)
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

ICON_PATH = Path(__file__).parent / "images" / "gerenciar.png"
icon_b64 = b64encode(ICON_PATH.read_bytes()).decode()

st.markdown(
    f"""
<div style="display:flex;align-items:center;gap:8px;">
  <img src="data:image/png;base64,{icon_b64}" alt="Gerenciar icon"
       style="width:48px;height:48px;object-fit:contain;border-radius:4px;" />
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
if not ( {"gerenciar_usuarios", "gerenciar_papeis"} <= perms_lower or "view_pagina_admin_usuarios" in perms_lower ):
    st.warning("Página não disponível para seu perfil.")
    st.stop()

# Toast de feedback pós-ação (via session_state)
if "flash_toast" in st.session_state:
    st.toast(st.session_state.pop("flash_toast"), icon="✅")

# ======================================================================================
# Utilities: helpers de API + cache curto (10s)
# ======================================================================================
@st.cache_data(ttl=10)
def _try_get(url: str):
    """GET simples que retorna (status_code, json|None). Mantém TTL curto p/ responsividade."""
    r = req_get(url)
    return (r.status_code, r.json() if r and r.headers.get("content-type", "").startswith("application/json") else None)


@st.cache_data(ttl=10)
def _admin_listar_projetos():
    """Catálogo de projetos para o multiselect do modal.
    1) Tenta `/admin/projetos/lista`; 2) fallback para `/projetos/lista/`.
    3) **Normaliza chaves** (código/nome/área) para evitar variações vindas do backend.
    """
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
    """Busca lista de usuários (admin). Propaga mensagens de erro da API na UI."""
    try:
        r = req_get("/admin/usuarios", params={"q": q_} if q_ else None)
        if r.status_code == 200:
            return r.json()
        st.error(r.json().get("detail") if "application/json" in r.headers.get("content-type", "") else r.text)
    except Exception as e:
        st.error(f"Erro: {e}")
    return []

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
            # Limpa caches usados na seção e força recarga
            _admin_listar_projetos.clear()
            _try_get.clear()
            st.rerun()

    data_u = _load_users(q)

    if not data_u:
        st.info("Nenhum usuário encontrado.")
    else:
        opcoes_setor = ["Retalho", "TI", "Marketing", "RH"]  # domínio apresentado

        # ---------------- Modal (Dialog) — Gerenciar Acesso ----------------
        if st.session_state.get("modal_user_acesso"):
            alvo = st.session_state["modal_user_acesso"]

            @st.dialog(f"Gerenciar Acesso — {alvo['nome']}", width="large")
            def dialog_acesso():
                st.caption(alvo["email"])

                # Sempre recarrega catálogo ao abrir o modal
                _admin_listar_projetos.clear()
                _try_get.clear()
                all_projs = _admin_listar_projetos()

                current = _admin_listar_acessos_usuario(alvo["id_usuario"])

                # Setor atual (usa select da lista, se já alterado, senão setor do alvo)
                setor_state_key = f"setor_{alvo['id_usuario']}"
                setor_atual = st.session_state.get(setor_state_key, None)
                user_setor = (setor_atual if setor_atual is not None else (alvo.get("setor") or "")).strip()
                user_setor_norm = user_setor.upper()

                # Filtro: lista apenas projetos do MESMO setor do usuário
                projs_filtrados = [
                    p for p in (all_projs or [])
                    if (p.get("area_negocio", "").strip().upper() == user_setor_norm)
                ]

                # Opções (nome → código) e defaults (acessos já existentes)
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
                colx, coly = st.columns([1, 1], vertical_alignment="center")
                with colx:
                    if st.button("Salvar alterações", type="primary", use_container_width=True, disabled=(not projs_filtrados)):
                        selecionados_cod = {opts[n] for n in selecionados}
                        atuais_filtrados = atuais.intersection(set(opts.values()))

                        # Diferenças: o que conceder vs. o que revogar
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

            dialog_acesso()

        # ---------------- Lista de usuários ----------------
        for u in data_u:
            setor_str = (u.get("setor") or "")
            cargo_str = (u.get("cargo") or "")
            is_admin_user = (cargo_str or "").strip() == "Administrador"

            header = f"#{u['id_usuario']} • {u['nome']}  |  {u['email']}  |  {cargo_str}  |  {setor_str}"
            with st.expander(header, expanded=False):

                if is_admin_user:
                    # Admin não muda setor/acessos por aqui (somente leitura)
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
                        # Select de setor com default no valor atual (se existir)
                        opcoes = [""] + ["Retalho", "TI", "Marketing", "RH"]
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
            r = req_get("/admin/solicitacoes", params={"status": _status})
            if r.status_code == 200:
                return r.json()
            st.error(r.json().get("detail") if "application/json" in r.headers.get("content-type", "") else r.text)
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
                st.error(r.json().get("detail") if "application/json" in r.headers.get("content-type", "") else r.text)
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