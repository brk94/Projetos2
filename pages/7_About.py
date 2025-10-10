# pages/7_About.py
import streamlit as st

# navegação/segurança unificadas (já criadas por você)
from ui_nav import ensure_session_and_perms, render_sidebar

# ====== Config da página ======
st.set_page_config(
    page_title="Sobre | MC Sonae",
    page_icon="ℹ️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# esconder a navegação nativa do multipage
st.markdown("<style>[data-testid='stSidebarNav']{display:none!important}</style>", unsafe_allow_html=True)

# sessão/permissões + sidebar padrão
perms = ensure_session_and_perms()
render_sidebar(perms, current_page="about")

# ====== Estilização extra (leve) ======
st.markdown(
    """
    <style>
      .badge {
        display:inline-block;
        padding:6px 10px;
        border-radius:999px;
        font-size:0.85rem;
        font-weight:600;
        background:#eef2ff;
        color:#4338ca;
        border:1px solid #c7d2fe;
      }
      .soft-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 18px 16px;
      }
      .pill {
        border-radius: 12px;
        padding: 14px;
        border: 1px solid #e5e7eb;
        background: #fafafa;
      }
      .pill-blue   { background:#eef6ff; border-color:#dbeafe; }
      .pill-green  { background:#ecfdf5; border-color:#d1fae5; }
      .pill-purple { background:#f5f3ff; border-color:#e9d5ff; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ====== Cabeçalho ======
st.title("Visão de Projeto: Automação de Comunicação na MC Sonae")
st.markdown(
    "Uma solução completa para automatizar processos de comunicação e gestão de projetos, "
    "desenvolvida especificamente para as necessidades da MC Sonae."
)

st.divider()

# ====== Seção: Visão do Projeto ======
with st.container(border=True):
    st.subheader("🔭 Visão do Projeto")
    st.markdown(
        "O projeto tem como objetivo **centralizar a automação** dos processos de gestão de projetos, "
        "promovendo maior **eficiência**, **transparência** e **controle**."
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            """
            <div class="pill pill-blue">
              <b>Eficiência</b><br>
              Redução de esforço manual, geração ágil de relatórios.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div class="pill pill-green">
              <b>Transparência</b><br>
              Visibilidade consolidada do portfólio de projetos.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            """
            <div class="pill pill-purple">
              <b>Controle</b><br>
              Acompanhamento em tempo real e histórico por sprint.
            </div>
            """,
            unsafe_allow_html=True,
        )

# ====== Seção: O Desafio ======
st.write("")  # respiro
with st.container(border=True):
    st.subheader("🧩 O Desafio")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Problemas Identificados**")
        st.markdown(
            """
            - Relatórios manuais demorados  
            - Comunicação descentralizada  
            - Falta de visibilidade em tempo real  
            - Dados espalhados em múltiplas ferramentas
            """
        )
    with c2:
        st.markdown("**Metas Estabelecidas**")
        st.markdown(
            """
            - Centralizar informações de projetos  
            - Automatizar a geração de relatórios  
            - Melhorar a comunicação entre equipes  
            - Oferecer dashboards consolidados em tempo real
            """
        )

# ====== Seção: Nossa Solução ======
st.write("")
with st.container(border=True):
    st.subheader("🛠️ Nossa Solução")
    st.markdown(
        "Plataforma integrada que automatiza a coleta, processamento e visualização de dados dos projetos."
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            """
            <div class="soft-card">
              <h4>📊 Dashboard Executivo</h4>
              <p>Consolidação dos principais indicadores dos projetos.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div class="soft-card">
              <h4>🧾 Relatórios Automatizados</h4>
              <p>Geração automática de status, orçamento e marcos por sprint.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            """
            <div class="soft-card">
              <h4>🛡️ Gestão de Riscos</h4>
              <p>Rastreamento de impedimentos e histórico de marcos.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ====== Seção: Como Usar ======
st.write("")
with st.container(border=True):
    st.subheader("📚 Como Usar")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**1) Acesse o Dashboard**")
        st.caption("Visão geral com KPIs e indicadores consolidados.")
    with c2:
        st.markdown("**2) Monitore o Status**")
        st.caption("Acompanhe marcos, KPIs e histórico por sprint.")
    with c3:
        st.markdown("**3) Gere Relatórios**")
        st.caption("Upload de relatórios por área, com processamento automático.")

# ====== Seção: Disclaimer ======
st.write("")
with st.container(border=True):
    st.subheader("⚠️ Disclaimer Acadêmico")
    st.markdown(
        """
        Este projeto foi desenvolvido como parte de um programa acadêmico da **CESAR School**,
        com fins educacionais. Embora baseado em necessidades reais da **MC Sonae**, trata-se
        de um **protótipo demonstrativo** e não deve ser utilizado em produção sem as devidas
        adaptações e validações.
        """
    )

# ====== Seção: Agradecimentos ======
st.write("")
with st.container(border=True):
    st.subheader("🙏 Agradecimentos")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            """
            <div class="soft-card">
              <h4>🎓 CESAR School</h4>
              <p>Pela orientação acadêmica e suporte metodológico durante o desenvolvimento do projeto.</p>
              <span class="badge">Educação</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div class="soft-card">
              <h4>🏢 MC Sonae</h4>
              <p>Pela parceria e fornecimento de requisitos reais que enriqueceram o protótipo.</p>
              <span class="badge">Parceria</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.write("")
st.caption("Grupo 1 — CESAR School • Projeto Acadêmico 2025")
