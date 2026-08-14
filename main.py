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

async def fetch_wyzie_subtitles(api_key: str, video_type: str, video_id: str):
    if not api_key:
        return {"subtitles": []}

    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            # Petición directa al addon oficial de Wyzie concatenando la API Key correctamente
            # Wyzie acepta la clave en la URL como: https://stremio.wyzie.io/token=<API_KEY>/subtitles/...
            # O en formato base: https://stremio.wyzie.io/<API_KEY>/subtitles/...
            
            clean_type = "series" if video_type in ["series", "tv"] else "movie"
            url = f"https://stremio.wyzie.io/{api_key}/subtitles/{clean_type}/{video_id}.json"
            
            params = {
                "ai_translate": "true",
                "langs": "es"
            }

            logger.info(f"Pidiendo subtítulos a Wyzie para {video_id}...")
            response = await client.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                wyzie_subs = data.get("subtitles", [])
                
                stremio_subs = []
                for index, sub in enumerate(wyzie_subs):
                    stremio_subs.append({
                        "id": sub.get("id", f"wyzie_ai_es_{index}"),
                        "url": sub.get("url", ""),
                        "lang": "spa"
                    })
                return {"subtitles": stremio_subs}
            else:
                logger.warning(f"Wyzie respondió status: {response.status_code}")

        except Exception as e:
            logger.error(f"Error procesando petición: {e}")

    return {"subtitles": []}

@app.get("/{user_api_key}/subtitles/{video_type}/{video_id}.json")
async def get_subtitles_base(user_api_key: str, video_type: str, video_id: str):
    return await fetch_wyzie_subtitles(user_api_key, video_type, video_id)

@app.get("/{user_api_key}/subtitles/{video_type}/{video_id}/{extra:path}.json")
async def get_subtitles_extra(user_api_key: str, video_type: str, video_id: str, extra: str):
    full_id = f"{video_id}:{extra}" if extra else video_id
    return await fetch_wyzie_subtitles(user_api_key, video_type, full_id)
