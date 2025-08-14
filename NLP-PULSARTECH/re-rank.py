# re-ranker.py

from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, CrossEncoder, util
from typing import List, Dict, Any
from contextlib import asynccontextmanager
import torch

# --- LÜTFEN GÜNCELLEYİN ---
BI_ENCODER_PATH = "paraphrase-multilingual-MiniLM-L12-v2"
CROSS_ENCODER_PATH = "cross-encoder/ms-marco-MiniLM-L-6-v2"

bi_encoder_model = None
cross_encoder_model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bi_encoder_model, cross_encoder_model
    print(f"[RE-RANKER] [INFO] Bi-Encoder modeli yerel yoldan yükleniyor: {BI_ENCODER_PATH}")
    bi_encoder_model = SentenceTransformer(BI_ENCODER_PATH)
    print(f"[RE-RANKER] [INFO] Cross-Encoder modeli yerel yoldan yükleniyor: {CROSS_ENCODER_PATH}")
    cross_encoder_model = CrossEncoder(CROSS_ENCODER_PATH, max_length=512)
    print("[RE-RANKER] [OK] Tum siralama modelleri basariyla yuklendi.")
    yield
    print("[RE-RANKER] [INFO] Servis durduruldu.")

app = FastAPI(title="Local Two-Stage Re-Ranking Service", lifespan=lifespan)

class DocumentSnippet(BaseModel): url: str; title: str; snippet: str
class ReRankRequest(BaseModel):
    original_query: str
    documents: List[DocumentSnippet]

@app.post("/rerank")
async def rerank_documents_two_stage(request: ReRankRequest) -> Dict[str, Any]:
    if not request.documents: return {"ranked_documents": []}
    doc_contents = [f"{doc.title} {doc.snippet}" for doc in request.documents]
    print(f"[RE-RANKER] Asama 1: {len(doc_contents)} aday Bi-Encoder ile on elemeye aliniyor...")
    corpus_embeddings = bi_encoder_model.encode(doc_contents, convert_to_tensor=True)
    query_embedding = bi_encoder_model.encode(request.original_query, convert_to_tensor=True)
    fast_scores = util.cos_sim(query_embedding, corpus_embeddings)[0]
    top_k_fast = min(5, len(doc_contents))
    top_results = torch.topk(fast_scores, k=top_k_fast)
    print(f"[RE-RANKER] Asama 2: En iyi {top_k_fast} aday Cross-Encoder ile siralanıyor...")
    cross_encoder_pairs = []
    top_indices = top_results.indices.tolist()
    for idx in top_indices:
        cross_encoder_pairs.append([request.original_query, doc_contents[idx]])
    if not cross_encoder_pairs: return {"ranked_documents": []}
    cross_scores = cross_encoder_model.predict(cross_encoder_pairs)
    final_ranked_docs = []
    for i, score in enumerate(cross_scores):
        original_doc_index = top_indices[i]
        doc_snippet = request.documents[original_doc_index]
        final_ranked_docs.append({"score": score.item(), "document": doc_snippet.dict()})
    final_ranked_docs.sort(key=lambda x: x['score'], reverse=True)
    return {"ranked_documents": final_ranked_docs}