"""
Página Streamlit — Dashboard de Projetos (TI)

Seções:
- Imports e helpers visuais
- Configuração base da página + CSS
- Sessão/Permissões (gate de acesso)
- Funções de API (com cache curto)
- Helpers de formatação/KPI
- Seletores (Projeto/Sprint) e carga de dados
- Cabeçalho do Status Report (cards)
- Abas: Resumo, KPIs (inclui donut e tendência), Metas (milestones)
"""

# ======================================================================================
# Imports e helpers visuais
# ======================================================================================
import streamlit as st
import pandas as pd
import altair as alt
import re
import html

# === Navegação/Segurança unificadas ===
from ui_nav import (
    garantir_sessao_e_permissoes,
    render_menu_lateral,
    _buscar_me_perfil,
    req_get,  # wrappers com refresh automático
)

# ---------------------- Helpers visuais ----------------------
# Notas: _field evita if/else para dict/objeto. 
# render_metric_card gera um pequeno cartão HTML seguro (escapa textos) para métricas do cabeçalho.
def _field(obj, name: str):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def render_metric_card(icon, label, value, tag_html=None):
    value_display = f'<div class="metric-card-value">{html.escape(str(value))}</div>' if not tag_html else tag_html
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-card-label">
                <span class="metric-card-icon">{icon}</span>
                {html.escape(str(label))}
            </div>
            {value_display}
        </div>
        """,
        unsafe_allow_html=True,
    )

# ======================================================================================
# Configuração base da página + CSS
# ======================================================================================
st.set_page_config(
    page_title="Dashboard de Projetos (TI)",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Oculta navegação nativa (estético)
st.markdown("<style>[data-testid='stSidebarNav']{display:none!important}</style>", unsafe_allow_html=True)

# ---------------------- CSS (unificado e limpo) ----------------------
st.markdown(
    """
    <style>
    :root{
      --slate-900:#0F172A; --slate-700:#334155; --slate-600:#475569; --slate-500:#64748B; --slate-400:#94A3B8;
      --border: rgba(148,163,184,.18);
      --shadow-1: 0 1px 1px rgba(0,0,0,.04), 0 6px 18px rgba(2,6,23,.06);
    }

    /* ===== Cards/KPIs ===== */
    .metric-card{ background:#fff; border-radius:12px; padding:16px; height:100px; box-shadow:0 2px 4px rgba(0,0,0,.02); }
    .metric-card-label{ font-size:13px; color:#555; margin-bottom:8px; display:flex; align-items:center; }
    .metric-card-icon{ margin-right:8px; font-size:18px; }
    .metric-card-value{ font-size:16px; font-weight:600; color:#111; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

    .status-tag-green{ display:inline-block; background:#e7f7ec; color:#006421; padding:4px 10px; border-radius:6px; font-weight:600; font-size:14px; }
    .status-tag-yellow{ display:inline-block; background:#fff7e6; color:#b98100; padding:4px 10px; border-radius:6px; font-weight:600; font-size:14px; }
    .status-tag-red{ display:inline-block; background:#ffecec; color:#a40000; padding:4px 10px; border-radius:6px; font-weight:600; font-size:14px; }
    .status-tag-blue{ display:inline-block; background:#f0f5ff; color:#0044cc; padding:4px 10px; border-radius:6px; font-weight:600; font-size:14px; }
    .status-tag-grey{ display:inline-block; background:#f1f5f9; color:#334155; padding:4px 10px; border-radius:6px; font-weight:600; font-size:14px; }

    .kpi-card{ background:#fff; border-radius:14px; padding:22px; box-shadow:var(--shadow-1); border:1px solid var(--border); min-height:110px; display:flex; flex-direction:column; gap:6px; }
    .kpi-card .label{ color:var(--slate-600); font-size:13px; margin-bottom:2px; }
    .kpi-card .value{ color:var(--slate-900); font-size:clamp(20px,2.2vw,28px); font-weight:800; line-height:1.15; }
    .kpi-card .sub{ color:var(--slate-600); font-size:clamp(11px,1.1vw,12px); margin-top:2px; line-height:1.25; }

    .kpi-list-card{ border:1px solid var(--border); border-radius:12px; padding:16px; margin-bottom:12px; background:#fff; text-align:center; height:90px; box-shadow:0 1px 1px rgba(0,0,0,.02); }
    .kpi-section-title{ color:var(--slate-900); font-size:16px; font-weight:700; margin:22px 0 14px; }

    /* ===== Donut ===== */
    .donut-wrap{ position:relative; width:360px; max-width:100%; aspect-ratio:1/1; margin:0 auto; }
    .donut-ring{
      --thick: 3px;
      width:100%; height:100%; border-radius:50%;
      background:
        conic-gradient(from -90deg, transparent 0deg var(--ang), #E9EEF5 var(--ang) 360deg),
        conic-gradient(from -90deg, #F87171 0deg, #FB923C 60deg, #FBBF24 120deg, #A3E635 200deg, #22C55E 360deg);
      -webkit-mask:radial-gradient(farthest-side, transparent calc(50% - var(--thick)), #000 calc(50% - var(--thick)));
              mask:radial-gradient(farthest-side, transparent calc(50% - var(--thick)), #000 calc(50% - var(--thick)));
      box-shadow:0 1px 1px rgba(0,0,0,.04), 0 6px 18px rgba(2,6,23,.06) inset;
    }
    .donut-center{ position:absolute; inset:0; display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; pointer-events:none; }
    .donut-center .big{ font-weight:800; color:var(--slate-900); font-size:clamp(18px,3.2vw,26px); line-height:1.1; }
    .donut-center .small{ margin-top:4px; font-size:clamp(11px,1.2vw,12px); color:#6B7280; }

    /* ===== Tabela de milestones ===== */
    .milestone-table{ width:100%; border-collapse:collapse; font-size:14px; margin-top:16px; }
    .milestone-table th, .milestone-table td{ padding:12px 8px; border-bottom:1px solid #e5e7eb; text-align:left; vertical-align:middle; }
    .milestone-table th{ color:#4b5563; font-weight:600; background:#f9fafb; }
    .milestone-table tr:last-child td{ border-bottom:none; }
    .milestone-table .col-hash{ width:3%; } .milestone-table .col-desc{ width:37%; }
    .milestone-table .col-status{ width:15%; } .milestone-table .col-data-p{ width:20%; } .milestone-table .col-data-r{ width:25%; }

    /* ===== Abas ===== */
    .tab-card{ border-radius:12px; padding:24px; height:350px; border:1px solid #e0e0e0; overflow-y:auto; }
    .tab-card h3{ margin:0 0 16px; font-size:1.25rem; color:#111; }
    .tab-card .card-content{ font-size:1rem; color:#333; line-height:1.6; white-space:pre-wrap; }
    .tab-card-blue{ background:#f0f5ff; } .tab-card-green{ background:#f0fdf4; } .tab-card-purple{ background:#f9f5ff; }

    /* ===== Filtros (wrapper simples, sem "barras" arredondadas) ===== */
    .filters-wrap{ margin:8px 0 6px; }

    /* ===== Selectbox: estilo + centralização vertical ===== */
    .stApp [data-testid="stSelectbox"]{ margin-bottom:8px; }

    /* Cápsula do select */
    .stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div{
      background:#f8fafc;
      border:1px solid rgba(148,163,184,.35);
      border-radius:12px;
      min-height:44px;
      box-shadow:0 1px 0 rgba(2,6,23,.04) inset, 0 1px 2px rgba(2,6,23,.06);
      transition:border-color .15s ease, box-shadow .15s ease, background .15s ease;
    }
    .stApp [data-testid="stSelectbox"] [data-baseweb="select"]:hover > div{ border-color:#94A3B8; }
    .stApp [data-testid="stSelectbox"] [data-baseweb="select"]:focus-within > div{
      border-color:#4F46E5;
      box-shadow:0 0 0 3px rgba(79,70,229,.14);
      background:#fff;
    }

    /* Centralização vertical garantida */
    .stApp [data-testid="stSelectbox"] [data-baseweb="select"] div[role="combobox"]{
      display:flex;
      align-items:center;
      gap:.5rem;
      padding:0 12px;
      min-height:44px;
      line-height:44px;
    }
    .stApp [data-testid="stSelectbox"] [data-baseweb="select"] input{
      height:44px;
      line-height:44px;
      padding:0 6px;
    }
    /* Ícone seta */
    .stApp [data-baseweb="select"] svg{ opacity:.6; transition:opacity .15s ease; }
    .stApp [data-baseweb="select"]:hover svg{ opacity:.9; }

    /* Dropdown */
    .stApp div[data-baseweb="menu"]{
      border:1px solid rgba(148,163,184,.35) !important;
      box-shadow:0 12px 30px rgba(2,6,23,.12) !important;
      border-radius:12px !important;
      overflow:hidden;
    }
    .stApp div[data-baseweb="menu"] li[role="option"]{
      padding:10px 12px !important;
      font-size:14px !important;
      line-height:1.2 !important;
    }
    .stApp div[data-baseweb="menu"] li[role="option"][aria-selected="true"]{
      font-weight:700;
      background:#EEF2FF !important;
    }
    .stApp div[data-baseweb="menu"] li[role="option"]:hover{
      background:#EEF2FF !important;
    }

    /* Variantes de tamanho (se quiser usar) */
    .sel.sel--sm [data-baseweb="select"] > div{ min-height:38px; }
    .sel.sel--sm [data-baseweb="select"] div[role="combobox"]{ min-height:38px; line-height:38px; }
    .sel.sel--sm [data-baseweb="select"] input{ height:38px; line-height:38px; }
    .sel.sel--xs [data-baseweb="select"] > div{ min-height:34px; border-radius:10px; }
    .sel.sel--xs [data-baseweb="select"] div[role="combobox"]{ min-height:34px; line-height:34px; }
    .sel.sel--xs [data-baseweb="select"] input{ height:34px; line-height:34px; }
    .sel.sel--pill [data-baseweb="select"] > div{ border-radius:9999px; }

    </style>
    """,
    unsafe_allow_html=True,
)

# ======================================================================================
# Sessão/Permissões (gate de acesso)
# ======================================================================================
perms = garantir_sessao_e_permissoes()
perms_lower = {p.lower() for p in perms}

me = _buscar_me_perfil() or {}

# Normaliza o setor para string maiúscula; aceita Enums/dicts vindos do backend
setor_raw = me.get("setor")
setor_val = getattr(setor_raw, "value", setor_raw)  # Enum → .value ; string permanece
if isinstance(setor_val, dict) and "value" in setor_val:
    setor_val = setor_val["value"]
setor_norm = str(setor_val or "").strip().upper()

# Gate: admin pode ver; senão, exige setor TI
is_admin = (
    "view_pagina_admin_usuarios" in perms_lower
    or {"gerenciar_usuarios", "gerenciar_papeis"}.issubset(perms_lower)
)

if not (is_admin or setor_norm == "TI"):
    st.warning("Este dashboard é exclusivo para o setor de TI.")
    st.stop()

render_menu_lateral(perms, current_page="dash_ti")

if "view_pagina_dashboards" not in perms:
    st.error("Página não encontrada ou não disponível para seu perfil.")
    st.stop()

# ======================================================================================
# Funções de API (com cache curto)
# ======================================================================================
# Observações:
# - TTLs pequenos favorecem responsividade sem martelar a API a cada rerun.
# - Tratamento explícito de 401/403 evita ruído para usuários sem acesso.

def buscar_lista_projetos(eh_admin_flag: bool):
    path = "/projetos/lista/" if eh_admin_flag else "/me/projetos/visiveis"
    r = req_get(path)
    if r.status_code == 200: return r.json() or []
    if r.status_code in (401, 403): return []
    return []


@st.cache_data(ttl=15)
def buscar_lista_sprints(codigo_projeto: str):
    if not codigo_projeto: return []
    try:
        r = req_get(f"/projeto/{codigo_projeto}/lista-sprints/")
        if r.status_code == 200: return r.json()
        if r.status_code in (401, 403):
            st.warning("Você não tem permissão para ver os sprints deste projeto.")
            return []
    except Exception:
        return None
    return []


@st.cache_data(ttl=15)
def buscar_detalhe_relatorio(id_relatorio: int):
    if not id_relatorio: return None
    try:
        r = req_get(f"/relatorio/detalhe/{id_relatorio}")
        if r.status_code == 200: return r.json()
        if r.status_code in (401, 403):
            st.error("Você não tem permissão para ver os detalhes deste relatório.")
            return None
    except Exception:
        return None
    return None


@st.cache_data(ttl=20)
def buscar_historico_kpi(codigo_projeto: str, nome_kpi: str):
    if not codigo_projeto or not nome_kpi: return []
    try:
        r = req_get(f"/projeto/{codigo_projeto}/historico-kpi/{nome_kpi}")
        if r.status_code == 200: return r.json()
        if r.status_code in (401, 403):
            st.warning("Você não tem permissão para ver o histórico desse KPI.")
            return []
    except Exception:
        return None
    return []

# ======================================================================================
# Helpers de formatação/KPI
# ======================================================================================
# Observações:
# - _to_float aceita textos com separadores PT-BR.
# - pegar_kpi/valor_kpi agilizam a leitura nos blocos de UI.
# - get_status_tag_html padroniza cores/semântica dos status.

def _to_float(x):
    if x is None: return None
    if isinstance(x, (int, float)): return float(x)
    if isinstance(x, str):
        s = re.sub(r"[^\d,.-]", "", x.strip()).replace(".", "").replace(",", ".")
        try: return float(s)
        except: return None
    return None


def pegar_kpi(kpis, nomes):
    if isinstance(nomes, str): nomes = [nomes]
    alvo = [n.lower() for n in nomes]
    for k in kpis or []:
        nome = (k.get("nome_kpi") or "").lower().strip()
        if nome in alvo: return k
    for k in kpis or []:
        nome = (k.get("nome_kpi") or "").lower()
        if any(n in nome for n in alvo): return k
    return None


def valor_kpi(kpi):
    if not kpi: return None, None
    vn = kpi.get("valor_numerico_kpi")
    vt = kpi.get("valor_texto_kpi")
    num = _to_float(vn if vn is not None else vt)
    return num, vt


def fmt_eur(v):
    if v is None: return "—"
    s = f"{v:,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} €"


def fmt_eur_compacto(v):
    if v is None: return "—"
    if v >= 1_000_000: return "€" + f"{v/1_000_000:.1f}".replace(".", ",") + "M"
    if v >= 1_000: return "€" + f"{v/1_000:.0f}".replace(".", ",") + "k"
    return "€" + f"{v:.0f}".replace(".", ",")


def get_status_tag_html(status):
    if status is None: status = "Pendente"
    status_safe = html.escape(str(status))
    s = str(status).lower().strip()
    if s == "concluído": return f'<span class="status-tag-green">{status_safe}</span>'
    if s == "atrasado": return f'<span class="status-tag-red">{status_safe}</span>'
    if s == "em risco": return f'<span class="status-tag-yellow">{status_safe}</span>'
    if s == "em andamento": return f'<span class="status-tag-yellow">{status_safe}</span>'
    if s == "planejado": return f'<span class="status-tag-blue">{status_safe}</span>'
    return f'<span class="status-tag-grey">{status_safe}</span>'


def formatar_data_br(valor):
    """Converte datas ISO/str para dd/mm/aaaa; mantém texto original se não parsear."""
    if not valor:
        return "—"
    try:
        dt = pd.to_datetime(str(valor), errors="coerce", utc=False)
        if pd.isna(dt):
            return html.escape(str(valor))
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return html.escape(str(valor))

# ======================================================================================
# Seletores (Projeto/Sprint) e carga de dados
# ======================================================================================
st.title("📑 Visão Detalhada e Histórica do Projeto (TI)")
st.markdown("Selecione um projeto e o sprint desejado para carregar o status report.")

lista_projetos = buscar_lista_projetos(is_admin)
if lista_projetos is None:
    st.error("🚨 **Erro de Conexão:** API do Back-end offline. O servidor `uvicorn` está rodando?")
    st.stop()
if not lista_projetos:
    st.warning("Nenhum projeto foi processado ainda ou você não gerencia nenhum.")
    st.stop()

mapa_projetos = {p.get("nome_projeto"): p.get("codigo_projeto") for p in lista_projetos}

# Wrapper simples sem “card” (somente estilo por classe CSS)
st.markdown('<div class="filters-wrap">', unsafe_allow_html=True)
col_sel1, col_sel2 = st.columns(2)

with col_sel1:
    # compacto + pílula (opcional)
    st.markdown('<div class="sel sel--sm sel--pill">', unsafe_allow_html=True)
    nome_selecionado = st.selectbox("Projeto", list(mapa_projetos.keys()), key="sel_proj_dash")
    st.markdown("</div>", unsafe_allow_html=True)

codigo_selecionado = mapa_projetos[nome_selecionado]

# Sprint depende do projeto selecionado
lista_sprints = buscar_lista_sprints(codigo_selecionado)
if not lista_sprints:
    st.markdown('</div>', unsafe_allow_html=True)  # fecha .filters-wrap
    st.warning(f"O projeto **{nome_selecionado}** não possui nenhum relatório de sprint processado.")
    st.stop()

mapa_sprints = {
    f"Sprint {s['numero_sprint']} (ID Relatório: {s['id_relatorio']})": s['id_relatorio']
    for s in lista_sprints
}

with col_sel2:
    # tamanho padrão (ou troque para sel--xs/sel--sm)
    st.markdown('<div class="sel">', unsafe_allow_html=True)
    nome_sprint_selecionado = st.selectbox("Sprint", list(mapa_sprints.keys()), key="sel_sprint_dash")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)  # fecha .filters-wrap

id_relatorio_selecionado = mapa_sprints[nome_sprint_selecionado]

with st.spinner(f"Carregando dados do '{nome_selecionado}'..."):
    dados_api = buscar_detalhe_relatorio(id_relatorio_selecionado)

if not dados_api:
    st.error("Não foi possível carregar os detalhes deste relatório.")
    st.stop()

# ======================================================================================
# Cabeçalho do Status Report (cards)
# ======================================================================================
detalhe_relatorio = dados_api.get("detalhe_relatorio", {}) or {}
milestones = dados_api.get("milestones", []) or []
kpis = dados_api.get("kpis", []) or []

projeto_nome = detalhe_relatorio.get("nome_projeto", "N/A")
data_relatorio_str = formatar_data_br(detalhe_relatorio.get("data_relatorio"))
responsavel = detalhe_relatorio.get("gerente_projeto", "N/A")
codigo_proj = detalhe_relatorio.get("codigo_projeto", "N/A")
sprint_num = f"Sprint {detalhe_relatorio.get('numero_sprint', 0)}"
status_geral = detalhe_relatorio.get("status_geral", "N/A")
departamento = detalhe_relatorio.get("departamento")
prioridade = detalhe_relatorio.get("prioridade")

# Tag de status com cor semântica
a = status_geral
if a in ("Em Dia", "Em Andamento"):
    status_html = f'<span class="status-tag-green">{html.escape(a)}</span>'
elif a == "Em Risco":
    status_html = f'<span class="status-tag-yellow">{html.escape(a)}</span>'
elif a == "Atrasado":
    status_html = f'<span class="status-tag-red">{html.escape(a)}</span>'
else:
    status_html = f'<div class="metric-card-value">{html.escape(str(a))}</div>'

with st.container():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(
            f"""
            <h2 style="margin:0">Status Report</h2>
            <span style="font-size:1.1rem; color:#0044cc; font-weight:500;">{html.escape(projeto_nome)}</span>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div style="text-align:right; color:#555; font-size:.9rem;">
                Atualizado em<br>
                <span style="font-weight:600;">{html.escape(data_relatorio_str)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div style="margin-top:20px;"></div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1: render_metric_card("🧑‍💼", "Responsável", responsavel)
    with c2: render_metric_card("#️⃣", "Código do Projeto", codigo_proj)
    with c3: render_metric_card("🔄", "Sprint Atual", sprint_num)
    with c4: render_metric_card("📊", "Status do Projeto", "", tag_html=status_html)

    if departamento or prioridade:
        st.markdown('<div style="margin-top:16px;"></div>', unsafe_allow_html=True)
        c5, c6, _, _ = st.columns(4)
        if departamento:
            with c5: render_metric_card("🏢", "Departamento", departamento)
        if prioridade:
            if prioridade == "Alta":
                pr_tag = f'<span class="status-tag-red">{html.escape(prioridade)}</span>'
            elif prioridade == "Média":
                pr_tag = f'<span class="status-tag-yellow">{html.escape(prioridade)}</span>'
            else:
                pr_tag = f'<div class="metric-card-value">{html.escape(str(prioridade))}</div>'
            with c6: render_metric_card("🔥", "Prioridade", "", tag_html=pr_tag)

# ======================================================================================
# Abas: Resumo, KPIs (donut/tendência), Metas (milestones)
# ======================================================================================
tab_contexto, tab_kpis, tab_metas = st.tabs(["🤖 Resumo Executivo", "📊 Métricas Chave (KPIs)", "📅 Acompanhamento de Metas"])

# --- CONTEXTO ---
with tab_contexto:
    resumo = _field(detalhe_relatorio, "resumo_executivo") or "—"
    riscos  = _field(detalhe_relatorio, "riscos_e_impedimentos") or "—"
    passos  = _field(detalhe_relatorio, "proximos_passos") or "—"

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown(f'<div class="tab-card tab-card-blue"><h3>🤖 Sumário Executivo</h3><div class="card-content">{resumo}</div></div>', unsafe_allow_html=True)
    with col_b:
        st.markdown(f'<div class="tab-card tab-card-green"><h3>🛡️ Riscos e Impedimentos</h3><div class="card-content">{riscos}</div></div>', unsafe_allow_html=True)
    with col_c:
        st.markdown(f'<div class="tab-card tab-card-purple"><h3>🎯 Próximos Passos</h3><div class="card-content">{passos}</div></div>', unsafe_allow_html=True)

# --- KPIs ---
with tab_kpis:
    st.subheader("📊 Métricas Chave (KPIs) do Período")

    kpi_orc   = pegar_kpi(kpis, ["orçamento total", "orcamento total"])
    kpi_custo = pegar_kpi(kpis, ["custo realizado", "custo acumulado"])

    orc_num, _ = valor_kpi(kpi_orc)
    custo_num, _ = valor_kpi(kpi_custo)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f'<div class="kpi-card"><div class="label">Orçamento Total</div><div class="value">{fmt_eur(orc_num)}</div><div class="sub">Valor total alocado para o projeto</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        sub = "—"
        if orc_num and custo_num is not None:
            try: sub = f"{(custo_num / orc_num):.0%} do orçamento já foi utilizado até a data atual".replace(".", ",")
            except ZeroDivisionError: sub = "0% do orçamento utilizado"
        st.markdown(
            f'<div class="kpi-card"><div class="label">Custo Realizado</div><div class="value">{fmt_eur(custo_num)}</div><div class="sub">{sub}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="kpi-section-title">Utilização do Orçamento Total (se aplicável)</div>', unsafe_allow_html=True)

    if orc_num and custo_num is not None:
        util_pct = max(0, min(custo_num / orc_num, 1.0))
        ang = util_pct * 360
        centro_grande  = fmt_eur_compacto(custo_num)
        centro_pequeno = f"{fmt_eur(custo_num).replace(' €','')} / {fmt_eur(orc_num).replace(' €','')}"
        thick_px = -35

        st.markdown(
            f"""
            <div class="donut-wrap">
              <div class="donut-ring" style="--ang:{ang}deg; --thick:{thick_px}px;"></div>
              <div class="donut-center">
                <div class="big">{centro_grande}</div>
                <div class="small">{centro_pequeno}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.info("Ainda não há dados suficientes de Orçamento/Custo para montar o donut.")

    # Outros KPIs (exibe restantes em cards compactos)
    if kpis:
        _ignorar = {"orçamento total", "orcamento total", "custo realizado", "custo acumulado"}
        outros = [k for k in kpis if (k.get("nome_kpi") or "").lower().strip() not in _ignorar]
        if outros:
            num_cols = min(len(outros), 4)
            cols = st.columns(num_cols)
            for i, kpi in enumerate(outros):
                valor_display = kpi.get("valor_texto_kpi") or (
                    f"{kpi.get('valor_numerico_kpi', 0):,.2f}".replace(",", " ").replace(".", ",")
                    if kpi.get("valor_numerico_kpi") is not None else "—"
                )
                with cols[i % num_cols]:
                    st.markdown(
                        f"""
                        <div class="kpi-list-card">
                            <div style="font-size:13px;color:#666">{html.escape(kpi.get('nome_kpi','N/A'))}</div>
                            <div style="font-size:22px;font-weight:600;margin-top:6px">{html.escape(str(valor_display))}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    st.divider()
    st.subheader("📈 Análise de Tendência (Burn Rate)")

    historico_data = buscar_historico_kpi(codigo_selecionado, "Custo Realizado")
    if historico_data and len(historico_data) > 1:
        try:
            df_hist = pd.DataFrame(historico_data).rename(
                columns={"sprint_number":"Sprint","cost_realized":"Custo Acumulado","budget_total":"Orçamento Total (Teto)"}
            )
            df_melted = df_hist.melt("Sprint", var_name="Métrica", value_name="Valor (€)")
            base = (
                alt.Chart(df_melted)
                .mark_line(point=True)
                .encode(
                    x=alt.X("Sprint:O", title="Sprint"),
                    y=alt.Y("Valor (€):Q", title="Valor (€)"),
                    color=alt.Color("Métrica", scale=alt.Scale(domain=["Custo Acumulado","Orçamento Total (Teto)"], range=["#FFA500","#1C83E1"])),
                    tooltip=["Sprint","Métrica","Valor (€)"],
                )
                .interactive()
            )
            st.altair_chart(base, use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao renderizar gráfico de tendência: {e}")
    elif historico_data and len(historico_data) == 1:
        st.info("O gráfico de tendência aparecerá assim que você enviar o próximo relatório de Sprint.")
    else:
        st.warning("Não há dados históricos suficientes (KPI 'Custo Realizado') para gerar tendência.")

# --- METAS (Milestones) ---
with tab_metas:
    if not milestones:
        st.info("Nenhum milestone foi extraído para este relatório de sprint.")
    else:
        df_milestones = pd.DataFrame(milestones)

        # --- Normalização de colunas vindas do backend (aliases) ---
        def _pick(df, *cands):
            """Retorna o primeiro nome de coluna existente em df dentre os candidatos."""
            for c in cands:
                if c in df.columns:
                    return c
            return None

        rename_map = {}

        c = _pick(df_milestones, "descricao", "descricao_milestone", "milestone", "nome")
        if c and c != "descricao": rename_map[c] = "descricao"

        c = _pick(df_milestones, "status", "situacao")
        if c and c != "status": rename_map[c] = "status"

        c = _pick(df_milestones, "data_planejada", "data_prevista", "data_plano")
        if c and c != "data_planejada": rename_map[c] = "data_planejada"

        # >>> inclui o seu campo do BD: data_real_ou_revisada
        c = _pick(df_milestones, "data_real_revisada", "data_real_ou_revisada", "data_real", "data_revisada")
        if c and c != "data_real_revisada": rename_map[c] = "data_real_revisada"

        if rename_map:
            df_milestones = df_milestones.rename(columns=rename_map)

        st.subheader("Resumo Visual do Status")

        if "status" in df_milestones.columns:
            status_counts = df_milestones["status"].fillna("Pendente").value_counts().reset_index()
            status_counts.columns = ["status","count"]

            domain_status = ["Concluído","Em Andamento","Em Risco","Atrasado","Planejado","Pendente"]
            range_colors  = ["#A3E635","#BCEBAD","#FB923C","#F87171","#60A5FA","#9CA3AF"]
            color_scale   = alt.Scale(domain=domain_status, range=range_colors)

            col_chart, col_legend = st.columns([1,1], gap="large")
            with col_chart:
                base = alt.Chart(status_counts).encode(theta=alt.Theta("count:Q", stack=True)).properties(title="Distribuição de Status dos Milestones")
                donut = base.mark_arc(outerRadius=100, innerRadius=70).encode(
                    color=alt.Color("status:N", scale=color_scale, legend=None),
                    order=alt.Order("count:Q", sort="descending"),
                    tooltip=[
                    alt.Tooltip("status:N", title="Status: "),
                    alt.Tooltip("count:Q", title="Quantidade: "),
                    ],
                )
                st.altair_chart(donut, use_container_width=True)

            with col_legend:
                st.markdown('<div style="margin-top:35px;"></div>', unsafe_allow_html=True)
                color_map = dict(zip(domain_status, range_colors))
                for s in domain_status:
                    row = status_counts[status_counts["status"] == s]
                    count = int(row.iloc[0]["count"]) if not row.empty else 0
                    if count > 0 or s in ["Concluído","Em Andamento","Planejado"]:
                        st.markdown(
                            f'<div style="display:flex;align-items:center;margin-bottom:8px;font-size:14px;"><div style="width:12px;height:12px;background:{color_map.get(s,"#9CA3AF")};border-radius:50%;margin-right:10px;flex-shrink:0;"></div><span>{html.escape(s)} ({count} itens)</span></div>',
                            unsafe_allow_html=True,
                        )

        st.divider()
        st.markdown(f"#### 📅 Acompanhamento de Milestones (Sprint {detalhe_relatorio.get('numero_sprint', 0)})", unsafe_allow_html=True)

        # Garante colunas esperadas
        df_display = df_milestones.copy()
        df_display["#"] = range(1, len(df_display) + 1)
        for col in ["descricao","status","data_planejada","data_real_revisada"]:
            if col not in df_display.columns:
                df_display[col] = "—"

        # --- Construção segura do HTML + datas no padrão BR ---
        rows_html = []
        for _, row in df_display.iterrows():
            def esc(v, placeholder="—"):
                if v is None or (isinstance(v, float) and pd.isna(v)): return placeholder
                return html.escape(str(v))

            status_tag = get_status_tag_html(row["status"])
            rows_html.append(
                f"<tr>"
                f"<td>{esc(row['#'])}</td>"
                f"<td>{esc(row['descricao'])}</td>"
                f"<td>{status_tag}</td>"
                f"<td>{formatar_data_br(row['data_planejada'])}</td>"
                f"<td>{formatar_data_br(row['data_real_revisada'])}</td>"
                f"</tr>"
            )

        table_html = (
            '<table class="milestone-table">'
            "<thead><tr>"
            '<th class="col-hash">#</th>'
            '<th class="col-desc">Descrição</th>'
            '<th class="col-status">Status</th>'
            '<th class="col-data-p">Data Planejada</th>'
            '<th class="col-data-r">Data Real/Revisada</th>'
            "</tr></thead>"
            "<tbody>"
            + "".join(rows_html) +
            "</tbody></table>"
        )

        st.markdown(table_html, unsafe_allow_html=True)