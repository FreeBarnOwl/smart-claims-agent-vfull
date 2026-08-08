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


def test_bandeja_view_shows_fixture_cases_and_processes_pago_automatico():
    """Spike UI 'Bandeja': la vista debe mostrar los casos de demo (con su
    mensaje de WhatsApp y sus adjuntos) y, al pulsar 'Revisar y procesar'
    sobre el caso completo, debe reutilizar el camino ya blindado
    (process_and_store) y terminar en PAGO automatico."""
    os.environ.pop("ANTHROPIC_API_KEY", None)

    at = AppTest.from_file(STREAMLIT_APP_PATH, default_timeout=30)
    at.run()
    at.session_state["view"] = "bandeja"
    at.run()

    assert not at.exception

    all_text = " ".join(str(el.value) for el in (*at.markdown, *at.caption))
    # Cabecera del caso "pago automatico" es visible.
    assert "CLM-WA-0001" in all_text
    assert "Marta Soler Puig" in all_text

    # El mensaje de WhatsApp (dentro de st.chat_message) menciona la denuncia.
    chat_text = " ".join(
        str(m.value) for cm in at.chat_message for m in cm.markdown
    )
    assert "D-4521" in chat_text

    # st.image y st.download_button no son introspeccionables via AppTest
    # (no existen como tipos de elemento en su API), pero si el PNG de
    # preview o el PDF no existieran, st.image()/open() lanzarian una
    # excepcion que "assert not at.exception" ya habria capturado arriba.
    # El contenido real de la miniatura se verifica aparte en
    # test_bandeja_fixtures.py (sin pasar por AppTest).

    # El boton "Revisar y procesar" del primer caso dispara el proceso
    # real reutilizando process_and_store (A3 ya blindado).
    at.button(key="bandeja_process_CLM-WA-0001").click().run()

    assert not at.exception
    result_text = " ".join(str(el.value) for el in at.markdown)
    assert "Pago aprobado" in result_text
