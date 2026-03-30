"""Detecção de gênero pelo nome e adaptação de mensagens."""
import re
from typing import Optional

try:
    from guesser_genero import Genero
    _has_detector = True
except ImportError:
    _has_detector = False


def detect_gender_from_name(name: Optional[str]) -> str:
    """
    Detecta o gênero da pessoa pelo nome usando dados do IBGE.

    Usa a biblioteca gender-guesser-br para máxima precisão com nomes portugueses.
    Se a biblioteca não estiver disponível, usa heurística simples (sufixos comuns).

    Args:
        name: Nome da pessoa (ex: "Maria", "João", "Carol", "Leonel")

    Returns:
        "female" ou "male"
    """
    if not name:
        return "male"  # Padrão neutro

    clean = name.strip()

    # Tenta usar a biblioteca se disponível
    if _has_detector:
        try:
            genero = Genero(clean)
            # A biblioteca retorna um objeto Genero que pode ser convertido para string
            resultado = str(genero).lower()
            if "fem" in resultado or resultado == "f":
                return "female"
            elif "masc" in resultado or resultado == "m":
                return "male"
        except Exception:
            pass  # Fallback para heurística se houver erro

    # Fallback: heurística simples para nomes em português
    # Sufixos femininos comuns em português
    clean_lower = clean.lower()
    female_endings = ("a", "ita", "inha", "ana", "ela", "ena", "ida", "ada")
    if clean_lower.endswith(female_endings):
        return "female"
    return "male"


def adapt_gender_text(text: str, gender: str) -> str:
    """
    Remove as marcas (o)/(a) das palavras e adapta para o gênero correto.

    Exemplos:
    - "sozinho(a)" + female → "sozinha"
    - "sozinho(a)" + male → "sozinho"
    - "seguro(a)" + female → "segura"
    - "seguro(a)" + male → "seguro"

    Args:
        text: Texto com marcas de gênero
        gender: "female" ou "male"

    Returns:
        Texto adaptado sem as marcas
    """
    if gender == "female":
        # Remove (o) e mantém (a)
        # Ex: "sozinho(a)" → "sozinha"
        text = re.sub(r'(\w+)o\(a\)', r'\1a', text)
        # Ex: "seguro(a)" → "segura"
        text = re.sub(r'(\w+)o\(a\)', r'\1a', text)
    else:
        # Remove (a) e mantém (o)
        # Ex: "sozinho(a)" → "sozinho"
        text = re.sub(r'(\w+)o\(a\)', r'\1o', text)

    return text
