"""
Tests de la UI Streamlit standalone (streamlit_app.py) mediante
streamlit.testing.v1.AppTest — ejecuta el script en modo headless.

Verifica el blindaje A3: ante un fallo interno, la UI nunca debe mostrar
un traceback en pantalla (ni el texto interno de la excepcion).
"""
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


def test_caso_libre_view_lets_broken_amount_trigger_blindaje_a1():
    """Panel 'Caso libre' (blindaje A5): backup para peticiones improvisadas
    del tribunal. A diferencia del formulario de 'Nueva reclamación', el
    tipo de siniestro y el importe son texto libre (no selectbox/number_input
    con limites), para poder introducir en directo un dato roto y demostrar
    que el blindaje de entrada (Agente A, validate_claim_input) lo atrapa
    con un motivo legible en vez de fallar."""
    at = AppTest.from_file(STREAMLIT_APP_PATH, default_timeout=30)
    at.run()
    at.session_state["view"] = "libre"
    at.run()

    assert not at.exception

    at.text_input(key="libre_client_name").set_value("Caso Libre Tribunal").run()
    at.text_input(key="libre_claim_type").set_value("tipo-inventado-por-el-tribunal").run()
    at.text_input(key="libre_amount").set_value("no-es-un-numero").run()

    at.button(key="libre_submit").click().run()

    assert not at.exception
    all_text = " ".join(str(el.value) for el in (*at.markdown, *at.caption))
    assert "Rechazado" in all_text
    assert "importe reclamado invalido: 'no-es-un-numero'" in all_text


def test_conciliacion_view_shows_fixture_recommendations():
    """Vista 'Conciliación (Agente F)': demostrador secundario e
    independiente del flujo principal. Debe mostrar los 3 casos DPA/RC de
    demo, cada uno con la recomendación real que produce
    advise_conciliation() (no texto estático)."""
    at = AppTest.from_file(STREAMLIT_APP_PATH, default_timeout=30)
    at.run()
    at.session_state["view"] = "conciliacion"
    at.run()

    assert not at.exception

    all_text = " ".join(str(el.value) for el in (*at.markdown, *at.caption))
    assert "CLM-CONC-0001" in all_text
    assert "CLM-CONC-0002" in all_text
    assert "CLM-CONC-0003" in all_text

    # Caso 1 (stage 1 rechazada) -> recomienda subir de tramo.
    assert "siguiente tramo" in all_text.lower()
    # Caso 2 (40 dias sin respuesta) -> alerta de abandono.
    assert "riesgo de cierre por abandono" in all_text
    # Caso 3 (RC, cobertura insuficiente) -> alerta de escalada judicial.
    assert "riesgo de escalada judicial" in all_text
    # F nunca ejecuta: cada recomendacion deja claro que la ejecuta un humano.
    assert "la ejecuta un gestor humano" in all_text
