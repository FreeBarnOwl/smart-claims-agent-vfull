from app.agents.reasoning import reason


def test_reason_returns_fallback_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = reason(system="Ets un agent.", prompt="Decideix.", fallback="DECISIÓ: pago")
    assert out == "DECISIÓ: pago"


def test_reason_fallback_on_llm_error(monkeypatch):
    # Amb clau però la crida falla → ha de retornar el fallback, no propagar l'error.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    import app.agents.reasoning as r

    class _Boom:
        def __init__(self, *a, **k): ...
        def invoke(self, *a, **k): raise RuntimeError("api down")

    monkeypatch.setattr("langchain_anthropic.ChatAnthropic", _Boom)
    out = reason(system="s", prompt="p", fallback="FALLBACK")
    assert out == "FALLBACK"
