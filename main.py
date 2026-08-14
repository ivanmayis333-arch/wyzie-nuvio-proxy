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

async def fetch_wyzie_subtitles(api_key: str, video_type: str, video_id: str, extra: str = None):
    if not api_key:
        return {"subtitles": []}

    # Desglosar ID de IMDb (ej: tt18259538 o tt18259538:1:2)
    parts = video_id.split(":")
    imdb_id = parts[0]

    # Endpoint oficial de búsqueda de Wyzie
    url = "https://sub.wyzie.io/search"
    
    # Parámetros exactos requeridos según la documentación oficial
    params = {
        "id": imdb_id,
        "key": api_key,
        "language": "es"
    }

    # Si es una serie y vienen temporada y episodio
    if extra and ":" in extra:
        extra_parts = extra.split(":")
        params["season"] = extra_parts[0]
        params["episode"] = extra_parts[1]
    elif len(parts) >= 3:
        params["season"] = parts[1]
        params["episode"] = parts[2]

    # Cabeceras completas de navegador para evitar que Wyzie bloquee la petición desde Render
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://sub.wyzie.io",
        "Referer": "https://sub.wyzie.io/"
    }

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        try:
            logger.info(f"Consultando Wyzie API para ID: {imdb_id} con clave Pro...")
            response = await client.get(url, params=params, headers=headers)

            if response.status_code == 200:
                data = response.json()
                wyzie_subs = data if isinstance(data, list) else data.get("subtitles", [])

                stremio_subs = []
                for index, sub in enumerate(wyzie_subs):
                    sub_url = sub.get("url", "")
                    
                    # Descartar archivos de aviso o error
                    if sub_url and "notice.srt" not in sub_url and "invalid API key" not in sub_url:
                        display_name = sub.get("display", sub.get("name", "Español (Wyzie AI)"))
                        
                        stremio_subs.append({
                            "id": sub.get("id", f"wyzie_es_{index}"),
                            "url": sub_url,
                            "lang": "spa",
                            "title": display_name
                        })
                
                return {"subtitles": stremio_subs}
            else:
                logger.warning(f"Wyzie API devolvió status HTTP: {response.status_code}")

        except Exception as e:
            logger.error(f"Error procesando petición a Wyzie: {e}")

    return {"subtitles": []}

@app.get("/{user_api_key}/subtitles/{video_type}/{video_id}.json")
async def get_subtitles_base(user_api_key: str, video_type: str, video_id: str):
    return await fetch_wyzie_subtitles(user_api_key, video_type, video_id)

@app.get("/{user_api_key}/subtitles/{video_type}/{video_id}/{extra:path}.json")
async def get_subtitles_extra(user_api_key: str, video_type: str, video_id: str, extra: str):
    return await fetch_wyzie_subtitles(user_api_key, video_type, video_id, extra)
