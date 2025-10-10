# pages/3_Dashboard.py — Dashboard de Projetos (TI) com navegação unificada

import streamlit as st
import requests
import pandas as pd
import altair as alt
import plotly.graph_objects as go

# === Navegação/Segurança unificadas ===
from ui_nav import ensure_session_and_perms, render_sidebar, api_headers

# 1) Configuração da página (uma vez só)
st.set_page_config(
    page_title="📊 Dashboard de Projetos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2) Esconde a navegação nativa do Streamlit (para não mostrar todas as pages)
st.markdown(
    "<style>[data-testid='stSidebarNav']{display:none!important}</style>",
    unsafe_allow_html=True,
)

# 3) Checagem de sessão/permissões + menu unificado
perms = ensure_session_and_perms()          # redireciona pra Home se não logado/sem token
render_sidebar(perms, current_page="dash_projetos")

# 4) Gate de permissão desta página
if "view_pagina_dashboards" not in perms:
    st.error("Página não encontrada ou não disponível para seu perfil.")
    st.stop()

# ======================================================================
# A PARTIR DAQUI: LÓGICA ESPECÍFICA DO DASHBOARD (mantida da sua versão)
# ======================================================================

API_URL = "http://127.0.0.1:8000"
headers = api_headers()   # usa o Bearer salvo no login

# --- FUNÇÕES DE CHAMADA DA API (com autenticação) ---
@st.cache_data(ttl=60)
def buscar_lista_projetos():
    try:
        r = requests.get(f"{API_URL}/projetos/lista/", headers=headers, timeout=20)
        if r.status_code == 200:
            return r.json()
        elif r.status_code in (401, 403):
            st.warning("Você não tem permissão para listar os projetos.")
            return []
    except requests.ConnectionError:
        return None
    return []

@st.cache_data(ttl=15)
def buscar_lista_sprints(codigo_projeto: str):
    if not codigo_projeto:
        return []
    try:
        r = requests.get(
            f"{API_URL}/projeto/{codigo_projeto}/lista-sprints/",
            headers=headers,
            timeout=20,
        )
        if r.status_code == 200:
            return r.json()
        elif r.status_code in (401, 403):
            st.warning("Você não tem permissão para ver os sprints deste projeto.")
            return []
    except requests.ConnectionError:
        return None
    return []

@st.cache_data(ttl=15)
def buscar_detalhe_relatorio(id_relatorio: int):
    if not id_relatorio:
        return None
    try:
        r = requests.get(
            f"{API_URL}/relatorio/detalhe/{id_relatorio}",
            headers=headers,
            timeout=25,
        )
        if r.status_code == 200:
            return r.json()
        elif r.status_code in (401, 403):
            st.error("Você não tem permissão para ver os detalhes deste relatório.")
            return None
    except requests.ConnectionError:
        return None
    return None

@st.cache_data(ttl=20)
def buscar_historico_kpi(codigo_projeto: str, nome_kpi: str):
    if not codigo_projeto or not nome_kpi:
        return []
    try:
        r = requests.get(
            f"{API_URL}/projeto/{codigo_projeto}/historico-kpi/{nome_kpi}",
            headers=headers,
            timeout=20,
        )
        if r.status_code == 200:
            return r.json()
        elif r.status_code in (401, 403):
            st.warning("Você não tem permissão para ver o histórico desse KPI.")
            return []
    except requests.ConnectionError:
        return None
    return []

# --- Título e introdução ---
st.title("📑 Visão Detalhada e Histórica do Projeto (TI)")
st.markdown("Selecione um projeto e depois o sprint desejado para carregar o status report.")

# --- Seleção do Projeto ---
lista_projetos = buscar_lista_projetos()
if lista_projetos is None:
    st.error("🚨 **Erro de Conexão:** API do Back-end offline. O servidor `uvicorn` está rodando?")
    st.stop()
if not lista_projetos:
    st.warning("Nenhum projeto foi processado ainda. Envie relatórios na página **Processar Relatórios**.")
    st.stop()

mapa_projetos = {p["nome_projeto"]: p["codigo_projeto"] for p in lista_projetos}
nome_selecionado = st.selectbox("Selecione um Projeto:", options=list(mapa_projetos.keys()))
codigo_selecionado = mapa_projetos[nome_selecionado]

# --- Seleção do Sprint ---
lista_sprints = buscar_lista_sprints(codigo_selecionado)
if not lista_sprints:
    st.warning(f"O projeto **{nome_selecionado}** não possui nenhum relatório de sprint processado.")
    st.stop()

mapa_sprints = {
    f"Sprint {s['numero_sprint']} (ID Relatório: {s['id_relatorio']})": s['id_relatorio']
    for s in lista_sprints
}
nome_sprint_selecionado = st.selectbox("Selecione o Sprint (Histórico):", options=list(mapa_sprints.keys()))
id_relatorio_selecionado = mapa_sprints[nome_sprint_selecionado]

# --- Carregamento do detalhe do relatório ---
with st.spinner(f"Carregando dados do '{nome_selecionado}'..."):
    dados_api = buscar_detalhe_relatorio(id_relatorio_selecionado)

if not dados_api:
    st.error("Não foi possível carregar os detalhes deste relatório.")
    st.stop()

detalhe_relatorio = dados_api.get("detalhe_relatorio", {}) or {}
milestones = dados_api.get("milestones", []) or []
kpis = dados_api.get("kpis", []) or []

# --- Cabeçalho com status ---
col1, col2 = st.columns([4, 1])
with col1:
    st.header(f"Status Report: {detalhe_relatorio.get('nome_projeto', 'N/A')}")
with col2:
    status_atual = detalhe_relatorio.get("status_geral", "N/A")
    if status_atual == "Em Dia":
        st.markdown("<br><span style='padding:6px 10px;border-radius:8px;background:#e7f7ec'>✅ Em Dia</span>", unsafe_allow_html=True)
    elif status_atual == "Em Risco":
        st.markdown("<br><span style='padding:6px 10px;border-radius:8px;background:#fff7e6'>⚠️ Em Risco</span>", unsafe_allow_html=True)
    else:
        st.markdown(f"<br><span style='padding:6px 10px;border-radius:8px;background:#ffecec'>❌ {status_atual}</span>", unsafe_allow_html=True)

st.divider()

with st.container():
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Gerente", detalhe_relatorio.get("gerente_projeto", "N/A"))
    with c2:
        st.metric("Data do Relatório", str(detalhe_relatorio.get("data_relatorio", "N/A")))
    with c3:
        st.metric("Código do Projeto", detalhe_relatorio.get("codigo_projeto", "N/A"))
    with c4:
        st.metric("Sprint Selecionada", f"Sprint {detalhe_relatorio.get('numero_sprint', 0)}")

# --- Abas ---
tab_contexto, tab_kpis, tab_metas = st.tabs([
    "🤖 Sumário, Riscos e Próximos Passos",
    "📊 Métricas Chave (KPIs)",
    "📅 Acompanhamento de Metas"
])

with tab_contexto:
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        with st.container(border=True, height=350):
            st.subheader("🤖 Sumário Executivo")
            st.markdown(detalhe_relatorio.get("resumo_executivo", "N/A"), unsafe_allow_html=True)
    with col_b:
        with st.container(border=True, height=350):
            st.subheader("🛡️ Riscos e Impedimentos")
            st.markdown(detalhe_relatorio.get("riscos_e_impedimentos", "N/A"), unsafe_allow_html=True)
    with col_c:
        with st.container(border=True, height=350):
            st.subheader("🎯 Próximos Passos")
            st.markdown(detalhe_relatorio.get("proximos_passos", "N/A"), unsafe_allow_html=True)

with tab_kpis:
    st.subheader("📊 Métricas Chave (KPIs) do Período")

    if not kpis:
        st.info("Nenhuma métrica (KPI) foi extraída para este relatório.")
    else:
        cols = st.columns(max(1, len(kpis)))
        for i, kpi in enumerate(kpis):
            valor_display = kpi.get("valor_texto_kpi") or (
                f"{kpi.get('valor_numerico_kpi', 0):,.2f}" if kpi.get("valor_numerico_kpi") is not None else "—"
            )
            with cols[i]:
                st.markdown(
                    f"""
                    <div style="
                        border:1px solid #eee;border-radius:12px;padding:16px;margin-bottom:8px;
                        background:#fafafa; text-align:center">
                        <div style="font-size:13px;color:#666">{kpi.get('nome_kpi','N/A')}</div>
                        <div style="font-size:22px;font-weight:600;margin-top:6px">{valor_display}</div>
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
                columns={
                    "sprint_number": "Sprint",
                    "cost_realized": "Custo Acumulado",
                    "budget_total": "Orçamento Total (Teto)",
                }
            )
            df_melted = df_hist.melt("Sprint", var_name="Métrica", value_name="Valor (R$)")

            base = (
                alt.Chart(df_melted)
                .mark_line(point=True)
                .encode(
                    x=alt.X("Sprint:O", title="Sprint"),
                    y=alt.Y("Valor (R$):Q", title="Valor (R$)"),
                    color=alt.Color(
                        "Métrica",
                        scale=alt.Scale(
                            domain=["Custo Acumulado", "Orçamento Total (Teto)"],
                            range=["#FFA500", "#1C83E1"],
                        ),
                    ),
                    tooltip=["Sprint", "Métrica", "Valor (R$)"],
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

with tab_metas:
    if milestones:
        df_milestones = pd.DataFrame(milestones)
        st.subheader(f"📅 Acompanhamento de Milestones (Sprint {detalhe_relatorio.get('numero_sprint', 0)})")
        st.dataframe(df_milestones, width='stretch', hide_index=True)
    else:
        st.info("Nenhum milestone foi extraído para este relatório de sprint.")