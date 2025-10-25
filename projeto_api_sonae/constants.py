"""
Constantes de domínio usadas por API/Factory e camadas de UI.

Notas rápidas:
- `ALL_TYPES`: enum values (para API/Factory/validação).
- `AREAS_NEGOCIO`: strings amigáveis (para UI, selects, rótulos).
- `DEFAULT_TYPE`: valor padrão para novos projetos.
"""

# ======================================================================================
# Imports
# ======================================================================================
from .models import AreaNegocioEnum  # Enum de áreas de negócio

# ======================================================================================
# Áreas de Negócio — listas auxiliares
# ======================================================================================
# Mantemos explicitamente a ordem e os itens conforme o original para
# evitar impacto em validações/ordenadores que assumem essa sequência.
ALL_TYPES = [
    AreaNegocioEnum.TI,
    AreaNegocioEnum.RETALHO,
    AreaNegocioEnum.RH,
    AreaNegocioEnum.MARKETING,
]

# Lista textual para exibição em UI (mesma ordem de ALL_TYPES)
AREAS_NEGOCIO = ["TI", "Retalho", "RH", "Marketing"]

# Tipo padrão adotado na criação de novos projetos
DEFAULT_TYPE = AreaNegocioEnum.TI
