import streamlit as st
import requests
import pandas as pd
import altair as alt
import plotly.graph_objects as go 

# --- Configuração da Página ---
st.set_page_config(
    page_title="Detalhe do Projeto",
    page_icon="📑",
    layout="wide"
)

# --- CSS CUSTOMIZADO (Sem mudança) ---
st.markdown("""
<style>
     header {visibility: hidden;}
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    .badge-green { display: inline-block; padding: 6px 12px; background-color: #D4EDDA; color: #155724; border-radius: 16px; font-weight: bold; font-size: 0.9rem; text-align: center; float: right; }
    .badge-yellow { display: inline-block; padding: 6px 12px; background-color: #FFF3CD; color: #856404; border-radius: 16px; font-weight: bold; font-size: 0.9rem; text-align: center; float: right; }
    .badge-red { display: inline-block; padding: 6px 12px; background-color: #F8D7DA; color: #721C24; border-radius: 16px; font-weight: bold; font-size: 0.9rem; text-align: center; float: right; }
    .metric-card { padding: 1.5rem; border-radius: 0.5rem; margin-bottom: 1rem; }
    .metric-card-gray { background-color: #f0f2f6; }
    .metric-card-orange { background-color: #FFF2E6; }
    .metric-card-red { background-color: #FFEBEB; }
    .metric-card span:nth-child(1) { font-size: 1rem !important; color: #555555 !important; font-weight: 600 !important; }
    .metric-card span:nth-child(2) { font-size: 2rem !important; font-weight: 700 !important; color: #000000 !important; }
</style>
""", unsafe_allow_html=True)

API_URL = "http://127.0.0.1:8000"

# --- FUNÇÕES DE CHAMADA DA API (MODIFICADAS) ---
@st.cache_data(ttl=10)
def get_kpi_history(project_code, kpi_name):
    """
    NOVA FUNÇÃO: Busca o histórico de um KPI específico.
    """
    if not project_code or not kpi_name: return []
    try:
        # Nota: O nome do KPI deve ser "URL-encoded" (ex: "Custo Realizado" -> "Custo%20Realizado")
        # O requests faz isso automaticamente.
        response = requests.get(f"{API_URL}/projeto/{project_code}/historico-kpi/{kpi_name}")
        if response.status_code == 200: 
            return response.json()
    except requests.ConnectionError: 
        return None
    return []

@st.cache_data(ttl=60)
def get_lista_projetos():
    try:
        response = requests.get(f"{API_URL}/projetos/lista/")
        if response.status_code == 200:
            return response.json()
    except requests.ConnectionError: return None
    return []

@st.cache_data(ttl=10)
def get_lista_sprints(project_code):
    if not project_code: return []
    try:
        response = requests.get(f"{API_URL}/projeto/{project_code}/lista-sprints/")
        if response.status_code == 200: return response.json()
    except requests.ConnectionError: return None
    return []

@st.cache_data(ttl=10)
def get_detalhe_relatorio(report_id):
    if not report_id: return None
    try:
        response = requests.get(f"{API_URL}/relatorio/detalhe/{report_id}")
        if response.status_code == 200: return response.json() 
    except requests.ConnectionError: return None
    return None

# A função get_historico_financeiro FOI REMOVIDA
# Ela era muito específica e agora está obsoleta.

# --- INÍCIO DO LAYOUT DA PÁGINA ---
st.title("📑 Visão Detalhada e Histórica do Projeto")
st.markdown("Selecione um projeto e depois o sprint desejado para carregar o status report.")

# --- MENU DROPDOWN 1: PROJETO (Sem mudança) ---
lista_projetos = get_lista_projetos()
if lista_projetos is None:
    st.error("🚨 **Erro de Conexão:** API do Back-end offline. O servidor `uvicorn` está rodando?")
    st.stop()
if not lista_projetos:
    st.warning("Nenhum projeto foi processado ainda. Envie relatórios na página 'Processar Relatórios'.")
    st.stop()
project_names_map = {p["name"]: p["code"] for p in lista_projetos}
selected_name = st.selectbox("Selecione um Projeto:", options=project_names_map.keys())
selected_code = project_names_map[selected_name]

# --- MENU DROPDOWN 2: SPRINT (Sem mudança) ---
lista_sprints = get_lista_sprints(selected_code)
if not lista_sprints:
    st.warning(f"O projeto '{selected_name}' não possui nenhum relatório de sprint processado.")
    st.stop()
sprint_names_map = {f"Sprint {s['sprint_number']} (ID Relatório: {s['report_id']})": s['report_id'] for s in lista_sprints}
selected_sprint_name = st.selectbox("Selecione o Sprint (Histórico):", options=sprint_names_map.keys())
selected_report_id = sprint_names_map[selected_sprint_name]

# --- CARREGA OS DADOS DO PROJETO E SPRINT SELECIONADOS ---
with st.spinner(f"Carregando dados reais do '{selected_name}' (Sprint {selected_report_id})..."):
    dados_api = get_detalhe_relatorio(selected_report_id)
if not dados_api:
    st.error("Não foi possível carregar os detalhes deste relatório.")
    st.stop()

# --- DADOS PROCESSADOS (MODIFICADO) ---
projeto = dados_api.get("projeto", {})
milestones = dados_api.get("milestones", [])
kpis = dados_api.get("kpis", []) # <- NOVO: Pega a lista de KPIs

# --- LINHA 1: Título e Badge de Status (Sem mudança) ---
col1, col2 = st.columns([4, 1])
with col1:
    st.header(f"Status Report: {projeto.get('project_name', 'N/A')}") 
with col2:
    status_atual = projeto.get('overall_status', 'N/A')
    if status_atual == "Em Dia": st.markdown("<br><span class='badge-green'>✅ Em Dia</span>", unsafe_allow_html=True)
    elif status_atual == "Em Risco": st.markdown(f"<br><span class='badge-yellow'>⚠️ {status_atual}</span>", unsafe_allow_html=True)
    else: st.markdown(f"<br><span class='badge-red'>❌ {status_atual}</span>", unsafe_allow_html=True)

# --- SEÇÃO DE ANÁLISE DE MUDANÇA DE STATUS (Sem mudança) ---
status_anterior = projeto.get('status_anterior') 
if status_anterior and status_anterior != status_atual:
    if (status_atual == "Atrasado" and status_anterior == "Em Risco") or \
       (status_atual == "Em Risco" and status_anterior == "Em Dia"):
        st.error(f"🔺 **ALERTA DE STATUS (PIOROU):** O projeto mudou de **'{status_anterior}'** para **'{status_atual}'** nesta sprint.")
    elif (status_atual == "Em Dia" and status_anterior != "Em Dia"):
         st.success(f"✅ **MELHORIA DE STATUS:** O projeto melhorou de **'{status_anterior}'** para **'{status_atual}'** nesta sprint!")
elif status_anterior and status_anterior == status_atual:
    st.info(f"ℹ️ **Manutenção de Status:** O projeto permanece **'{status_atual}'** (igual ao sprint anterior).")
st.divider()

# --- LINHA 2: Metadados (Sem mudança) ---
with st.container():
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("👤 **Reporte de**"); st.markdown(f"### {projeto.get('project_manager', 'N/A')}")
    with col2:
        st.markdown("📅 **Data do Relatório**"); st.markdown(f"### {projeto.get('report_date', 'N/A')}") 
    with col3:
        st.markdown("#️⃣ **Código**"); st.markdown(f"### {projeto.get('project_code', 'N/A')}")
    with col4:
        st.markdown("🔄 **Sprint Selecionada**"); st.markdown(f"### Sprint {projeto.get('sprint_number', 0)}") 


# --- INÍCIO DAS TABS (MODIFICADO) ---
tab_contexto, tab_kpis, tab_metas = st.tabs([
    "🤖 Sumário, Riscos e Próximos Passos",
    "📊 Métricas Chave (KPIs)", # <- ABA FINANCEIRO RENOMEADA
    "📅 Acompanhamento de Metas"
])


# --- ABA 1: CONTEXTO (SUMÁRIO, RISCOS E PRÓXIMOS PASSOS) (Sem mudança) ---
with tab_contexto: 
    col1, col2, col3 = st.columns(3) 
    with col1:
        with st.container(border=True, height=350): 
            st.subheader("🤖 Sumário Executivo (Gerado por IA)")
            st.markdown(projeto.get('executive_summary', 'N/A'), unsafe_allow_html=True)
    with col2:
        with st.container(border=True, height=350):
            st.subheader("🛡️ Riscos e Impedimentos")
            riscos_texto_bruto = projeto.get('risks_and_impediments') 
            riscos_texto_lower = (riscos_texto_bruto or "").lower() 
            riscos_texto_formatado = (riscos_texto_bruto or 'Nenhum risco identificado.').replace('\n', '  \n')
            if (not riscos_texto_bruto) or ("nenhum risco" in riscos_texto_lower) or (riscos_texto_lower.startswith("resolvido")):
                st.success(f"✔️  \n{riscos_texto_formatado}") 
            else:
                st.error(f"❌  \n{riscos_texto_formatado}")
    with col3:
        with st.container(border=True, height=350):
            st.subheader("🎯 Próximos Passos")
            next_steps_texto = projeto.get('next_steps') 
            if not next_steps_texto or next_steps_texto.strip() == "":
                st.info("Nenhum próximo passo foi definido neste relatório.")
            else:
                st.markdown(next_steps_texto, unsafe_allow_html=True) 


# --- ABA 2: KPIs (ANTIGA FINANCEIRO) (MODIFICADA) ---
with tab_kpis: 
    st.subheader("📊 Métricas Chave (KPIs) do Período")
    
    # Tenta encontrar um KPI de variação para o alerta
    alerta_kpi = next((k for k in kpis if "Variação" in k.get('kpi_name', '')), None)
    if alerta_kpi and alerta_kpi.get('kpi_value_text') and "estouro" in alerta_kpi['kpi_value_text'].lower():
        st.warning(f"🔺 **Alerta de Variação:** {alerta_kpi['kpi_value_text']}", icon="⚠️")
    
    # Renderiza os KPIs dinamicamente
    kpis_financeiros = [k for k in kpis if k.get('kpi_category') == 'Financeiro']
    kpis_outros = [k for k in kpis if k.get('kpi_category') != 'Financeiro']

    if not kpis:
        st.info("Nenhuma métrica (KPI) foi extraída para este relatório.")
    else:
        # Renderiza KPIs Financeiros
        if kpis_financeiros:
            st.markdown("#### Métricas Financeiras")
            # Usa o CSS customizado para os cards
            cols_fin = st.columns(len(kpis_financeiros))
            for i, kpi in enumerate(kpis_financeiros):
                valor_display = kpi.get('kpi_value_text') or f"{kpi.get('kpi_value_numeric', 0):,.2f}"
                with cols_fin[i]:
                    st.markdown(f"""
                        <div class="metric-card metric-card-gray">
                        <span>{kpi.get('kpi_name', 'N/A')}</span><br>
                        <span>{valor_display}</span>
                        </div>
                    """, unsafe_allow_html=True)
        
        # Renderiza Outros KPIs
        if kpis_outros:
            st.markdown("#### Outras Métricas")
            cols_outros = st.columns(len(kpis_outros))
            for i, kpi in enumerate(kpis_outros):
                valor_display = kpi.get('kpi_value_text') or f"{kpi.get('kpi_value_numeric', 0):.2f}"
                with cols_outros[i]:
                     st.markdown(f"""
                        <div class="metric-card metric-card-gray">
                        <span>{kpi.get('kpi_name', 'N/A')}</span><br>
                        <span>{valor_display}</span>
                        </div>
                    """, unsafe_allow_html=True)
    
    st.divider()

    # --- Gráfico de Gauge (Modificado para ler KPIs) ---
    st.subheader("Utilização do Orçamento Total (se aplicável)")
    
    # O budget_total agora vem do objeto 'projeto' (que é o "pai")
    budget_total_projeto = projeto.get('budget_total', 0.0) 
    
    # O Custo Realizado agora vem da lista de KPIs
    cost_kpi = next((k for k in kpis if k.get('kpi_name') == 'Custo Realizado'), None)
    
    if cost_kpi and budget_total_projeto > 0:
        budget = budget_total_projeto
        cost_total_acumulado = cost_kpi.get('kpi_value_numeric', 0.0)
        
        try:
            utilizacao_pct = (cost_total_acumulado / budget)
            bar_color = "#FFA500" 
            if utilizacao_pct > 0.9: bar_color = "#F8D7DA" 
            elif utilizacao_pct > 0.75: bar_color = "#FFF3CD" 
            
            fig = go.Figure(go.Indicator(
                mode = "gauge+number", # Simplificado sem o 'delta'
                value = cost_total_acumulado,
                number = {'prefix': "R$ ", 'valueformat': ',.2f'},
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': f"Custo Acumulado ({utilizacao_pct:.1%}) <br> Orçamento Total: R$ {budget:,.2f}", 'font': {'size': 16}},
                gauge = {
                    'axis': {'range': [0, budget], 'tickwidth': 1, 'tickcolor': "darkblue"},
                    'bar': {'color': bar_color}, 'bgcolor': "white", 'borderwidth': 2, 'bordercolor': "gray",
                    'steps': [
                        {'range': [0, budget * 0.75], 'color': '#D4EDDA'},
                        {'range': [budget * 0.75, budget * 0.9], 'color': '#FFF3CD'},
                    ],
                    'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': budget * 0.95}
                }
            ))
            fig.update_layout(height=350, margin=dict(l=20, r=20, t=80, b=20))
            st.plotly_chart(fig, use_container_width=True)
            
        except ZeroDivisionError: 
            st.info("Orçamento Total é zero. Não é possível exibir o medidor.")
    else:
        st.info("KPIs de 'Custo Realizado' não encontrados neste relatório ou 'Orçamento Total' não definido para o projeto. Não é possível exibir o medidor.")
        
    st.divider()
    
    # --- Gráfico de Tendência (MODIFICADO DE VOLTA) ---
    st.subheader("📈 Análise de Tendência (Burn Rate)")
    
    # Chama a nova função, buscando especificamente o KPI "Custo Realizado"
    historico_data = get_kpi_history(selected_code, "Custo Realizado") 
    
    if historico_data and len(historico_data) > 1:
        try:
            df_historico = pd.DataFrame(historico_data)
            
            # Renomeia as colunas para bater com o que o gráfico espera
            df_historico = df_historico.rename(columns={
                "sprint_number": "Sprint", 
                "cost_realized": "Custo Acumulado", 
                "budget_total": "Orçamento Total (Teto)"
            })
            
            # Recria o gráfico (este é o código do seu arquivo original)
            df_melted = df_historico.melt('Sprint', var_name='Métrica', value_name='Valor (R$)')
            
            base = alt.Chart(df_melted).mark_line(point=True).encode(
                x=alt.X('Sprint:O', title='Sprint'), 
                y=alt.Y('Valor (R$):Q', title='Valor (R$)'),
                tooltip=['Sprint', 'Métrica', 'Valor (R$)']
            ).interactive() 
            
            domain_ = ['Custo Acumulado', 'Orçamento Total (Teto)']
            range_ = ['#FFA500', '#1C83E1'] 
            
            chart_with_colors = base.encode(
                color=alt.Color('Métrica', scale=alt.Scale(domain=domain_, range=range_))
            )
            
            st.altair_chart(chart_with_colors, use_container_width=True)
            
        except Exception as e:
            st.error(f"Erro ao renderizar gráfico: {e}")
            st.write(df_historico) 
            
    elif historico_data and len(historico_data) == 1:
        st.info("O gráfico de tendência (Burn Rate) aparecerá assim que você enviar o próximo relatório de Sprint.")
    else:
        st.warning("Não há dados históricos suficientes (com o KPI 'Custo Realizado') para gerar um gráfico de tendência.")
        

# --- ABA 3: METAS (MILESTONES) (Sem mudança) ---
with tab_metas: 
    
    if milestones:
        df_milestones = pd.DataFrame(milestones)
        df_milestones.index = df_milestones.index + 1
        
        # --- Bloco do Donut Chart (Sem mudança) ---
        st.subheader("Resumo Visual dos Status")
        try:
            status_counts = df_milestones['status'].value_counts().reset_index()
            status_counts.columns = ['Status', 'Contagem']
            
            domain_status = ['Concluído', 'Em Andamento', 'Atrasado', 'Pendente', 'Em Risco']
            range_status = ['#77C66E', '#5DA5DA', '#ED6E6D', '#B2B2B2', '#FAA43A'] 
            donut_chart = alt.Chart(status_counts).mark_arc(outerRadius=120, innerRadius=80).encode(
                theta=alt.Theta("Contagem:Q", stack=True), 
                color=alt.Color("Status:N", title="Status", 
                              scale=alt.Scale(domain=domain_status, range=range_status)),
                tooltip=["Status", "Contagem"] 
            ).properties(title="Distribuição de Status dos Milestones")
            
            st.altair_chart(donut_chart, use_container_width=True)
        except Exception as e:
            st.warning(f"Não foi possível renderizar o gráfico de status: {e}")
            
        st.divider()
        
        # --- Bloco da Tabela (Sem mudança) ---
        st.subheader(f"📅 Acompanhamento de Milestones (do Sprint {projeto.get('sprint_number', 0)})")

        df_para_exibir = df_milestones

        def highlight_slippage(row):
            return ['background-color: #FFF2E6'] * len(row) if row.get('slippage', False) else [''] * len(row)

        try:
            st.dataframe(
                df_milestones.style.apply(highlight_slippage, axis=1), 
                use_container_width=True,
                column_config = {
                    "description": st.column_config.TextColumn("Descrição"),
                    "status": st.column_config.TextColumn("Status"),
                    "date_planned": st.column_config.TextColumn("Data Planejada"),
                    "date_actual_or_revised": st.column_config.TextColumn("Data Real/Revisada"),
                    "milestone_history_id": None, "report_id_fk": None, "slippage": None 
                }
            )
        except Exception as e:
            st.error(f"Erro ao estilizar tabela de milestones: {e}")
            st.dataframe(df_milestones, use_container_width=True)

    else:
        st.info("Nenhum milestone foi extraído para este relatório de sprint.")