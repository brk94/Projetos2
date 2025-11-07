# pages/7_About.py
import streamlit as st
from ui_nav import garantir_sessao_e_permissoes, render_menu_lateral

# ====== Config da página ======
st.set_page_config(
    page_title="Sobre | MC Sonae",
    page_icon="ℹ️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Esconder a navegação nativa do multipage 
st.markdown("<style>[data-testid='stSidebarNav']{display:none!important}</style>", unsafe_allow_html=True)

# Sessão/permissões + sidebar padrão
perms = garantir_sessao_e_permissoes()
render_menu_lateral(perms, current_page="about")

# ====== CSS da casca visual ======
st.markdown("""
<style>
    /* Fundo branco obrigatório */
    [data-testid="stAppViewContainer"] {
        background-color: #ffffff !important;
    }

    .main .block-container {
        max-width: 900px;
        padding: 2.5rem 2rem;
    }

    .header-title {
        font-size: 26px;
        font-weight: 700;
        color: #1a1a1a;
        margin-bottom: 6px;
        line-height: 1.3;
    }

    .header-subtitle {
        font-size: 13.5px;
        color: #6b7280;
        line-height: 1.6;
        margin-bottom: 28px;
    }

    .section-box {
        background: white;
        border-radius: 12px;
        padding: 26px;
        margin-bottom: 18px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        border: 1px solid #e5e7eb;
    }

    .section-header { margin-bottom: 16px; }

    .section-icon {
        width: 22px;
        height: 22px;
        background: #f3f4f6;
        border-radius: 50%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-right: 9px;
        vertical-align: middle;
        font-size: 13px;
    }

    .section-title {
        font-size: 15px;
        font-weight: 600;
        color: #1a1a1a;
        margin: 0;
        display: inline-block;
        vertical-align: middle;
    }

    .section-text {
        font-size: 13.5px;
        color: #6b7280;
        line-height: 1.65;
        margin: 0;
    }

    .metric-row {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
        margin-top: 20px;
    }

    .metric-item {
        text-align: center;
        padding: 16px 10px;
        border-radius: 8px;
    }
    .metric-item:nth-child(1) { background: #E8F2FF; }
    .metric-item:nth-child(2) { background: #E5FCF0; }
    .metric-item:nth-child(3) { background: #F5EDFF; }

    .metric-title {
        font-size: 13.5px;
        font-weight: 600;
        color: #1a1a1a;
        margin-bottom: 4px;
    }

    .metric-value {
        font-size: 12px;
        color: #6b7280;
        line-height: 1.4;
    }

    .challenge-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 16px;
        margin-top: 16px;
    }

    .problem-item, .goal-item {
        border-radius: 8px;
        padding: 18px;
    }
    .problem-item {
        background: #fef2f2;
        border: 1px solid #fecaca;
    }
    .goal-item {
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
    }

    .item-title {
        font-size: 13.5px;
        font-weight: 600;
        margin-bottom: 10px;
    }
    .problem-item .item-title { color: #991b1b; }
    .goal-item .item-title { color: #065f46; }

    .problem-item ul, .goal-item ul { margin: 0; padding-left: 17px; }
    .problem-item li, .goal-item li {
        font-size: 12.5px;
        margin-bottom: 5px;
        line-height: 1.5;
    }
    .problem-item li { color: #991b1b; }
    .goal-item li { color: #065f46; }

    .solution-grid, .steps-grid, .thanks-grid {
        display: grid;
        gap: 16px;
        margin-top: 16px;
    }
    .solution-grid { grid-template-columns: repeat(3, 1fr); }
    .steps-grid    { grid-template-columns: repeat(3, 1fr); }
    .thanks-grid   { grid-template-columns: repeat(2, 1fr); }

    .solution-item {
        background: #f9fafb;
        border-radius: 8px;
        padding: 18px;
        text-align: left;
        border: 1px solid #e5e7eb;
    }

    .solution-icon {
        width: 42px;
        height: 42px;
        background: #dbeafe;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 12px;
        font-size: 21px;
        color: #2563eb;
    }

    .solution-item-title {
        font-size: 13.5px;
        font-weight: 600;
        color: #1a1a1a;
        margin-bottom: 7px;
    }

    .solution-item-desc {
        font-size: 12px;
        color: #6b7280;
        line-height: 1.5;
    }

    .step-item { display: flex; flex-direction: column; align-items: flex-start; }
    .step-number {
        width: 30px; height: 30px; background: #2563eb; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        color: white; font-weight: 600; font-size: 14px; margin-bottom: 12px;
        flex-shrink: 0;
    }
    .step-title { font-size: 13.5px; font-weight: 600; color: #1a1a1a; margin-bottom: 6px; }
    .step-desc  { font-size: 12px; color: #6b7280; line-height: 1.5; }

    .disclaimer-box {
        background: #fffbeb;
        border: 1px solid #fcd34d;
        border-radius: 8px;
        padding: 18px;
    }
    .disclaimer-title {
        font-size: 13.5px; font-weight: 600; color: #92400e; margin-bottom: 9px; display: flex; align-items: center;
    }
    .disclaimer-icon {
        width: 17px; height: 17px; background: #fbbf24; border-radius: 50%;
        display: inline-flex; align-items: center; justify-content: center;
        margin-right: 7px; color: white; font-size: 11px; font-weight: bold;
    }
    .disclaimer-text { font-size: 12.5px; color: #92400e; line-height: 1.6; }

    .thanks-item {
        background: #f9fafb;
        border-radius: 8px;
        padding: 16px;
        text-align: left;
        border: 1px solid #e5e7eb;
    }
    .thanks-item-title { font-size: 13.5px; font-weight: 600; color: #1a1a1a; margin-bottom: 5px; }
    .thanks-item-desc  { font-size: 12px; color: #6b7280; line-height: 1.5; }

    .footer-text {
        text-align: center;
        font-size: 12px;
        color: #9ca3af;
        margin-top: 0px;
        padding-top: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ====== Conteúdo (apenas visual da casca) ======
st.markdown("""
<div class="header-title">Visão de Projeto: Automação de Comunicação na MC Sonae</div>
<div class="header-subtitle">Uma solução completa para automatizar processos de comunicação e gestão de projetos, desenvolvida especificamente para as necessidades da MC Sonae.</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="section-box">
    <div class="section-header">
        <span class="section-icon">🎯</span>
        <span class="section-title">Visão do Projeto</span>
    </div>
    <p class="section-text">O projeto de Automação de Comunicação na MC Sonae tem como objetivo centralizar e automatizar os processos de gestão de projetos, proporcionando maior eficiência, transparência e controle sobre as atividades organizacionais.</p>
    <div class="metric-row">
        <div class="metric-item">
            <div class="metric-title">Eficiência</div>
            <div class="metric-value">Redução de 40% no tempo de reporting</div>
        </div>
        <div class="metric-item">
            <div class="metric-title">Transparência</div>
            <div class="metric-value">Visibilidade completa dos projetos</div>
        </div>
        <div class="metric-item">
            <div class="metric-title">Controle</div>
            <div class="metric-value">Monitoramento em tempo real</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="section-box">
    <div class="section-header">
        <span class="section-icon">💡</span>
        <span class="section-title">O Desafio</span>
    </div>
    <p class="section-text">A MC Sonae enfrentava desafios significativos na gestão de múltiplos projetos simultâneos, com comunicação fragmentada, relatórios manuais demorados e falta de visibilidade centralizada do status dos projetos.</p>
    <div class="challenge-grid">
        <div class="problem-item">
            <div class="item-title">Problemas Identificados</div>
            <ul>
                <li>Relatórios manuais demorados</li>
                <li>Comunicação descentralizada</li>
                <li>Falta de visibilidade em tempo real</li>
                <li>Dados espalhados em múltiplas ferramentas</li>
            </ul>
        </div>
        <div class="goal-item">
            <div class="item-title">Metas Estabelecidas</div>
            <ul>
                <li>Centralizar informações de projetos</li>
                <li>Automatizar geração de relatórios</li>
                <li>Melhorar comunicação entre equipes</li>
                <li>Implementar dashboards em tempo real</li>
            </ul>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="section-box">
    <div class="section-header">
        <span class="section-icon">⚙️</span>
        <span class="section-title">Nossa Solução</span>
    </div>
    <p class="section-text">Plataforma integrada que automatiza a coleta, processamento e apresentação de dados de projetos, fornecendo dashboards interativos, relatórios automatizados e alertas proativos para gestores e equipes.</p>
    <div class="solution-grid">
        <div class="solution-item">
            <div class="solution-icon">🎯</div>
            <div class="solution-item-title">Dashboard Executivo</div>
            <div class="solution-item-desc">Visão consolidada de todos os projetos com métricas-chave e indicadores de performance.</div>
        </div>
        <div class="solution-item">
            <div class="solution-icon">📊</div>
            <div class="solution-item-title">Relatórios Automatizados</div>
            <div class="solution-item-desc">Geração automática de relatórios de status, orçamento e marcos de projeto.</div>
        </div>
        <div class="solution-item">
            <div class="solution-icon">🛡️</div>
            <div class="solution-item-title">Gestão de Riscos</div>
            <div class="solution-item-desc">Identificação proativa de riscos e impedimentos com alertas automatizados.</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="section-box">
    <div class="section-header">
        <span class="section-icon">📖</span>
        <span class="section-title">Como Usar</span>
    </div>
    <div class="steps-grid">
        <div class="step-item">
            <div class="step-number">1</div>
            <div class="step-title">Acesse o Dashboard</div>
            <div class="step-desc">Faça login na plataforma e acesse a página inicial para uma visão geral dos projetos.</div>
        </div>
        <div class="step-item">
            <div class="step-number">2</div>
            <div class="step-title">Envie relatórios para processamento</div>
            <div class="step-desc">Carregue os arquivos (PDF/DOCX); a plataforma interpreta os dados e cria os painéis automaticamente.</div>
        </div>
        <div class="step-item">
            <div class="step-number">3</div>
            <div class="step-title">Monitore o dashboard em tempo real</div>
            <div class="step-desc">Acompanhe métricas, orçamentos e marcos; as visualizações se atualizam conforme novos relatórios são enviados.</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="disclaimer-box">
    <div class="disclaimer-title">
        <span class="disclaimer-icon">!</span>
        Disclaimer Acadêmico
    </div>
    <div class="disclaimer-text">Este projeto foi desenvolvido como parte do programa acadêmico da CESAR School e tem fins educacionais. Embora baseado em necessidades reais da MC Sonae, trata-se de um protótipo demonstrativo que não deve ser utilizado em ambiente de produção sem as devidas validações e adaptações.</div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="section-box" style="margin-top: 18px;">
    <div class="section-header">
        <span class="section-icon">👥</span>
        <span class="section-title">Agradecimentos</span>
    </div>
    <p class="section-text">Agradecemos a todos que contribuíram para o desenvolvimento deste projeto:</p>
    <div class="thanks-grid">
        <div class="thanks-item">
            <div class="thanks-item-title">CESAR School</div>
            <div class="thanks-item-desc">Pela orientação acadêmica e estrutura para desenvolvimento do projeto.</div>
        </div>
        <div class="thanks-item">
            <div class="thanks-item-title">MC Sonae</div>
            <div class="thanks-item-desc">Pela parceria e fornecimento de requisitos reais para o desenvolvimento.</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="footer-text">Grupo 1 — CESAR School • Projeto Acadêmico 2025</div>', unsafe_allow_html=True)
