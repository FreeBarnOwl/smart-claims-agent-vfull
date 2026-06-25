"""
Smart-Claims Agent — Dashboard (despliegue Streamlit Cloud).

App AUTONOMA: invoca el grafo de agentes (`process_claim`) en el mismo
proceso, sin necesidad del backend FastAPI ni de MariaDB. Pensada para
desplegarse en Streamlit Community Cloud, donde solo corre un proceso Python.

Estetica: Salesforce Lightning + identidad de marca Seguros Pepin
(logo real, azul corporativo, acento naranja).

La persistencia en BD es best-effort dentro de `process_claim`: si no hay
MariaDB (caso de Streamlit Cloud), el flujo devuelve igualmente el resultado
y el historial se mantiene en memoria de sesion.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid

import pandas as pd
import streamlit as st

# ── Acceso al paquete backend (app.*) ─────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_ROOT, "backend"))

# Clave de Anthropic: en Streamlit Cloud va en st.secrets; en local, en .env.
try:
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = str(st.secrets["ANTHROPIC_API_KEY"])
    if "HITL_AMOUNT_THRESHOLD" in st.secrets:
        os.environ["HITL_AMOUNT_THRESHOLD"] = str(st.secrets["HITL_AMOUNT_THRESHOLD"])
except Exception:
    pass

try:
    from dotenv import find_dotenv, load_dotenv
    load_dotenv(find_dotenv())
except Exception:
    pass

from app.agents.orchestrator import process_claim  # noqa: E402


# ── Constantes de presentacion ────────────────────────────────────────────

LOGO_URL = "https://segurospepin.com/wp-content/uploads/2020/03/Layer-1-251x95.png"

# Paleta: azul corporativo Seguros Pepin + acento naranja + semantica Lightning
C_PRIMARY      = "#0B4DA2"   # azul corporativo
C_PRIMARY_DARK = "#07336B"
C_ACCENT       = "#F39200"   # naranja de marca
C_BG           = "#F3F3F3"   # gris Lightning
C_CARD         = "#FFFFFF"
C_BORDER       = "#DDDBDA"
C_TEXT         = "#16325C"
C_TEXT_SOFT    = "#5C6B82"

AGENT_LABELS = {
    "agent_a_orchestrator":         "Agente A · Orquestador",
    "agent_b_document_validator":   "Agente B · Validación documental",
    "agent_c_multimodal_extractor": "Agente C · Extracción multimodal",
    "agent_d_coverage_checker":     "Agente D · Verificación de cobertura",
    "agent_e_claim_resolver":       "Agente E · Resolución",
    "agent_g_fraud_compliance":     "Agente G · Fraude y cumplimiento",
}

CLAIM_TYPES = {
    "danys_propis":    "Daños propios",
    "responsabilitat": "Responsabilidad civil",
    "robatori":        "Robo",
    "danys_mecanics":  "Daños mecánicos",
}

REQUIRED_DOCS_BY_TYPE = {
    "danys_propis":    ["foto_danys", "factura", "denuncia_companyia"],
    "responsabilitat": ["foto_danys", "acta_policial", "dades_tercer"],
    "robatori":        ["acta_policial", "llista_objectes_robats"],
    "danys_mecanics":  ["informe_taller", "factura"],
}

# Estado/decision -> (etiqueta, tipo de pill)
DECISION_STYLE = {
    "PAGO":            ("Resuelto · Pago aprobado", "success"),
    "RECHAZO":         ("Rechazado · Sin cobertura", "error"),
    "RECHAZO_FRAUDE":  ("Bloqueado · Fraude / OFAC", "error"),
    "REVISION_HUMANA": ("Revisión humana requerida", "warning"),
    "INFO_REQUERIDA":  ("Información requerida", "info"),
}


# ── Configuracion de pagina ───────────────────────────────────────────────

st.set_page_config(
    page_title="Smart-Claims Agent · Seguros Pepín",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── CSS — estetica Salesforce Lightning ───────────────────────────────────

st.markdown(f"""
<style>
    /* Oculta el chrome por defecto de Streamlit */
    #MainMenu, footer, header [data-testid="stToolbar"] {{ visibility: hidden; }}
    .stApp {{ background: {C_BG}; }}
    html, body, [class*="css"] {{
        font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: {C_TEXT};
    }}
    .block-container {{ padding-top: 1rem; max-width: 1200px; }}

    /* Barra superior tipo Lightning */
    .sca-topbar {{
        background: linear-gradient(90deg, {C_PRIMARY_DARK} 0%, {C_PRIMARY} 100%);
        border-radius: 10px;
        padding: 14px 22px;
        display: flex; align-items: center; gap: 16px;
        margin-bottom: 18px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.12);
    }}
    .sca-topbar img {{ height: 34px; background:#fff; padding:4px 8px; border-radius:6px; }}
    .sca-topbar .title {{ color:#fff; font-size:20px; font-weight:600; letter-spacing:.2px; }}
    .sca-topbar .sub {{ color:#cfe0f5; font-size:12px; margin-left:auto; text-align:right; }}

    /* Tarjetas */
    .sca-card {{
        background:{C_CARD}; border:1px solid {C_BORDER}; border-radius:10px;
        padding:16px 18px; box-shadow:0 1px 3px rgba(0,0,0,0.06);
    }}
    .sca-metric {{ text-align:left; }}
    .sca-metric .lbl {{ font-size:11px; text-transform:uppercase; letter-spacing:.6px;
        color:{C_TEXT_SOFT}; font-weight:600; }}
    .sca-metric .val {{ font-size:24px; font-weight:600; color:{C_TEXT}; margin-top:4px; }}
    .sca-metric .delta {{ font-size:11px; color:{C_TEXT_SOFT}; }}

    /* Pills de estado */
    .pill {{ display:inline-block; padding:4px 12px; border-radius:999px;
        font-size:12px; font-weight:600; letter-spacing:.2px; }}
    .pill.success {{ background:#EAF5EC; color:#2E844A; border:1px solid #9BD0A8; }}
    .pill.error   {{ background:#FCE9E9; color:#BA0517; border:1px solid #F0A9A4; }}
    .pill.warning {{ background:#FEF3E6; color:#A35C00; border:1px solid #FAC685; }}
    .pill.info    {{ background:#EAF1FB; color:{C_PRIMARY}; border:1px solid #A9C4EC; }}
    .pill.neutral {{ background:#F1F1F1; color:#5C6B82; border:1px solid #DDDBDA; }}

    /* Cabecera de seccion */
    .sca-section {{ font-size:13px; font-weight:700; text-transform:uppercase;
        letter-spacing:.7px; color:{C_TEXT_SOFT}; margin:22px 0 10px 0; }}

    /* Timeline de razonamiento (activity feed Lightning) */
    .sca-step {{ background:{C_CARD}; border:1px solid {C_BORDER}; border-left:4px solid {C_PRIMARY};
        border-radius:8px; padding:12px 16px; margin:8px 0; }}
    .sca-step.flagged {{ border-left-color:{C_ACCENT}; }}
    .sca-step .agent {{ font-size:12px; font-weight:700; color:{C_PRIMARY};
        text-transform:uppercase; letter-spacing:.4px; }}
    .sca-step .action {{ font-size:11px; color:{C_TEXT_SOFT}; margin-left:6px; }}
    .sca-step .reason {{ font-size:14px; color:{C_TEXT}; line-height:1.55; margin-top:6px;
        white-space:pre-wrap; }}

    /* Botones */
    .stButton > button, .stFormSubmitButton > button {{
        background:{C_PRIMARY}; color:#fff; border:none; border-radius:6px;
        font-weight:600; padding:8px 16px;
    }}
    .stButton > button:hover, .stFormSubmitButton > button:hover {{
        background:{C_PRIMARY_DARK}; color:#fff;
    }}
    section[data-testid="stSidebar"] {{ background:#FFFFFF; border-right:1px solid {C_BORDER}; }}
    .stTabs [data-baseweb="tab-list"] {{ gap:4px; }}
    .stTabs [data-baseweb="tab"] {{ font-weight:600; }}
</style>
""", unsafe_allow_html=True)


# ── Cabecera ───────────────────────────────────────────────────────────────

st.markdown(f"""
<div class="sca-topbar">
    <img src="{LOGO_URL}" alt="Seguros Pepín"/>
    <span class="title">Smart-Claims Agent</span>
    <span class="sub">Gestión agéntica de siniestros<br/>Seguros Pepín, S.A.</span>
</div>
""", unsafe_allow_html=True)


# ── Utilidades ─────────────────────────────────────────────────────────────

def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def pill(label: str, kind: str) -> str:
    return f'<span class="pill {kind}">{label}</span>'


def decision_pill(result: dict) -> str:
    dec = result.get("decision")
    label, kind = DECISION_STYLE.get(dec, (result.get("status", "—"), "neutral"))
    return pill(label, kind)


def metric_card(lbl: str, val: str, delta: str = "") -> str:
    d = f'<div class="delta">{delta}</div>' if delta else ""
    return (f'<div class="sca-card sca-metric"><div class="lbl">{lbl}</div>'
            f'<div class="val">{val}</div>{d}</div>')


def _step_header(agent: str, action: str = "", flagged: bool = False) -> str:
    color = C_ACCENT if flagged else C_PRIMARY
    act = f'<span style="font-size:11px;color:{C_TEXT_SOFT}"> · {action}</span>' if action else ""
    return (f'<span style="font-size:12px;font-weight:700;color:{color};'
            f'text-transform:uppercase;letter-spacing:.4px">{agent}</span>{act}')


def render_timeline(result: dict) -> None:
    """Renderiza el Chain of Thought. La razon se pinta con st.markdown para
    que el formato que devuelve Claude (titulos, listas) se vea correctamente."""
    decisions = result.get("decisions_log") or []
    if decisions:
        for d in decisions:
            agent = AGENT_LABELS.get(d.get("agent", ""), d.get("agent", "Agente"))
            with st.container(border=True):
                st.markdown(
                    _step_header(agent, d.get("action", ""), bool(d.get("hitl_required"))),
                    unsafe_allow_html=True,
                )
                st.markdown(d.get("reasoning", "") or "_(sin razonamiento)_")
    else:
        for i, step in enumerate(result.get("reasoning_trace", []), 1):
            with st.container(border=True):
                st.markdown(_step_header(f"Paso {i}"), unsafe_allow_html=True)
                st.markdown(step)


# ── Sidebar — alta de expediente ───────────────────────────────────────────

with st.sidebar:
    st.markdown('<div class="sca-section">Nueva reclamación</div>', unsafe_allow_html=True)
    with st.form("claim_form", clear_on_submit=False):
        client_id = st.text_input("ID Cliente", value="CLIENT-A")
        client_email = st.text_input("Email del cliente", value="cliente@segurospepin.com")
        claim_type = st.selectbox(
            "Tipo de siniestro",
            options=list(CLAIM_TYPES.keys()),
            format_func=lambda k: CLAIM_TYPES[k],
        )
        amount = st.number_input(
            "Importe reclamado (€)", min_value=0.0, max_value=100000.0,
            value=2500.0, step=100.0,
        )
        docs_avail = REQUIRED_DOCS_BY_TYPE.get(claim_type, [])
        documents = st.multiselect(
            "Documentos aportados", options=docs_avail, default=docs_avail,
            help="Deselecciona alguno para simular documentación incompleta.",
        )
        submitted = st.form_submit_button("Procesar reclamación", use_container_width=True)

    st.caption("El sistema ejecuta los 6 agentes y devuelve la decisión con su "
               "razonamiento (Chain of Thought).")


# ── Procesamiento ──────────────────────────────────────────────────────────

if "history" not in st.session_state:
    st.session_state["history"] = []

if submitted:
    claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"
    payload = dict(
        claim_id=claim_id, client_id=client_id, claim_type=claim_type,
        amount_requested=float(amount), channel="web",
        documents=documents, client_email=client_email,
    )
    with st.spinner("Procesando reclamación con los agentes (puede tardar unos segundos)..."):
        start = time.time()
        try:
            result = _run(process_claim(**payload))
            result["_elapsed"] = time.time() - start
            result["_claim_id"] = claim_id
            result["_client_id"] = client_id
            result["_claim_type"] = claim_type
            result["_amount_requested"] = float(amount)
            st.session_state["last_result"] = result
            st.session_state["history"].insert(0, result)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Error procesando la reclamación: {exc}")


# ── Cuerpo principal ───────────────────────────────────────────────────────

tab_detail, tab_history = st.tabs(["  Expediente actual  ", "  Historial  "])

with tab_detail:
    result = st.session_state.get("last_result")
    if not result:
        st.markdown('<div class="sca-card">Configura una reclamación en el panel '
                    'lateral y pulsa <b>Procesar reclamación</b> para ver el expediente '
                    'y el razonamiento de los agentes.</div>', unsafe_allow_html=True)
        st.markdown('<div class="sca-section">Escenarios sugeridos</div>', unsafe_allow_html=True)
        st.markdown("""
- **Pago automático** — Daños propios · 2.500 € · todos los documentos.
- **Revisión humana (HITL)** — Responsabilidad civil · 9.500 € · todos los documentos.
- **Información requerida** — Daños propios · 3.000 € · deselecciona documentos.
- **Rechazo** — Daños mecánicos · 1.500 € (sin cobertura en póliza).
""")
    else:
        amount_paid = (result.get("resolution") or {}).get("amount_paid")
        col_h1, col_h2 = st.columns([3, 2])
        with col_h1:
            st.markdown(f"### Expediente {result.get('_claim_id', '')}")
            st.markdown(decision_pill(result), unsafe_allow_html=True)
        with col_h2:
            reason_term = result.get("termination_reason")
            if reason_term:
                st.markdown(f'<div style="text-align:right;color:{C_TEXT_SOFT};'
                            f'font-size:13px;margin-top:8px">{reason_term}</div>',
                            unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(metric_card("Estado", result.get("status", "—")), unsafe_allow_html=True)
        c2.markdown(metric_card("Decisión", result.get("decision") or "—"), unsafe_allow_html=True)
        c3.markdown(metric_card(
            "Importe pagado",
            f"{amount_paid:,.0f} €" if amount_paid else "—",
            f"de {result.get('_amount_requested', 0):,.0f} € solicitados",
        ), unsafe_allow_html=True)
        c4.markdown(metric_card("Tiempo", f"{result.get('_elapsed', 0):.1f} s"),
                    unsafe_allow_html=True)

        fraud = result.get("fraud_result") or {}
        if fraud:
            verdict = fraud.get("verdict") or (
                "FLAGGED" if fraud.get("is_flagged") else "CLEAR")
            score = fraud.get("risk_score") or fraud.get("score")
            kind = "error" if fraud.get("is_flagged") else "success"
            extra = f" · score {score:.2f}" if isinstance(score, (int, float)) else ""
            st.markdown('<div class="sca-section">Cribado antifraude (Agente G)</div>',
                        unsafe_allow_html=True)
            st.markdown(pill(f"{verdict}{extra}", kind), unsafe_allow_html=True)

        st.markdown('<div class="sca-section">Cadena de razonamiento de los agentes</div>',
                    unsafe_allow_html=True)
        render_timeline(result)


with tab_history:
    history = st.session_state.get("history", [])
    st.markdown('<div class="sca-section">Expedientes procesados en esta sesión</div>',
                unsafe_allow_html=True)
    if not history:
        st.markdown('<div class="sca-card">Aún no se ha procesado ninguna reclamación.</div>',
                    unsafe_allow_html=True)
    else:
        rows = [{
            "Expediente": r.get("_claim_id"),
            "Cliente": r.get("_client_id"),
            "Tipo": CLAIM_TYPES.get(r.get("_claim_type"), r.get("_claim_type")),
            "Estado": r.get("status"),
            "Decisión": r.get("decision"),
            "Solicitado (€)": r.get("_amount_requested"),
            "Pagado (€)": (r.get("resolution") or {}).get("amount_paid"),
        } for r in history]
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown('<div class="sca-section">Distribución por decisión</div>',
                    unsafe_allow_html=True)
        st.bar_chart(df["Decisión"].value_counts())
