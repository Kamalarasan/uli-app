import faiss
import numpy as np
import httpx
import json
import logging
from typing import List
from app.config import settings

logger = logging.getLogger(__name__)

POLICIES = [
    "DTI limits: max 40% for home loans, 35% for personal, 45% for business.",
    "Minimum income requirements by loan type: Personal loan minimum 30000 INR/month, Home loan 50000 INR/month.",
    "Credit score thresholds: minimum 650 for personal loans, 700 for home loans, 680 for auto loans.",
    "Tenure bounds: personal loans between 12-60 months, home loans between 12-360 months.",
    "Industry risk ratings: IT=LOW, MANUFACTURING=MEDIUM, RETAIL=HIGH, REAL ESTATE=HIGH.",
    "Fraud detection thresholds: Multiple address changes in 6 months flag for high risk.",
    "Employment stability requirements: min 1 year for salaried individuals, 2 years for self-employed.",
    "Self-employed income documentation requirements: Minimum 2 years of ITR and 12 months bank statements.",
    "Maximum loan-to-income ratios: Personal loans max 12x monthly income, Home loans max 60x.",
    "Interest rate bands by risk tier: Tier 1 (750+ score) 10%, Tier 2 (700-749) 12%, Tier 3 (<700) 14%.",
    "Age requirements: Minimum 21 years at loan application, maximum 60 years at loan maturity for salaried.",
    "Co-applicant requirements: Mandatory for home loans if primary applicant income is below 50000.",
    "Property valuation: Loan amount cannot exceed 80% of registered property value.",
    "Business vintage: Minimum 3 years of continuous operation for unsecured business loans.",
    "Bounce history: Max 2 bounces allowed in the last 6 months for any loan approval.",
    "Existing debt: Must be factored into DTI calculations using EMI amounts from credit report.",
    "Address verification: Mandatory physical verification if Aadhaar address does not match current address.",
    "Guarantor rules: Required for education loans above 7.5 Lakhs.",
    "Prepayment penalties: 0% for floating rate home loans, 2% for personal loans.",
    "Loan disbursement: Only to the applicant's verified bank account via NEFT/RTGS."
]

class VectorStore:
    def __init__(self):
        self.index = None
        self.documents = []
        self.dimension = 4096
    
    async def initialize(self):
        """Initialize and seed the vector store."""
        embeddings = await self._embed_documents(POLICIES)
        self.documents = POLICIES
        vectors = np.array(embeddings, dtype=np.float32)
        # Normalize for cosine similarity
        faiss.normalize_L2(vectors)
        self.index = faiss.IndexFlatIP(self.dimension)
        self.index.add(vectors)
        logger.info(f"Vector store initialized with {len(POLICIES)} policy documents")
    
    async def _embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings via NVIDIA NV-Embed API."""
        url = f"{settings.NVIDIA_BASE_URL}/embeddings"
        headers = {
            "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json={"input": texts, "model": settings.NVIDIA_EMBED_MODEL, "input_type": "query"}
                )
                response.raise_for_status()
                data = response.json()
                return [d["embedding"] for d in data["data"]]
        except Exception as e:
            logger.warning(f"Failed to use NVIDIA embedding API: {e}. Falling back to random embeddings.")
            return np.random.rand(len(texts), self.dimension).tolist()
    
    async def search(self, query: str, k: int = 5) -> List[str]:
        """Search for relevant policies given a query."""
        if not self.index:
            return []
        
        query_embedding = await self._embed_documents([query])
        q_vec = np.array(query_embedding, dtype=np.float32)
        faiss.normalize_L2(q_vec)
        
        distances, indices = self.index.search(q_vec, k)
        results = []
        for idx in indices[0]:
            if idx < len(self.documents) and idx >= 0:
                results.append(self.documents[idx])
        return results
    
    def is_initialized(self) -> bool:
        return self.index is not None

vector_store = VectorStore()
