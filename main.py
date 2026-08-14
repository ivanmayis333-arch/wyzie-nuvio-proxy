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

async def fetch_wyzie_subtitles(api_key: str, path_suffix: str):
    if not api_key:
        return {"subtitles": []}

    # 1. Crear el objeto JSON exacto sin espacios extra (separators=(',', ':'))
    clean_key = api_key.strip()
    config_obj = {
        "apiKey": clean_key,
        "languages": "es"
    }
    
    # 2. Convertir a JSON compacto y codificar para la URL
    json_compact = json.dumps(config_obj, separators=(',', ':'))
    encoded_config = urllib.parse.quote(json_compact)

    # 3. Construir la URL hacia el addon oficial de Stremio de Wyzie
    url = f"https://stremio.wyzie.io/{encoded_config}/{path_suffix}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        try:
            logger.info(f"Petición a Wyzie Stremio: {url}")
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                wyzie_subs = data.get("subtitles", [])

                stremio_subs = []
                for index, sub in enumerate(wyzie_subs):
                    sub_url = sub.get("url", "")
                    
                    # Filtrar posibles archivos de error o aviso que devuelva Wyzie
                    if sub_url and "notice.srt" not in sub_url and "invalid API key" not in sub_url and "store.wyzie.io" not in sub_url:
                        stremio_subs.append({
                            "id": sub.get("id", f"wyzie_es_{index}"),
                            "url": sub_url,
                            "lang": "spa",
                            "title": sub.get("title", sub.get("name", "Español (Wyzie AI)"))
                        })
                
                return {"subtitles": stremio_subs}
            else:
                logger.warning(f"Wyzie Stremio devolvió HTTP status: {response.status_code}")

        except Exception as e:
            logger.error(f"Error en proxy Wyzie: {e}")

    return {"subtitles": []}

@app.get("/{user_api_key}/subtitles/{video_type}/{video_id}.json")
async def get_subtitles_base(user_api_key: str, video_type: str, video_id: str):
    clean_type = "series" if video_type in ["series", "tv"] else "movie"
    path_suffix = f"subtitles/{clean_type}/{video_id}.json"
    return await fetch_wyzie_subtitles(user_api_key, path_suffix)

@app.get("/{user_api_key}/subtitles/{video_type}/{video_id}/{extra:path}.json")
async def get_subtitles_extra(user_api_key: str, video_type: str, video_id: str, extra: str):
    clean_type = "series" if video_type in ["series", "tv"] else "movie"
    path_suffix = f"subtitles/{clean_type}/{video_id}/{extra}.json"
    return await fetch_wyzie_subtitles(user_api_key, path_suffix)
