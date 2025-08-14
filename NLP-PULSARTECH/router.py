# strategic_router_service.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import google.generativeai as genai
import json
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
from transformers import pipeline
import torch
import os

GEMINI_API_KEY = "AIzaSyD9EGmWuDExT5rMyuJeUDbj1-RUPCOI91k"

INTENT_MODEL_PATH = "C:\\Users\\esadf\\OneDrive\\Masaüstü\\NLP-PULSARTECH\\Intent"
NER_MODEL_PATH = "C:\\Users\\esadf\\OneDrive\\Masaüstü\\NLP-PULSARTECH\\Ner_Search"

TASK_ORIENTED_INTENTS = [
    "universite_bilgisi_isteme", "bolum_bilgisi_isteme", "kontenjan_bilgisi_isteme",
    "taban_puan_bilgisi_isteme", "burs_bilgisi_isteme", "iletisim_bilgisi_isteme",
    "konum_bilgisi_isteme", "universite_karsilastirma", "bolum_karsilastirma",
    "puan_kontenjan_karsilastirma", "tercih_tavsiyesi_isteme", "yurt_bilgisi_isteme",
]

NER_EXCLUSION_INTENTS = {
    "puan_kontenjan_karsilastirma",
    "universite_karsilastirma",
    "bolum_karsilastirma",
    "tercih_tavsiyesi_isteme",
    "kariyer_rehberligi_isteme"
}

intent_pipeline = None
ner_pipeline = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global intent_pipeline, ner_pipeline
    print("[ROUTER] --- Modeller Yükleniyor ---")
    device = 0 if torch.cuda.is_available() else -1
    print(f"[ROUTER] Kullanılacak cihaz: {'GPU' if device == 0 else 'CPU'}")
    try:
        if os.path.isdir(INTENT_MODEL_PATH):
            intent_pipeline = pipeline("text-classification", model=INTENT_MODEL_PATH, tokenizer=INTENT_MODEL_PATH, device=device)
            print(f"[ROUTER] [OK] Niyet Tanıma modeli yüklendi.")
        else: raise FileNotFoundError(f"Niyet modeli klasörü bulunamadı: {INTENT_MODEL_PATH}")
        
        if os.path.isdir(NER_MODEL_PATH):
            ner_pipeline = pipeline("ner", model=NER_MODEL_PATH, tokenizer=NER_MODEL_PATH, aggregation_strategy="simple", device=device)
            print(f"[ROUTER] [OK] NER modeli yüklendi.")
        else: raise FileNotFoundError(f"NER model klasörü bulunamadı: {NER_MODEL_PATH}")
            
    except Exception as e: 
        print(f"[ROUTER] [HATA] Modeller yüklenemedi: {e}")
    
    print("[ROUTER] --- Model Yükleme Tamamlandı ---")
    yield
    print("[ROUTER] [INFO] Servis durduruldu.")

class QueryRequest(BaseModel):
    user_query: str

class ExecutionPlan(BaseModel):
    action_type: str
    detailed_intent: str
    extracted_entities: Optional[List[Dict[str, Any]]] = None
    optimized_queries: Optional[List[str]] = None

app = FastAPI(title="Strategic Conditional Router Service", lifespan=lifespan)
genai.configure(api_key=GEMINI_API_KEY)

async def call_gemini_for_queries(user_query: str):
    """Gemini'yi arayarak arama sorguları üretir."""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash-latest")
        config = {"response_mime_type": "application/json"}
        prompt = f'Kullanıcı Sorusu: "{user_query}"\nBu soruya en uygun 1-3 adet Google arama sorgusunu bir JSON listesi olarak ver. Örnek: ["sorgu 1", "sorgu 2"]'
        response = await model.generate_content_async(prompt, generation_config=config)
        return response.text.strip()
    except Exception as e:
        print(f"!! [ROUTER] Gemini Cagri Hatasi (Sorgu Uretimi): {e}")
        return None

@app.post("/create_plan", response_model=ExecutionPlan)
async def create_execution_plan(request: QueryRequest):
    if not intent_pipeline:
        raise HTTPException(status_code=503, detail="Niyet modeli şu an kullanılamıyor.")

    intent_result_raw = intent_pipeline(request.user_query)[0]
    detected_intent = intent_result_raw.get('label', 'anlasilmadi')
    action_type = "RAG_SEARCH" if detected_intent in TASK_ORIENTED_INTENTS else "DIRECT_CHAT"

    print(f"[ROUTER] Niyet: {detected_intent}, Eylem: {action_type}")

    extracted_entities, optimized_queries = None, None

    if action_type == "RAG_SEARCH":
        if detected_intent in NER_EXCLUSION_INTENTS:
            print(f"[ROUTER] Özel planlama niyeti ({detected_intent}), NER modeli atlanıyor.")
            queries_response_str = await call_gemini_for_queries(request.user_query)
            if queries_response_str:
                try:
                    optimized_queries = json.loads(queries_response_str)
                except (json.JSONDecodeError, TypeError):
                    optimized_queries = [request.user_query]
            else:
                optimized_queries = [request.user_query]
        else:
            print(f"[ROUTER] Standart görev niyeti ({detected_intent}), NER modeli çalıştırılıyor.")
            if ner_pipeline:
                print("[ROUTER] Türkçe karakter uyumluluğu için metin küçültülüyor...")
                query_for_nlp = request.user_query.casefold()
                entities_raw = ner_pipeline(query_for_nlp)
            
            queries_response_str = await call_gemini_for_queries(request.user_query)
            if queries_response_str:
                try: optimized_queries = json.loads(queries_response_str)
                except (json.JSONDecodeError, TypeError): optimized_queries = [request.user_query]
            else: optimized_queries = [request.user_query]

        if optimized_queries:
            print(f"[ROUTER] Üretilen Sorgular: {optimized_queries}")

    return ExecutionPlan(
        action_type=action_type, 
        detailed_intent=detected_intent, 
        extracted_entities=extracted_entities, 
        optimized_queries=optimized_queries
    )