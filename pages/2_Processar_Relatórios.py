# pages/2_Processar_Relatórios.py
import streamlit as st
import requests
import pandas as pd
import time

from ui_nav import ensure_session_and_perms, render_sidebar, api_headers

st.set_page_config(page_title="Processar Relatórios", page_icon="📤", layout="centered")

# Esconde nav nativa
st.markdown("""
<style>
[data-testid="stSidebarNav"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# Guard de sessão + perms
if not st.session_state.get("logged_in") or not st.session_state.get("auth_token"):
    st.switch_page("Home.py")
    
# Sessão + permissões (redireciona pra Home automaticamente se não logado)
perms = ensure_session_and_perms()

# Sidebar unificada (marcando a página atual)
render_sidebar(perms, current_page="processar")

API_URL = "http://127.0.0.1:8000"

def get_lista_tipos_projeto():
    try:
        r = requests.get(f"{API_URL}/projetos/tipos", headers=api_headers(), timeout=15)
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
    except requests.ConnectionError:
        st.error("API offline.")
        return []

st.title("📤 Processamento de Novos Relatórios")
st.markdown("Envie novos relatórios (.docx, .pdf) para serem processados.")

tipos_disponiveis = get_lista_tipos_projeto()
if not tipos_disponiveis:
    st.error("Não foi possível carregar os tipos de projeto da API.")
    st.stop()

tipo_sel = st.selectbox("Tipo de projeto", tipos_disponiveis, key="tipo_projeto_select")

uploaded_files = st.file_uploader(
    "Selecione um ou mais relatórios",
    type=["docx", "pdf"],
    accept_multiple_files=True,
    key="uploader_relatorios"
)

if uploaded_files and st.button("Processar relatórios", key="btn_processar"):
    files_to_send = [
        ("files", (f.name, f.getvalue(), f.type or "application/octet-stream"))
        for f in uploaded_files
    ]
    data_payload = {"project_type": tipo_sel}

    resp = requests.post(
        f"{API_URL}/processar-relatorios/",
        files=files_to_send,
        data=data_payload,
        headers=api_headers(),
        timeout=60,
    )

    if resp.status_code in (200, 202):
        task = resp.json()
        task_id = task.get("task_id") or task.get("id") or task.get("taskId")
        st.success("Upload enviado. Acompanhe o processamento...")

        if task_id:
            while True:
                status_resp = requests.get(
                    f"{API_URL}/tasks/status/{task_id}",
                    headers=api_headers(),
                    timeout=15,
                )
                if status_resp.status_code == 200:
                    info = status_resp.json()
                    st.write(info)
                    if info.get("status") in {"concluido", "falhou"}:
                        break
                else:
                    st.warning(f"Falha ao consultar status (HTTP {status_resp.status_code})")
                    st.caption(status_resp.text)
                    break
                time.sleep(2)
    else:
        st.error(f"Falha ao enviar (HTTP {resp.status_code})")
        st.caption(resp.text)

st.markdown("---")
st.subheader("Histórico de Processamentos Recentes (Mock)")
mock_log_df = pd.DataFrame({
    "Arquivo": ["Relatorio_Semanal_App.pdf", "Status_Report_Logistica_Q3.xlsx", "Briefing_Projeto_Omega.docx"],
    "Status": ["Sucesso", "Sucesso", "Falha (Formato Inválido)"],
    "Data": ["14/09/2025 10:30", "13/09/2025 15:01", "13/09/2025 09:15"]
})
st.dataframe(mock_log_df, width='stretch')
