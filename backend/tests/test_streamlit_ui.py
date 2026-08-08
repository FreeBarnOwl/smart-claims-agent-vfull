"""
Tests de la UI Streamlit standalone (streamlit_app.py) mediante
streamlit.testing.v1.AppTest — ejecuta el script en modo headless.

Verifica el blindaje A3: ante un fallo interno, la UI nunca debe mostrar
un traceback en pantalla (ni el texto interno de la excepcion).
"""
import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

import app.agents.orchestrator as orchestrator_module

STREAMLIT_APP_PATH = str(
    Path(__file__).resolve().parents[2] / "streamlit_app.py"
)


def test_streamlit_demo_scenario_never_shows_raw_traceback(monkeypatch):
    """Si process_claim falla de forma inesperada, la UI debe mostrar un
    mensaje generico (st.error) y NUNCA el traceback ni el texto interno
    de la excepcion (blindaje A3)."""
    os.environ.pop("ANTHROPIC_API_KEY", None)

    async def _boom(**kwargs):
        raise RuntimeError("detalle interno sensible que no debe salir")

    monkeypatch.setattr(orchestrator_module, "process_claim", _boom)

    at = AppTest.from_file(STREAMLIT_APP_PATH, default_timeout=30)
    at.run()
    at.session_state["view"] = "nueva"
    at.run()

    # Lanza el primer escenario de demostracion ("Pago automatico").
    at.button(key="sc_0").click().run()

    # La app NUNCA debe terminar con una excepcion sin capturar en pantalla.
    assert not at.exception

    # El detalle interno de la excepcion no debe filtrarse a ningun texto
    # visible (st.error, st.markdown, st.caption, etc.).
    all_text = " ".join(
        str(el.value) for el in (*at.error, *at.markdown, *at.caption)
    )
    assert "detalle interno sensible" not in all_text
