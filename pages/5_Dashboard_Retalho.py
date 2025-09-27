import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import date, timedelta

st.set_page_config(page_title="Análise de Retalho", page_icon="🏪", layout="wide")

st.title("🏪 Análise de Operações de Retalho")
st.markdown("Painel de controle para performance de vendas, estoque e comportamento do consumidor.")
st.markdown("<p style='font-size: 0.8rem; font-style: italic; color: #888;'>Nota: Dados fictícios para demonstração.</p>", unsafe_allow_html=True)

# --- DADOS MOCK ---
@st.cache_data
def load_data():
    # Dados de vendas diárias para o gráfico de tendência
    dias_analise = 90
    datas = [date.today() - timedelta(days=i) for i in range(dias_analise)]
    datas.reverse()
    vendas_diarias = np.random.randint(25000, 45000, size=dias_analise) + np.sin(np.linspace(0, 2 * np.pi, dias_analise)) * 5000
    df_vendas_tempo = pd.DataFrame({'Data': datas, 'Vendas': vendas_diarias}).set_index('Data')
    
    # Dados de produtos por categoria
    produtos = {
        'categoria': ['Padaria', 'Laticínios', 'Hortifruti', 'Carnes', 'Padaria', 'Laticínios', 'Hortifruti', 'Carnes'],
        'produto': ['Pão Francês', 'Leite Integral', 'Banana Prata', 'Alcatra', 'Bolo de Chocolate', 'Queijo Minas', 'Maçã Fuji', 'Frango a Passarinho'],
        'vendas': np.random.randint(500, 2000, 8),
        'estoque': np.random.randint(100, 500, 8)
    }
    df_produtos = pd.DataFrame(produtos)
    return df_vendas_tempo, df_produtos

df_vendas_tempo, df_produtos = load_data()

# --- KPIs principais ---
col1, col2, col3 = st.columns(3)
col1.metric("Faturamento (90 dias)", f"R$ {df_vendas_tempo['Vendas'].sum()/1_000_000:.2f}M", "1.2% vs. Período Anterior")
col2.metric("NPS Consolidado", "52", "+3", "normal")
col3.metric("% de Quebra Médio", "4.8%", "-0.5%", "inverse")

st.divider()

# --- Análise de Vendas no Tempo e Cesta de Compras ---
st.subheader("Tendência de Vendas e Análise da Cesta de Compras")

col_grafico, col_metricas = st.columns([3, 1])

with col_grafico:
    st.line_chart(df_vendas_tempo)

with col_metricas:
    st.metric("Ticket Médio", "R$ 78,50", "+R$ 1,20")
    st.metric("Itens por Cesta", "4.2", "-0.1")
    st.metric("Taxa de Conversão na Loja", "65%", "+2.5%")


# --- Análise Interativa de Produtos ---
st.subheader("Análise de Vendas por Categoria")
categorias = ['Todas'] + list(df_produtos['categoria'].unique())
cat_selecionada = st.selectbox('Filtrar por Categoria:', options=categorias)

if cat_selecionada == 'Todas':
    df_filtrado = df_produtos
else:
    df_filtrado = df_produtos[df_produtos['categoria'] == cat_selecionada]

fig = px.bar(df_filtrado, x='produto', y='vendas', title=f'Vendas para: {cat_selecionada}',
             color='produto', template='plotly_white')
st.plotly_chart(fig, use_container_width=True)


# --- Tabela Avançada de Estoque ---
with st.expander("Clique para ver a Gestão de Estoque Detalhada"):
    st.subheader("Níveis de Estoque e Alertas")
    df_produtos['% estoque'] = (df_produtos['estoque'] / 500)
    st.dataframe(
        df_produtos,
        column_config={
            "produto": "Produto",
            "estoque": st.column_config.NumberColumn("Estoque (Un.)"),
            "% estoque": st.column_config.ProgressColumn(
                "Nível de Estoque",
                format="%.2f%%",
                min_value=0,
                max_value=1,
            ),
        },
        use_container_width=True,
        hide_index=True,
    )