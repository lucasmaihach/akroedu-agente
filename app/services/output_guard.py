"""
Validação de output do LLM antes de enviar ao lead.

Garante que nenhuma mensagem gerada pelo LLM vaze informações de preço
durante o script ativo — independente do prompt ou do que o modelo gerou.
"""
import re

# Padrões que indicam vazamento de preço no texto gerado pelo LLM
_PRICE_PATTERNS = [
    r"R\$\s*[\d.,]+",               # R$ 9.500 / R$197
    r"\b9[.,]?500\b",               # 9.500 / 9500
    r"\b7[.,]?94\b",                # 794 (parcela integral)
    r"\b5[.,]?59\b",                # 559 (bolsa 1)
    r"\b2[.,]?57\b",                # 257 (bolsa 2)
    r"\b197\b",                     # 197 (matrícula bolsa 2)
    r"\b350\b",                     # 350 (matrícula bolsa 1)
    r"(preço|valor|investimento|custo|mensalidade)\s*(é|de|:)\s*\d",
    r"\d+x\s*de\s*R?\$?\s*\d",     # 14x de R$794
    r"parcela[a-z]*\s+de\s+R",      # parcela de R$
]

_PRICE_RE = re.compile("|".join(_PRICE_PATTERNS), re.IGNORECASE)


def contains_price(text: str) -> bool:
    """Retorna True se o texto contém informação de preço."""
    return bool(_PRICE_RE.search(text))


def sanitize(text: str | None) -> str | None:
    """
    Retorna None se o texto contiver preço (descarta silenciosamente).
    Retorna o texto original caso contrário.
    """
    if text is None:
        return None
    return None if contains_price(text) else text
