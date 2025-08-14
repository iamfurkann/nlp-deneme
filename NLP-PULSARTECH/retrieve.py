# retrieve_service.py

import asyncio
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from googleapiclient.discovery import build
from trafilatura import fetch_url, extract
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

# --- LÜTFEN GÜNCELLEYİN ---
GOOGLE_API_KEY = "AIzaSyD9EGmWuDExT5rMyuJeUDbj1-RUPCOI91k"
SEARCH_ENGINE_ID = "7591159fd88734d3d"
REDIS_URL = "rediss://default:ASZeAAIjcDE0NjliYmJkYjcwYmI0N2ZlOWQ0ZGI4ZmY1NTFmN2Q4NnAxMA@pet-goose-9822.upstash.io:6379"

PRIORITY_SITE = "yokatlas.yok.gov.tr"
redis_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    print("[RETRIEVER] Servis basliyor, Redis'e baglaniliyor...")
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        print("[RETRIEVER] [OK] Redis cache baglantisi kuruldu.")
    except Exception as e:
        print(f"[RETRIEVER] [HATA] Redis cache baglantisi kurulamadi: {e}")
        redis_client = None
    yield
    if redis_client: await redis_client.close()

app = FastAPI(title="Enriched Retriever Service", lifespan=lifespan)

class ExtractedEntity(BaseModel): entity_group: str; score: float; word: str; start: int; end: int
class RetrieveRequest(BaseModel):
    optimized_queries: Optional[List[str]] = []
    extracted_entities: Optional[List[ExtractedEntity]] = None
class FetchContentRequest(BaseModel): urls: List[str]

def construct_queries_from_entities(entities: List[ExtractedEntity]) -> List[str]:
    if not entities: return []
    grouped_entities = {}
    for entity in entities:
        group = entity.entity_group
        if group not in grouped_entities: grouped_entities[group] = []
        cleaned_word = entity.word.strip()
        grouped_entities[group].append(f'"{cleaned_word}"')
    uni_list, dept_list, info_list = list(set(grouped_entities.get("UNI", []))), list(set(grouped_entities.get("DEPT", []))), list(set(grouped_entities.get("INFO_TYPE", [])))
    new_queries = []
    for uni in uni_list:
        for dept in dept_list: new_queries.append(f"{uni} {dept}")
        for info in info_list: new_queries.append(f"{uni} {info}")
    for dept in dept_list:
        for info in info_list: new_queries.append(f"{dept} {info}")
    if not new_queries:
        for group in grouped_entities.values(): new_queries.extend(group)
    yok_atlas_queries = [f"{q} site:{PRIORITY_SITE}" for q in new_queries]
    final_queries = list(dict.fromkeys(yok_atlas_queries + new_queries))
    print(f"[RETRIEVER] [INFO] Varlıklardan üretilen yeni sorgular: {final_queries}")
    return final_queries

async def search_google_async(query: str) -> List[Dict[str, str]]:
    loop = asyncio.get_event_loop()
    service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
    def do_search():
        res = service.cse().list(q=query, cx=SEARCH_ENGINE_ID, num=3).execute()
        return [{"url": i.get('link'), "title": i.get('title'), "snippet": i.get('snippet')} for i in res.get('items', [])]
    try:
        results = await loop.run_in_executor(None, do_search)
        print(f"[RETRIEVER] [SEARCH] '{query}' icin {len(results)} sonuc bulundu.")
        return results
    except Exception as e:
        print(f"[RETRIEVER] [HATA] '{query}' icin Google arama hatasi: {e}")
        return []

@app.post("/retrieve", response_model=Dict[str, Any])
async def retrieve_snippets(request: RetrieveRequest):
    entity_based_queries = construct_queries_from_entities(request.extracted_entities or [])
    all_queries = list(dict.fromkeys(entity_based_queries + (request.optimized_queries or [])))
    if not all_queries: raise HTTPException(status_code=400, detail="Arama yapmak için hiçbir sorgu bulunamadı.")
    print(f"\n[RETRIEVER] Toplam {len(all_queries)} tekil sorgu ile arama başlatılıyor...")
    search_tasks = [search_google_async(query) for query in all_queries]
    results_list = await asyncio.gather(*search_tasks)
    unique_results = {result['url']: result for result_group in results_list for result in result_group if result.get('url')}
    final_results = list(unique_results.values())
    print(f"[RETRIEVER] Toplam {len(final_results)} adet tekil döküman özeti toplandı.")
    return {"data": final_results}

@app.post("/fetch_content")
async def fetch_full_content(request: FetchContentRequest):
    if not request.urls: return {"data": []}
    async def get_content(url: str):
        if not redis_client: return {"url": url, "content": "Cache servisi calismiyor."}
        cached_content = await redis_client.get(f"content:{url}")
        if cached_content:
            print(f"[RETRIEVER] [CACHE_HIT] {url}")
            return {"url": url, "content": cached_content}
        print(f"[RETRIEVER] [CACHE_MISS] {url} webden cekiliyor...")
        loop = asyncio.get_event_loop()
        try:
            downloaded = await loop.run_in_executor(None, fetch_url, url)
            content = extract(downloaded)
            if content:
                await redis_client.set(f"content:{url}", content, ex=86400)
                return {"url": url, "content": content}
        except Exception as e:
            print(f"[RETRIEVER] [HATA] Icerik Hatasi: {url} - {e}")
        return {"url": url, "content": "İçerik ayrıştırılamadı."}
    content_tasks = [get_content(url) for url in request.urls]
    results = await asyncio.gather(*content_tasks)
    return {"data": results}