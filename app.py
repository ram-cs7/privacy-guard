"""
PrivacyGuard Agent — Streamlit UI
Tabs: Scan | Similarity Search | Dashboard | Audit Log | Setup
"""

import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime

from agent      import PrivacyGuardAgent
from database   import MongoDBClient
from embeddings import EmbeddingClient
import config

# ── Page setup ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PrivacyGuard Agent",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #0d1117; }
[data-testid="stSidebar"]          { background: #161b22; }
.stApp                             { background: #0d1117; }
.metric-card {
    background: #1c2128; border: 1px solid #30363d;
    border-radius: 10px; padding: 16px; margin: 4px 0;
}
.step-card {
    background: #1c2128; border-left: 3px solid #7c3aed;
    padding: 10px 14px; border-radius: 0 8px 8px 0; margin: 4px 0;
    font-size: 0.88em;
}
.risk-CRITICAL { color:#ff4b4b; font-weight:700; }
.risk-HIGH     { color:#ff8c00; font-weight:700; }
.risk-MEDIUM   { color:#ffd700; font-weight:700; }
.risk-LOW      { color:#00c851; font-weight:700; }
.entity-pill {
    display:inline-block; padding:2px 10px; border-radius:20px;
    font-size:11px; font-weight:600; margin:2px;
    background:#30363d; color:#e6edf3;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for key, default in [
    ("agent",     None), ("db",         None),
    ("embedder",  None), ("connected",  False),
    ("results",   None), ("scan_count", 0),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛡️ PrivacyGuard")
    st.caption("Gemini · MongoDB Atlas · Vector Search")
    st.divider()

    st.subheader("🔑 API Configuration")
    gemini_key = st.text_input("Gemini API Key", type="password",
                               value=os.getenv("GEMINI_API_KEY", ""),
                               help="Get free key at aistudio.google.com")
    mongo_uri  = st.text_input("MongoDB URI", type="password",
                               value=os.getenv("MONGODB_URI", ""),
                               help="mongodb+srv://user:pass@cluster.mongodb.net/")
    db_name    = st.text_input("Database", value=config.DB_NAME)

    if st.button("🔌 Connect", use_container_width=True, type="primary"):
        if gemini_key and mongo_uri:
            with st.spinner("Connecting..."):
                try:
                    st.session_state.agent    = PrivacyGuardAgent(gemini_key)
                    st.session_state.embedder = EmbeddingClient(gemini_key)
                    st.session_state.db       = MongoDBClient(mongo_uri, db_name)
                    st.session_state.connected = True
                    stats = st.session_state.db.get_stats()
                    st.session_state.scan_count = stats.get("total_scans", 0)
                    st.success("✅ Connected!")
                except Exception as e:
                    st.error(f"❌ {e}")
        else:
            st.warning("Enter Gemini key + MongoDB URI")

    st.divider()
    if st.session_state.connected:
        st.success("🟢 Connected")
        st.caption(f"Total scans: {st.session_state.scan_count}")
    else:
        st.error("🔴 Not connected")

    st.divider()
    st.subheader("📋 Recent Scans")
    if st.session_state.connected:
        try:
            recent = st.session_state.db.get_recent_scans(5)
            for s in recent:
                risk  = s.get("overall_risk", "?")
                color = config.RISK_COLORS.get(risk, "#aaa")
                name  = s.get("filename", "doc")[:18]
                date  = s.get("timestamp", "")[:10]
                st.markdown(
                    f'<div style="font-size:0.82em; padding:4px 0;">'
                    f'📄 {name}<br>'
                    f'<span style="color:{color};font-weight:600">{risk}</span>'
                    f' &nbsp;·&nbsp; {date}</div>',
                    unsafe_allow_html=True
                )
        except Exception:
            st.caption("No scans yet")

# ── Main tabs ─────────────────────────────────────────────────────────────────
tab_scan, tab_search, tab_dash, tab_audit, tab_setup = st.tabs([
    "🔍 Scan", "🧲 Similarity Search",
    "📊 Dashboard", "📁 Audit Log", "⚙️ Setup"
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SCAN
# ═══════════════════════════════════════════════════════════════════════════════
with tab_scan:
    st.title("🛡️ PrivacyGuard Agent")
    st.markdown("AI-powered PII detection · Compliance analysis · MongoDB audit trail")
    st.divider()

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.subheader("📥 Input")
        method = st.radio("Input method", ["Paste text", "Upload file"], horizontal=True)

        text_content = ""
        filename     = "manual_input.txt"

        if method == "Upload file":
            uploaded = st.file_uploader(
                "Upload document",
                type=["txt", "pdf", "csv", "json", "md", "html"]
            )
            if uploaded:
                filename = uploaded.name
                if filename.endswith(".pdf"):
                    try:
                        import PyPDF2, io
                        reader = PyPDF2.PdfReader(io.BytesIO(uploaded.read()))
                        text_content = "\n".join(
                            p.extract_text() or "" for p in reader.pages
                        )
                    except Exception:
                        st.error("Install PyPDF2: pip install PyPDF2")
                else:
                    text_content = uploaded.read().decode("utf-8", errors="ignore")
                st.success(f"✅ {filename} loaded — {len(text_content):,} characters")
        else:
            text_content = st.text_area(
                "Paste document text",
                height=220,
                placeholder=(
                    "Paste any document — emails, contracts, medical notes, "
                    "HR records, logs...\n\n"
                    "Example: Patient John Doe (SSN: 123-45-6789) was admitted "
                    "on 12/03/1985. Contact: john.doe@email.com, +1-555-0100."
                )
            )
            filename = "manual_input.txt"

        st.subheader("⚙️ Options")
        compliance = st.multiselect(
            "Compliance frameworks",
            config.COMPLIANCE_FRAMEWORKS,
            default=["GDPR", "CCPA"],
        )
        use_vector = st.checkbox(
            "Enable Vector Search (store embedding for similarity search)",
            value=True,
            help="Generates a semantic embedding and saves to MongoDB Vector Search"
        )

        scan_btn = st.button(
            "🚀 Run PrivacyGuard Agent",
            use_container_width=True,
            type="primary",
            disabled=not st.session_state.connected
        )
        if not st.session_state.connected:
            st.info("👈 Connect your API keys in the sidebar")

    with col_right:
        st.subheader("🤖 Agent Reasoning")
        reasoning_placeholder = st.empty()

    # ── Run ───────────────────────────────────────────────────────────────────
    if scan_btn and text_content.strip():
        steps = []

        def on_step(msg):
            steps.append(msg)
            html = "".join(
                f'<div class="step-card">{'✅' if i < len(steps)-1 else '⏳'} {s}</div>'
                for i, s in enumerate(steps)
            )
            reasoning_placeholder.markdown(html, unsafe_allow_html=True)

        with st.spinner("Agent running..."):
            try:
                results = st.session_state.agent.analyze(
                    text_content, compliance, on_step
                )
                results["filename"]  = filename
                results["timestamp"] = datetime.utcnow().isoformat()

                # Generate embedding & save
                embedding = None
                if use_vector:
                    on_step("🔢 Generating semantic embedding for Vector Search...")
                    embedding = st.session_state.embedder.embed_document_summary(results)

                scan_id = st.session_state.db.save_scan(results, embedding)
                results["scan_id"] = scan_id
                st.session_state.results = results
                st.session_state.scan_count += 1
                on_step(f"💾 Saved to MongoDB — Scan ID: {scan_id}")
                st.success("✅ Scan complete!")
            except Exception as e:
                st.error(f"Agent error: {e}")
                import traceback; st.code(traceback.format_exc())

    # ── Results ───────────────────────────────────────────────────────────────
    if st.session_state.results:
        r = st.session_state.results
        st.divider()
        st.subheader("📋 Results")

        risk  = r.get("overall_risk", "?")
        color = config.RISK_COLORS.get(risk, "#aaa")

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Overall Risk",    risk)
        m2.metric("Risk Score",      f"{r.get('risk_score', 0)}/100")
        m3.metric("Entities Found",  r.get("entity_count", 0))
        m4.metric("Regulations",     len(r.get("regulations_triggered", [])))
        m5.metric("Scan Time",       f"{r.get('scan_duration_s', 0):.1f}s")

        # Risk bar
        score = r.get("risk_score", 0)
        st.markdown(
            f'<div style="background:#21262d;border-radius:8px;height:10px;margin:8px 0;">'
            f'<div style="background:{color};width:{score}%;height:10px;'
            f'border-radius:8px;transition:width 0.5s;"></div></div>',
            unsafe_allow_html=True
        )

        st.divider()
        st.subheader("🔎 Detected Entities")
        entities = r.get("entities", [])
        if entities:
            rows = []
            for ent in entities:
                rl    = ent.get("risk_level", "LOW")
                color2 = config.RISK_COLORS.get(rl, "#aaa")
                rows.append({
                    "Type":        ent.get("type", "?"),
                    "Value":       ent.get("value", "?")[:60],
                    "Risk":        ent.get("risk_level", "?"),
                    "Regulations": ", ".join(ent.get("regulations", [])),
                    "Explanation": ent.get("explanation", "")[:100],
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.success("🟢 No sensitive entities detected.")

        st.divider()
        regs = r.get("regulations_triggered", [])
        gaps = r.get("compliance_gaps", [])
        if regs:
            st.subheader("⚖️ Regulations Triggered")
            st.markdown(" ".join(f"`{reg}`" for reg in regs))
        if gaps:
            st.subheader("🚨 Compliance Gaps")
            for g in gaps:
                st.markdown(f"- {g}")

        st.divider()
        recs = r.get("recommendations", [])
        if recs:
            st.subheader("📌 Recommendations")
            for rec in recs:
                st.markdown(f"- {rec}")

        with st.expander("📄 Full Compliance Report"):
            st.markdown(r.get("report", "No report generated."))

        with st.expander("🧠 Pre-scan Analysis"):
            st.json(r.get("prescan", {}))

        c1, c2 = st.columns(2)
        c1.download_button(
            "⬇️ Download JSON Report",
            data=json.dumps(r, indent=2, default=str),
            file_name=f"privacyguard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
        c2.download_button(
            "⬇️ Download Markdown Report",
            data=r.get("report", ""),
            file_name=f"privacyguard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown"
        )

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — VECTOR SIMILARITY SEARCH
# ═══════════════════════════════════════════════════════════════════════════════
with tab_search:
    st.subheader("🧲 Semantic Similarity Search")
    st.markdown(
        "Find past scans similar to a query using **MongoDB Vector Search** "
        "and Gemini embeddings."
    )

    if not st.session_state.connected:
        st.info("Connect in the sidebar to use search.")
    else:
        sc1, sc2 = st.columns([3, 1])
        with sc1:
            query = st.text_input(
                "Search query",
                placeholder="e.g. 'medical records with patient health data' or 'credit card PII'"
            )
        with sc2:
            risk_filter = st.selectbox(
                "Filter by risk",
                ["All", "CRITICAL", "HIGH", "MEDIUM", "LOW"]
            )

        c_vec, c_text = st.columns(2)

        with c_vec:
            if st.button("🔍 Vector Search", use_container_width=True,
                         help="Semantic similarity via embeddings"):
                if query:
                    with st.spinner("Generating query embedding..."):
                        try:
                            q_emb    = st.session_state.embedder.embed_query(query)
                            results  = st.session_state.db.vector_search(
                                q_emb,
                                risk_filter if risk_filter != "All" else None
                            )
                            if results:
                                st.success(f"Found {len(results)} similar scans")
                                for res in results:
                                    score = res.get("score", 0)
                                    risk  = res.get("overall_risk", "?")
                                    col   = config.RISK_COLORS.get(risk, "#aaa")
                                    with st.expander(
                                        f"📄 {res.get('filename','?')} — "
                                        f"similarity: {score:.3f} — {risk}"
                                    ):
                                        st.markdown(f"**Summary:** {res.get('summary','')}")
                                        st.markdown(
                                            f"Risk Score: `{res.get('risk_score','?')}`  "
                                            f"| Entities: `{res.get('entity_count','?')}`"
                                        )
                                        st.caption(f"Scan ID: {res.get('scan_id','?')}")
                            else:
                                st.warning("No similar scans found. Run more scans first.")
                        except Exception as e:
                            st.error(f"Vector search error: {e}")
                            st.info("Make sure the Vector Search index is created in Atlas UI. See Setup tab.")

        with c_text:
            if st.button("🔤 Full-Text Search", use_container_width=True,
                         help="Atlas Search across all scan text"):
                if query:
                    with st.spinner("Searching..."):
                        try:
                            results = st.session_state.db.full_text_search(query)
                            if results:
                                st.success(f"Found {len(results)} scans")
                                for res in results:
                                    with st.expander(
                                        f"📄 {res.get('filename','?')} — "
                                        f"{res.get('overall_risk','?')}"
                                    ):
                                        st.markdown(res.get("summary", ""))
                                        st.caption(res.get("timestamp", "")[:19])
                            else:
                                st.warning("No results found.")
                        except Exception as e:
                            st.error(f"Search error: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
with tab_dash:
    st.subheader("📊 Analytics Dashboard")

    if not st.session_state.connected:
        st.info("Connect to view dashboard.")
    else:
        if st.button("🔄 Refresh"):
            st.rerun()

        try:
            stats = st.session_state.db.get_stats()
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Total Scans",     stats.get("total_scans", 0))
            m2.metric("Avg Risk Score",  stats.get("avg_risk_score", 0))
            m3.metric("Total Entities",  stats.get("total_entities", 0))
            m4.metric("Critical Scans",  stats.get("critical", 0))
            m5.metric("High Risk Scans", stats.get("high", 0))

            st.divider()
            col_a, col_b = st.columns(2)

            # Risk distribution
            with col_a:
                st.subheader("Risk Distribution")
                risk_data = {
                    "Risk Level": ["CRITICAL","HIGH","MEDIUM","LOW"],
                    "Count":      [stats.get("critical",0), stats.get("high",0),
                                   stats.get("medium",0),  stats.get("low",0)]
                }
                df_risk = pd.DataFrame(risk_data).set_index("Risk Level")
                st.bar_chart(df_risk)

            # Entity breakdown
            with col_b:
                st.subheader("Entity Types Detected")
                entity_data = st.session_state.db.get_entity_breakdown()
                if entity_data:
                    df_ent = pd.DataFrame(entity_data)[["type","count"]]
                    df_ent = df_ent.set_index("type")
                    st.bar_chart(df_ent)

            st.divider()

            # Regulation breakdown
            col_c, col_d = st.columns(2)
            with col_c:
                st.subheader("Regulations Triggered")
                reg_data = st.session_state.db.get_regulation_breakdown()
                if reg_data:
                    df_reg = pd.DataFrame(reg_data).set_index("regulation")
                    st.bar_chart(df_reg)

            # Risk trend
            with col_d:
                st.subheader("Risk Score Trend")
                trend = st.session_state.db.get_risk_trend()
                if trend:
                    df_trend = pd.DataFrame(trend).set_index("date")
                    st.line_chart(df_trend["avg_score"])

            st.divider()
            st.subheader("Recent Scans")
            scans = st.session_state.db.get_recent_scans(20)
            if scans:
                df_scans = pd.DataFrame([{
                    "File":        s.get("filename","?"),
                    "Risk":        s.get("overall_risk","?"),
                    "Score":       s.get("risk_score",0),
                    "Entities":    s.get("entity_count",0),
                    "Regulations": ", ".join(s.get("regulations_triggered",[])),
                    "Scanned At":  s.get("timestamp","")[:19],
                } for s in scans])
                st.dataframe(df_scans, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"Dashboard error: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — AUDIT LOG
# ═══════════════════════════════════════════════════════════════════════════════
with tab_audit:
    st.subheader("📁 Audit Log")
    st.markdown("Full GDPR Art. 30 compliant audit trail of all processing activities.")

    if not st.session_state.connected:
        st.info("Connect to view audit log.")
    else:
        try:
            logs = st.session_state.db.get_audit_log(50)
            if logs:
                df_log = pd.DataFrame([{
                    "Action":    l.get("action","?"),
                    "File":      l.get("filename","?"),
                    "Risk":      l.get("risk","?"),
                    "Entities":  l.get("entities","?"),
                    "Timestamp": l.get("timestamp","")[:19],
                    "Scan ID":   l.get("scan_id","?"),
                } for l in logs])
                st.dataframe(df_log, use_container_width=True, hide_index=True)
            else:
                st.info("No audit entries yet. Run a scan first.")

            st.divider()
            st.subheader("🗑️ GDPR Right to Erasure")
            del_id = st.text_input("Scan ID to delete")
            if st.button("Delete Scan", type="secondary") and del_id:
                if st.session_state.db.delete_scan(del_id):
                    st.success(f"Scan {del_id} permanently deleted.")
                else:
                    st.error("Scan not found.")

        except Exception as e:
            st.error(f"Audit log error: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — SETUP
# ═══════════════════════════════════════════════════════════════════════════════
with tab_setup:
    st.subheader("⚙️ Atlas Index Setup")
    st.markdown("""
    MongoDB Vector Search and Atlas Search require indexes to be created once.
    Run these steps after your first connection.
    """)

    st.info("""
    **Required one-time setup on MongoDB Atlas:**

    1. Go to [cloud.mongodb.com](https://cloud.mongodb.com)
    2. Navigate to your cluster → **Atlas Search**
    3. Create the indexes below
    """)

    with st.expander("📋 Vector Search Index Definition (copy into Atlas UI)"):
        st.code(json.dumps({
            "fields": [{
                "type":          "vector",
                "path":          "embedding",
                "numDimensions": 768,
                "similarity":    "cosine"
            }, {
                "type": "filter",
                "path": "overall_risk"
            }]
        }, indent=2), language="json")
        st.caption(f"Collection: `document_vectors` | Index name: `{config.VECTOR_INDEX_NAME}`")

    with st.expander("📋 Atlas Search Index Definition (copy into Atlas UI)"):
        st.code(json.dumps({
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
        }, indent=2), language="json")
        st.caption(f"Collection: `scans` | Index name: `{config.ATLAS_SEARCH_INDEX}`")

    st.divider()
    st.subheader("🔌 MongoDB MCP Server Setup")
    st.markdown("The MongoDB MCP server lets AI agents interact with your database via natural language.")
    st.code("""
# Install MongoDB MCP server
npm install -g @modelcontextprotocol/server-mongodb

# Set your MongoDB URI
export MONGODB_URI="your_mongodb_uri"

# Run the MCP server
npx @modelcontextprotocol/server-mongodb
""", language="bash")

    st.divider()
    if st.session_state.connected:
        st.subheader("🧪 Test Connection")
        if st.button("Run Index Setup (requires Atlas M10+)"):
            with st.spinner("Creating indexes..."):
                msgs = st.session_state.db.create_atlas_indexes()
                for msg in msgs:
                    st.write(msg)
