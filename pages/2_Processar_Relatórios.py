import streamlit as st
import time
import pandas as pd
import requests


# Configuração da Página
st.set_page_config(
    page_title="Processar Relatórios",
    page_icon="📤",
    layout="centered" # Centralizado fica melhor para uma página de upload
)

st.title("📤 Processamento de Novos Relatórios")
st.markdown("Envie novos relatórios (.doc, .xls, .pdf) para serem processados pela IA.")

# Requisito do Desafio: Aceitar múltiplos formatos
uploaded_files = st.file_uploader(
    "Selecione os arquivos de relatório:",
    type=["doc", "docx", "xls", "xlsx", "pdf"],
    accept_multiple_files=True
)

st.markdown("---")

if st.button("Iniciar Processamento", type="primary"):
    if uploaded_files:
        # Prepare os arquivos para enviar (formato multipart)
        files_to_send = [("files", (file.name, file.getvalue(), file.type)) for file in uploaded_files]

        try:
            # Chama a sua API FastAPI local!
            response = requests.post("http://127.0.0.1:8000/processar-relatorios/", files=files_to_send)

            if response.status_code == 200:
                st.success(f"Processamento concluído! Resposta da API: {response.json()}")
                st.cache_data.clear() 
            else:
                st.error(f"Erro da API: {response.text}")
        except requests.exceptions.ConnectionError:
            st.error("Erro: Não foi possível conectar à API. Você ligou o servidor 'uvicorn main:app'?")

# Tabela de log simulada
st.markdown("---")
st.subheader("Histórico de Processamentos Recentes")
mock_log_df = pd.DataFrame({
    "Arquivo": ["Relatorio_Semanal_App.pdf", "Status_Report_Logistica_Q3.xlsx", "Briefing_Projeto_Omega.docx"],
    "Status": ["Sucesso", "Sucesso", "Falha (Formato Inválido)"],
    "Data": ["14/09/2025 10:30", "13/09/2025 15:01", "13/09/2025 09:15"]
})
st.dataframe(mock_log_df, use_container_width=True)