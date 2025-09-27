import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import date, timedelta

st.set_page_config(page_title="Performance de Marketing", page_icon="🎯", layout="wide")

st.title("🎯 Dashboard de Performance de Marketing")
st.markdown("Análise de funil, canais e retorno sobre investimento em campanhas.")
st.markdown("<p style='font-size: 0.8rem; font-style: italic; color: #888;'>Nota: Dados fictícios para demonstração.</p>", unsafe_allow_html=True)


# --- DADOS MOCK ---
@st.cache_data
def create_mock_data(start_date, end_date):
    days = (end_date - start_date).days + 1
    dates = pd.to_datetime([start_date + timedelta(days=i) for i in range(days)])
    data = pd.DataFrame({
        'data': dates,
        'investimento': np.random.uniform(500, 1500, days),
        'impressoes': np.random.randint(80000, 200000, days),
        'cliques': np.random.randint(2000, 5000, days),
        'conversoes': np.random.randint(50, 200, days),
    })
    data['receita'] = data['conversoes'] * np.random.uniform(80, 120, days)
    return data

# --- FILTRO DE DATA ---
st.sidebar.header("Filtros")
date_range = st.sidebar.date_input(
    "Selecione o Período de Análise",
    (date.today() - timedelta(days=90), date.today()),
    format="DD/MM/YYYY"
)

# --- LÓGICA DE FILTRO ---
try:
    start_date, end_date = date_range
except ValueError:
    st.error("Selecione um intervalo de datas válido.")
    st.stop()

df = create_mock_data(start_date, end_date)

# --- KPIs DINÂMICOS ---
total_investido = df['investimento'].sum()
total_receita = df['receita'].sum()
total_conversoes = df['conversoes'].sum()
roi = (total_receita - total_investido) / total_investido if total_investido else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Investimento Total", f"R$ {total_investido:,.2f}")
col2.metric("Receita Total", f"R$ {total_receita:,.2f}")
col3.metric("Conversões", f"{total_conversoes:,}")
col4.metric("ROI (Retorno s/ Invest.)", f"{roi:.2%}")

st.divider()

# --- GRÁFICOS ---
tab1, tab2 = st.tabs(["**Visão Geral da Performance**", "**Análise de Retorno (ROI)**"])

with tab1:
    st.subheader("Performance ao Longo do Tempo")
    df_resumo_diario = df.set_index('data')
    st.line_chart(df_resumo_diario[['investimento', 'receita']])

with tab2:
    st.subheader("Composição do Retorno Sobre Investimento (ROI)")
    fig = go.Figure(go.Waterfall(
        name="Análise de ROI",
        orientation="v",
        measure=["relative", "relative", "total"],
        x=["Investimento", "Receita Gerada", "Lucro Bruto"],
        textposition="outside",
        text=[f"R$ {total_investido:,.0f}", f"R$ {total_receita:,.0f}", f"R$ {total_receita - total_investido:,.0f}"],
        y=[-total_investido, total_receita, 0],
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        decreasing={"marker": {"color": "#d62728"}},
        increasing={"marker": {"color": "#2ca02c"}},
        totals={"marker": {"color": "#1f77b4"}}
    ))
    fig.update_layout(title="Demonstrativo de ROI", showlegend=True, template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)