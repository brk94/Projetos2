import streamlit as st
import pandas as pd
import requests

API_URL = "http://127.0.0.1:8000"

# --- Configuração da Página ---
st.set_page_config(
    page_title="Processar Relatórios",
    page_icon="📤",
    layout="centered"
)

@st.cache_data(ttl=3600) # Cache de 1 hora
def get_lista_tipos_projeto():
    """ Busca os tipos de projeto permitidos da API. """
    try:
        response = requests.get(f"{API_URL}/projetos/tipos/")
        if response.status_code == 200:
            return response.json()
    except requests.ConnectionError:
        return ["ERRO: API OFFLINE"] # Retorna um erro amigável
    return []

# --- CONTEÚDO PRINCIPAL ---
st.title("📤 Processamento de Novos Relatórios")
st.markdown("Envie novos relatórios (.doc, .xls, .pdf) para serem processados.")

# --- SELETOR DE TIPO DE PROJETO ---
# Busca os tipos da API
tipos_disponiveis = get_lista_tipos_projeto()

if not tipos_disponiveis:
    st.error("Não foi possível carregar os tipos de projeto da API.")
    st.stop()

project_type = st.selectbox(
    "Selecione o TIPO de relatório que está enviando:",
    options=tipos_disponiveis 
)
st.info(f"Você selecionou o tipo: **{project_type}**")

# --- UPLOAD DE ARQUIVOS ---
uploaded_files = st.file_uploader(
    "Selecione os arquivos de relatório:",
    type=["doc", "docx", "xls", "xlsx", "pdf"],
    accept_multiple_files=True
)

st.markdown("---")

# --- LÓGICA DE ENVIO (MODIFICADA) ---
if st.button("Iniciar Processamento", type="primary"):
    if uploaded_files and project_type:
        
        files_to_send = [("files", (file.name, file.getvalue(), file.type)) for file in uploaded_files]
        
        # Enviamos o 'project_type', não o 'project_code'
        data_payload = {"project_type": project_type} 

        try:
            with st.spinner(f"Processando {len(uploaded_files)} arquivo(s) do tipo '{project_type}'..."):
                response = requests.post(
                    f"{API_URL}/processar-relatorios/", 
                    files=files_to_send,
                    data=data_payload # Envia o project_type
                )

            if response.status_code == 200:
                st.success(f"Processamento concluído!")
                st.json(response.json())
                st.cache_data.clear() 
            else:
                st.error(f"Erro da API ({response.status_code}): {response.text}")
        
        except requests.exceptions.ConnectionError:
            st.error("Erro: Não foi possível conectar à API. Você ligou o servidor 'uvicorn main:app'?")
        except Exception as e:
            st.error(f"Um erro inesperado ocorreu: {e}")
            
    else:
        st.warning("Você precisa selecionar um tipo e ao menos um arquivo.")

# ... (Tabela de log mock continua igual) ...
st.markdown("---")
st.subheader("Histórico de Processamentos Recentes (Mock)")
mock_log_df = pd.DataFrame({
    "Arquivo": ["Relatorio_Semanal_App.pdf", "Status_Report_Logistica_Q3.xlsx", "Briefing_Projeto_Omega.docx"],
    "Status": ["Sucesso", "Sucesso", "Falha (Formato Inválido)"],
    "Data": ["14/09/2025 10:30", "13/09/2025 15:01", "13/09/2025 09:15"]
})
st.dataframe(mock_log_df, width='stretch')