# pages/6_Dashboard_Marketing.py
import streamlit as st
import plotly.graph_objects as go
import numpy as np

# Navegação/segurança unificadas
from ui_nav import garantir_sessao_e_permissoes, render_menu_lateral

# ===== Config página =====
st.set_page_config(
    page_title="Dashboard Marketing",
    page_icon="📣",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Oculta navegação nativa do Streamlit (mantemos apenas a nossa)
st.markdown("<style>[data-testid='stSidebarNav']{display:none!important}</style>", unsafe_allow_html=True)

# ===== Sessão/permissões + sidebar =====
perms = garantir_sessao_e_permissoes()
render_menu_lateral(perms, current_page="dash_mkt")

# Bloqueio por permissão
if "view_pagina_dashboards" not in perms:
    st.error("Página não encontrada ou não disponível para seu perfil.")
    st.stop()

# ====== Cabeçalho ======
with st.container(border=True):
    left, right = st.columns([0.85, 0.15])
    with left:
        st.markdown("##### 📣 Visualizando: **Dashboard Marketing**")
        st.markdown(
            """
            **Dashboard de Performance de Marketing**  
            _Análise de KPIs de campanhas do último trimestre._  
            <small>Projeto selecionado: <b>projeto-campanhas-digitais</b></small>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            """
            <div style="text-align:right">
              <span style="
                padding:6px 10px;border-radius:999px;
                background:#f1f5ff;border:1px solid #dbe3ff;
                color:#3b5bdb;font-size:12px;">
                ● Campanhas Digitais 2025
              </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.write("")  # respiro

# ====== KPIs — métricas superiores ======
k1, k2, k3, k4 = st.columns(4)
with k1:
    with st.container(border=True):
        st.caption("Receita Total")
        st.markdown("### 145 432,67 €")
        st.markdown("<span style='color:#16a34a'>↑ 18,7%</span>", unsafe_allow_html=True)

with k2:
    with st.container(border=True):
        st.caption("Receita Bruta")
        st.markdown("### 2 234 891,23 €")
        st.markdown("<span style='color:#16a34a'>↑ 12,4%</span>", unsafe_allow_html=True)

with k3:
    with st.container(border=True):
        st.caption("Leads")
        st.markdown("### 23 847")
        st.markdown("<span style='color:#16a34a'>↑ 25,6%</span>", unsafe_allow_html=True)

with k4:
    with st.container(border=True):
        st.caption("ROI (Retorno / Invest.)")
        st.markdown("### 1 435,82%")
        st.markdown("<span style='color:#16a34a'>↑ 8,3%</span>", unsafe_allow_html=True)

st.write("")

# ====== Seletor de análise (2 abas) ======
with st.container(border=True):
    st.markdown("#### 🔎 Seleção de Análise")
    # Preferimos segmented_control quando disponível (Streamlit ≥ 1.33)
    try:
        view = st.segmented_control(
            "Escolha uma visão",
            options=["Visão Geral da Performance", "Análise de Retorno (ROI)"],
            default="Visão Geral da Performance",
        )
    except Exception:
        # Fallback para radio se segmented_control não existir na sua versão
        view = st.radio(
            "Escolha uma visão",
            ["Visão Geral da Performance", "Análise de Retorno (ROI)"],
            index=0,
            horizontal=True,
        )

st.write("")

# ====== Dados mock ======
meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun"]
receita = np.array([82000, 90000, 94000, 120000, 135000, 145000])
leads = np.array([1800, 1950, 2100, 2300, 2400, 2500])

# ====== Visões ======
if view == "Visão Geral da Performance":
    with st.container(border=True):
        st.markdown("#### 📈 Visão Geral da Performance")
        # Eixo duplo: Receita (linha) x Leads (linha mais fina)
        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=meses,
                y=receita,
                mode="lines+markers",
                name="Receita (€)",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=meses,
                y=leads,
                mode="lines+markers",
                name="Leads",
                yaxis="y2",
            )
        )

        fig.update_layout(
            margin=dict(l=20, r=20, t=10, b=10),
            hovermode="x unified",
            xaxis=dict(title="Mês"),
            yaxis=dict(title="Receita (€)"),
            yaxis2=dict(
                title="Leads",
                overlaying="y",
                side="right",
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

    with st.container(border=True):
        st.markdown("#### 🧩 Destaques por Canal (mock)")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Social Ads", "€ 58,2K", "+12%")
        with c2:
            st.metric("Search (SEM)", "€ 41,6K", "+9%")
        with c3:
            st.metric("E-mail", "€ 24,1K", "+6%")
        with c4:
            st.metric("Afiliados", "€ 21,5K", "+4%")

else:
    with st.container(border=True):
        st.markdown("#### 📊 Composição do Retorno Sobre Investimento (ROI)")
        # Barras simples: Investimento, Receita Gerada, Lucro Bruto
        categorias = ["Investimento", "Receita Gerada", "Lucro Bruto"]
        valores = [66000, 1100000, 950000]

        fig = go.Figure(
            data=[
                go.Bar(
                    x=categorias,
                    y=valores,
                    text=[f"€{v:,.0f}".replace(",", ".") for v in valores],
                    textposition="outside",
                )
            ]
        )
        fig.update_layout(
            margin=dict(l=20, r=20, t=10, b=10),
            xaxis_title="Indicador",
            yaxis_title="Valor (€)",
        )
        st.plotly_chart(fig, use_container_width=True)

    with st.container(border=True):
        st.markdown("#### 🧮 Indicadores de Eficiência (mock)")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("CPL (Custo por Lead)", "€ 2,77", "-6%")
        with c2:
            st.metric("CPA (Custo por Aquisição)", "€ 31,40", "-4%")
        with c3:
            st.metric("Taxa de Conversão", "3,9%", "+0,4 pp")

st.write("")
st.caption("Todos os dados acima são ilustrativos (mock) — apenas para validação visual das telas.")