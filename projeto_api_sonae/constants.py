# projeto_api_sonae/constants.py

from .models import AreaNegocioEnum

# A lista que será usada pela API e pela Factory
# Agora é gerada diretamente a partir do Enum no models.py,
# garantindo que ambos os arquivos estejam sempre sincronizados.

ALL_TYPES = [
    AreaNegocioEnum.TI,
    AreaNegocioEnum.RETALHO,
    AreaNegocioEnum.RH,
    AreaNegocioEnum.MARKETING
]

AREAS_NEGOCIO = ["TI", "Retalho", "RH", "Marketing"]

# O tipo padrão para novos projetos
DEFAULT_TYPE = AreaNegocioEnum.TI
