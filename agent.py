"""
PrivacyGuard Agent — Multi-step Gemini-powered PII detection engine.

Pipeline:
  Step 1  Pre-scan      → document overview & metadata
  Step 2  Chunk         → split large documents
  Step 3  Detect        → entity extraction per chunk
  Step 4  Classify      → risk scoring & compliance mapping
  Step 5  Deduplicate   → merge overlapping detections
  Step 6  Report        → generate full compliance report
"""

import json
import re
from datetime import datetime
import google.generativeai as genai
from config import GEMINI_MODEL, TEMPERATURE, MAX_TOKENS, MAX_CHUNK_SIZE, CHUNK_OVERLAP


# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are PrivacyGuard, an elite AI agent specialised in data privacy 
compliance and PII detection. You have deep expertise in GDPR, CCPA, HIPAA, and PCI-DSS.

Your detection capabilities:
- Explicit PII: names, emails, phones, SSNs, credit cards, addresses, DOBs, passports
- Implicit PII: contextual health data, financial references, credentials
- Sensitive patterns: API keys, tokens, passwords embedded in text
- Cross-reference PII: combinations that together identify individuals

You reason step-by-step and are thorough — a missed entity is a compliance risk.
Always respond in valid JSON only. No markdown fences. No preamble. Pure JSON."""


DETECT_PROMPT = """Detect ALL PII and sensitive data in this document chunk.

Compliance frameworks: {compliance}

Document chunk:
\"\"\"
{text}
\"\"\"

Return ONLY this JSON (no markdown):
{{
  "entities": [
    {{
      "type": "NAME|EMAIL|PHONE|SSN|CREDIT_CARD|ADDRESS|DOB|HEALTH_INFO|FINANCIAL_INFO|PASSPORT|IP_ADDRESS|CREDENTIALS|OTHER_PII",
      "value": "<exact detected value or clear description>",
      "context": "<surrounding sentence showing the entity in context>",
      "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
      "regulations": ["GDPR"],
      "explanation": "<why this is sensitive and what regulation applies>"
    }}
  ],
  "chunk_risk": "LOW|MEDIUM|HIGH|CRITICAL",
  "notes": "<any unusual or implicit PII patterns noticed>"
}}"""


CLASSIFY_PROMPT = """You are reviewing PII detection results from a document scan.
Given these detected entities, produce a final risk assessment and compliance report.

Detected entities:
{entities}

Compliance frameworks checked: {compliance}
Document name: {filename}
Scan timestamp: {timestamp}

Return ONLY this JSON (no markdown):
{{
  "overall_risk": "LOW|MEDIUM|HIGH|CRITICAL",
  "risk_score": <0-100 integer>,
  "risk_breakdown": {{
    "critical_count": <int>,
    "high_count": <int>,
    "medium_count": <int>,
    "low_count": <int>
  }},
  "regulations_triggered": ["GDPR", "CCPA"],
  "compliance_gaps": [
    "<specific compliance gap 1>",
    "<specific compliance gap 2>"
  ],
  "summary": "<3-4 sentence plain English summary of findings>",
  "recommendations": [
    "<specific actionable recommendation 1>",
    "<specific actionable recommendation 2>",
    "<specific actionable recommendation 3>",
    "<specific actionable recommendation 4>",
    "<specific actionable recommendation 5>"
  ],
  "report": "<full markdown compliance report with sections: Executive Summary, Findings, Risk Assessment, Regulatory Implications, Remediation Steps>"
}}"""


PRESCAN_PROMPT = """Analyse this document and provide a brief overview before deep scanning.

Document (first 1000 chars):
\"\"\"
{text}
\"\"\"

Return ONLY this JSON:
{{
  "document_type": "<e.g. HR record, medical note, financial statement, email>",
  "likely_contains_pii": true,
  "predicted_risk": "LOW|MEDIUM|HIGH|CRITICAL",
  "key_areas_to_watch": ["<area 1>", "<area 2>"],
  "estimated_entities": <integer estimate>
}}"""


class PrivacyGuardAgent:
    """
    Multi-step Gemini agent for PII detection and compliance analysis.
    Integrates with MongoDB for audit storage and vector similarity search.
    """

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
            generation_config=genai.types.GenerationConfig(
                temperature=TEMPERATURE,
                max_output_tokens=MAX_TOKENS,
            )
        )
        self.scan_log = []

    def analyze(self, text: str, compliance: list, callback=None) -> dict:
        """
        Full 6-step agent pipeline.
        callback(step_description) is called after each step for UI updates.
        """
        self.scan_log = []
        start_time   = datetime.utcnow()

        # ── Step 1: Pre-scan ──────────────────────────────────────────────────
        self._log(callback, "🔍 Pre-scanning document — detecting type and structure...")
        prescan = self._prescan(text)
        self._log(callback,
            f"📄 Detected: {prescan.get('document_type', 'unknown')} | "
            f"Predicted risk: {prescan.get('predicted_risk', '?')} | "
            f"~{prescan.get('estimated_entities', '?')} entities expected"
        )

        # ── Step 2: Chunk ─────────────────────────────────────────────────────
        chunks = self._chunk(text)
        self._log(callback,
            f"✂️  Split into {len(chunks)} chunk(s) for thorough analysis. "
            f"Checking against: {', '.join(compliance)}"
        )

        # ── Step 3: Detect entities per chunk ─────────────────────────────────
        all_entities = []
        chunk_notes  = []
        for i, chunk in enumerate(chunks):
            self._log(callback,
                f"🧠 Scanning chunk {i+1}/{len(chunks)} for PII entities..."
            )
            result = self._detect_chunk(chunk, compliance)
            all_entities.extend(result.get("entities", []))
            if result.get("notes"):
                chunk_notes.append(result["notes"])

        self._log(callback,
            f"⚡ Raw detection complete — {len(all_entities)} raw entities found"
        )

        # ── Step 4: Deduplicate ───────────────────────────────────────────────
        self._log(callback, "🔄 Deduplicating and merging overlapping detections...")
        unique_entities = self._deduplicate(all_entities)
        self._log(callback,
            f"✅ {len(unique_entities)} unique entities after deduplication"
        )

        # ── Step 5: Classify + report ─────────────────────────────────────────
        self._log(callback, "📊 Running compliance mapping and risk classification...")
        classification = self._classify(
            unique_entities, compliance,
            filename=prescan.get("document_type", "document"),
            timestamp=start_time.isoformat()
        )

        # ── Step 6: Assemble final result ─────────────────────────────────────
        self._log(callback,
            f"📋 Report generated — Overall risk: "
            f"{classification.get('overall_risk','?')} | "
            f"Score: {classification.get('risk_score', 0)}/100"
        )

        final = {
            **classification,
            "entities":        unique_entities,
            "entity_count":    len(unique_entities),
            "prescan":         prescan,
            "chunk_notes":     chunk_notes,
            "scan_duration_s": (datetime.utcnow() - start_time).total_seconds(),
            "agent_log":       self.scan_log,
        }
        return final

    # ── Internal steps ─────────────────────────────────────────────────────────

    def _prescan(self, text: str) -> dict:
        prompt = PRESCAN_PROMPT.format(text=text[:1000])
        try:
            return self._call(prompt)
        except Exception:
            return {"document_type": "unknown", "predicted_risk": "MEDIUM"}

    def _detect_chunk(self, text: str, compliance: list) -> dict:
        prompt = DETECT_PROMPT.format(
            compliance=", ".join(compliance),
            text=text
        )
        try:
            return self._call(prompt)
        except Exception:
            return {"entities": [], "chunk_risk": "UNKNOWN", "notes": ""}

    def _classify(self, entities: list, compliance: list,
                  filename: str, timestamp: str) -> dict:
        prompt = CLASSIFY_PROMPT.format(
            entities=json.dumps(entities, indent=2),
            compliance=", ".join(compliance),
            filename=filename,
            timestamp=timestamp
        )
        try:
            return self._call(prompt)
        except Exception as e:
            return {
                "overall_risk":        "UNKNOWN",
                "risk_score":          0,
                "risk_breakdown":      {},
                "regulations_triggered": [],
                "compliance_gaps":     [],
                "summary":             f"Classification failed: {e}",
                "recommendations":     ["Re-run scan"],
                "report":              "Report generation failed."
            }

    def _call(self, prompt: str) -> dict:
        """Call Gemini and parse JSON response."""
        response = self.model.generate_content(prompt)
        text = response.text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$",          "", text)
        return json.loads(text)

    def _chunk(self, text: str) -> list[str]:
        """Split text into overlapping chunks."""
        if len(text) <= MAX_CHUNK_SIZE:
            return [text]
        chunks, start = [], 0
        while start < len(text):
            chunks.append(text[start:start + MAX_CHUNK_SIZE])
            start += MAX_CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    def _deduplicate(self, entities: list) -> list:
        """Remove duplicates by (type, normalised_value) key."""
        seen, unique = set(), []
        for ent in entities:
            key = (
                ent.get("type", ""),
                ent.get("value", "").lower().strip()
            )
            if key not in seen:
                seen.add(key)
                unique.append(ent)
        return unique

    def _log(self, callback, message: str):
        self.scan_log.append(message)
        if callback:
            callback(message)
