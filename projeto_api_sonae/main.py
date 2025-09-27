# main.py (MODIFICADO)

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form
from typing import List
import io

# Nossos módulos locais de OOP

from . import config
from . import models 
from . import services 
from . import constants

# A NOVA ESTRUTURA DE PARSERS
from parsers.factory import ReportParserFactory

# ... (criação das tabelas continua igual) ...

app = FastAPI(title="API Projeto MC Sonae")

# --- INICIALIZAÇÃO DOS SERVIÇOS (MODIFICADO) ---
try:
    ai_service = services.AIService(
        nlp_model=config.nlp, 
        gemini_model=config.gemini_model,
        gemini_config=config.gemini_generation_config
    )
    
    # A Factory agora é importada de 'parsers.factory'
    parser_factory = ReportParserFactory(ai_service=ai_service)
    
    repository = services.DatabaseRepository(session_factory=config.SessionLocal)

    print("\n--- Todos os serviços (ORM) foram inicializados com sucesso! ---")

except Exception as e:
    print(f"\n--- FALHA CRÍTICA NA INICIALIZAÇÃO: {e} ---")
    exit(1)


# --- ENDPOINTS DA API (MODIFICADOS) ---

@app.get("/projetos/tipos/", response_model=List[str])
async def get_project_types():
    """ Retorna a lista de tipos de projeto permitidos pelo sistema. """
    return constants.ALL_TYPES

@app.post("/processar-relatorios/")
async def processar_relatorios(
    background_tasks: BackgroundTasks, 
    files: List[UploadFile] = File(...),
    project_type: str = Form(...) # <- MODIFICADO: Recebe 'TI', 'Retalho', etc.
):
    nomes_processados = []
    nomes_falhados = []
    
    print(f"Iniciando processamento para relatórios do tipo: {project_type}")

    for file in files:
        file_stream = io.BytesIO(await file.read())
        try:
            # 1. A Factory usa o project_type para escolher o parser
            parser = parser_factory.get_parser(file.filename, project_type)
            
            if not parser:
                print(f"Falha: Nenhum parser encontrado para {file.filename} e tipo {project_type}")
                nomes_falhados.append(file.filename); continue

            # 2. O parser extrai os dados (incluindo o project_code de dentro do arquivo)
            parsed_data = parser.parse(file_stream)
            
            if not parsed_data:
                print(f"Falha: Parser não conseguiu processar o arquivo {file.filename}")
                nomes_falhados.append(file.filename); continue
            
            # 3. REMOVEMOS a verificação de project_code
            
            # 4. Envia para salvar no DB, passando o project_type junto
            background_tasks.add_task(repository.save_parsed_report, parsed_data, project_type)
            nomes_processados.append(file.filename)
        except Exception as e:
            print(f"ERRO INESPERADO AO PROCESSAR {file.filename}: {e}")
            nomes_falhados.append(file.filename)
            
    return {
        "status": "sucesso", 
        "arquivos_enviados_para_processamento": nomes_processados,
        "arquivos_falhados_ou_ignorados": nomes_falhados
    }

# --- Endpoints de leitura (Modificados) ---

@app.get("/dashboard-executivo/", response_model=models.DashboardStats)
async def get_dashboard_data():
    try:
        return repository.get_dashboard_stats() # Função de repo já foi refatorada
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/projetos/lista/", response_model=List[models.ProjectListItem])
async def get_projetos_lista():
    try:
        return repository.get_project_list() # Nenhuma mudança
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/projeto/{project_code}/lista-sprints/", response_model=List[models.SprintListItem])
async def get_sprints_do_projeto(project_code: str):
    try:
        return repository.get_sprints_do_projeto(project_code) # Nenhuma mudança
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/relatorio/detalhe/{report_id}", response_model=models.ReportDetailResponse)
async def get_detalhe_do_relatorio(report_id: int):
    try:
        data = repository.get_detalhe_do_relatorio(report_id) # Função de repo já foi refatorada
        if not data:
            raise HTTPException(status_code=404, detail="Relatório (Sprint) não encontrado")
        return data
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        print(f"ERRO AO BUSCAR DETALHE DO RELATÓRIO {report_id}: {e}")
        raise HTTPException(status_code=500, detail="Erro ao buscar detalhes do relatório.")
    
@app.get("/projeto/{project_code}/historico-kpi/{kpi_name}", response_model=List[models.FinancialHistoryItem])
async def get_historico_de_kpi(project_code: str, kpi_name: str):
    """
    NOVO ENDPOINT: Retorna o histórico de um KPI específico para o gráfico de tendência.
    """
    try:
        data = repository.get_kpi_history(project_code, kpi_name)
        return data
    except Exception as e:
        print(f"ERRO AO BUSCAR HISTÓRICO DE KPI {project_code}/{kpi_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))