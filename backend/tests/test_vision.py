"""
Tests del modulo de extraccion multimodal (vision.py).
Verifica el comportamiento de fallback y la configuracion de timeout
(blindaje A4) sin depender de la red real.
"""
from app.agents.vision import analyze_document


def test_analyze_document_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = analyze_document(b"data", "image/png", "foto.png")
    assert out is None


def test_analyze_document_configures_timeout(monkeypatch):
    """La llamada a Claude Vision debe configurarse con timeout (blindaje
    A4): una llamada colgada debe caer al fallback (None) en ~20s."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    captured = {}

    class _FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            raise RuntimeError("no deberia llegar aqui en este test")

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            self.messages = _FakeMessages()

    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", _FakeClient)

    out = analyze_document(b"data", "image/png", "foto.png")

    assert out is None
    assert captured.get("timeout") == 20
