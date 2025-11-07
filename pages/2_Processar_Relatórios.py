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
from pathlib import Path
from base64 import b64encode

from ui_nav import garantir_sessao_e_permissoes, render_menu_lateral, api_headers, req_get, req_post

# ======================================================================================
# Configuração da página + CSS utilitário (apenas visual)
# ======================================================================================
st.set_page_config(page_title="Processar Relatórios", page_icon="📤", layout="centered")

# Esconde nav nativa e ajusta estilos de botão/linha flex
st.markdown(
    """
<style>
/* Oculta a navegação nativa da sidebar e os controles de colapso */
section[data-testid="stSidebar"] [data-testid="stSidebarNav"],
section[data-testid="stSidebar"] nav[aria-label="Page list"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarCollapseButton"],
button[kind="header"]{
  display: none !important;
}
/* ===== SIDEBAR: mantém botões brancos ===== */
section[data-testid="stSidebar"] div.stButton > button{
  background:#fff !important;
  border:1px solid #E2E8F0 !important;
  color:#1E293B !important;
  border-radius:8px !important;
  padding:.5rem 1rem !important;
  font-weight:500 !important;
  transition:all .2s ease-in-out !important;
}
section[data-testid="stSidebar"] div.stButton > button:hover{
  background:#F8FAFC !important; border-color:#CBD5E1 !important; transform:scale(1.02)!important;
}
section[data-testid="stSidebar"] div.stButton > button:active{ transform:scale(0.98)!important; }

/* ===== MAIN: primários (ex. “Processar relatórios”) AZUIS ===== */
.stApp [data-testid="stAppViewContainer"] div.stButton > 
button[data-testid="baseButton-primary"],
.stApp [data-testid="stAppViewContainer"] div.stButton > 
button[kind="primary"]{
  background:#2F5DE7 !important;
  border:1px solid #2F5DE7 !important;
  color:#fff !important;
  border-radius:8px !important;
  padding:.5rem 1rem !important;
  font-weight:500 !important;
  transition:all .2s ease-in-out !important;
  width:100% !important;
}
.stApp [data-testid="stAppViewContainer"] div.stButton > 
button[data-testid="baseButton-primary"]:hover,
.stApp [data-testid="stAppViewContainer"] div.stButton > 
button[kind="primary"]:hover{
  background:#2546c4 !important; border-color:#2546c4 !important; transform:scale(1.02)!important;
}
.stApp [data-testid="stAppViewContainer"] div.stButton > 
button[data-testid="baseButton-primary"]:active,
.stApp [data-testid="stAppViewContainer"] div.stButton > 
button[kind="primary"]:active{ transform:scale(0.98)!important; }

/* ===== MAIN: Soft Delete (secondary dentro de EXPANDER) VERMELHO ===== */
.stApp [data-testid="stAppViewContainer"] [data-testid="stExpander"] div.stButton > 
button[data-testid="baseButton-secondary"],
.stApp [data-testid="stAppViewContainer"] [data-testid="stExpander"] div.stButton > 
button[kind="secondary"]{
  background:#E0625F !important;
  border:1px solid #E0625F !important;
  color:#fff !important;
  border-radius:8px !important;
  padding:.5rem 1rem !important;
  font-weight:500 !important;
  transition:all .2s ease-in-out !important;
}
.stApp [data-testid="stAppViewContainer"] [data-testid="stExpander"] div.stButton > 
button[data-testid="baseButton-secondary"]:hover,
.stApp [data-testid="stAppViewContainer"] [data-testid="stExpander"] div.stButton > 
button[kind="secondary"]:hover{
  background:#d44a47 !important; border-color:#d44a47 !important; transform:scale(1.02)!important;
}
.stApp [data-testid="stAppViewContainer"] [data-testid="stExpander"] div.stButton > 
button[data-testid="baseButton-secondary"]:active,
.stApp [data-testid="stAppViewContainer"] [data-testid="stExpander"] div.stButton > 
button[kind="secondary"]:active{ transform:scale(0.98)!important; }

/* ===== Utilitário de linha ===== */
.soft-row { display:flex; gap:.75rem; align-items:center; }
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
# Adiciona classe main ao conteúdo principal
# ======================================================================================
st.markdown('<div class="main">', unsafe_allow_html=True)

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
ICON_PATH = Path(__file__).parent / "images" / "upload.png"
icon_b64 = b64encode(ICON_PATH.read_bytes()).decode()

st.markdown(f"""
<div class="title-row">
  <img src="data:image/png;base64,{icon_b64}" class="title-icon" alt="Upload icon" />
  <h1>Processamento de Novos Relatórios</h1>
</div>
<style>
.title-row {{
  display:flex; align-items:center; gap:.6rem; margin-bottom:.25rem;
}}
.title-row .title-icon {{
  width:72px; height:72px; object-fit:contain; border-radius:4px;
}}
.title-row h1 {{ margin:0; }}
</style>
""", unsafe_allow_html=True)

# Tipos permitidos (aplicando RBAC do backend)
tipos_disponiveis = get_lista_tipos_projeto()
if not tipos_disponiveis:
    st.error("Não foi possível carregar os tipos de projeto da API.")
    st.stop()

tipo_sel = st.selectbox("Tipo de projeto", tipos_disponiveis, key="tipo_projeto_select")

uploaded_files = st.file_uploader(
    "Selecione um relatório",
    type=["docx", "pdf"],
    accept_multiple_files=True,
    key="uploader_relatorios",
)

# ======================================================================================
# Envio para a API e *polling* de status
# ======================================================================================
if uploaded_files and st.button("Processar Relatório", key="btn_processar", type="primary", use_container_width=True):
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
            st.caption("Motivo (opcional)")
            st.markdown('<div class="soft-row">', unsafe_allow_html=True)

            motivo_val = st.text_input(
                "Motivo (opcional)",
                key=f"mot_{codigo}",
                placeholder="Descreva por que este projeto deve ir para a lixeira…",
                label_visibility="collapsed",
            )

            abrir_conf = st.button(
                "🗑️ Soft Delete",
                key=f"softdel_{codigo}",
                type="secondary",  
                use_container_width=True,
            )

            st.markdown('</div>', unsafe_allow_html=True)

            # Estado: abre/fecha o bloco de confirmação
            flag_key = f"ask_soft_{codigo}"
            if flag_key not in st.session_state:
                st.session_state[flag_key] = False
            if abrir_conf:
                st.session_state[flag_key] = True

            if st.session_state.get(flag_key, False):
                st.markdown("""
                <style>
                /* Neutraliza estilos vermelhos do expander só para a área abaixo */
                .neutral-actions div.stButton > button,
                .neutral-actions div.stButton > button[kind="secondary"],
                .neutral-actions div.stButton > button[data-testid="baseButton-secondary"]{
                background:#FFFFFF !important;
                border:1px solid #E2E8F0 !important;
                color:#1E293B !important;
                border-radius:8px !important;
                font-weight:500 !important;
                box-shadow:none !important;
                }
                .neutral-actions div.stButton > button:hover{
                background:#F8FAFC !important;
                border-color:#CBD5E1 !important;
                transform:none !important;
                }
                </style>
                """, unsafe_allow_html=True)

                st.warning(
                    f"Tem certeza que deseja enviar **{nome}** ({codigo}) para a lixeira?\n\n"
                    "• Ação **reversível**\n",
                    icon="⚠️",
                )
                if motivo_val:
                    st.caption(f"Motivo informado: _{motivo_val}_")

                # Área com botões neutros
                st.markdown('<div class="neutral-actions">', unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                with c1:
                    confirmar = st.button("Confirmar", key=f"confirm_{codigo}", use_container_width=True)
                with c2:
                    cancelar = st.button("Cancelar", key=f"cancel_{codigo}", use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

                if confirmar:
                    # fecha o aviso inline imediatamente
                    st.session_state[flag_key] = False
                    try:
                        resp = req_post(
                            f"/projetos/{codigo}/soft-delete",
                            json={"motivo": (motivo_val or "").strip() or None},
                            headers=api_headers(),
                            timeout=15,
                        )
                        if resp.status_code == 200:
                            st.toast("Projeto enviado para a lixeira.", icon="✅")
                            time.sleep(1.5)  # dá tempo de ver o toast
                            st.rerun()
                        else:
                            msg = resp.json().get("detail") if "application/json" in resp.headers.get("content-type","") else resp.text
                            st.toast("❌ Falha no soft delete.", icon="❌")
                            if msg:
                                st.caption(msg)  # opcional; pode remover se quiser apenas o toast
                    except Exception as e:
                        st.toast("❌ Erro ao contatar a API.", icon="❌")
                        st.caption(f"{e}")

                if cancelar:
                    st.session_state[flag_key] = False
                    st.toast("Ação cancelada.", icon="ℹ️")
                    time.sleep(1.5)  # espera ~2s e limpa a UI
                    st.rerun()

st.markdown('</div>', unsafe_allow_html=True)