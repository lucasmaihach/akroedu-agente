from __future__ import annotations

import re


_BR_CANONICAL_RE = re.compile(r"^55[1-9][0-9]9?[0-9]{8}$")


def is_canonical_br_phone(phone: str | None) -> bool:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    return bool(_BR_CANONICAL_RE.fullmatch(digits))


def normalize_phone(phone: str | None) -> str:
    """
    Normaliza telefone para dígitos e canoniza números BR.

    Regras:
    - Mantém apenas dígitos.
    - Se vier sem DDI BR (10/11 dígitos), prefixa 55.
    - Se vier com DDI BR e 12 dígitos (modelo antigo com 8 dígitos no assinante),
      tenta inserir o 9º dígito para celulares (assinante iniciando em 6/7/8/9).
    """
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if not digits:
        return ""

    if digits.startswith("00"):
        digits = digits[2:]

    if digits.startswith("55"):
        if len(digits) == 13:
            return digits
        if len(digits) == 12:
            ddd = digits[2:4]
            subscriber = digits[4:]
            if len(subscriber) == 8 and subscriber[:1] in {"6", "7", "8", "9"}:
                return f"55{ddd}9{subscriber}"
            return digits

    if len(digits) in (10, 11):
        return f"55{digits}"

    return digits


def phone_variants(phone: str | None) -> list[str]:
    """
    Retorna variações equivalentes de telefone BR para deduplicação.
    Ex.: 5555999013075 <-> 555599013075
    """
    canonical = normalize_phone(phone)
    if not canonical:
        return []

    variants: set[str] = {canonical}

    if canonical.startswith("55"):
        if len(canonical) == 13 and canonical[4] == "9":
            variants.add(canonical[:4] + canonical[5:])
        elif len(canonical) == 12:
            ddd = canonical[2:4]
            subscriber = canonical[4:]
            if len(subscriber) == 8 and subscriber[:1] in {"6", "7", "8", "9"}:
                variants.add(f"55{ddd}9{subscriber}")

    return list(variants)
