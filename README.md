# 🛡️ PrivacyGuard Agent

> AI-powered PII detection, compliance analysis & semantic audit search — built with Gemini + MongoDB Atlas

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Built with Gemini](https://img.shields.io/badge/Built%20with-Gemini-4285F4)](https://aistudio.google.com)
[![MongoDB Atlas](https://img.shields.io/badge/MongoDB-Atlas-00ED64)](https://mongodb.com)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B)](https://streamlit.io)

Built for the **Google Cloud Rapid Agent Hackathon 2026 — MongoDB Track**

---

## 🚀 What It Does

PrivacyGuard Agent goes beyond pattern matching. It uses Gemini's reasoning to:

1. **Pre-scan** — understand document type and predict risk before deep analysis
2. **Detect** — find explicit *and contextual* PII across chunked document segments
3. **Classify** — score risk (0–100) and map to GDPR, CCPA, HIPAA, PCI-DSS
4. **Store** — save full audit trail to MongoDB (GDPR Art. 30 compliant)
5. **Embed** — generate semantic vectors via Gemini text-embedding-004
6. **Search** — find similar past scans using MongoDB Vector Search

A rule-based scanner flags `john@email.com`. PrivacyGuard understands that *"the patient showed improvement"* in a medical note is health data — even without a name attached.

---

## ⚡ Run in Under 10 Minutes

### Prerequisites
- Python 3.10+
- [Gemini API key](https://aistudio.google.com/app/apikey) (free)
- [MongoDB Atlas cluster](https://cloud.mongodb.com) (free M0 tier works)

### 1. Clone
```bash
git clone https://github.com/YOUR_USERNAME/privacyguard-agent.git
cd privacyguard-agent
```

### 2. Install
```bash
pip install -r requirements.txt
```

### 3. Configure
```bash
cp .env.example .env
# Edit .env — add your Gemini API key and MongoDB URI
```

### 4. Run
```bash
streamlit run app.py
```
Open http://localhost:8501

### Docker
```bash
docker-compose up
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit UI                         │
│  Scan | Similarity Search | Dashboard | Audit | Setup   │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────▼───────────┐
         │   PrivacyGuard Agent   │  Gemini 1.5 Flash
         │                       │
         │  Step 1: Pre-scan     │  → Document type prediction
         │  Step 2: Chunk        │  → Split large documents
         │  Step 3: Detect       │  → Entity extraction per chunk
         │  Step 4: Deduplicate  │  → Merge overlapping detections
         │  Step 5: Classify     │  → Risk score + compliance map
         │  Step 6: Report       │  → Full markdown report
         └───────────┬───────────┘
                     │
    ┌────────────────▼────────────────────────────────┐
    │              MongoDB Atlas (MCP Partner)         │
    │                                                  │
    │  scans            → Full scan results            │
    │  entities         → Individual PII entities      │
    │  audit_log        → GDPR Art.30 processing log   │
    │  document_vectors → Gemini embedding vectors     │
    │                                                  │
    │  Vector Search    → Semantic similarity search   │
    │  Atlas Search     → Full-text search             │
    │  Aggregations     → Dashboard analytics          │
    └──────────────────────────────────────────────────┘
```

---

## 🗂️ Project Structure

```
privacyguard-agent/
├── app.py              # Streamlit UI (5 tabs)
├── agent.py            # Gemini multi-step PII detection agent
├── database.py         # MongoDB Atlas client (Vector + Atlas Search)
├── embeddings.py       # Gemini text-embedding-004 client
├── config.py           # Centralised configuration
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── LICENSE             # MIT
├── README.md
└── sample_docs/
    ├── medical.txt     # Test: medical record with PII
    └── financial.txt   # Test: loan application with PII
```

---

## 🔍 Detected Entity Types

| Type | Examples |
|---|---|
| NAME | Full names, usernames |
| EMAIL | All email formats |
| PHONE | International formats |
| SSN | Social security numbers |
| CREDIT_CARD | Card numbers + CVVs |
| ADDRESS | Full postal addresses |
| DOB | Dates of birth |
| HEALTH_INFO | Diagnoses, conditions, medications |
| FINANCIAL_INFO | Bank accounts, salaries, routing numbers |
| PASSPORT | Passport numbers |
| IP_ADDRESS | IPv4 and IPv6 |
| CREDENTIALS | API keys, passwords, tokens |
| OTHER_PII | Contextual / implicit PII |

---

## 🔧 MongoDB Features Used

| Feature | How Used |
|---|---|
| **MongoDB MCP Server** | Agent integration for natural language DB queries |
| **Vector Search** | Semantic similarity across past scans (cosine, 768-dim) |
| **Atlas Search** | Full-text search with fuzzy matching |
| **Aggregation Pipeline** | Dashboard stats, risk trends, entity breakdown |
| **GDPR Art.17 Delete** | Right-to-erasure implementation |
| **Multi-collection** | scans / entities / audit_log / document_vectors |

---

## ⚙️ Atlas Index Setup

After connecting, go to **Atlas UI → Atlas Search** and create:

**Vector Search index** on `document_vectors` collection:
```json
{
  "fields": [
    {"type": "vector", "path": "embedding", "numDimensions": 768, "similarity": "cosine"},
    {"type": "filter", "path": "overall_risk"}
  ]
}
```
Index name: `privacyguard_vector_index`

**Atlas Search index** on `scans` collection:
```json
{
  "mappings": {
    "dynamic": false,
    "fields": {
      "filename": {"type": "string"},
      "summary": {"type": "string"},
      "overall_risk": {"type": "string"}
    }
  }
}
```
Index name: `privacyguard_search_index`

---

## 📄 License

MIT — see [LICENSE](LICENSE)

---

*Built for Google Cloud Rapid Agent Hackathon 2026 — MongoDB Track*
