# pages/5_Dashboard_RH.py
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# === Navegação/Segurança unificadas ===
from ui_nav import garantir_sessao_e_permissoes, render_menu_lateral, api_headers

# 1) Config da página (uma vez só)
st.set_page_config(
    page_title="Dashboard RH | MC Sonae",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Esconde a navegação nativa de multipage
st.markdown("<style>[data-testid='stSidebarNav']{display:none!important}</style>", unsafe_allow_html=True)

# 2) Sessão + permissões + sidebar
perms = garantir_sessao_e_permissoes()
render_menu_lateral(perms, current_page="dash_rh")

# Se não puder ver dashboards, bloqueia
if "view_pagina_dashboards" not in perms:
    st.error("Página não encontrada ou não disponível para seu perfil.")
    st.stop()

# ------------------------------------------------------------------------------------
# HEADER
# ------------------------------------------------------------------------------------
with st.container():
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:.5rem;opacity:.75;font-size:.9rem;">
            <span>👥</span> <span>Visualizando: <strong>Dashboard Recursos Humanos</strong></span>
            <span style="margin-left:auto;border-radius:999px;padding:.25rem .6rem;border:1px solid #e6e6e6;font-size:.75rem;">
                ● Talent Management System
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <div style="
        margin-top:.75rem;margin-bottom:1rem;
        border:1px solid #f1e6b3;background:#fffaf0;
        border-radius:14px;padding:14px 18px;">
        <div style="display:flex;align-items:center;gap:.6rem;">
            <div style="width:32px;height:32px;border-radius:8px;background:#ffb30022;display:flex;align-items:center;justify-content:center;">🏆</div>
            <div>
                <div style="font-weight:700;font-size:1.05rem;">Dashboard de Capital Humano</div>
                <div style="font-size:.9rem;opacity:.85;">Análise da jornada do colaborador, da aquisição ao engajamento.</div>
                <div style="font-size:.75rem;opacity:.6;">Projeto selecionado: projeto-talent-management</div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------------------------
# MÉTRICAS (cards)
# ------------------------------------------------------------------------------------
c1, c2, c3, c4, c5 = st.columns([1,1,1,1,1])

with c1:
    st.markdown("**Headcount Total**")
    st.markdown("<div style='font-size:1.6rem;font-weight:700;'>1,824</div><div style='color:#1b8c36;font-size:.8rem;'>↑ +28</div>", unsafe_allow_html=True)

with c2:
    st.markdown("**Turnover Anual**")
    st.markdown("<div style='font-size:1.6rem;font-weight:700;'>12.1%</div><div style='color:#cc3a3a;font-size:.8rem;'>↓ 1.1%</div>", unsafe_allow_html=True)

with c3:
    st.markdown("**eNPS**")
    st.markdown("<div style='font-size:1.6rem;font-weight:700;'>+45</div><div style='color:#cc3a3a;font-size:.8rem;'>↓ 2 pts</div>", unsafe_allow_html=True)

with c4:
    st.markdown("**Vagas em Aberto**")
    st.markdown("<div style='font-size:1.6rem;font-weight:700;'>32</div><div style='color:#1b8c36;font-size:.8rem;'>↑ +5</div>", unsafe_allow_html=True)

with c5:
    st.markdown("**Tempo médio de contratação**")
    st.markdown("<div style='font-size:1.6rem;font-weight:700;'>28 dias</div><div style='color:#1b8c36;font-size:.8rem;'>↑ +2 dias</div>", unsafe_allow_html=True)

st.markdown("---")

# ------------------------------------------------------------------------------------
# TABS — 3 visões mockadas
# ------------------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["Aquisição de Talentos", "Engajamento e Cultura", "Diversidade e Inclusão"])

# ========== TAB 1: Aquisição de Talentos ==========
with tab1:
    st.subheader("Funil de Contratação (Último Trimestre)")
    stages = ["Candidaturas", "Triagem RH", "Entrevista Gestor", "Oferta", "Contratado"]
    values = [1340, 470, 180, 65, 32]

    fig_funnel = go.Figure(go.Funnel(
        y=stages,
        x=values,
        textposition="inside",
        textinfo="value+percent initial",
        opacity=0.9
    ))
    fig_funnel.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=420)
    st.plotly_chart(fig_funnel, use_container_width=True)

    st.markdown("### Tempo Médio por Etapa")
    etapas = ["Candidaturas → Triagem", "Triagem → Entrevista", "Entrevista → Oferta", "Oferta → Contratação"]
    dias = [5, 9, 7, 7]
    fig_bar = px.bar(x=etapas, y=dias, labels={"x":"Etapas","y":"Dias"}, text=dias)
    fig_bar.update_traces(textposition="outside")
    fig_bar.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=340)
    st.plotly_chart(fig_bar, use_container_width=True)

# ========== TAB 2: Engajamento e Cultura ==========
with tab2:
    st.subheader("Análise de Sentimento (Pesquisa de Clima Anual)")
    c1, c2 = st.columns([1,1])

    with c1:
        st.markdown("**Resultados por: Gestão**")
        labels = ["Positivo", "Neutro", "Negativo"]
        vals = [65, 20, 15]
        fig_pie = px.pie(
            values=vals, names=labels, hole=.5
        )
        fig_pie.update_layout(showlegend=True, height=360, margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        st.markdown("**Comentários em Destaque (Exemplos)**")
        st.markdown(
            """
            <div style="display:flex;flex-direction:column;gap:.5rem;">
              <div style="padding:.6rem .8rem;border:1px solid #e6f0ff;background:#f6f9ff;border-radius:10px;">💬 “O plano de carreira precisa ser mais transparente.”</div>
              <div style="padding:.6rem .8rem;border:1px solid #e6f0ff;background:#f6f9ff;border-radius:10px;">💬 “Adoro os novos benefícios de bem-estar!”</div>
              <div style="padding:.6rem .8rem;border:1px solid #e6f0ff;background:#f6f9ff;border-radius:10px;">💬 “A comunicação entre departamentos poderia melhorar.”</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Absenteísmo por Mês (Mock)")
    meses = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
    taxa = [2.1, 2.3, 2.0, 1.9, 2.2, 2.4, 2.5, 2.1, 2.0, 2.3, 2.4, 2.2]
    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(x=meses, y=taxa, mode="lines+markers"))
    fig_line.update_layout(yaxis_title="%", height=340, margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig_line, use_container_width=True)

# ========== TAB 3: Diversidade e Inclusão ==========
with tab3:
    st.subheader("Composição da Força de Trabalho")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Distribuição por Gênero**")
        labels = ["Feminino","Masculino","Outro/Não informado"]
        vals = [62, 35, 3]
        fig_gender = px.pie(values=vals, names=labels)
        fig_gender.update_layout(height=360, margin=dict(l=10,r=10,t=10,b=10), showlegend=True)
        st.plotly_chart(fig_gender, use_container_width=True)

    with c2:
        st.markdown("**Distribuição por Tempo de Casa**")
        grupos = ["< 1 ano","1–3 anos","3–5 anos","5+ anos"]
        qtd = [25, 40, 20, 15]
        fig_tempo = px.bar(x=grupos, y=qtd, text=qtd, labels={"x":"Tempo de Casa","y":"% Colaboradores"})
        fig_tempo.update_traces(textposition="outside")
        fig_tempo.update_layout(height=360, margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(fig_tempo, use_container_width=True)

    st.markdown("### Contratações por Região (Mock)")
    regioes = ["Norte","Centro","Lisboa","Alentejo","Algarve","Ilhas"]
    contr = [38, 22, 64, 12, 15, 9]
    fig_region = px.bar(x=regioes, y=contr, text=contr, labels={"x":"Região","y":"Contratações"})
    fig_region.update_traces(textposition="outside")
    fig_region.update_layout(height=320, margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig_region, use_container_width=True)