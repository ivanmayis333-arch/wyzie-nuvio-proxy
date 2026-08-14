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

    # Separar el ID de IMDb si es un episodio de serie (ejemplo: tt18259538:1:2)
    parts = video_id.split(":")
    imdb_id = parts[0]

    # Endpoint oficial exacto según la documentación de Wyzie:
    # https://sub.wyzie.io/search?id=...&key=...
    url = "https://sub.wyzie.io/search"
    
    params = {
        "id": imdb_id,
        "key": api_key,
        "language": "es",
        "ai_translate": "true"
    }

    # Si es una serie y vienen temporada y episodio
    if len(parts) >= 3:
        params["season"] = parts[1]
        params["episode"] = parts[2]

    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            logger.info(f"Consultando Wyzie oficial en sub.wyzie.io para ID: {imdb_id}")
            response = await client.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                wyzie_subs = data if isinstance(data, list) else data.get("subtitles", [])

                stremio_subs = []
                for index, sub in enumerate(wyzie_subs):
                    sub_url = sub.get("url", "")
                    
                    # Ignorar respuestas de error formateadas como subtítulo
                    if sub_url and "no API key set" not in sub_url:
                        stremio_subs.append({
                            "id": sub.get("id", f"wyzie_ai_es_{index}"),
                            "url": sub_url,
                            "lang": "spa"
                        })
                
                return {"subtitles": stremio_subs}
            else:
                logger.warning(f"Wyzie devolvió status code: {response.status_code}")

        except Exception as e:
            logger.error(f"Error consultando la API de Wyzie: {e}")

    return {"subtitles": []}

@app.get("/{user_api_key}/subtitles/{video_type}/{video_id}.json")
async def get_subtitles_base(user_api_key: str, video_type: str, video_id: str):
    clean_type = "series" if video_type in ["series", "tv"] else "movie"
    return await fetch_wyzie_subtitles(user_api_key, clean_type, video_id)

@app.get("/{user_api_key}/subtitles/{video_type}/{video_id}/{extra:path}.json")
async def get_subtitles_extra(user_api_key: str, video_type: str, video_id: str, extra: str):
    clean_type = "series" if video_type in ["series", "tv"] else "movie"
    full_id = f"{video_id}:{extra}" if extra else video_id
    return await fetch_wyzie_subtitles(user_api_key, clean_type, full_id)
