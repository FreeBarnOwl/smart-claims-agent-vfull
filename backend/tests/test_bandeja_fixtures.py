"""
Tests de las fixtures de demo de la vista 'Bandeja' (streamlit_fixtures.py,
en la raiz del repo). No pasan por AppTest: verifican directamente que los
assets referenciados existen y son validos, porque st.image/st.download_button
no son introspeccionables via streamlit.testing.v1.AppTest (no existen como
tipos de elemento en su API).
"""
import sys
from pathlib import Path

from PIL import Image

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit_fixtures as fx  # noqa: E402


def test_all_attachment_files_exist_on_disk():
    for case in fx.BANDEJA_CASES:
        for att in case["attachments"]:
            assert Path(att["path"]).is_file(), f"falta {att['path']}"


def test_invoice_attachment_has_a_valid_page_preview_thumbnail():
    """La factura no puede quedar solo como icono + nombre: debe tener una
    miniatura PNG real de su primera pagina (renderizada al generar los
    assets), ya que es el adjunto que el Agente C lee de verdad."""
    case = fx.BANDEJA_CASES[0]
    factura = next(a for a in case["attachments"] if a["doc_type"] == "factura")

    assert factura["preview_path"], "la factura no tiene preview_path"
    preview = Path(factura["preview_path"])
    assert preview.is_file()

    with Image.open(preview) as img:
        assert img.width > 100
        assert img.height > 100
