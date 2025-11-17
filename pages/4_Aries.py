"""
Página Streamlit — ARIES (NLP, só Administrador, sem banco)

Fluxo:
- Gate de sessão + menu lateral (RBAC padrão do projeto)
- Checagem de cargo "Administrador"
- Upload de relatório ARIES (.docx / .pdf)
- Chamada ao endpoint /aries/interpretar (IA + NLP, sem banco)
- Exibição visual:
  - Visão geral + papel da SONAE
  - Mapa dos Work Packages (WP1..WP7) em tabela + gráfico simples
  - Cards dos pilotos/cenários
  - Lista de tabelas relevantes
  - Abas com detalhes (atividades/resultados, riscos/licões, ideias)
"""

from __future__ import annotations

import html
from typing import Any, Dict, List

import altair as alt
import pandas as pd
import streamlit as st

from ui_nav import (
    garantir_sessao_e_permissoes,
    render_menu_lateral,
    _buscar_me_perfil,
    req_post,
)

# ======================================================================================
# Configuração da página
# ======================================================================================

st.set_page_config(
    page_title="ARIES (NLP)",
    page_icon="🧠",
    layout="wide",
)

# Esconde o nav padrão do multipage do Streamlit (usamos só o menu custom)
st.markdown(
    """
<style>
[data-testid="stSidebarNav"] { display: none !important; }

/* Casca geral da página */
.aries-main {
    padding-top: 0.5rem;
}

/* Cards genéricos */
.aries-card {
    background-color: #ffffff;
    border-radius: 16px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
}
.aries-card h3 {
    margin-top: 0;
    margin-bottom: 0.5rem;
    font-size: 1rem;
}
.aries-card p {
    margin: 0;
    font-size: 0.92rem;
    line-height: 1.5;
}

/* Lista em card */
.aries-list {
    padding-left: 1.1rem;
    margin: 0;
}
.aries-list li {
    margin-bottom: 0.25rem;
    font-size: 0.92rem;
}

/* “Pílulas” de ideias */
.aries-pill {
    display: inline-block;
    padding: 0.3rem 0.75rem;
    border-radius: 999px;
    border: 1px solid #d0d7ff;
    font-size: 0.8rem;
    margin-right: 0.4rem;
    margin-bottom: 0.4rem;
    background-color: #f5f7ff;
}
</style>
""",
    unsafe_allow_html=True,
)

# ======================================================================================
# Gate de sessão + permissão de Administrador
# ======================================================================================

perms = garantir_sessao_e_permissoes()
render_menu_lateral(perms, current_page="aries")

me = _buscar_me_perfil() or {}
cargos = me.get("cargos") or []
cargos_norm = [str(c).strip().lower() for c in cargos if isinstance(c, str)]

if "administrador" not in cargos_norm:
    st.error("Esta página é exclusiva para usuários com cargo de **Administrador**.")
    st.stop()

# ======================================================================================
# Helpers de UI
# ======================================================================================


def _render_card_html(title: str, body: str) -> None:
    """Renderiza um card simples com título e parágrafo."""
    st.markdown(
        f"""
        <div class="aries-card">
            <h3>{html.escape(title)}</h3>
            <p>{html.escape(body) if body else "—"}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_lista_card(title: str, items: List[str]) -> str:
    """Gera HTML de um card com lista <ul>."""
    if not items:
        return ""
    safe_items = "".join(
        f"<li>{html.escape(str(i))}</li>"
        for i in items
        if str(i).strip()
    )
    if not safe_items:
        return ""
    return f"""
    <div class="aries-card">
        <h3>{html.escape(title)}</h3>
        <ul class="aries-list">
            {safe_items}
        </ul>
    </div>
    """


def _render_ideias_pills(items: List[str]) -> str:
    """Gera HTML de um card com ideias em formato de pílulas."""
    if not items:
        return ""
    pills = "".join(
        f'<span class="aries-pill">{html.escape(str(i))}</span>'
        for i in items
        if str(i).strip()
    )
    if not pills:
        return ""
    return f"""
    <div class="aries-card">
        <h3>💡 Ideias para inspirar o MC Sonae</h3>
        {pills}
    </div>
    """


def _render_wp_table(work_packages: List[Dict[str, Any]]) -> None:
    """Mostra uma tabela com os Work Packages WP1..WP7 (id, título, objetivo, status)."""
    if not work_packages:
        _render_card_html(
            "Mapa de Work Packages",
            "O relatório não trouxe informações suficientes sobre os WPs.",
        )
        return

    rows = []
    for wp in work_packages:
        wp_id = str(wp.get("id") or "").strip()
        titulo = str(wp.get("titulo") or "").strip()
        objetivo = str(wp.get("objetivo") or "").strip()
        status = str(wp.get("status") or "").strip() or "nao_mencionado"
        if not wp_id:
            continue
        rows.append(
            {
                "WP": wp_id,
                "Título": titulo,
                "Objetivo": objetivo,
                "Status": status,
            }
        )

    if not rows:
        _render_card_html(
            "Mapa de Work Packages",
            "O relatório não trouxe informações suficientes sobre os WPs.",
        )
        return

    st.markdown("### 🧩 Mapa dos Work Packages (WP1..WP7)")
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_wp_intensity_chart(work_packages: List[Dict[str, Any]]) -> None:
    """
    Gráfico simples: quantos itens (atividades + resultados) são descritos por WP.
    Ideia: mostrar quão “presente” cada WP está no relatório.
    """
    if not work_packages:
        return

    rows = []
    for wp in work_packages:
        wp_id = str(wp.get("id") or "").strip() or "WP"
        atividades = wp.get("principais_atividades") or []
        resultados = wp.get("principais_resultados") or []
        count = len([a for a in atividades if str(a).strip()]) + len(
            [r for r in resultados if str(r).strip()]
        )
        if count > 0:
            rows.append({"WP": wp_id, "Itens mencionados": count})

    if not rows:
        return

    df = pd.DataFrame(rows)
    st.markdown("#### 📊 Quantidade de atividades/resultados citados por WP")
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("WP:N", title="Work Package"),
            y=alt.Y("Itens mencionados:Q", title="Qtde de itens descritos"),
            tooltip=["WP", "Itens mencionados"],
        )
    )
    st.altair_chart(chart, use_container_width=True)


def _render_pilotos_cards(pilotos: List[Dict[str, Any]]) -> None:
    """Cards para cada piloto/cenário (e-commerce, aeroporto, etc.)."""
    if not pilotos:
        _render_card_html(
            "Pilotos e cenários",
            "O relatório não traz detalhes suficientes sobre pilotos/cenários.",
        )
        return

    st.markdown("### 🧪 Pilotos e cenários")

    for piloto in pilotos:
        nome = str(piloto.get("nome") or "").strip() or "Piloto"
        desc = str(piloto.get("descricao") or "").strip()
        status = str(piloto.get("status") or "").strip() or "indefinido"
        wps = piloto.get("work_packages_relacionados") or []
        wps_str = ", ".join(str(w).strip() for w in wps if str(w).strip()) or "—"
        kpis = piloto.get("principais_kpis") or []

        kpis_html = ""
        if kpis:
            safe_items = "".join(
                f"<li>{html.escape(str(i))}</li>"
                for i in kpis
                if str(i).strip()
            )
            if safe_items:
                kpis_html = f"<ul class='aries-list'>{safe_items}</ul>"

        st.markdown(
            f"""
            <div class="aries-card">
                <h3>{html.escape(nome)}</h3>
                <p><strong>Status:</strong> {html.escape(status)}</p>
                <p><strong>Work Packages relacionados:</strong> {html.escape(wps_str)}</p>
                <p>{html.escape(desc) if desc else ""}</p>
                {kpis_html}
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_tabelas_relevantes(tabelas: List[Dict[str, Any]]) -> None:
    """Lista resumida das principais tabelas do relatório."""
    if not tabelas:
        _render_card_html(
            "Tabelas relevantes",
            "O relatório não trouxe (ou o modelo não identificou) tabelas específicas a destacar.",
        )
        return

    titulo_card = "📑 Tabelas relevantes no relatório ARIES"
    items = []
    for t in tabelas:
        titulo = str(t.get("titulo") or "").strip()
        tema = str(t.get("tema") or "").strip()
        desc = str(t.get("descricao") or "").strip()
        pedacos = []
        if titulo:
            pedacos.append(f"Título: {titulo}")
        if tema:
            pedacos.append(f"Tema: {tema}")
        if desc:
            pedacos.append(f"Descrição: {desc}")
        if pedacos:
            items.append(" — ".join(pedacos))

    html_lista = _render_lista_card(titulo_card, items)
    if html_lista:
        st.markdown(html_lista, unsafe_allow_html=True)
    else:
        _render_card_html(
            "Tabelas relevantes",
            "O relatório não trouxe (ou o modelo não identificou) tabelas específicas a destacar.",
        )


# ======================================================================================
# Layout principal
# ======================================================================================

st.markdown('<div class="aries-main">', unsafe_allow_html=True)

st.title("Relatório ARIES — Interpretação com IA")
st.caption(
    "Envie um relatório (ex.: **ARIES periodic report - part B total v04 vSONAE.docx**) "
    "para gerar um resumo visual com IA e NLP."
)

st.divider()

uploaded = st.file_uploader(
    "Envie o arquivo do relatório ARIES",
    type=["docx", "pdf"],
    help="Aceita .docx ou .pdf. O conteúdo não será salvo, apenas interpretado pela IA.",
)

if uploaded is not None:
    st.info(f"Arquivo selecionado: **{uploaded.name}**")

    if st.button("Interpretar com IA", use_container_width=True):
        with st.spinner("Lendo o arquivo e gerando insights com IA..."):
            try:
                files = {
                    "file": (
                        uploaded.name,
                        uploaded.getvalue(),
                        uploaded.type or "application/octet-stream",
                    )
                }

                # Endpoint pesado (parsing + IA): timeout maior
                resp = req_post("/aries/interpretar", files=files, timeout=90)

                if resp.status_code == 200:
                    data = resp.json() or {}
                    conteudo: Dict[str, Any] = data.get("conteudo") or {}

                    visao_geral = (conteudo.get("visao_geral") or "").strip()
                    papel_sonae = (conteudo.get("papel_sonae") or "").strip()
                    work_packages = conteudo.get("work_packages") or []
                    pilotos = conteudo.get("pilotos") or []
                    tabelas_rel = conteudo.get("tabelas_relevantes") or []
                    riscos = conteudo.get("riscos") or []
                    licoes = conteudo.get("licoes") or []
                    ideias = conteudo.get("ideias_mc_sonae") or []

                    # ---------------- Cabeçalho: visão geral + papel SONAE ----------------
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        _render_card_html("🔎 Visão geral do projeto ARIES", visao_geral)
                    with col2:
                        _render_card_html("🏬 Papel da SONAE / SONAE MC", papel_sonae)

                    st.divider()

                    # ---------------- Work Packages ----------------
                    _render_wp_table(work_packages)
                    _render_wp_intensity_chart(work_packages)

                    st.divider()

                    # ---------------- Pilotos / Cenários ----------------
                    _render_pilotos_cards(pilotos)

                    st.divider()

                    # ---------------- Tabelas relevantes ----------------
                    _render_tabelas_relevantes(tabelas_rel)

                    st.divider()

                    # ---------------- Abas de detalhes ----------------
                    tab1, tab2, tab3 = st.tabs(
                        [
                            "📋 Atividades & Resultados por WP",
                            "⚠️ Riscos & Lições",
                            "💡 Ideias para o MC Sonae",
                        ]
                    )

                    # Tab 1: Atividades & Resultados por WP
                    with tab1:
                        if not work_packages:
                            _render_card_html(
                                "Atividades & Resultados por WP",
                                "O relatório não trouxe detalhes suficientes de Work Packages.",
                            )
                        else:
                            for wp in work_packages:
                                wp_id = str(wp.get("id") or "").strip() or "WP"
                                titulo_wp = str(wp.get("titulo") or "").strip()
                                titulo_full = (
                                    f"{wp_id} — {titulo_wp}" if titulo_wp else wp_id
                                )
                                atividades = wp.get("principais_atividades") or []
                                resultados = wp.get("principais_resultados") or []

                                st.subheader(titulo_full)
                                col_a, col_b = st.columns(2)
                                with col_a:
                                    html_a = _render_lista_card(
                                        "Atividades principais", atividades
                                    )
                                    if html_a:
                                        st.markdown(html_a, unsafe_allow_html=True)
                                    else:
                                        st.caption(
                                            "Nenhuma atividade principal destacada para este WP."
                                        )
                                with col_b:
                                    html_b = _render_lista_card(
                                        "Resultados principais", resultados
                                    )
                                    if html_b:
                                        st.markdown(html_b, unsafe_allow_html=True)
                                    else:
                                        st.caption(
                                            "Nenhum resultado principal destacado para este WP."
                                        )

                    # Tab 2: Riscos & Lições
                    with tab2:
                        html_blocos = ""
                        html_blocos += _render_lista_card("Riscos e desafios", riscos)
                        html_blocos += _render_lista_card(
                            "Lições aprendidas / Recomendações", licoes
                        )
                        if not html_blocos:
                            _render_card_html(
                                "Riscos & Lições",
                                "O relatório não traz riscos ou lições explícitas.",
                            )
                        else:
                            st.markdown(html_blocos, unsafe_allow_html=True)

                    # Tab 3: Ideias para MC Sonae
                    with tab3:
                        html_blocos = _render_ideias_pills(ideias)
                        if not html_blocos:
                            _render_card_html(
                                "Ideias para o MC Sonae",
                                "Não foram identificadas ideias específicas para o MC Sonae.",
                            )
                        else:
                            st.markdown(html_blocos, unsafe_allow_html=True)

                elif resp.status_code in (401, 403):
                    st.error("Você não tem permissão para usar este recurso (Admin apenas).")
                    st.caption(resp.text)
                else:
                    st.error(f"Falha ao interpretar o relatório (HTTP {resp.status_code}).")
                    st.caption(resp.text)
            except Exception as e:
                st.error(f"Erro ao chamar a API: {e}")
else:
    st.info(
        "Envie um arquivo do projeto ARIES (.docx ou .pdf) para começar a gerar insights com IA."
    )

st.markdown("</div>", unsafe_allow_html=True)