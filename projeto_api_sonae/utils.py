"""
Helpers utilitários usados pelos parsers (regex e limpeza financeira)

- `helper_extrair_VALOR_LINHA`: captura **um valor em uma única linha** (sem DOTALL)
- `helper_extrair_BLOCO_TEXTO`: captura **blocos multi‑linha** (com DOTALL)
- `helper_limpar_financeiro`: normaliza strings monetárias e converte para float
"""

# ======================================================================================
# Imports
# ======================================================================================

import re

# ======================================================================================
# Extração por regex (1 linha e bloco)
# ======================================================================================

def helper_extrair_VALOR_LINHA(texto: str, padrao: str) -> str | None:
    """
    "SNIPER": captura o **primeiro grupo** do `padrao` em **uma linha**.

    - Flags: `re.IGNORECASE` (❌ sem `re.DOTALL`).
    - Útil para campos como *Status*, *Custo*, *Orçamento* etc.
    - Retorna `None` se não encontrar.
    """
    match = re.search(padrao, texto, re.IGNORECASE)  # <-- SEM re.DOTALL
    if match:
        return match.group(1).strip()
    return None


def helper_extrair_BLOCO_TEXTO(texto: str, padrao: str) -> str | None:
    """
    "REDE DE PESCA": captura **blocos multi‑linha** (ex.: Sumário, Riscos).

    - Flags: `re.IGNORECASE | re.DOTALL` (✔️ com `DOTALL`).
    - O `padrao` deve ter **um grupo de captura** para o conteúdo do bloco.
    - Retorna `None` se não encontrar.
    """
    match = re.search(padrao, texto, re.IGNORECASE | re.DOTALL)  # <-- COM re.DOTALL
    if match:
        return match.group(1).strip()
    return None

# ======================================================================================
# Financeiro — Normalização de valores monetários
# ======================================================================================

def helper_limpar_financeiro(texto: str) -> float:
    """Limpa texto monetário (ex.: "R$ 1.234,56") e retorna `float`.

    Passos (mantidos):
    1) Remove "R$", espaços e pontos de milhar; troca vírgula por ponto.
    2) Extrai o primeiro número (aceita negativo) e converte para float.
    3) Em qualquer falha, retorna `0.0` (com `try/except` silencioso).
    """
    try:
        # Remove "R$", "R\$", espaços, pontos de milhar e converte vírgula decimal
        texto_limpo = re.sub(r"[R$\s\.]", "", str(texto)).replace(",", ".")
        # Extrai o primeiro número (útil se houver texto: "(Estouro)")
        match = re.search(r"(-?[\d\.]+)", texto_limpo)  # Suporte a negativos (mantido)
        if match:
            return float(match.group(1))
    except Exception:
        # Ignora erros de conversão (ex.: input None) — comportamento original
        pass
    return 0.0