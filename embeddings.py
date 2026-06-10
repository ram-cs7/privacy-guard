"""
PrivacyGuard — Embedding generation using Google Gemini text-embedding-004.
Used for MongoDB Vector Search similarity matching.
"""
import google.generativeai as genai
from config import EMBEDDING_MODEL, EMBEDDING_DIM


class EmbeddingClient:
    """Generate text embeddings via Gemini for MongoDB Vector Search."""

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)

    def embed(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
        """
        Generate a single embedding vector.
        task_type options: RETRIEVAL_DOCUMENT | RETRIEVAL_QUERY | SEMANTIC_SIMILARITY
        """
        text = text.strip()[:8000]          # API limit
        if not text:
            return [0.0] * EMBEDDING_DIM

        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=text,
            task_type=task_type,
        )
        return result["embedding"]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts, returning a list of vectors."""
        return [self.embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query (different task type for better retrieval)."""
        return self.embed(text, task_type="RETRIEVAL_QUERY")

    def embed_document_summary(self, scan_result: dict) -> list[float]:
        """
        Create a rich embedding from a scan result for semantic similarity search.
        Combines filename, summary, entity types, and regulations into one vector.
        """
        parts = [
            scan_result.get("summary", ""),
            "Entities: " + ", ".join(
                e.get("type", "") for e in scan_result.get("entities", [])
            ),
            "Regulations: " + ", ".join(scan_result.get("regulations_triggered", [])),
            "Risk: " + scan_result.get("overall_risk", ""),
        ]
        combined = " | ".join(filter(None, parts))
        return self.embed(combined)
