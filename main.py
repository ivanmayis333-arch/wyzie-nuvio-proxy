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

    # Separar el ID de IMDb base si incluye temporada y episodio (ej. tt12345:1:2)
    parts = video_id.split(":")
    imdb_id = parts[0]
    
    params = {
        "id": imdb_id,
        "ai_translate": "es"
    }
    
    if len(parts) >= 3:
        params["season"] = parts[1]
        params["episode"] = parts[2]

    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # 1. Intentar endpoint de búsqueda estándar
            url = "https://api.wyzie.io/search"
            response = await client.get(url, headers=headers, params=params)
            
            # 2. Si retorna 404, intentar endpoint directo por ID de medio
            if response.status_code == 404:
                url_direct = f"https://api.wyzie.io/subtitles/{imdb_id}"
                response = await client.get(url_direct, headers=headers, params={"ai_translate": "es"})

            response.raise_for_status()
            data = response.json()

            # Wyzie puede responder con una lista o con un diccionario
            if isinstance(data, list):
                wyzie_subs = data
            else:
                wyzie_subs = data.get("subtitles", [])

            stremio_subs = []

            # Transformamos al formato estándar de Stremio / Nuvio
            for index, sub in enumerate(wyzie_subs):
                stremio_subs.append({
                    "id": sub.get("id", f"wyzie_ai_es_{index}"),
                    "url": sub.get("url", ""),
                    "lang": "spa"  # Código ISO de español para Stremio
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
    Ruta con parámetros extra (ej. cuando Nuvio pasa parámetros de temporada/episodio).
    """
    # Si el extra trae el formato S:E (ej. 1:2), anexarlo al ID
    full_id = f"{video_id}:{extra}" if ":" in extra else video_id
    return await fetch_wyzie_subtitles(user_api_key, full_id)
