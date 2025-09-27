import re

def helper_extrair_VALOR_LINHA(texto: str, padrao: str) -> str | None:
    """
    Helper "SNIPER": Caça padrões de UMA LINHA. (SEM re.DOTALL).
    Usado para campos como Status, Custo, Orçamento.
    """
    match = re.search(padrao, texto, re.IGNORECASE) # <-- SEM re.DOTALL
    if match:
        return match.group(1).strip()
    return None

def helper_extrair_BLOCO_TEXTO(texto: str, padrao: str) -> str | None:
    """
    Helper "REDE DE PESCA": Caça blocos de texto de MÚLTIPLAS LINHAS. (COM re.DOTALL).
    Usado para Sumário Executivo e Riscos.
    """
    match = re.search(padrao, texto, re.IGNORECASE | re.DOTALL) # <-- COM re.DOTALL
    if match:
        return match.group(1).strip()
    return None

def helper_limpar_financeiro(texto: str) -> float:
    """Função helper para limpar texto de dinheiro e converter para float."""
    try:
        # Remove "R$", "R\$", pontos de milhar, e substitui vírgula decimal por ponto
        texto_limpo = re.sub(r"[R$\s\.]", "", str(texto)).replace(",", ".")
        # Pega apenas os números (caso tenha texto como "(Estouro)" junto)
        match = re.search(r"(-?[\d\.]+)", texto_limpo) # Adicionado suporte a números negativos
        if match:
            return float(match.group(1))
    except Exception:
        pass # Ignora erros de conversão (ex: se o input for None)
    return 0.0