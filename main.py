from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
import logging

# Configuración básica de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Wyzie AI Subs Proxy")

# Configuración estricta de CORS para compatibilidad con Nuvio/Stremio Web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/{user_api_key}/manifest.json")
async def get_manifest(user_api_key: str):
    """
    Retorna el manifest oficial de Stremio.
    El user_api_key se mantiene dinámico en la URL para cada usuario.
    """
    return {
        "id": "org.wyzie.aitranslate.public",
        "version": "1.0.0",
        "name": "Wyzie AI Subs (Public)",
        "description": "Proxy privado para subtítulos traducidos por IA usando tu propia API Key de Wyzie.",
        "resources": ["subtitles"],
        "types": ["movie", "series"],
        "idPrefixes": ["tt"],
        "behaviorHints": {
            "configurable": True,
            "configurationRequired": True
        }
    }

async def fetch_wyzie_subtitles(api_key: str, video_id: str):
    """
    Función core que realiza la petición a la API de Wyzie.
    """
    if not api_key:
        return {"subtitles": []}

    url = "https://api.wyzie.io/v1/subtitles"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    params = {
        "id": video_id,
        "ai_translate": "es"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            # Extraemos la lista de subtítulos de la respuesta de Wyzie
            wyzie_subs = data.get("subtitles", [])
            stremio_subs = []

            # Transformamos al formato estándar de Stremio
            for index, sub in enumerate(wyzie_subs):
                stremio_subs.append({
                    "id": sub.get("id", f"wyzie_ai_es_{index}"),
                    "url": sub.get("url", ""),
                    "lang": "spa"  # Estandarizado a español de España/Latino según Stremio
                })

            return {"subtitles": stremio_subs}

        except httpx.HTTPError as e:
            logger.error(f"Error HTTP en Wyzie API: {e}")
            return {"subtitles": []}
        except Exception as e:
            logger.error(f"Error procesando subtítulos: {e}")
            return {"subtitles": []}

@app.get("/{user_api_key}/subtitles/{video_type}/{video_id}.json")
async def get_subtitles_base(user_api_key: str, video_type: str, video_id: str):
    """
    Ruta estándar para películas y series sin parámetros extra.
    """
    return await fetch_wyzie_subtitles(user_api_key, video_id)

@app.get("/{user_api_key}/subtitles/{video_type}/{video_id}/{extra:path}.json")
async def get_subtitles_extra(user_api_key: str, video_type: str, video_id: str, extra: str):
    """
    Ruta con parámetros extra (a veces Stremio envía hash de video u otros metadatos).
    """
    return await fetch_wyzie_subtitles(user_api_key, video_id)