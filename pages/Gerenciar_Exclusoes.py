"""
Página Streamlit — Gerenciar Exclusões (Soft Delete)

Seções:
- Imports e configuração visual da página
- Gate de permissões (apenas perfis autorizados visualizam)
- KPIs rápidos (contagem e por setor)
- Filtros (texto e setor) + botão Atualizar
- Ações por item (Restaurar / Excluir permanentemente)
- Lista de projetos excluídos
- Sumário de atividade recente

Destaques dos comentários:
- Por que o gate de permissões é feito antes de qualquer listagem
- Motivo de usar `@st.cache_data(ttl=10)` para a lista de excluídos
- Observações sobre `req_*` (wrappers de requisições) e tratamento de erros
"""

# ======================================================================================
# Imports e setup visual
# ======================================================================================
import streamlit as st
from collections import Counter
from datetime import datetime
from ui_nav import garantir_sessao_e_permissoes, render_menu_lateral, req_get, req_post, req_delete

# Config da página (título/ícone/layout) + CSS para esconder a nav padrão
st.set_page_config(page_title="Gerenciar Exclusões", page_icon="🗑️", layout="wide")
st.markdown(
    """
<style>
[data-testid="stSidebarNav"]{display:none!important}
button[kind="header"]{display:none!important}
</style>
""",
    unsafe_allow_html=True,
)

# ======================================================================================
# Gate de sessão/permissão (early‑exit)
# ======================================================================================
# - `garantir_sessao_e_permissoes()` retorna as permissões correntes do usuário.
# - `render_menu_lateral()` desenha o menu considerando a página atual.
# - Gate: só permite a página para quem possui pelo menos UMA das permissões listadas
#   (gerenciar usuários, gerenciar papéis, excluir relatório) OU a permissão específica
#   de acesso à página de exclusões do admin.
perms = garantir_sessao_e_permissoes()
render_menu_lateral(perms, current_page="admin_exclusoes")
perms_lower = {p.lower() for p in (perms or [])}
if not ( {"gerenciar_usuarios", "gerenciar_papeis", "excluir_relatorio"} & perms_lower
         or "view_pagina_admin_exclusoes" in perms_lower ):
    st.warning("Página não disponível para seu perfil.")
    st.stop()

st.title("🗑️ Gerenciar Exclusões")
st.caption("Gerencie projetos marcados com Soft Delete. Você pode restaurá-los ou excluí-los permanentemente.")

# Domínio de setores (usado em filtros e KPIs)
SETORES = ["Retalho", "TI", "Marketing", "RH"]

# ======================================================================================
# Helpers locais
# ======================================================================================

def _formatar_data(iso_or_none: str | None) -> str:
    """Converte ISO8601 (ou None) → dd/mm/aaaa HH:MM, com fallback seguro.
    Aceita também strings com sufixo "Z" (UTC).
    """
    if not iso_or_none:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_or_none.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso_or_none


@st.cache_data(ttl=10)
def carregar_deletados():
    """Busca a lista de projetos com `is_deletado=1` do endpoint admin.
    Cache com TTL curto (10s) evita chamadas repetidas ao navegar/filtrar.
    """
    r = req_get("/admin/projetos/excluidos")
    if r.status_code == 200:
        return r.json()
    raise RuntimeError(r.json().get("detail") if "application/json" in r.headers.get("content-type","") else r.text)


# ======================================================================================
# Carga inicial de dados (com tratamento de erro de rede/API)
# ======================================================================================
try:
    data = carregar_deletados()
except Exception as e:
    st.error(f"Falha ao carregar exclusões: {e}")
    st.stop()

# ======================================================================================
# KPIs rápidos (visão geral)
# ======================================================================================
from collections import Counter as _CounterAlias  # (só para deixar explícito o uso)
_total = len(data)
_by_setor = Counter([d.get("area_negocio") or "—" for d in data])
col0, col1, col2, col3, col4 = st.columns([1.2, 1, 1, 1, 1])
with col0: st.metric("Total de Exclusões", _total)
with col1: st.metric("Exclusões Marketing", _by_setor.get("Marketing", 0))
with col2: st.metric("Exclusões Retalho", _by_setor.get("Retalho", 0))
with col3: st.metric("Exclusões TI", _by_setor.get("TI", 0))
with col4: st.metric("Exclusões RH", _by_setor.get("RH", 0))

st.divider()

# ======================================================================================
# Filtros (texto e setor) + ação de atualizar (invalidar cache)
# ======================================================================================
# - O botão Atualizar limpa o cache de `carregar_deletados()` e força `rerun()`.
# - O filtro de texto confere tanto `codigo_projeto` quanto `nome_projeto` (case‑insensitive).
c1, c2, c3 = st.columns([2, 1.2, 0.8])
with c1:
    q = st.text_input("Buscar por código ou nome do projeto", placeholder="ex.: PROJ-001 ou Projeto X")
with c2:
    setor_sel = st.selectbox("Setor", ["Todos"] + SETORES, index=0)
with c3:
    st.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)
    if st.button("Atualizar", use_container_width=True):
        carregar_deletados.clear()
        st.rerun()


def filtros(item: dict) -> bool:
    """Aplica os filtros do select (setor) e do campo de busca."""
    if setor_sel != "Todos" and (item.get("area_negocio") or "") != setor_sel:
        return False
    if q:
        qn = q.strip().lower()
        if qn not in (item.get("codigo_projeto","" ).lower()) and qn not in (item.get("nome_projeto","" ).lower()):
            return False
    return True

items = [d for d in data if filtros(d)]
if not items:
    st.info("Nenhum projeto excluído encontrado para os filtros selecionados.")
    st.stop()

# ======================================================================================
# Ações (REST) — Restaurar e Excluir Permanentemente
# ======================================================================================
# Observação:
# - `req_post` e `req_delete` são wrappers que já incluem headers e lidam com sessão.
# - Após sucesso, limpamos o cache e chamamos `st.rerun()` para refletir o novo estado.

def restaurar(codigo: str, label: str):
    try:
        r = req_post(f"/admin/projetos/{codigo}/restaurar")
        if r.status_code == 200:
            st.toast(f"Projeto restaurado: {label}", icon="♻️")
            carregar_deletados.clear()
            st.rerun()
        else:
            st.error(r.json().get("detail") if "application/json" in r.headers.get("content-type","") else r.text)
    except Exception as e:
        st.error(f"Erro de rede: {e}")


def excluir_perm(codigo: str, label: str, motivo: str | None):
    try:
        r = req_delete(f"/admin/projetos/{codigo}", params={"permanente": "1", "motivo": (motivo or "")})
        if r.status_code == 200:
            st.toast(f"Excluído permanentemente: {label}", icon="🗑️")
            carregar_deletados.clear()
            st.rerun()
        else:
            st.error(r.json().get("detail") if "application/json" in r.headers.get("content-type","") else r.text)
    except Exception as e:
        st.error(f"Erro de rede: {e}")

# ======================================================================================
# Lista renderizada (cartões) com ações por item
# ======================================================================================
st.subheader("Relatórios Excluídos (Soft Delete)")
for item in items:
    cod   = item.get("codigo_projeto")
    nome  = item.get("nome_projeto") or cod
    setor = item.get("area_negocio") or "—"
    del_por = item.get("deletado_por_nome") or "—"
    del_em  = _formatar_data(item.get("deletado_em"))
    motivo  = (item.get("motivo_exclusao") or "").strip()
    header  = f"{nome}  ·  {cod}"

    with st.container(border=True):
        st.markdown(f"**{header}**")
        st.caption(f"🗂️ Setor: {setor}  •  🧑‍💼 Excluído por: {del_por}  •  🗓️ {del_em}")
        if motivo:
            st.write(f"**Motivo original:** {motivo}")

        cA, cB, _ = st.columns([0.22, 0.65, 2])
        with cA:
            if st.button("♻️ Restaurar", key=f"restaurar_{cod}", use_container_width=True):
                restaurar(cod, f"{nome} ({cod})")
        with cB:
            with st.popover(f"🗑️ Excluir Permanentemente — {cod}", use_container_width=True):
                st.write("Essa ação é irreversível. Informe um motivo e confirme.")
                motivo_conf = st.text_input("Motivo (opcional)", key=f"motivo_conf_{cod}")
                colx1, colx2 = st.columns([1, 1])
                with colx1:
                    if st.button("Cancelar", key=f"cancel_{cod}"):
                        st.rerun()
                with colx2:
                    if st.button("Excluir Definitivamente", type="primary", key=f"hard_{cod}"):
                        excluir_perm(cod, f"{nome} ({cod})", motivo_conf)

st.divider()

# ======================================================================================
# Atividade recente (pequeno sumário ao fim da página)
# ======================================================================================
st.subheader("Atividade Recente")

last = sorted(data, key=lambda d: d.get("deletado_em") or "", reverse=True)
last_txt = f"{last[0]['nome_projeto']} ({last[0]['codigo_projeto']}) em {_formatar_data(last[0].get('deletado_em'))}" if last else "—"

mais_ativo = "—"
if data:
    c = Counter([d.get("deletado_por_nome") or "—" for d in data])
    mais_ativo = f"{c.most_common(1)[0][0]}"

st.markdown(f"- **Último projeto excluído:** {last_txt}")
st.markdown(f"- **Usuário mais ativo:** {mais_ativo}")
st.markdown(f"- **Total de itens nesta lista:** {len(data)}")

st.info("A exclusão permanente remove definitivamente os dados do sistema. Verifique se realmente não serão necessários antes de prosseguir.")