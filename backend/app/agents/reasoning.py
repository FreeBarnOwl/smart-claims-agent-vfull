"""
Helper de raonament — LLM opcional amb fallback determinista.

Si hi ha ANTHROPIC_API_KEY a l'entorn, genera el raonament (CoT) amb Claude.
Si no, o si la crida falla, retorna el `fallback` determinista que passa qui crida.
Això permet que la demo funcioni sempre, amb o sense clau d'API.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"


def reason(system: str, prompt: str, fallback: str) -> str:
    """Retorna un raonament en text.

    Args:
        system: Instrucció de sistema (rol de l'agent).
        prompt: Context concret de l'expedient.
        fallback: Text determinista a retornar si no hi ha LLM disponible.

    Returns:
        El raonament generat per Claude, o el `fallback` si no hi ha clau
        d'API o la crida falla.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return fallback
    try:
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(model=MODEL, max_tokens=1024, temperature=0)
        response = llm.invoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ]
        )
        content = response.content
        return content if isinstance(content, str) else str(content)
    except Exception as exc:  # qualsevol error → fallback, la demo no es trenca
        logger.warning("Fallback de raonament (LLM no disponible): %s", exc)
        return fallback
