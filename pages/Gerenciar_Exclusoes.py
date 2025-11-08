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
"""

# ======================================================================================
# Imports e setup visual
# ======================================================================================
import streamlit as st
from collections import Counter
from datetime import datetime
from ui_nav import garantir_sessao_e_permissoes, render_menu_lateral, req_get, req_post, req_delete

from pathlib import Path
from base64 import b64encode

# ======================================================================================
# Utilitários de imagem (robustos)
# ======================================================================================
def _load_image_b64(filename: str) -> str | None:
    here = Path(__file__).resolve().parent
    candidates = [
        here / "images" / filename,
        Path.cwd() / "pages" / "images" / filename,
        here / filename,
    ]
    for p in candidates:
        if p.exists():
            try:
                return b64encode(p.read_bytes()).decode()
            except Exception:
                pass
    return None

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

_icon_b64 = _load_image_b64("remove.png")
st.markdown(
    f"""
<div style="display:flex;align-items:center;gap:8px;">
  {'<img src="data:image/png;base64,' + _icon_b64 + '" alt="Remove icon" style="width:48px;height:48px;object-fit:contain;border-radius:4px;" />' if _icon_b64 else '🗑️'}
  <h1 style="margin:0;">Gerenciar Exclusões</h1>
</div>
""",
    unsafe_allow_html=True,
)

st.caption("Gerencie projetos marcados com Soft Delete. Você pode restaurá-los ou excluí-los permanentemente.")

# ======================================================================================
# Gate de sessão/permissão (early-exit)
# ======================================================================================
perms = garantir_sessao_e_permissoes()
render_menu_lateral(perms, current_page="admin_exclusoes")
perms_lower = {p.lower() for p in (perms or [])}
if not ( {"gerenciar_usuarios", "gerenciar_papeis", "excluir_relatorio"} & perms_lower
         or "view_pagina_admin_exclusoes" in perms_lower ):
    st.warning("Página não disponível para seu perfil.")
    st.stop()

# Domínio de setores
SETORES = ["Retalho", "TI", "Marketing", "RH"]

# ======================================================================================
# Helpers locais
# ======================================================================================
def _formatar_data(iso_or_none: str | None) -> str:
    if not iso_or_none:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_or_none.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso_or_none

@st.cache_data(ttl=10)
def carregar_deletados():
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
# KPIs rápidos
# ======================================================================================
_total = len(data)
_by_setor = Counter([d.get("area_negocio") or "—" for d in data])

tot_ti          = _by_setor.get("TI", 0)
tot_retalho     = _by_setor.get("Retalho", 0)
tot_marketing   = _by_setor.get("Marketing", 0)
tot_rh          = _by_setor.get("RH", 0)

st.markdown(f"""
<div class="kpi-card">
  <div class="kpi-grid">
    <div class="kpi-item" style="--accent:#F59E0B">
      <div class="kpi-copy">
        <div class="kpi-label">Total de Exclusões</div>
        <div class="kpi-value">{_total}</div>
      </div>
      <span class="kpi-icon">📄</span>
    </div>
    <div class="kpi-item" style="--accent:#10B981">
      <div class="kpi-copy">
        <div class="kpi-label">Exclusões TI</div>
        <div class="kpi-value">{tot_ti}</div>
      </div>
      <span class="kpi-icon">🖥️</span>
    </div>
    <div class="kpi-item" style="--accent:#F59E0B">
      <div class="kpi-copy">
        <div class="kpi-label">Exclusões Retalho</div>
        <div class="kpi-value">{tot_retalho}</div>
      </div>
      <span class="kpi-icon">🛒</span>
    </div>
    <div class="kpi-item" style="--accent:#3B82F6">
      <div class="kpi-copy">
        <div class="kpi-label">Exclusões Marketing</div>
        <div class="kpi-value">{tot_marketing}</div>
      </div>
      <span class="kpi-icon">📊</span>
    </div>
    <div class="kpi-item" style="--accent:#8B5CF6">
      <div class="kpi-copy">
        <div class="kpi-label">Exclusões RH</div>
        <div class="kpi-value">{tot_rh}</div>
      </div>
      <span class="kpi-icon">👤</span>
    </div>
  </div>
</div>

<style>
.kpi-card{
  background:#FFFFFF; border:1px solid #E2E8F0; border-radius:16px;
  padding:12px 14px; margin-bottom:12px;
}
.kpi-grid{
  display:grid; grid-template-columns:repeat(5, 1fr); gap:0;
}
.kpi-item{
  position:relative; display:flex; align-items:center; justify-content:space-between;
  padding:12px 16px; border-right:1px solid #E5E7EB;
}
.kpi-item:last-child{ border-right:none; }
.kpi-item::before{
  content:""; position:absolute; left:8px; top:10px; bottom:10px; width:4px;
  background:var(--accent); border-radius:4px;
}
.kpi-copy{ padding-left:12px; }
.kpi-label{ font-size:.9rem; color:#475569; margin-bottom:4px; }
.kpi-value{ font-weight:700; font-size:1.25rem; color:var(--accent); }
.kpi-icon{ opacity:.9; font-size:1.15rem; }

@media (max-width: 1100px){
  .kpi-grid{ grid-template-columns:repeat(2,1fr); }
  .kpi-item{ border-right:none; border-bottom:1px solid #E5E7EB; }
  .kpi-item:last-child{ border-bottom:none; }
}
</style>
""", unsafe_allow_html=True)

# ======================================================================================
# Filtros (texto e setor) + ação de atualizar
# ======================================================================================
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

# ======================================================================================
# Atividade recente
# ======================================================================================
st.subheader("Atividade Recente")

last = sorted(data, key=lambda d: d.get("deletado_em") or "", reverse=True)
last_txt = f"{last[0]['nome_projeto']} ({last[0]['codigo_projeto']}) em {_formatar_data(last[0].get('deletado_em'))}" if last else "—"

mais_ativo = "—"
if data:
    c = Counter([d.get("deletado_por_nome") or "—" for d in data])
    mais_ativo = f"{c.most_common(1)[0][0]}"

total_itens = len(data)

st.markdown(f"""
<div class="recent-card">
  <div class="recent-row">
    <div class="recent-label">Último projeto excluído</div>
    <div class="recent-value">{last_txt}</div>
  </div>
  <div class="recent-row">
    <div class="recent-label">Usuário mais ativo</div>
    <div class="recent-value">{mais_ativo}</div>
  </div>
  <div class="recent-row">
    <div class="recent-label">Total de itens nesta lista</div>
    <div class="recent-value">{total_itens}</div>
  </div>
</div>

<div class="note-card">
  A exclusão permanente remove definitivamente os dados do sistema. Verifique se realmente não serão necessários antes de prosseguir.
</div>

<style>
.recent-card {{
  background:#FFFFFF;
  border:1px solid #E2E8F0;
  border-radius:16px;
  padding:14px 16px;
  margin:8px 0 12px;
}}
.recent-row {{
  display:flex;
  align-items:flex-start;
  gap:10px;
  padding:8px 0;
  border-bottom:1px dashed #E5E7EB;
}}
.recent-row:last-of-type {{ border-bottom:none; }}
.recent-label {{
  min-width:220px;
  color:#475569;
  font-size:0.95rem;
}}
.recent-value {{
  color:#0F172A;
  font-weight:600;
}}
@media (max-width: 900px) {{
  .recent-label {{ min-width:160px; }}
}}
.note-card {{
  background:#FFFBEB;
  border:1px solid #F59E0B33;
  color:#92400E;
  border-radius:16px;
  padding:12px 14px;
  margin:8px 0 16px;
  font-size:0.93rem;
  line-height:1.35;
}}
</style>
""", unsafe_allow_html=True)
