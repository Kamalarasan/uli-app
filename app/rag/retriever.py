import httpx
import logging
from typing import List
from app.config import settings
from app.rag.vector_store import vector_store

logger = logging.getLogger(__name__)

async def retrieve_and_rerank(query: str, k: int = 5, rerank_top_n: int = 3) -> List[str]:
    """Full RAG retrieval: embed query -> FAISS search -> NVIDIA reranker."""
    if not vector_store.is_initialized():
        await vector_store.initialize()
        
    docs = await vector_store.search(query, k=k)
    if not docs:
        return []
        
    reranked = await _rerank(query, docs, top_n=rerank_top_n)
    return reranked

async def _rerank(query: str, documents: List[str], top_n: int = 3) -> List[str]:
    """Rerank documents using NVIDIA reranker API."""
    url = f"{settings.NVIDIA_BASE_URL}/ranking"
    headers = {
        "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": settings.NVIDIA_RERANKER_MODEL,
        "query": {"text": query},
        "passages": [{"text": doc} for doc in documents]
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            rankings = data.get("rankings", [])
            # Sort by rank
            sorted_docs = []
            for rank_item in rankings:
                idx = rank_item["index"]
                if idx < len(documents):
                    sorted_docs.append(documents[idx])
                    
            return sorted_docs[:top_n]
    except Exception as e:
        logger.warning(f"Reranking API failed: {e}. Falling back to original order.")
        return documents[:top_n]
