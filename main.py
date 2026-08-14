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

async def forward_to_wyzie_addon(api_key: str, path_suffix: str):
    if not api_key:
        return {"subtitles": []}

    # Configuración oficial requerida por el addon de Stremio de Wyzie
    config_data = {
        "apiKey": api_key,
        "languages": "es"
    }
    
    # Codificar el JSON para la URL
    encoded_config = urllib.parse.quote(json.dumps(config_data))

    # Construir la URL exacta del addon oficial de Stremio
    target_url = f"https://stremio.wyzie.io/{encoded_config}/{path_suffix}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        try:
            logger.info(f"Redirigiendo petición al addon oficial de Wyzie: {target_url}")
            response = await client.get(target_url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                wyzie_subs = data.get("subtitles", [])

                stremio_subs = []
                for index, sub in enumerate(wyzie_subs):
                    sub_url = sub.get("url", "")
                    
                    # Filtrar errores falsos devueltos como archivos SRT
                    if sub_url and "notice.srt" not in sub_url and "invalid API key" not in sub_url:
                        stremio_subs.append({
                            "id": sub.get("id", f"wyzie_es_{index}"),
                            "url": sub_url,
                            "lang": "spa",
                            "title": sub.get("title", sub.get("name", "Español (Wyzie AI)"))
                        })
                
                return {"subtitles": stremio_subs}
            else:
                logger.warning(f"El addon oficial respondió con código HTTP {response.status_code}")

        except Exception as e:
            logger.error(f"Error conectando con el addon oficial: {e}")

    return {"subtitles": []}

@app.get("/{user_api_key}/subtitles/{video_type}/{video_id}.json")
async def get_subtitles_base(user_api_key: str, video_type: str, video_id: str):
    clean_type = "series" if video_type in ["series", "tv"] else "movie"
    path_suffix = f"subtitles/{clean_type}/{video_id}.json"
    return await forward_to_wyzie_addon(user_api_key, path_suffix)

@app.get("/{user_api_key}/subtitles/{video_type}/{video_id}/{extra:path}.json")
async def get_subtitles_extra(user_api_key: str, video_type: str, video_id: str, extra: str):
    clean_type = "series" if video_type in ["series", "tv"] else "movie"
    path_suffix = f"subtitles/{clean_type}/{video_id}/{extra}.json"
    return await forward_to_wyzie_addon(user_api_key, path_suffix)
