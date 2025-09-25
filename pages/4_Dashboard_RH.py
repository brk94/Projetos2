import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Capital Humano", page_icon="🤝", layout="wide")

st.title("🤝 Dashboard de Capital Humano")
st.markdown("Análise da jornada do colaborador, da aquisição ao engajamento.")
st.markdown("<p style='font-size: 0.8rem; font-style: italic; color: #888;'>Nota: Dados fictícios para demonstração.</p>", unsafe_allow_html=True)

# --- DADOS MOCK ---
@st.cache_data
def load_data():
    data_sentimento = {
        'tema': ['Gestão', 'Benefícios', 'Carreira', 'Ambiente', 'Equilíbrio'],
        'positivo': [65, 88, 72, 81, 60],
        'neutro': [20, 10, 18, 12, 25],
        'negativo': [15, 2, 10, 7, 15]
    }
    df_sentimento = pd.DataFrame(data_sentimento)
    return df_sentimento

df_sentimento = load_data()

# --- KPIs ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Headcount Total", "1,824", "+28")
col2.metric("Turnover Anual", "12.1%", "1.1%", "inverse")
col3.metric("eNPS", "+45", "-2 pts")
col4.metric("Vagas em Aberto", "32", "+5")
st.divider()


# --- ABAS PARA JORNADA DO COLABORADOR ---
tab1, tab2, tab3 = st.tabs(["**1. Aquisição de Talentos**", "**2. Engajamento e Cultura**", "**3. Diversidade e Inclusão**"])

with tab1:
    st.subheader("Funil de Contratação (Último Trimestre)")
    fig = go.Figure(go.Funnel(
        y=["Candidaturas", "Triagem RH", "Entrevista Gestor", "Oferta", "Contratado"],
        x=[1250, 420, 150, 45, 32],
        textinfo="value+percent initial"
    ))
    fig.update_layout(template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Análise de Sentimento (Pesquisa de Clima Anual)")
    tema_selecionado = st.select_slider(
        "Selecione um tema para analisar:",
        options=df_sentimento['tema']
    )
    dados_tema = df_sentimento[df_sentimento['tema'] == tema_selecionado].iloc[0]

    col1, col2 = st.columns([1, 2])
    with col1:
        st.write(f"**Resultados para: {tema_selecionado}**")
        fig_donut = go.Figure(data=[go.Pie(
            labels=['Positivo', 'Neutro', 'Negativo'],
            values=[dados_tema['positivo'], dados_tema['neutro'], dados_tema['negativo']],
            hole=.5,
            marker_colors=['#2ca02c', '#ff7f0e', '#d62728']
        )])
        fig_donut.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig_donut, use_container_width=True)

    with col2:
        st.write("**Comentários em Destaque (Exemplos):**")
        st.info("💬 'O plano de carreira precisa ser mais transparente.'")
        st.success("👍 'Adoro os novos benefícios de bem-estar!'")
        st.warning("🤔 'A comunicação entre as áreas poderia melhorar.'")

with tab3:
    st.subheader("Composição da Força de Trabalho")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Distribuição por Gênero**")
        fig_genero = go.Figure(data=[go.Pie(labels=['Feminino', 'Masculino', 'Outro/Não informado'], values=[46, 52, 2])])
        st.plotly_chart(fig_genero, use_container_width=True)
    with col2:
        st.write("**Distribuição por Tempo de Casa**")
        fig_tempo = go.Figure(data=[go.Bar(
            x=['< 1 ano', '1-3 anos', '3-5 anos', '5+ anos'],
            y=[25, 40, 20, 15]
        )])
        st.plotly_chart(fig_tempo, use_container_width=True)