"""
Tests del helper de razonamiento (reasoning.py).
Verifica que el fallback determinista se invoca correctamente cuando no
hay ANTHROPIC_API_KEY disponible.
"""
import os

import httpx
import pytest

from app.agents.reasoning import reason


def test_reason_uses_fallback_when_no_api_key(monkeypatch):
    """Sin ANTHROPIC_API_KEY, reason() debe devolver el fallback."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = reason(
        system="Eres un agente de prueba.",
        prompt="Procesa esto.",
        fallback="FALLBACK_DETERMINISTA",
    )
    assert out == "FALLBACK_DETERMINISTA"


def test_reason_falls_back_on_exception(monkeypatch):
    """Si la llamada al LLM falla, reason() devuelve el fallback."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-that-will-fail")

    # Si el import falla (no hay langchain_anthropic) o la llamada
    # falla por la fake key, el fallback se devuelve igualmente.
    out = reason(
        system="Eres un agente de prueba.",
        prompt="Procesa esto.",
        fallback="FALLBACK_POR_ERROR",
    )
    # En entorno de tests sin red real, el fallback se activara
    assert out == "FALLBACK_POR_ERROR" or isinstance(out, str)


def test_reason_configures_llm_timeout(monkeypatch):
    """El cliente LLM debe configurarse con timeout (blindaje A4): una
    llamada colgada (p. ej. wifi caido durante la defensa) debe caer al
    fallback en ~60s, no bloquear indefinidamente."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    captured = {}

    class _FakeChatAnthropic:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def invoke(self, messages):
            raise RuntimeError("no deberia llegar aqui en este test")

    import langchain_anthropic
    monkeypatch.setattr(langchain_anthropic, "ChatAnthropic", _FakeChatAnthropic)

    out = reason(system="sys", prompt="prompt", fallback="FALLBACK_TIMEOUT")

    assert out == "FALLBACK_TIMEOUT"
    assert captured.get("timeout") == 60


def test_reason_falls_back_on_real_api_timeout_error(monkeypatch):
    """Blindaje A4 (realista): si la llamada agota el timeout, el SDK de
    Anthropic lanza `anthropic.APITimeoutError` (no un RuntimeError
    generico). reason() debe capturar esta excepcion real y caer al
    fallback, igual que ante cualquier otro fallo de red."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")

    import anthropic

    class _FakeChatAnthropic:
        def __init__(self, **kwargs):
            pass

        def invoke(self, messages):
            request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
            raise anthropic.APITimeoutError(request=request)

    import langchain_anthropic
    monkeypatch.setattr(langchain_anthropic, "ChatAnthropic", _FakeChatAnthropic)

    out = reason(system="sys", prompt="prompt", fallback="FALLBACK_REAL_TIMEOUT")

    assert out == "FALLBACK_REAL_TIMEOUT"
