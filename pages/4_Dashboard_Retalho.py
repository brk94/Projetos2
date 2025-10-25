# pages/4_Dashboard_Retalho.py
# Mock do Dashboard de Retalho (visual consistente com Home/ui_nav)

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

# === Navegação/Segurança unificadas ===
from ui_nav import garantir_sessao_e_permissoes, render_menu_lateral

# 1) Configuração da página (uma vez só)
st.set_page_config(
    page_title="Dashboard Retalho | MC Sonae",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Esconde a navegação nativa do multipage
st.markdown("<style>[data-testid='stSidebarNav']{display:none!important}</style>", unsafe_allow_html=True)

# 2) Sessão + sidebar padronizada
perms = garantir_sessao_e_permissoes()
render_menu_lateral(perms, current_page="dash_retalho")

# 3) Autorização
if "view_pagina_dashboards" not in perms:
    st.error("Página não encontrada ou não disponível para seu perfil.")
    st.stop()

# ------------------------------------------------------------------------------------
#                                    MOCK DATA
# ------------------------------------------------------------------------------------
# Série mensal (tendência)
meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
vendas_mensais = [52000, 56000, 51000, 65000, 59000, 70000, 64000, 76000, 72000, 81000, 75000, 88000]

df_tendencia = pd.DataFrame({"Mês": meses, "Receita (€)": vendas_mensais})

# Vendas por categoria (colunas)
cats = ["Frutas e Vegetais", "Carnes e Peixes", "Laticínios", "Padaria", "Bebidas", "Cereais e Grãos", "Óleos e Snacks"]
valores = [82000, 73000, 91000, 58000, 67000, 62000, 46000]
df_cats = pd.DataFrame({"Categoria": cats, "Vendas (€)": valores})

# Níveis de estoque (progress bars)
estoque_items = [
    ("Maçãs Gala", 85, "Frutas e Vegetais"),
    ("Leite Integral", 70, "Laticínios"),
    ("Pão de Forma", 70, "Padaria"),
    ("Carne Bovina", 98, "Carnes e Peixes"),
    ("Cereal Matinal", 62, "Cereais e Grãos"),
    ("Refrigerante Cola", 55, "Bebidas"),
    ("Batata Palha", 43, "Óleos e Snacks"),
]

# KPIs (mock)
preco_medio = 95.80
produtos_vendidos = 4287
receita_total = sum(vendas_mensais)

# ------------------------------------------------------------------------------------
#                                    HEADER / BREADCRUMB
# ------------------------------------------------------------------------------------
with st.container(border=False):
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:.5rem;opacity:.8">
          <span style="font-size:.9rem;">🧭 Visualizando:</span>
          <span style="font-weight:600;">Dashboard Retalho</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------------------------------
#                                    KPIs
# ------------------------------------------------------------------------------------
with st.container(border=True):
    c1, c2, c3 = st.columns([1, 1, 1], gap="large")
    with c1:
        st.caption("Dashboard Retalho · Varejo Alimentar")
        st.subheader("Métricas de vendas de produtos alimentícios")
        st.caption("Projeto acadêmico — pipeline supply-chain (mock)")

    k1, k2, k3 = st.columns([1, 1, 1], gap="large")
    with k1:
        st.metric("Preço Médio", f"{preco_medio:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."), "+7.25%")
    with k2:
        st.metric("Produtos Vendidos", f"{produtos_vendidos:,.0f}", "+15.8%")
    with k3:
        st.metric("Receita Total", f"{receita_total:,.0f} €".replace(",", "X").replace(".", ",").replace("X", "."), "+12.4%")

# ------------------------------------------------------------------------------------
#                                    Tendência mensal (Linha)
# ------------------------------------------------------------------------------------
with st.container(border=True):
    st.caption("📈 Tendência de Vendas · Produtos Alimentícios")
    fig_line = go.Figure()
    fig_line.add_trace(
        go.Scatter(
            x=df_tendencia["Mês"],
            y=df_tendencia["Receita (€)"],
            mode="lines+markers",
            name="Receita",
        )
    )
    fig_line.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=360,
        xaxis_title=None,
        yaxis_title="€",
    )
    st.plotly_chart(fig_line, use_container_width=True)

# ------------------------------------------------------------------------------------
#                       Vendas por Categoria (Barras) + Filtro (mock)
# ------------------------------------------------------------------------------------
with st.container(border=True):
    st.caption("📊 Análise de Vendas por Categoria Alimentícia")

    colf1, colf2 = st.columns([1, 3], gap="small")
    with colf1:
        st.write("**Filtrar por categoria:**")
        cat_sel = st.selectbox(
            "Categoria",
            ["Todas"] + cats,
            index=0,
            label_visibility="collapsed",
        )

    if cat_sel != "Todas":
        df_plot = df_cats[df_cats["Categoria"] == cat_sel]
        subtitulo = f"Vendas para **{cat_sel}**"
    else:
        df_plot = df_cats.copy()
        subtitulo = "Vendas para **Todas as Categorias**"

    with colf2:
        total = int(df_plot["Vendas (€)"].sum())
        st.caption(f"Total: **{total:,.0f} €** • {len(df_plot)} categoria(s)".replace(",", "."))

    fig_bar = px.bar(
        df_plot,
        x="Categoria",
        y="Vendas (€)",
        text_auto=True,
    )
    fig_bar.update_layout(
        margin=dict(l=10, r=10, t=20, b=10),
        height=360,
        xaxis_title=None,
        yaxis_title="€",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# ------------------------------------------------------------------------------------
#                                    Estoque (progress)
# ------------------------------------------------------------------------------------
with st.container(border=True):
    st.caption("📦 Níveis de Estoque · Produtos Alimentícios")

    for nome, pct, cat in estoque_items:
        with st.container(border=True):
            top = st.columns([3, 1])
            with top[0]:
                st.write(f"**{nome}**")
                st.caption(cat)
            with top[1]:
                st.write(f"**{pct}%**")

            st.progress(pct / 100.0, text=None)

# ------------------------------------------------------------------------------------
#                                    Rodapé / info
# ------------------------------------------------------------------------------------
st.markdown(
    f"""
    <div style="opacity:.7;font-size:.9rem;margin-top:1rem">
      Última atualização: {date.today().strftime('%d/%m/%Y')}
      · Dados demonstrativos (mock).
    </div>
    """,
    unsafe_allow_html=True,
)