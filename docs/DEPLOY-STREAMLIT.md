# Despliegue en Streamlit Community Cloud

Guía para publicar el dashboard **Smart-Claims Agent** en Streamlit Cloud.

## Qué se despliega

El fichero raíz **`streamlit_app.py`** es una app **autónoma**: ejecuta el grafo de
agentes (`process_claim`) **en el mismo proceso**, sin backend FastAPI ni MariaDB. Esto
es necesario porque Streamlit Community Cloud solo ejecuta **un proceso Python** (no puede
levantar los 5 servicios Docker del proyecto).

- **UI:** estética Salesforce Lightning + identidad de marca Seguros Pepín (logo real,
  azul corporativo, acento naranja).
- **Persistencia:** best-effort. En Streamlit Cloud no hay MariaDB, así que la escritura
  en BD se omite con un aviso y el historial se mantiene en memoria de sesión.
- **LLM:** la clave de Anthropic se inyecta vía *Secrets* de Streamlit (ver abajo). Sin
  clave, el sistema sigue funcionando con el *fallback* determinista.

## Ficheros relevantes

| Fichero | Rol |
|---|---|
| `streamlit_app.py` | App Streamlit autónoma (punto de entrada del deploy) |
| `requirements.txt` (raíz) | Dependencias del deploy (versiones verificadas) |
| `.streamlit/secrets.toml.example` | Plantilla de secrets (la real va en el panel de Streamlit) |

> El `backend/requirements.txt` y `frontend/` siguen siendo para el despliegue Docker; el
> deploy de Streamlit Cloud usa **solo** `streamlit_app.py` + `requirements.txt` de la raíz.

## Pasos

1. **Accede a Streamlit Community Cloud:** https://share.streamlit.io e inicia sesión con
   **GitHub** (la cuenta debe tener acceso al repositorio `FreeBarnOwl/smart-claims-agent-vfull`;
   si no, pide ser añadido como colaborador).
2. **New app → From existing repo.**
   - Repository: `FreeBarnOwl/smart-claims-agent-vfull`
   - Branch: `main`
   - Main file path: `streamlit_app.py`
3. **Advanced settings:**
   - Python version: **3.11** o **3.12**.
   - **Secrets** (pega esto con tu clave real):
     ```toml
     ANTHROPIC_API_KEY = "sk-ant-api03-..."
     HITL_AMOUNT_THRESHOLD = "5000"
     ```
4. **Deploy.** El primer build instala `requirements.txt` (tarda unos minutos).
5. La app queda publicada en una URL `https://<algo>.streamlit.app`.

## Notas y limitaciones

- **Sin base de datos:** el historial vive en la sesión del navegador (se pierde al recargar
  del todo). Es lo esperado para una demo; la persistencia real requiere el despliegue Docker
  con MariaDB.
- **Coste:** cada reclamación hace varias llamadas a Claude (CoT). Controla el saldo de la
  cuenta de Anthropic. Sin clave, la demo usa el *fallback* determinista (gratis).
- **Arranque en frío:** las apps gratuitas de Streamlit se "duermen" tras inactividad; la
  primera carga tras dormir tarda un poco.
- **Seguridad:** la clave va en *Secrets* de Streamlit, nunca en el repositorio. El
  `.gitignore` ya ignora `.env` y `.streamlit/secrets.toml`.

## Prueba en local (opcional)

```powershell
# desde la raíz del repo
py -m streamlit run streamlit_app.py
```
En local, la clave se lee del `.env` (vía `load_dotenv`) o de `.streamlit/secrets.toml`.
