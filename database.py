"""
PrivacyGuard — MongoDB Atlas client.

Features:
  • Standard CRUD for scans, entities, audit log
  • Vector Search  — semantic similarity across past scans
  • Atlas Search   — full-text search across audit history
  • MCP-compatible — structured for MongoDB MCP server tool calls
  • GDPR Art.17    — right-to-erasure delete
"""

from __future__ import annotations
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.operations import SearchIndexModel
import config


class MongoDBClient:
    """
    MongoDB Atlas client with Vector Search + Atlas Search.
    All public methods mirror what the MongoDB MCP server exposes,
    making this layer easily swappable with direct MCP tool calls.
    """

    def __init__(self, uri: str, db_name: str = config.DB_NAME):
        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self.client.admin.command("ping")           # fail fast if bad URI
        self.db       = self.client[db_name]
        self.scans    = self.db[config.SCANS_COLLECTION]
        self.entities = self.db[config.ENTITIES_COLLECTION]
        self.audit    = self.db[config.AUDIT_COLLECTION]
        self.vectors  = self.db[config.VECTORS_COLLECTION]
        self._ensure_indexes()

    # ── Index setup ────────────────────────────────────────────────────────────

    def _ensure_indexes(self):
        """Create standard indexes. Vector / Atlas Search indexes must be
        created separately via Atlas UI or create_atlas_indexes()."""
        self.scans.create_index([("timestamp", DESCENDING)])
        self.scans.create_index([("overall_risk", ASCENDING)])
        self.scans.create_index([("regulations_triggered", ASCENDING)])
        self.entities.create_index([("scan_id", ASCENDING)])
        self.entities.create_index([("type", ASCENDING)])
        self.entities.create_index([("risk_level", DESCENDING)])
        self.audit.create_index([("timestamp", DESCENDING)])
        self.vectors.create_index([("scan_id", ASCENDING)], unique=True)

    def create_atlas_indexes(self):
        """
        Create Atlas Vector Search + Atlas Search indexes programmatically.
        Call once after cluster setup. Requires Atlas M10+ for search indexes,
        but M0 (free) supports vector search via the Atlas UI.

        Returns status messages for each index.
        """
        messages = []

        # ── Vector Search index ───────────────────────────────────────────────
        vector_index_def = {
            "name": config.VECTOR_INDEX_NAME,
            "type": "vectorSearch",
            "definition": {
                "fields": [{
                    "type":          "vector",
                    "path":          "embedding",
                    "numDimensions": config.EMBEDDING_DIM,
                    "similarity":    "cosine"
                }, {
                    "type": "filter",
                    "path": "overall_risk"
                }]
            }
        }
        try:
            self.vectors.create_search_index(
                SearchIndexModel(**vector_index_def)
            )
            messages.append("✅ Vector Search index created")
        except Exception as e:
            messages.append(f"⚠️  Vector index: {e}")

        # ── Atlas Search (full-text) index ────────────────────────────────────
        search_index_def = {
            "name": config.ATLAS_SEARCH_INDEX,
            "type": "search",
            "definition": {
                "mappings": {
                    "dynamic": False,
                    "fields": {
                        "filename":              {"type": "string"},
                        "summary":               {"type": "string"},
                        "report":                {"type": "string"},
                        "overall_risk":          {"type": "string"},
                        "regulations_triggered": {"type": "string"},
                        "timestamp":             {"type": "date"},
                    }
                }
            }
        }
        try:
            self.scans.create_search_index(
                SearchIndexModel(**search_index_def)
            )
            messages.append("✅ Atlas Search index created")
        except Exception as e:
            messages.append(f"⚠️  Search index: {e}")

        return messages

    # ── Core CRUD ──────────────────────────────────────────────────────────────

    def save_scan(self, result: dict, embedding: list[float] | None = None) -> str:
        """
        Persist a full scan result.
        If an embedding vector is provided, also saves to vectors collection
        for future Vector Search queries.
        Returns the scan_id as a string.
        """
        result.pop("_id", None)
        now = datetime.utcnow().isoformat()

        scan_doc = {
            "filename":              result.get("filename", "unknown"),
            "timestamp":             result.get("timestamp", now),
            "overall_risk":          result.get("overall_risk", "UNKNOWN"),
            "risk_score":            result.get("risk_score", 0),
            "entity_count":          result.get("entity_count", 0),
            "regulations_triggered": result.get("regulations_triggered", []),
            "compliance_gaps":       result.get("compliance_gaps", []),
            "summary":               result.get("summary", ""),
            "recommendations":       result.get("recommendations", []),
            "report":                result.get("report", ""),
            "risk_breakdown":        result.get("risk_breakdown", {}),
            "prescan":               result.get("prescan", {}),
            "scan_duration_s":       result.get("scan_duration_s", 0),
        }
        scan_id = self.scans.insert_one(scan_doc).inserted_id

        # Save individual entities (linked to scan)
        entities = result.get("entities", [])
        if entities:
            self.entities.insert_many([
                {
                    "scan_id":    scan_id,
                    "timestamp":  scan_doc["timestamp"],
                    "filename":   scan_doc["filename"],
                    **{k: v for k, v in ent.items() if k != "_id"}
                }
                for ent in entities
            ])

        # Save embedding vector for Vector Search
        if embedding:
            self.vectors.update_one(
                {"scan_id": scan_id},
                {"$set": {
                    "scan_id":      scan_id,
                    "embedding":    embedding,
                    "overall_risk": scan_doc["overall_risk"],
                    "timestamp":    scan_doc["timestamp"],
                    "filename":     scan_doc["filename"],
                }},
                upsert=True
            )

        # Audit log (GDPR Art. 30 — records of processing)
        self.audit.insert_one({
            "action":    "SCAN_COMPLETED",
            "scan_id":   scan_id,
            "timestamp": now,
            "risk":      scan_doc["overall_risk"],
            "filename":  scan_doc["filename"],
            "entities":  len(entities),
        })

        return str(scan_id)

    def get_scan(self, scan_id: str) -> dict | None:
        doc = self.scans.find_one({"_id": ObjectId(scan_id)})
        return self._clean(doc)

    def get_scan_entities(self, scan_id: str) -> list[dict]:
        docs = list(self.entities.find({"scan_id": ObjectId(scan_id)}))
        return [self._clean(d) for d in docs]

    def get_recent_scans(self, limit: int = 20) -> list[dict]:
        docs = list(
            self.scans.find({}, {"report": 0, "agent_log": 0})
                      .sort("timestamp", DESCENDING)
                      .limit(limit)
        )
        return [self._clean(d) for d in docs]

    def delete_scan(self, scan_id: str) -> bool:
        """GDPR Art. 17 — Right to Erasure."""
        oid = ObjectId(scan_id)
        self.entities.delete_many({"scan_id": oid})
        self.vectors.delete_one({"scan_id": oid})
        result = self.scans.delete_one({"_id": oid})
        self.audit.insert_one({
            "action":    "SCAN_DELETED",
            "scan_id":   scan_id,
            "timestamp": datetime.utcnow().isoformat(),
        })
        return result.deleted_count > 0

    # ── Vector Search ──────────────────────────────────────────────────────────

    def vector_search(self, query_embedding: list[float],
                      risk_filter: str | None = None,
                      limit: int = config.VECTOR_RESULTS) -> list[dict]:
        """
        Semantic similarity search across all past scans using MongoDB Vector Search.
        Optionally filter by risk level.
        Returns similar scans ranked by cosine similarity.
        """
        filter_doc = {}
        if risk_filter and risk_filter != "All":
            filter_doc["overall_risk"] = risk_filter

        pipeline = [{
            "$vectorSearch": {
                "index":          config.VECTOR_INDEX_NAME,
                "path":           "embedding",
                "queryVector":    query_embedding,
                "numCandidates":  config.VECTOR_CANDIDATES,
                "limit":          limit,
                **({"filter": filter_doc} if filter_doc else {}),
            }
        }, {
            "$project": {
                "scan_id":      1,
                "filename":     1,
                "overall_risk": 1,
                "timestamp":    1,
                "score":        {"$meta": "vectorSearchScore"},
            }
        }, {
            "$lookup": {
                "from":         config.SCANS_COLLECTION,
                "localField":   "scan_id",
                "foreignField": "_id",
                "as":           "scan_details",
            }
        }, {
            "$unwind": "$scan_details"
        }, {
            "$project": {
                "score":        1,
                "filename":     1,
                "overall_risk": 1,
                "timestamp":    1,
                "summary":      "$scan_details.summary",
                "risk_score":   "$scan_details.risk_score",
                "entity_count": "$scan_details.entity_count",
            }
        }]

        results = list(self.vectors.aggregate(pipeline))
        return [self._clean(r) for r in results]

    # ── Atlas Search (full-text) ───────────────────────────────────────────────

    def full_text_search(self, query: str, limit: int = 10) -> list[dict]:
        """
        Full-text search across scan summaries, reports, and filenames
        using MongoDB Atlas Search.
        """
        pipeline = [{
            "$search": {
                "index": config.ATLAS_SEARCH_INDEX,
                "text": {
                    "query": query,
                    "path":  ["filename", "summary", "report"],
                    "fuzzy": {"maxEdits": 1}
                }
            }
        }, {
            "$project": {
                "report":    0,
                "agent_log": 0,
                "score":     {"$meta": "searchScore"},
            }
        }, {
            "$limit": limit
        }]

        try:
            results = list(self.scans.aggregate(pipeline))
            return [self._clean(r) for r in results]
        except Exception:
            # Fallback to regex if Atlas Search index not ready
            regex   = {"$regex": query, "$options": "i"}
            results = list(
                self.scans.find(
                    {"$or": [{"filename": regex}, {"summary": regex}]},
                    {"report": 0}
                ).limit(limit)
            )
            return [self._clean(r) for r in results]

    # ── Aggregation & Stats ────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Dashboard statistics via MongoDB aggregation pipeline."""
        pipeline = [{
            "$group": {
                "_id":             None,
                "total_scans":     {"$sum": 1},
                "total_entities":  {"$sum": "$entity_count"},
                "avg_risk_score":  {"$avg": "$risk_score"},
                "critical":  {"$sum": {"$cond": [{"$eq": ["$overall_risk", "CRITICAL"]}, 1, 0]}},
                "high":      {"$sum": {"$cond": [{"$eq": ["$overall_risk", "HIGH"]},     1, 0]}},
                "medium":    {"$sum": {"$cond": [{"$eq": ["$overall_risk", "MEDIUM"]},   1, 0]}},
                "low":       {"$sum": {"$cond": [{"$eq": ["$overall_risk", "LOW"]},      1, 0]}},
            }
        }]
        result = list(self.scans.aggregate(pipeline))
        if result:
            s = result[0]
            s.pop("_id", None)
            s["avg_risk_score"] = round(s.get("avg_risk_score", 0), 1)
            return s
        return {"total_scans": 0, "total_entities": 0, "avg_risk_score": 0,
                "critical": 0, "high": 0, "medium": 0, "low": 0}

    def get_entity_breakdown(self) -> list[dict]:
        """Entity type frequency for chart visualisation."""
        pipeline = [
            {"$group": {"_id": "$type", "count": {"$sum": 1},
                        "critical": {"$sum": {"$cond": [{"$eq": ["$risk_level", "CRITICAL"]}, 1, 0]}}}},
            {"$sort": {"count": DESCENDING}},
            {"$project": {"type": "$_id", "count": 1, "critical": 1, "_id": 0}}
        ]
        return list(self.entities.aggregate(pipeline))

    def get_risk_trend(self, days: int = 30) -> list[dict]:
        """Daily risk score trend for time-series chart."""
        pipeline = [{
            "$group": {
                "_id":        {"$substr": ["$timestamp", 0, 10]},
                "avg_score":  {"$avg": "$risk_score"},
                "scan_count": {"$sum": 1},
            }
        }, {
            "$sort": {"_id": ASCENDING}
        }, {
            "$limit": days
        }, {
            "$project": {
                "date":       "$_id",
                "avg_score":  {"$round": ["$avg_score", 1]},
                "scan_count": 1,
                "_id":        0
            }
        }]
        return list(self.scans.aggregate(pipeline))

    def get_regulation_breakdown(self) -> list[dict]:
        """How often each regulation is triggered."""
        pipeline = [
            {"$unwind": "$regulations_triggered"},
            {"$group": {"_id": "$regulations_triggered", "count": {"$sum": 1}}},
            {"$sort": {"count": DESCENDING}},
            {"$project": {"regulation": "$_id", "count": 1, "_id": 0}}
        ]
        return list(self.scans.aggregate(pipeline))

    def get_audit_log(self, limit: int = 50) -> list[dict]:
        docs = list(self.audit.find().sort("timestamp", DESCENDING).limit(limit))
        return [self._clean(d) for d in docs]

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _clean(doc: dict | None) -> dict | None:
        """Convert ObjectId fields to strings for JSON serialisation."""
        if doc is None:
            return None
        for key in ("_id", "scan_id"):
            if key in doc and isinstance(doc[key], ObjectId):
                doc[key] = str(doc[key])
        return doc

    def close(self):
        self.client.close()
