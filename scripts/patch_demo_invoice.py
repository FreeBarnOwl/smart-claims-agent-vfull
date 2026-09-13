"""
Corrige el texto de la factura de demo del expediente CLM-WA-0001 y regenera
su miniatura.

QUE HACE
--------
`assets/demo/factura_taller_can_bosch.pdf` es un binario suelto (generado en su
dia con reportlab, sin script generador en el repo). Dos de sus datos no
cuadraban con las fotografias reales del mismo expediente, que muestran un SEAT
gris con matricula dominicana A 742931 y el faro y la aleta delanteros
IZQUIERDOS destrozados:

    Vehiculo: Seat Leon . Matricula 4521-BXK   ->  Matricula A 742931
    Faro delantero derecho                     ->  Faro delantero izquierdo

Este script aplica esas dos sustituciones sobre el stream de contenido de la
pagina con PyMuPDF, que reconstruye /Length y la tabla xref por su cuenta. NO
regenera el PDF: tipografia, posiciones y colores quedan intactos. Los importes
no se tocan (base 2.645,00 EUR + IVA 21% 555,45 EUR = 3.200,45 EUR), porque la
memoria y el manual ya entregados citan ese total.

Despues rehace `factura_taller_can_bosch_preview.png`, la miniatura de la 1a
pagina que la tarjeta de la Bandeja muestra junto al adjunto (ver
`_attachment(...)` en streamlit_fixtures.py). Si no se regenera, la tarjeta
seguiria enseniando la matricula vieja.

Es idempotente: si el PDF ya esta corregido, informa y no escribe nada.

COMO EJECUTARLO
---------------
Desde la raiz del repositorio:

    py -m pip install pymupdf        # dependencia solo de desarrollo
    py scripts/patch_demo_invoice.py

PyMuPDF no esta en requirements.txt a proposito: el sistema no lo necesita en
ejecucion, solo esta utilidad puntual de mantenimiento de assets.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "assets" / "demo" / "factura_taller_can_bosch.pdf"
PNG = ROOT / "assets" / "demo" / "factura_taller_can_bosch_preview.png"

# (texto antiguo, texto nuevo). Ambos son ASCII: no hay que lidiar con los
# escapes octales que PDF usa para los acentos.
SUBS: list[tuple[bytes, bytes]] = [
    (b"4521-BXK", b"A 742931"),
    (b"Faro delantero derecho", b"Faro delantero izquierdo"),
]

# La miniatura original se genero a 144 dpi (1191x1684 px). Mantener el mismo
# valor evita que la tarjeta de la Bandeja cambie de tamanio.
PREVIEW_DPI = 144


def main() -> int:
    doc = pymupdf.open(PDF)
    page = doc[0]
    (xref,) = page.get_contents()
    content = doc.xref_stream(xref)

    pending = [(old, new) for old, new in SUBS if content.count(old) == 1]
    already = [(old, new) for old, new in SUBS
               if content.count(old) == 0 and content.count(new) == 1]

    if len(already) == len(SUBS):
        print("La factura ya esta corregida; no se escribe nada.")
        doc.close()
        return 0

    if len(pending) + len(already) != len(SUBS):
        doc.close()
        print("ERROR: el PDF no contiene el texto esperado. Revisalo a mano.",
              file=sys.stderr)
        return 1

    for old, new in pending:
        content = content.replace(old, new)
        print("OK   %-24s -> %s" % (old.decode(), new.decode()))

    doc.update_stream(xref, content, compress=True)
    tmp = PDF.with_suffix(".pdf.tmp")
    doc.save(tmp, deflate=True)
    doc.close()
    shutil.move(tmp, PDF)

    # Verificacion sobre el fichero ya escrito, no sobre el objeto en memoria.
    doc = pymupdf.open(PDF)
    text = doc[0].get_text()
    assert not doc.is_repaired, "tabla xref inconsistente"
    assert "A 742931" in text and "Faro delantero izquierdo" in text
    assert "4521-BXK" not in text and "Faro delantero derecho" not in text
    assert all(x in text for x in ("2.645,00", "555,45", "3.200,45")), "importes alterados"

    pix = doc[0].get_pixmap(dpi=PREVIEW_DPI)
    pix.save(PNG)
    doc.close()
    print("Miniatura regenerada: %s (%dx%d)" % (PNG.name, pix.width, pix.height))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
