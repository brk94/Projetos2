import streamlit as st

# --- Configuração da Página ---
st.set_page_config(
    page_title="Sobre o Projeto | MC Sonae",
    page_icon="📊",  # Ícone que representa dados/dashboard
    layout="wide"
)

# --- Conteúdo Principal ---
st.title("📊 Visão de Projeto: Automação de Comunicação na MC Sonae")
st.markdown("""
Este aplicativo é a solução desenvolvida pelo **Grupo 1** do curso de **Projetos 2 da CESAR School**, 
em resposta a um desafio estratégico apresentado pela **MC Sonae**.
""")

st.markdown("---")

st.markdown("### 🎯 O Desafio")
st.markdown("""
A MC Sonae enfrenta um desafio recorrente há 10 anos: a dificuldade em automatizar a criação de conteúdo 
para comunicar o progresso e os resultados dos seus inúmeros projetos internos. O processo manual existente 
gera baixa visibilidade (interna e externa), desmotiva as equipes por ser um "passo extra" e limita a capacidade de investimento 
estratégico, ao dificultar o acompanhamento de marcos importantes.
""")

st.markdown("### 💡 Nossa Solução")
st.markdown("""
Nossa solução é uma plataforma web que ataca diretamente essa dor, automatizando o fluxo de 
informação do relatório bruto até o insight visual. A ideia foi escolhida por sua viabilidade técnica, alinhamento com o cronograma e por resolver a incerteza do projeto através de uma arquitetura definida.

A arquitetura é composta por:

* **1. Scraper Inteligente:** Um motor de extração de dados capaz de ler múltiplos formatos de relatórios 
    (.doc, .xls, .pdf) que hoje estão dispersos pela organização.
* **2. Camada de IA (NLP & OCR):** Utiliza Processamento de Linguagem Natural e Reconhecimento Ótico de 
    Caracteres para limpar, resumir, classificar e extrair KPIs-chave dos textos não estruturados.
* **3. API REST Centralizadora:** Um back-end robusto construído em **FastAPI** que serve como o "cérebro" do 
    sistema, entregando os dados já processados e estruturados em um esquema canônico definido.
* **4. Dashboard Interativo (Este App):** Este front-end em Streamlit consome a API e apresenta as 
    informações de forma clara e visual, permitindo que gestores tomem decisões rápidas e acompanhem 
    o status dos projetos em tempo real.
""")

st.markdown("### 🧭 Como Usar")
st.markdown("""
Navegue pelas diferentes seções do dashboard usando o menu lateral para explorar os KPIs consolidados, 
o progresso dos projetos e os marcos de investimento extraídos automaticamente dos relatórios.
""")

st.markdown("### ⚠️ Disclaimer Acadêmico")
st.markdown("""
Este projeto é um protótipo funcional desenvolvido para fins estritamente acadêmicos, como requisito 
do curso de Projetos 2 da CESAR School. **Não é uma ferramenta oficial afiliada ou endossada pela 
MC Sonae.** Todos os dados apresentados (se houver) são para fins de demonstração.
""")

st.markdown("### 🙏 Agradecimentos")
st.markdown("""
Agradecemos à **MC Sonae** pela parceria e por fornecer um desafio real e de grande impacto no mercado. 
Agradecemos também aos nossos professores e monitores da **CESAR School** pelo direcionamento e 
metodologia aplicados neste projeto.
""")


# --- CSS para esconder o menu principal e rodapé do Streamlit ---
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True
)