from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Wyzie AI Subs Proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/{user_api_key}/manifest.json")
async def get_manifest(user_api_key: str):
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
    if not api_key:
        return {"subtitles": []}

    # Separar ID de IMDb si viene con formato de serie (tt12345:1:2)
    parts = video_id.split(":")
    imdb_id = parts[0]
    
    # Construcción de la petición usando la API oficial de Wyzie
    url = "https://api.wyzie.io/subtitles"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    # Parámetros estándar que requiere Wyzie
    params = {
        "id": imdb_id,
        "language": "es",
        "ai_translate": "true"
    }
    
    if len(parts) >= 3:
        params["season"] = parts[1]
        params["episode"] = parts[2]

    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            logger.info(f"Consultando Wyzie para ID: {imdb_id} con API Key: {api_key[:4]}***")
            response = await client.get(url, headers=headers, params=params)
            
            # Si el endpoint base /subtitles devuelve 404, probamos el endpoint de Stremio oficial
            if response.status_code == 404:
                alt_url = f"https://stremio.wyzie.io/{api_key}/subtitles/movie/{imdb_id}.json"
                response = await client.get(alt_url)

            if response.status_code == 200:
                data = response.json()
                wyzie_subs = data if isinstance(data, list) else data.get("subtitles", [])
                
                stremio_subs = []
                for index, sub in enumerate(wyzie_subs):
                    stremio_subs.append({
                        "id": sub.get("id", f"wyzie_ai_es_{index}"),
                        "url": sub.get("url", ""),
                        "lang": "spa"
                    })
                return {"subtitles": stremio_subs}
            else:
                logger.warning(f"Respuesta inesperada de Wyzie: Status {response.status_code}")

        except Exception as e:
            logger.error(f"Error procesando petición a Wyzie: {e}")

    return {"subtitles": []}

@app.get("/{user_api_key}/subtitles/{video_type}/{video_id}.json")
async def get_subtitles_base(user_api_key: str, video_type: str, video_id: str):
    return await fetch_wyzie_subtitles(user_api_key, video_id)

@app.get("/{user_api_key}/subtitles/{video_type}/{video_id}/{extra:path}.json")
async def get_subtitles_extra(user_api_key: str, video_type: str, video_id: str, extra: str):
    full_id = f"{video_id}:{extra}" if ":" in extra else video_id
    return await fetch_wyzie_subtitles(user_api_key, full_id)
