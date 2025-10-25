"""
Página Streamlit — Processar Relatórios

Seções:
- Configuração visual e CSS
- Gate de sessão/permissões + menu lateral
- Helpers de API (tipos de projeto e projetos do usuário)
- Formulário de upload e envio para `/processar-relatorios/`
- Polling do status da tarefa (`/tasks/status/{task_id}`)
- Histórico: lista de projetos gerenciados com ação de **Soft Delete**
"""

# ======================================================================================
# Imports e setup
# ======================================================================================
import streamlit as st
import pandas as pd  # (mantido; pode ser útil em evoluções da página)
import time

from ui_nav import garantir_sessao_e_permissoes, render_menu_lateral, api_headers, req_get, req_post

# ======================================================================================
# Configuração da página + CSS utilitário (apenas visual)
# ======================================================================================
st.set_page_config(page_title="Processar Relatórios", page_icon="📤", layout="centered")

# Esconde nav nativa e ajusta estilos de botão/linha flex
st.markdown(
    """
<style>
/* ——— Oculta a navegação nativa do Streamlit ——— */
[data-testid="stSidebarNav"] { display: none !important; }           /* lista de páginas */
[data-testid="stSidebarCollapsedControl"] { display: none !important; }  /* “hamburger” do topo */
button[kind="header"] { display: none !important; }                   /* botões padrão do header */

/* ——— Botão primário em vermelho (página inteira) ——— */
:root { --primary-color: #dc2626; }
.stButton > button[kind="primary"]{
  background-color:#E0625F !important;  /* sua cor */
  border-color:#b91c1c !important;
}
.stButton > button[kind="primary"]:hover{
  background-color:#b91c1c !important;
  border-color:#991b1b !important;
}

/* ——— Linha com input + botão alinhados verticalmente ——— */
.soft-row { display:flex; gap:0.75rem; align-items:center; }
.soft-row .soft-motivo { flex:1; }
</style>
""",
    unsafe_allow_html=True,
)

# ======================================================================================
# Sessão + permissões e navegação lateral
# ======================================================================================
# Redireciona para Home se não houver sessão/token. O helper `garantir_sessao_e_permissoes`
# também retorna o conjunto de permissões do usuário autenticado.
perms = garantir_sessao_e_permissoes()

if not st.session_state.get("logged_in") or not st.session_state.get("auth_token"):
    st.switch_page("Home.py")

# Sidebar unificada (marcando a página atual)
render_menu_lateral(perms, current_page="processar")

# ======================================================================================
# Helpers de API — Tipos de projeto e projetos do usuário
# ======================================================================================

def get_lista_tipos_projeto():
    """Busca tipos de projeto permitidos para **este usuário**.
    - Usa `/projetos/tipos` (aplica RBAC no backend).
    - Aceita tanto resposta `{"tipos": [...]}` quanto uma lista direta.
    - Em 401/403 mostra mensagens amigáveis; em outras falhas, alerta.
    """
    try:
        r = req_get("/projetos/tipos")
        if r.status_code == 200:
            data = r.json()
            return data.get("tipos", data) if isinstance(data, dict) else data
        elif r.status_code in (401, 403):
            st.error("Sem permissão para listar tipos de projeto.")
            st.caption(r.text)
            return []
        else:
            st.warning(f"Falha ao buscar tipos (HTTP {r.status_code})")
            st.caption(r.text)
            return []
    except Exception:
        st.error("API offline.")
        return []


def _load_my_projects():
    """Carrega projetos **gerenciados** pelo usuário (para ações de Soft Delete).
    - Usa `/me/projetos/gerenciados` (definido no backend; já respeita lixeira).
    - Mensagens de erro diferenciadas para 401/403 vs outros erros.
    """
    try:
        r = req_get("/me/projetos/gerenciados")
        if r.status_code == 200:
            return r.json() or []
        elif r.status_code in (401, 403):
            st.warning("Você não tem projetos gerenciados ou não tem permissão.")
            return []
        else:
            st.error(f"Falha ao buscar projetos gerenciados (HTTP {r.status_code})")
            st.caption(r.text)
            return []
    except Exception as e:
        st.error(f"Erro ao buscar projetos: {e}")
        return []

# ======================================================================================
# UI — Upload e seleção de tipo de projeto
# ======================================================================================
st.title("📤 Processamento de Novos Relatórios")
st.markdown("Envie novos relatórios (.docx, .pdf) para serem processados.")

# Tipos permitidos (aplicando RBAC do backend)
tipos_disponiveis = get_lista_tipos_projeto()
if not tipos_disponiveis:
    st.error("Não foi possível carregar os tipos de projeto da API.")
    st.stop()

tipo_sel = st.selectbox("Tipo de projeto", tipos_disponiveis, key="tipo_projeto_select")

uploaded_files = st.file_uploader(
    "Selecione um ou mais relatórios",
    type=["docx", "pdf"],
    accept_multiple_files=True,
    key="uploader_relatorios",
)

# ======================================================================================
# Envio para a API e *polling* de status
# ======================================================================================
if uploaded_files and st.button("Processar relatórios", key="btn_processar"):
    # Monta payload multipart com os arquivos selecionados
    files_to_send = [
        ("files", (f.name, f.getvalue(), f.type or "application/octet-stream"))
        for f in uploaded_files
    ]
    data_payload = {"project_type": tipo_sel}

    # Usa `req_post` para garantir refresh + retry (wrapper do projeto)
    resp = req_post(
        "/processar-relatorios/",
        files=files_to_send,
        data=data_payload,
        headers=api_headers(),   # mantém headers; multipart é tratado pelo requests
        timeout=60,
    )

    if resp.status_code in (200, 202):
        task = resp.json()
        task_id = task.get("task_id") or task.get("id") or task.get("taskId")
        st.success("Upload enviado. Acompanhe o processamento...")

        # Polling simples de status (até ~90s) — mantém lógica original
        if task_id:
            status_box = st.empty()
            progress = st.empty()

            max_wait = 90      # tempo máximo esperando (segundos)
            interval = 1.5     # intervalo entre consultas (segundos)
            steps = int(max_wait / interval)

            with st.spinner("Processando relatório..."):
                for i in range(steps):
                    status_resp = req_get(
                        f"/tasks/status/{task_id}",
                        headers=api_headers(),
                        timeout=15,
                    )

                    if status_resp.status_code != 200:
                        progress.empty()
                        status_box.warning(f"Falha ao consultar status (HTTP {status_resp.status_code})")
                        st.caption(status_resp.text)
                        break

                    info = status_resp.json()
                    estado = (info.get("status") or "").lower()

                    if estado in {"pendente", "processando"}:
                        pct = int((i + 1) / steps * 100)
                        progress.progress(pct, text=f"Processando... {pct}%")
                    elif estado in {"concluido", "done"}:
                        progress.empty()
                        status_box.success(info.get("detail") or "Processado com sucesso.")
                        break
                    elif estado in {"falhou", "failed"}:
                        progress.empty()
                        status_box.error(info.get("detail") or "Falha no processamento.")
                        break

                    time.sleep(interval)
                else:
                    # saiu pelo timeout sem concluir
                    progress.empty()
                    status_box.warning("O processamento está demorando mais que o esperado. Tente checar novamente em alguns instantes.")
    else:
        st.error(f"Falha ao enviar (HTTP {resp.status_code})")
        st.caption(resp.text)

# ======================================================================================
# Histórico — Projetos gerenciados com ação de Soft Delete
# ======================================================================================
st.markdown("---")
st.subheader("Histórico de Relatórios")

projetos = _load_my_projects()

if not projetos:
    st.info("Nenhum projeto gerenciado por você (ou todos já estão na lixeira).")
else:
    for p in projetos:
        codigo = p.get("codigo_projeto") or ""
        nome   = p.get("nome_projeto") or codigo

        with st.expander(f"{nome}  •  ({codigo})", expanded=False):
            # legenda + linha flex (input cresce; botão mantém altura/tema vermelho)
            st.caption("Motivo (opcional)")
            st.markdown('<div class="soft-row">', unsafe_allow_html=True)

            motivo_val = st.text_input(
                "Motivo (opcional)",
                key=f"mot_{codigo}",
                placeholder="Descreva por que este projeto deve ir para a lixeira…",
                label_visibility="collapsed",
            )

            soft_clicked = st.button(
                "🗑️ Soft Delete",
                key=f"softdel_{codigo}",
                type="primary",               # pega o CSS vermelho do topo
            )

            st.markdown('</div>', unsafe_allow_html=True)

            if soft_clicked:
                try:
                    resp = req_post(
                        f"/projetos/{codigo}/soft-delete",
                        json={"motivo": (motivo_val or "").strip() or None},
                        headers=api_headers(),
                        timeout=15,
                    )
                    if resp.status_code == 200:
                        st.toast("Projeto enviado para a lixeira.", icon="✅")
                        st.rerun()
                    else:
                        msg = resp.json().get("detail") if "application/json" in resp.headers.get("content-type","") else resp.text
                        st.error(msg or f"Falha (HTTP {resp.status_code})")
                except Exception as e:
                    st.error(f"Erro: {e}")

    # Botão de atualizar DEPOIS da lista (evita pulo visual)
    st.divider()
    if st.button("Atualizar lista", use_container_width=False):
        st.rerun()