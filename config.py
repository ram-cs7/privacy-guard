"""PrivacyGuard Agent — centralised configuration."""
import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MONGODB_URI    = os.getenv("MONGODB_URI", "")
DB_NAME        = os.getenv("DB_NAME", "privacyguard")

# ── MongoDB collections ───────────────────────────────────────────────────────
SCANS_COLLECTION    = "scans"
ENTITIES_COLLECTION = "entities"
AUDIT_COLLECTION    = "audit_log"
VECTORS_COLLECTION  = "document_vectors"

# ── Models ────────────────────────────────────────────────────────────────────
GEMINI_MODEL     = "gemini-3.5-flash"
EMBEDDING_MODEL  = "models/gemini-embedding-2"
EMBEDDING_DIM    = 768          # gemini-embedding-2 output dimension

# ── Vector Search ─────────────────────────────────────────────────────────────
VECTOR_INDEX_NAME  = "privacyguard_vector_index"
ATLAS_SEARCH_INDEX = "privacyguard_search_index"
VECTOR_CANDIDATES  = 100
VECTOR_RESULTS     = 5

# ── Agent settings ────────────────────────────────────────────────────────────
MAX_CHUNK_SIZE   = 3000
CHUNK_OVERLAP    = 200
MAX_TOKENS       = 8192
TEMPERATURE      = 0.1

# ── Compliance frameworks ─────────────────────────────────────────────────────
COMPLIANCE_FRAMEWORKS = ["GDPR", "CCPA", "HIPAA", "PCI-DSS"]

# ── Risk levels ───────────────────────────────────────────────────────────────
RISK_COLORS = {
    "CRITICAL": "#ff4b4b",
    "HIGH":     "#ff8c00",
    "MEDIUM":   "#ffd700",
    "LOW":      "#00c851",
    "UNKNOWN":  "#aaaaaa",
}

# ── PII Entity types ──────────────────────────────────────────────────────────
ENTITY_TYPES = [
    "NAME", "EMAIL", "PHONE", "SSN", "CREDIT_CARD",
    "ADDRESS", "DOB", "HEALTH_INFO", "FINANCIAL_INFO",
    "PASSPORT", "IP_ADDRESS", "CREDENTIALS", "OTHER_PII"
]
