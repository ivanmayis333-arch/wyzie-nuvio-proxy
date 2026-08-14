from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
import json
import urllib.parse
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

async def fetch_wyzie_subtitles(api_key: str, video_type: str, video_id: str, extra: str = None):
    if not api_key:
        return {"subtitles": []}

    # 1. Crear el objeto JSON que exige el servidor de Wyzie
    config_obj = {
        "apiKey": api_key,
        "languages": "es"
    }
    
    # 2. Convertir el JSON a string y codificarlo para la URL (URL Encoding)
    json_str = json.dumps(config_obj)
    encoded_config = urllib.parse.quote(json_str)

    # 3. Construir la URL con el sufijo correcto (película o serie)
    clean_type = "series" if video_type in ["series", "tv"] else "movie"
    
    if extra:
        endpoint = f"subtitles/{clean_type}/{video_id}/{extra}.json"
    else:
        endpoint = f"subtitles/{clean_type}/{video_id}.json"

    url = f"https://stremio.wyzie.io/{encoded_config}/{endpoint}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            logger.info(f"Enviando petición a Wyzie con JSON codificado: {url}")
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                wyzie_subs = data.get("subtitles", [])

                stremio_subs = []
                for index, sub in enumerate(wyzie_subs):
                    sub_url = sub.get("url", "")
                    
                    # Filtrar posibles mensajes de error o cuota formateados como subtítulos
                    if sub_url and "store.wyzie.io" not in sub_url and "no API key" not in sub_url:
                        stremio_subs.append({
                            "id": sub.get("id", f"wyzie_es_{index}"),
                            "url": sub_url,
                            "lang": "spa"
                        })
                
                return {"subtitles": stremio_subs}
            else:
                logger.warning(f"Wyzie devolvió respuesta HTTP {response.status_code}")

        except Exception as e:
            logger.error(f"Error al conectar con Wyzie: {e}")

    return {"subtitles": []}

@app.get("/{user_api_key}/subtitles/{video_type}/{video_id}.json")
async def get_subtitles_base(user_api_key: str, video_type: str, video_id: str):
    return await fetch_wyzie_subtitles(user_api_key, video_type, video_id)

@app.get("/{user_api_key}/subtitles/{video_type}/{video_id}/{extra:path}.json")
async def get_subtitles_extra(user_api_key: str, video_type: str, video_id: str, extra: str):
    return await fetch_wyzie_subtitles(user_api_key, video_type, video_id, extra)
