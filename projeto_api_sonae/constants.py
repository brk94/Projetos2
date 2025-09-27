# projeto_api_sonae/constants.py

class ProjectTypes:
    """ Define as strings 'oficiais' para os tipos de projeto. """
    TECH = "Projetos de Tecnologia"
    RETAIL = "Retalho Alimentar"
    # No futuro, adicione aqui:
    # HEALTH = "Saúde e Bem-Estar" 

# A lista que será usada pela API e pela Factory
ALL_TYPES = [
    ProjectTypes.TECH,
    ProjectTypes.RETAIL
]

# O tipo padrão para novos projetos
DEFAULT_TYPE = ProjectTypes.TECH