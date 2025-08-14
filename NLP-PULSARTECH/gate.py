# main_gateway.py

import asyncio
import aiohttp
from fastapi import FastAPI
from pydantic import BaseModel
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from typing import List, Dict, Any

# --- LÜTFEN GÜNCELLEYİN ---
GEMINI_API_KEY = "AIzaSyD9EGmWuDExT5rMyuJeUDbj1-RUPCOI91k"

# --- Servis Adresleri ---
ROUTER_URL = "http://127.0.0.1:8001/create_plan"
RETRIEVER_URL = "http://127.0.0.1:8000"
RERANKER_URL = "http://127.0.0.1:8002/rerank"

# --- Prompt Şablonları ---
PROMPT_ANALYZE_FULL_CONTENT = """
SENARYO: Sana, bir kullanıcının sorusunu cevaplamak için web'den toplanmış en alakalı sayfaların tam metin içerikleri verildi. Sen, bu detaylı içerikleri derinlemesine analiz ederek, veriye dayalı, nihai ve eksiksiz bir cevap hazırlayan uzman bir araştırma analistisin.
KULLANICININ ORİJİNAL SORUSU: "{user_query}"
--- SANA SUNULAN TAM SAYFA İÇERİKLERİ (Numaralandırılmış) ---
{context}
--- İÇERİKLERİN SONU ---
GÖREVİN: Yukarıdaki tam sayfa içeriklerini kullanarak kullanıcının sorusunu en iyi ve en eksiksiz şekilde cevaplayan, kapsamlı ve yapılandırılmış bir metin oluştur. Cevabını SADECE sana sunulan verilere dayandır.
KURALLAR:
1. Eğer bir üniversite veya bölüm listesi sunuyorsan, bunu MUTLAKA Markdown tablosu formatında oluştur.
2. Cevabının en sonuna, "---" ile ayırarak, "Kaynaklar" başlığı altında kullandığın kaynakların tam URL listesini numaralandırarak ekle.
"""
PROMPT_DIRECT_CHAT = """
Sen empatik bir tercih danışmanısın. Adın 'Rehber Asistan'. Şu mesaja uygun bir cevap ver: "{user_query}"
"""

# --- Uygulama ---
app = FastAPI(title="Always-Detailed RAG Gateway")
genai.configure(api_key=GEMINI_API_KEY)
class AskRequest(BaseModel): query: str
DEFAULT_SAFETY_SETTINGS = { HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE, }

async def call_gemini_synthesis(prompt: str, model_name: str = "gemini-1.5-flash-latest"):
    try:
        model = genai.GenerativeModel(model_name, safety_settings=DEFAULT_SAFETY_SETTINGS)
        response = await model.generate_content_async(prompt, generation_config={"temperature": 0.2})
        return response.text
    except Exception as e:
        print(f"!! [GATEWAY] Gemini Sentezleme Hatasi: {e}")
        return "Üzgünüm, bilgileri sentezlerken bir sorunla karşılaştım."

@app.post("/ask_intelligent")
async def ask_intelligent_system(request: AskRequest):
    original_query = request.query
    timeout = aiohttp.ClientTimeout(total=180)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        print(f"\n[GATEWAY] Yeni sorgu alindi: '{original_query}'")
        try:
            async with session.post(ROUTER_URL, json={"user_query": original_query}) as resp:
                resp.raise_for_status(); plan = await resp.json()
        except aiohttp.ClientError as e: return {"answer": f"Yönlendirici servisine baglanirken hata olustu: {e}", "sources_used": []}

        action_type = plan.get("action_type")
        print(f"[GATEWAY] Yönlendirici karari: Eylem={action_type}")

        if action_type == "DIRECT_CHAT":
            chat_prompt = PROMPT_DIRECT_CHAT.format(user_query=original_query)
            return {"answer": await call_gemini_synthesis(chat_prompt), "sources_used": []}

        if action_type == "RAG_SEARCH":
            print("\n[GATEWAY] --- HER ZAMAN DERİN ARAMA MODU AKTİF ---")
            
            # Adım 1: Özetleri al ve sırala
            retriever_payload = {"optimized_queries": plan.get("optimized_queries", []), "extracted_entities": plan.get("extracted_entities", [])}
            async with session.post(f"{RETRIEVER_URL}/retrieve", json=retriever_payload) as resp:
                if resp.status != 200: return {"answer": f"Retriever servisi hata verdi: {await resp.text()}", "sources_used": []}
                doc_snippets = (await resp.json()).get("data", [])
            if not doc_snippets: return {"answer": "Internet aramalarımda konuyla ilgili bir içerik bulamadım.", "sources_used": []}
            
            async with session.post(RERANKER_URL, json={"original_query": original_query, "documents": doc_snippets}) as resp:
                if resp.status != 200: return {"answer": f"Re-ranker servisi hata verdi: {await resp.text()}", "sources_used": []}
                ranked_snippets = (await resp.json()).get("ranked_documents", [])
            if not ranked_snippets: return {"answer": "Bulunan bilgiler sorunuzla yeterince alakalı görünmüyor.", "sources_used": []}

            # Adım 2: Sıralanmış en iyi kaynakların DOĞRUDAN tam içeriğini çek
            urls_to_fetch = [doc['document']['url'] for doc in ranked_snippets[:3]]
            print(f"[GATEWAY] En iyi {len(urls_to_fetch)} kaynağın tam içeriği çekiliyor...")
            async with session.post(f"{RETRIEVER_URL}/fetch_content", json={"urls": urls_to_fetch}) as resp:
                if resp.status != 200: return {"answer": f"Detaylı içerik çekilemedi: {await resp.text()}", "sources_used": []}
                full_content_docs = (await resp.json()).get("data", [])

            # Adım 3: Detaylı içerikle nihai cevabı üret
            context_parts_detailed = [f"--- KAYNAK [{i+1}]: {doc.get('url')} ---\n{doc.get('content')}" for i, doc in enumerate(full_content_docs) if doc.get('content')]
            if not context_parts_detailed:
                return {"answer": "İlgili dökümanların içeriği anlamlı bir şekilde işlenemedi.", "sources_used": []}
            
            detailed_sources = [doc.get('url') for doc in full_content_docs if doc.get('content')]
            detailed_answer_prompt = PROMPT_ANALYZE_FULL_CONTENT.format(user_query=original_query, context="\n\n".join(context_parts_detailed))
            final_answer = await call_gemini_synthesis(detailed_answer_prompt)
            print("[GATEWAY] Detaylı cevap üretildi. İşlem tamamlandı.")
            return {"answer": final_answer, "sources_used": detailed_sources}
        
        return {"answer": "Beklenmedik bir eylem tipi ile karşılaşıldı.", "sources_used": []}