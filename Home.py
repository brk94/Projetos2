import streamlit as st

# --- Configuração da Página ---
st.set_page_config(
    page_title="Home | Projeto MC Sonae",
    page_icon="📈",
    layout="wide"
)

# --- Conteúdo Principal (Boas-Vindas) ---

st.title("Bem-vindo ao Dashboard de Automação de Projetos MC Sonae")
st.markdown("### 🚀 Desenvolvido pelo **Grupo 1** | **CESAR School - Projetos 2**")
st.markdown("---")

# NOTA: Substitua o URL abaixo pela imagem principal do seu projeto (Ex: O banner do Kickoff)
# Este é um placeholder visual genérico de dashboards
st.image("https://images.pexels.com/photos/3183150/pexels-photo-3183150.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=1", 
         caption="Desafio CESAR School & MC Sonae: Automação da Comunicação de Projetos")

st.header("O que este dashboard faz?")
st.markdown("""
Esta aplicação é a solução funcional para o desafio de automatizar a comunicação de resultados de projetos na MC Sonae.

Nosso sistema transforma relatórios dispersos (`.doc`, `.xls`, `.pdf`) em insights visuais e centralizados, permitindo o acompanhamento de KPIs e marcos de investimento em tempo real.
""")

st.subheader("Como navegar:")
st.info("""
👈 **Use o menu lateral** para acessar as principais funcionalidades:

* **Dashboard Executivo:** Acesse os KPIs, status e acompanhe os marcos de todos os projetos.
* **Explorar Projetos:** Filtre um projeto específico para ver seu resumo de IA e rastreabilidade de dados.
* **Processar Relatórios:** Envie novos documentos para análise e ingestão no sistema.
* **Sobre o Projeto:** Entenda o desafio completo, a arquitetura da nossa solução (Scraper, IA, API) e quem somos nós.
""")

# Créditos da equipe
with st.expander("Conheça a Equipe de Desenvolvimento (Grupo 1)"):
    st.markdown("""
    - André Coelho
    - Carlos Eduardo
    - João Danilo
    - João Victor
    - Paulo Eduardo
    - Pedro Araújo
    - Pedro Leite
    """)

# --- CSS para esconder o menu padrão e rodapé do Streamlit ---
st.markdown(
    """
    <style>
    /* Isso esconde o menu e o rodapé padrão do Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True
)