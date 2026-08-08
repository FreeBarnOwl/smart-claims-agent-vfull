"""
Fixtures de demo para la vista 'Bandeja' (validación visual de la ingesta
multicanal: WhatsApp → conector simulado → bandeja del gestor).

Estrictamente aditivo: no crea estado en el backend ni endpoints nuevos.
Los campos de cada caso vienen PREPARADOS aquí (narrativa: el conector de
canal, mockeado, ya los entregó); el sistema no parsea el texto del
mensaje. Los adjuntos son bytes reales leídos de assets/demo/, que el
Agente C sí analiza de verdad al procesar.
"""
from __future__ import annotations

from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "demo"


def _attachment(label: str, file: str, media_type: str, doc_type: str, kind: str,
                 preview_file: str | None = None) -> dict:
    return {
        "label": label,
        "file": file,
        "path": str(ASSETS_DIR / file),
        "media_type": media_type,
        "doc_type": doc_type,
        "kind": kind,  # "image" | "pdf" — controla cómo se previsualiza en la tarjeta
        # Miniatura (PNG) de la 1a página, para PDFs: la factura es lo que el
        # Agente C lee de verdad, no puede quedar solo como icono + nombre.
        "preview_path": str(ASSETS_DIR / preview_file) if preview_file else None,
    }


BANDEJA_CASES = [
    {
        "id": "CLM-WA-0001",
        "origin": "WhatsApp · conector simulado",
        "entry_date": "08/08/2026 09:14",
        "client_id": "CLIENT-BANDEJA-01",
        "client_name": "Marta Soler Puig",
        "client_email": "marta.soler@example.com",
        "claim_type": "danys_propis",
        "amount": 3200.0,
        # "denuncia_companyia" consta como ya registrada (ver mensaje); no
        # lleva adjunto propio, por eso no aparece en "attachments".
        "documents": ["foto_danys", "factura", "denuncia_companyia"],
        "whatsapp_message": (
            "Hola buenas! Ayer choqué contra un poste al aparcar y se llevó "
            "el parachoques y el faro delantero 😩 Ayer mismo abrí el "
            "reclamo por teléfono y me dieron el número de denuncia D-4521. "
            "Os mando las fotos del golpe y la factura del taller, gracias!"
        ),
        "attachments": [
            _attachment("Foto daño frontal", "foto_danys_frontal_placeholder.png",
                        "image/png", "foto_danys", "image"),
            _attachment("Foto daño lateral", "foto_danys_lateral_placeholder.png",
                        "image/png", "foto_danys", "image"),
            _attachment("Factura del taller", "factura_taller_can_bosch.pdf",
                        "application/pdf", "factura", "pdf",
                        preview_file="factura_taller_can_bosch_preview.png"),
        ],
    },
    {
        "id": "CLM-WA-0002",
        "origin": "WhatsApp · conector simulado",
        "entry_date": "08/08/2026 11:02",
        "client_id": "CLIENT-BANDEJA-02",
        "client_name": "Jordi Ferrer Camps",
        "client_email": "jordi.ferrer@example.com",
        "claim_type": "danys_propis",
        "amount": 2900.0,
        # Documentación incompleta a propósito: faltan factura y denuncia,
        # tal como dice el propio mensaje del cliente.
        "documents": ["foto_danys"],
        "whatsapp_message": (
            "Buenos días, tuve un golpe con el coche este finde y quiero "
            "reclamarlo. Os paso una foto de cómo quedó, luego os mando la "
            "factura del taller y el número de denuncia en cuanto los tenga."
        ),
        "attachments": [
            _attachment("Foto daño frontal", "foto_danys_frontal_placeholder.png",
                        "image/png", "foto_danys", "image"),
        ],
    },
]


def bandeja_uploaded_files(case: dict) -> list[dict]:
    """Construye la lista de adjuntos en la forma que espera process_claim
    (uploaded_files), leyendo los bytes reales de assets/demo/ — misma
    forma que produce read_uploads() en streamlit_app.py."""
    return [
        {
            "filename": att["file"],
            "media_type": att["media_type"],
            "data": Path(att["path"]).read_bytes(),
            "doc_type": att["doc_type"],
        }
        for att in case["attachments"]
    ]
