"""RUMOURPRINT AI v0.7 — a professional newsroom application for narrative investigation and evidence-led verification."""
from __future__ import annotations

import csv
import html
import io
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from engine import compare, pairwise_scores, shift_signals
from semantic import MODEL_NAME, load_local_model
from evidence import search_news, search_fact_checks, suggest_query, broaden_query, build_brief, EvidenceError
from network import build_network, figure_for_network, highlight_differences

APP_DIR = Path(__file__).resolve().parent
MAX_CLAIMS = 250
MAX_TEXT = 2500

st.set_page_config(
    page_title="RUMOURPRINT AI | Narrative verification workspace",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    f"<style>{(APP_DIR / 'assets' / 'styles.css').read_text(encoding='utf-8')}</style>",
    unsafe_allow_html=True,
)

SAMPLES = []

if "reports" not in st.session_state:
    st.session_state.reports = [dict(row) for row in SAMPLES]
if "last_matches" not in st.session_state:
    st.session_state.last_matches = None
if "last_engine" not in st.session_state:
    st.session_state.last_engine = ""
if "last_query" not in st.session_state:
    st.session_state.last_query = ""
if "clusters" not in st.session_state:
    st.session_state.clusters = None
if "cluster_method" not in st.session_state:
    st.session_state.cluster_method = ""


def escape(text: object) -> str:
    return html.escape(str(text), quote=True)


def section_heading(index: str, eyebrow: str, title: str, description: str = "") -> None:
    """Render structural HTML directly, avoiding Markdown showing closing tags."""
    description_html = (
        f'<p class="rp-section-description">{escape(description)}</p>'
        if description else ""
    )
    section_html = (
        '<div class="rp-section-heading">'
        '<div class="rp-section-heading-copy">'
        f'<p class="rp-eyebrow"><span class="rp-section-index">{escape(index)}</span>'
        f'{escape(eyebrow)}</p>'
        f'<h2>{escape(title)}</h2>'
        f'{description_html}'
        '</div></div>'
    )
    st.html(section_html)


@st.cache_resource(show_spinner=False)
def get_semantic_model():
    return load_local_model(APP_DIR)


def selected_model():
    if st.session_state.engine_choice != "Multilingual semantic AI":
        return None, "wording", None
    try:
        with st.spinner("Loading the multilingual AI model. On first use this downloads approximately 220 MB; please wait…"):
            model = get_semantic_model()
        return model, "semantic", None
    except Exception as exc:
        # A failing download never prevents access to the investigation desk.
        return None, "wording", str(exc)


def clear_derived() -> None:
    st.session_state.clusters = None
    st.session_state.cluster_method = ""
    st.session_state.map_matrix = None
    st.session_state.map_method = ""
    st.session_state.map_items = []


def add_row(text: str, source: str, time: str | None = None) -> None:
    st.session_state.reports.append({
        "text": text,
        "source": source,
        "time": time or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    })
    clear_derived()


def csv_safe(value: object) -> str:
    """Prevent Excel formula execution on later CSV open."""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def export_csv() -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["text", "source", "time"])
    writer.writeheader()
    for row in st.session_state.reports:
        writer.writerow({key: csv_safe(row.get(key, "")) for key in ("text", "source", "time")})
    return buffer.getvalue()


with st.sidebar:
    brand_icon_col, brand_text_col = st.columns([1, 3], gap="small", vertical_alignment="center")
    with brand_icon_col:
        st.image("<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 64 64\" width=\"64\" height=\"64\" fill=\"none\"><rect x=\"4\" y=\"4\" width=\"56\" height=\"56\" rx=\"16\" fill=\"#1A2A29\" stroke=\"#33524E\" stroke-width=\"2\"/><path d=\"M19 32C19 24.82 24.82 19 32 19C39.18 19 45 24.82 45 32\" stroke=\"#D9C28B\" stroke-width=\"2.8\" stroke-linecap=\"round\"/><path d=\"M23 32C23 27.03 27.03 23 32 23C36.97 23 41 27.03 41 32\" stroke=\"#7FC0AE\" stroke-width=\"2.6\" stroke-linecap=\"round\"/><path d=\"M27 32C27 29.24 29.24 27 32 27C34.76 27 37 29.24 37 32\" stroke=\"#EFF6F4\" stroke-width=\"2.4\" stroke-linecap=\"round\"/><path d=\"M32 32L45 45\" stroke=\"#7FC0AE\" stroke-width=\"2.6\" stroke-linecap=\"round\"/><circle cx=\"46.5\" cy=\"46.5\" r=\"4.5\" fill=\"#D9C28B\" stroke=\"#1A2A29\" stroke-width=\"1.4\"/></svg>", width=58)
    with brand_text_col:
        st.html('''
            <div class="rp-brand-copy">
              <span class="rp-brand-name">RUMOURPRINT AI</span>
              <small>NARRATIVE VERIFICATION WORKSPACE</small>
              <div class="rp-powered-by">Powered by <strong>Fresh Exclusive Media</strong></div>
            </div>
        ''')
    st.html('<div class="rp-side-heading">WORKSPACE</div>')
    page = st.radio(
        "Workspace", ["Investigation desk", "Evidence desk", "Relationship map", "Claim library", "About & ethics"],
        label_visibility="collapsed", key="workspace_page",
    )
    st.markdown('<div class="rp-side-separator"></div><div class="rp-side-heading">ANALYSIS ENGINE</div>', unsafe_allow_html=True)
    st.selectbox(
        "Similarity method", ["Multilingual semantic AI", "Quick text matching"],
        key="engine_choice", help="Multilingual semantic AI uses a model on this app’s server. Quick mode works without downloading a model.",
    )
    if st.session_state.engine_choice == "Multilingual semantic AI":
        st.caption("The first analysis loads a multilingual model on the server. Luganda results are experimental; please review matches.")
    else:
        st.caption("Quick mode is lighter and faster, but it may miss paraphrases, negations and translations.")
    st.markdown('''
        <div class="rp-side-status">
          <div class="rp-side-status-title"><span class="rp-status-light"></span> Professional review required</div>
          <p>Similarity detection is not verification. Use the Evidence desk to gather source material and document editorial findings before publication.</p>
        </div>
        <div class="rp-sidebar-footer">VERSION 0.8 <span>·</span> NEWSROOM EDITION</div>
    ''', unsafe_allow_html=True)


if page == "Investigation desk":
    st.markdown('''
        <div class="rp-page-header">
          <div class="rp-page-kicker">WORKSPACE <span>/</span> INVESTIGATION DESK</div>
          <div class="rp-page-title-row">
            <h1>Investigate changing narratives<span class="rp-title-dot">.</span></h1>
            <span class="rp-mode-pill"><span class="rp-mode-dot"></span> VERIFICATION WORKSPACE</span>
          </div>
          <p>Compare claims by meaning, examine wording shifts and identify stories that may need investigation.</p>
        </div>
    ''', unsafe_allow_html=True)
    st.markdown(
        f'''<div class="rp-stats">
         <div class="rp-stat"><div class="rp-stat-label">SUBMITTED MESSAGES</div><div class="rp-stat-value">{len(st.session_state.reports):02d}</div><div class="rp-stat-detail">Current user session</div></div>
         <div class="rp-stat"><div class="rp-stat-label">ANALYSIS METHOD</div><div class="rp-stat-value rp-stat-method">{'Semantic AI' if st.session_state.engine_choice == 'Multilingual semantic AI' else 'Text matching'}</div><div class="rp-stat-detail">Server-side comparison</div></div>
         <div class="rp-stat"><div class="rp-stat-label">EVIDENCE CONNECTION</div><div class="rp-stat-value rp-stat-pending">Available</div><div class="rp-stat-detail">Manual evidence review</div></div>
        </div>''', unsafe_allow_html=True,
    )

    main_col, right_col = st.columns([3.2, 1.35], gap="large")
    with main_col:
        section_heading("01", "NEW INVESTIGATION", "Submit a claim", "Paste a public claim or transcript. The tool compares it with messages saved in your current session. Do not enter confidential newsroom sources or personal information.")
        with st.form("submit_claim", clear_on_submit=False):
            claim = st.text_area(
                "MESSAGE OR TRANSCRIPT", height=154,
                placeholder="Paste a forwarded message, social post or short video transcript…",
                key="investigation_claim", max_chars=MAX_TEXT,
            )
            source = st.selectbox(
                "SOURCE PLATFORM", ["WhatsApp", "Facebook", "TikTok", "X", "Other"],
                key="investigation_platform",
            )
            submitted = st.form_submit_button("Analyse and save message  →", type="primary", use_container_width=True)

        if submitted:
            text = claim.strip()
            if len(text) < 15:
                st.warning("Please enter at least 15 characters to run a comparison.")
            elif len(st.session_state.reports) >= MAX_CLAIMS:
                st.error("The working library is full. Export your data before clearing or archiving it.")
            else:
                model, mode, error = selected_model()
                if error:
                    st.warning("Semantic model unavailable. The message was compared using quick wording matching instead. Check the application logs if the model download fails.")
                try:
                    with st.spinner("Comparing the message against submitted claims…"):
                        results = compare(text, st.session_state.reports, model=model)
                except Exception as exc:
                    st.error(f"Analysis could not be completed. Try Quick text matching. Details: {exc}")
                else:
                    st.session_state.last_matches = results
                    st.session_state.last_engine = mode
                    st.session_state.last_query = text
                    add_row(text, source)
                    st.success(f"Message saved. {len(results)} possible narrative connection(s) found using {('semantic AI' if mode == 'semantic' else 'wording comparison')}.")

        section_heading("02", "COMPARISON RESULTS", "Possible related messages")
        matches = st.session_state.last_matches
        if matches is None:
            st.markdown('''<div class="rp-empty-state"><div class="rp-empty-mark">≡</div>
                <h3>Analysis results appear here</h3>
                <p>Submit a message to see which existing claims may describe a related story and how the wording differs.</p></div>''', unsafe_allow_html=True)
        elif not matches:
            st.info("No messages passed the review threshold. This does not establish that your claim is original, accurate or false.")
        else:
            st.caption(
                f"{len(matches)} possible connection(s) · "
                f"{'Semantic matching' if st.session_state.last_engine == 'semantic' else 'Wording comparison'} · "
                "Similarity is not an accuracy or truth score."
            )
            for index, match in enumerate(matches[:10], 1):
                summary = f"{index:02d}   {match['label']} · {match['score']:.0f}/100 similarity index · {match['item']['source']}"
                with st.expander(summary, expanded=index == 1):
                    st.markdown("**Submitted message from library**")
                    st.write(match["item"]["text"])
                    st.markdown("**Changes to review**")
                    for signal in match["signals"]:
                        st.markdown(f"- {signal}")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown("**Only in new message**")
                        st.write(", ".join(match["added"][:25]) or "No distinct keywords")
                    with col_b:
                        st.markdown("**Only in library version**")
                        st.write(", ".join(match["removed"][:25]) or "No distinct keywords")
                    st.caption("Human review required. This is not a fact-check, dissemination route or proof of the first source.")
    with right_col:
        st.markdown('''
            <div class="rp-aside-card">
              <p class="rp-aside-kicker">INVESTIGATION PROTOCOL</p>
              <h3>From claim to comparison</h3>
              <div class="rp-workflow-item"><span>01</span><div><strong>Capture</strong><p>Preserve the original submitted wording.</p></div></div>
              <div class="rp-workflow-item"><span>02</span><div><strong>Connect</strong><p>Compare meaning against earlier submitted messages.</p></div></div>
              <div class="rp-workflow-item"><span>03</span><div><strong>Examine</strong><p>Flag scope, certainty, denials and changed figures.</p></div></div>
              <div class="rp-aside-divider"></div>
              <div class="rp-aside-caption">EVIDENCE READY</div>
              <p class="rp-aside-footnote">Live evidence retrieval and source-linked verification reports.</p>
            </div>
            <div class="rp-note-card"><div class="rp-note-heading">EDITORIAL STANDARD</div>
              <p>Related wording does not prove that either claim is false. Investigate evidence before reporting a verdict.</p>
            </div>''', unsafe_allow_html=True)

elif page == "Evidence desk":
    st.markdown("""\n        <div class=\"rp-page-header\">\n          <div class=\"rp-page-kicker\">WORKSPACE <span>/</span> EVIDENCE DESK</div>\n          <h1>Research published evidence<span class=\"rp-title-dot\">.</span></h1>\n          <p>Search current reporting and published fact-check reviews, then record your editorial findings in a documented evidence brief.</p>\n        </div>""", unsafe_allow_html=True)
    claim_input = st.text_area("CLAIM UNDER INVESTIGATION", value=st.session_state.last_query, height=110, max_chars=2500)
    query = st.text_input("EDITABLE SEARCH TERMS", value=suggest_query(claim_input) if claim_input else "")
    st.info("Public demo: do not enter private messages, phone numbers or identifying information. Edited search terms are sent to external search providers.")
    api_key = st.text_input("Google Fact Check Tools API key (optional)", type="password", help="Leave empty to search news only. A key enables searches of published fact-check reviews.")
    search_news_enabled = st.checkbox("Search current news headlines", value=True)
    search_checks_enabled = st.checkbox("Search published fact-checks", value=False, disabled=not bool(api_key))
    st.caption("An API key is optional. If you have not enabled the Fact Check Tools API in Google Cloud, leave the key empty and search news only. Never share your key in screenshots.")
    if st.button("Search evidence sources", type="primary"):
        if not claim_input.strip() or len(query.strip()) < 3:
            st.warning("Enter a claim and at least three characters of search terms.")
        elif not search_news_enabled and not search_checks_enabled:
            st.warning("Select at least one evidence source.")
        else:
            st.session_state.evidence_news = []
            st.session_state.evidence_checks = []
            st.session_state.evidence_claim = claim_input.strip()
            st.session_state.evidence_query = query.strip()
            st.session_state.evidence_news_status = "not_requested"
            st.session_state.evidence_checks_status = "not_requested"
            st.session_state.evidence_news_query_used = query.strip()
            if search_news_enabled:
                try:
                    with st.spinner("Searching current news headlines..."):
                        hits = search_news(query)
                        if not hits:
                            broader = broaden_query(query)
                            if broader and broader.casefold() != query.strip().casefold():
                                st.session_state.evidence_news_query_used = broader
                                hits = search_news(broader)
                        st.session_state.evidence_news = hits
                        st.session_state.evidence_news_status = "found" if hits else "empty"
                except EvidenceError as exc:
                    st.session_state.evidence_news_status = "error"
                    st.warning(f"News search: {exc}")
            if search_checks_enabled:
                try:
                    with st.spinner("Searching published fact-checks..."):
                        st.session_state.evidence_checks = search_fact_checks(query, api_key)
                        st.session_state.evidence_checks_status = "found" if st.session_state.evidence_checks else "empty"
                except EvidenceError as exc:
                    st.session_state.evidence_checks_status = "error"
                    st.warning(f"Fact-check search: {exc}")
    news = st.session_state.get("evidence_news", [])
    checks = st.session_state.get("evidence_checks", [])
    st.subheader("Published fact-check reviews")
    if not checks:
        if st.session_state.get("evidence_checks_status") == "error":
            st.caption("Fact-check API request failed. This is not a fact-check result. You can continue with news search.")
        elif st.session_state.get("evidence_checks_status") == "empty":
            st.caption("No related published fact-check reviews found. This does not establish the claim is true or false.")
        else:
            st.caption("No fact-check reviews retrieved. This does not prove the claim is true.")
    for item in checks:
        st.markdown(f"**{escape(item['title'])}** — {escape(item['publisher'])}")
        st.caption(f"Published: {item['date'] or 'Unknown'} · Publisher rating: {item['rating'] or 'Not supplied'}")
        st.link_button("Open original review", item['url'])
    st.subheader("Current news headlines")
    used_query = st.session_state.get("evidence_news_query_used", "")
    if st.session_state.get("evidence_news_status") in ("found", "empty") and used_query and used_query != st.session_state.get("evidence_query", ""):
        st.info(f"No results for the original long phrase, so news search was retried with: {used_query}")
    if not news:
        if st.session_state.get("evidence_news_status") == "empty":
            st.caption("The news feed responded, but no matching headlines were found. Try shorter search terms, a known location or an official organisation name. This does not prove the claim is false.")
        elif st.session_state.get("evidence_news_status") == "error":
            st.caption("News lookup failed. Check the warning above or try a different connection.")
        else:
            st.caption("No news headlines retrieved yet. This does not prove the claim is false.")
    for item in news:
        st.markdown(f"**{escape(item['title'])}** — {escape(item['publisher'])}")
        st.caption(f"Published: {item['date'] or 'Unknown'} · Headline is not independently verified evidence")
        st.link_button("Read source article", item['url'])
    notes = st.text_area("JOURNALIST'S REVIEW NOTES", placeholder="What did primary sources confirm? Which facts remain unverified?")
    if st.session_state.get("evidence_claim"):
        brief = build_brief(st.session_state.evidence_claim, st.session_state.get("evidence_query", ""), news, checks, notes)
        st.download_button("Download evidence research brief (.md)", brief, file_name="rumourprint_evidence_brief.md", mime="text/markdown")
    st.caption("A related fact-check's rating must never be applied automatically to your submitted claim. Verify source dates, original records and context before publication.")

elif page == "Relationship map":
    st.markdown("""
        <div class="rp-page-header">
          <div class="rp-page-kicker">WORKSPACE <span>/</span> RELATIONSHIP MAP</div>
          <h1>Map the changing story<span class="rp-title-dot">.</span></h1>
          <p>Explore how submitted versions of a narrative relate to each other. Lines show similarity only—not real-world transmission, chronology, or authorship.</p>
        </div>""", unsafe_allow_html=True)
    st.info("Research visualisation: every point is a message in your current session library. Connected points have similar wording or meaning. This is **not** a social-network spread graph or a truth score.")
    section_heading("01", "CLAIM RELATIONSHIPS", "Build the relationship map", "Adjust the connection threshold to examine stronger or weaker similarity links.")
    if len(st.session_state.reports) < 2:
        st.warning("Add at least two messages in Investigation desk before creating a relationship map.")
    else:
        if len(st.session_state.reports) > 60:
            st.warning("The map visualises the first 60 claims in this version, to keep it fast. The complete library remains accessible elsewhere.")
        if st.button("Build / refresh relationship map  →", type="primary"):
            model, mode, error = selected_model()
            if error:
                st.warning("Local AI model unavailable; this map will use quick wording comparison. Try again after model setup if necessary.")
            items = [dict(row) for row in st.session_state.reports[:60]]
            try:
                with st.spinner("Analysing narrative similarities and preparing the graph…"):
                    matrix = pairwise_scores([row["text"] for row in items], model=model)
                st.session_state.map_matrix = matrix
                st.session_state.map_method = mode
                st.session_state.map_items = items
            except Exception as exc:
                st.error(f"Could not build map: {exc}. Switch the analysis engine to Quick text matching and retry.")

        matrix = st.session_state.get("map_matrix")
        items = st.session_state.get("map_items", [])
        if matrix is None:
            st.markdown('<div class="rp-empty-state"><div class="rp-empty-mark">◎</div><h3>Ready to connect the claims</h3><p>Build the relationship map to reveal clusters, isolated messages and potentially important differences.</p></div>', unsafe_allow_html=True)
        elif len(matrix) != len(items):
            st.error("The map data is out of date. Click Build / refresh relationship map to recalculate.")
        else:
            default_threshold = 0.61 if st.session_state.map_method == "semantic" else 0.44
            threshold = st.slider("MINIMUM CONNECTION STRENGTH", min_value=0.30, max_value=0.95, value=default_threshold, step=0.01,
                                  help="Higher thresholds show only more similar message pairs. These are heuristic similarity scores, not likelihoods or probabilities.")
            graph = build_network(items, matrix, threshold)
            groups_with_links = sum(len(group) > 1 for group in graph["components"])
            isolated = sum(len(group) == 1 for group in graph["components"])
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("MESSAGES", len(items))
            col2.metric("SIMILARITY LINKS", len(graph["edges"]))
            col3.metric("CONNECTED GROUPS", groups_with_links)
            col4.metric("ISOLATED MESSAGES", isolated)
            st.caption(f"Engine: {'Multilingual semantic AI' if st.session_state.map_method == 'semantic' else 'Quick wording matching'} · Minimum connection {threshold:.0%} · Node numbers correspond to the list below.")
            try:
                fig = figure_for_network(graph, items)
                st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False, "displayModeBar": False})
                from plotly.io import to_html
                html_export = to_html(fig, include_plotlyjs=True, full_html=True)
                st.download_button("Download interactive map (.html)", data=html_export,
                                   file_name="rumourprint_relationship_map.html", mime="text/html")
                st.caption("The downloadable HTML includes message text in node tooltips. Keep it private if your investigation contains sensitive information.")
            except ImportError:
                st.error("Plotly is missing. Check the hosting logs and the project requirements for Plotly.")
            st.divider()
            st.markdown("**Strongest candidate connections**")
            st.caption("These are the closest submitted-message pairs at the selected threshold. A high similarity score does not imply a claim is true or that either message was shared first.")
            ranked_edges = sorted(graph["edges"], key=lambda edge: (-edge["weight"], edge["source"], edge["target"]))[:12]
            if ranked_edges:
                st.dataframe(
                    [
                        {
                            "MESSAGE A": f"#{edge['source'] + 1:02d}",
                            "MESSAGE B": f"#{edge['target'] + 1:02d}",
                            "SIMILARITY": f"{edge['weight'] * 100:.0f}/100",
                            "REVIEW CUE": shift_signals(items[edge["target"]]["text"], items[edge["source"]]["text"])[0],
                        }
                        for edge in ranked_edges
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No pairs pass the current threshold. Try lowering the connection strength to inspect weaker candidates.")
            st.divider()
            section_heading("02", "CLAIM EVOLUTION REVIEW", "Compare two versions", "Select two submitted messages to inspect exact wording changes and possible shifts in meaning.")
            labels = [f"#{i+1:02d} · {str(item.get('source','Unknown'))[:22]} · {item['text'][:65]}" for i, item in enumerate(items)]
            c_a, c_b = st.columns(2)
            with c_a:
                first = st.selectbox("VERSION A (REFERENCE)", range(len(items)), format_func=lambda i: labels[i], index=0)
            with c_b:
                second = st.selectbox("VERSION B (COMPARED)", range(len(items)), format_func=lambda i: labels[i], index=min(1,len(items)-1))
            if first == second:
                st.info("Select two different messages to compare changes.")
            else:
                a, b = items[first], items[second]
                old_markup, new_markup = highlight_differences(a["text"], b["text"])
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f'<div class="rp-diff-panel"><div class="rp-diff-label">VERSION A · {escape(a.get("source", "Unknown"))}</div><div class="rp-diff-text">{old_markup}</div></div>', unsafe_allow_html=True)
                with c2:
                    st.markdown(f'<div class="rp-diff-panel"><div class="rp-diff-label">VERSION B · {escape(b.get("source", "Unknown"))}</div><div class="rp-diff-text">{new_markup}</div></div>', unsafe_allow_html=True)
                st.caption(f"Pairwise similarity: {matrix[first][second]*100:.0f}/100 · Red = removed/replaced in version A; green = added/replaced in version B. Ordering here is chosen by you, not inferred publication order.")
                st.markdown("**Changes worth investigating**")
                for signal in shift_signals(b["text"], a["text"]):
                    st.markdown(f"- {signal}")
                st.caption("Matching narratives can disagree or directly contradict each other. Check dates, original evidence and context before drawing conclusions.")
            st.divider()
            section_heading("03", "MAP REFERENCE", "Messages included in the map", "The numbered entries correspond to the nodes in the diagram.")
            for i, item in enumerate(items):
                with st.expander(f"#{i+1:02d} · {item.get('source', 'Unknown')} · {item['text'][:78]}"):
                    st.write(item["text"])
                    st.caption(f"Recorded: {item.get('time', 'Unknown')} · No source authenticity verified")
            st.caption("Changing the slider changes the visual connections, not the underlying messages. The map groups are exploratory and should be reviewed by a journalist.")

elif page == "Claim library":
    st.markdown('''
        <div class="rp-page-header">
          <div class="rp-page-kicker">WORKSPACE <span>/</span> CLAIM LIBRARY</div>
          <h1>Claim library<span class="rp-title-dot">.</span></h1>
          <p>Review stored claims, export your research and import CSV files from earlier sessions.</p>
        </div>''', unsafe_allow_html=True)
    section_heading("01", "SAVED MATERIAL", "Submitted messages", "Review the claims currently stored in your working session, then export or import material as needed.")
    if not st.session_state.reports:
        st.info("Your claim library is empty. Submit two or more public claims in Investigation desk to compare narratives and build the relationship map.")
    st.dataframe(
        list(reversed(st.session_state.reports)), use_container_width=True, hide_index=True,
        column_config={
            "text": st.column_config.TextColumn("CLAIM / TRANSCRIPT", width="large"),
            "source": st.column_config.TextColumn("SOURCE", width="medium"),
            "time": st.column_config.TextColumn("SUBMITTED", width="medium"),
        },
    )
    st.download_button(
        "Export claim library  ↓", export_csv(), "rumourprint_claims.csv",
        "text/csv", use_container_width=False,
    )
    section_heading("02", "DATA PORTABILITY", "Import earlier messages", "Import previously exported CSV records into this session without deleting existing items.")
    uploaded = st.file_uploader("Claim library CSV", type=["csv"], accept_multiple_files=False)
    if uploaded and st.button("Import messages"):
        try:
            if uploaded.size > 1_000_000:
                raise ValueError("CSV must be smaller than 1 MB.")
            decoded = uploaded.getvalue().decode("utf-8-sig")
            rows = csv.DictReader(io.StringIO(decoded))
            if not rows.fieldnames or "text" not in rows.fieldnames:
                raise ValueError("CSV must contain a 'text' column.")
            added, skipped = 0, 0
            existing = {row["text"].strip().casefold() for row in st.session_state.reports}
            for row in rows:
                text = (row.get("text") or "").strip()
                if not 15 <= len(text) <= MAX_TEXT or text.casefold() in existing or len(st.session_state.reports) >= MAX_CLAIMS:
                    skipped += 1
                    continue
                add_row(text, (row.get("source") or "Imported")[:100], (row.get("time") or "Imported")[:80])
                existing.add(text.casefold())
                added += 1
            st.success(f"Imported {added} messages; skipped {skipped} duplicates, invalid or excess rows.")
        except (UnicodeDecodeError, csv.Error, ValueError) as exc:
            st.error(f"Import failed: {exc}")
    st.caption("Your library is stored only in this browser session, not saved as a permanent account. Export important work; do not submit private or identifying information to this public demo.")

else:
    st.markdown('''
        <div class="rp-page-header">
          <div class="rp-page-kicker">WORKSPACE <span>/</span> ABOUT &amp; ETHICS</div>
          <h1>Built for responsible investigation<span class="rp-title-dot">.</span></h1>
          <p>The platform helps journalists compare changing claims, organise related narratives and document evidence-led review.</p>
        </div>
        <div class="rp-ethics-grid">
          <div class="rp-ethics-card"><span>01 / SEMANTIC SIMILARITY</span><h3>Related in meaning</h3>
          <p>A server-hosted multilingual embedding model finds possible related claims, even when their exact wording differs. Scores are not probabilities.</p></div>
          <div class="rp-ethics-card"><span>02 / EDITORIAL STANDARD</span><h3>No automated verdicts</h3>
          <p>The model does not establish truth, authorship or transmission paths. Related claims may explicitly contradict each other.</p></div>
          <div class="rp-ethics-card"><span>03 / LOCAL PRIVACY</span><h3>Server-side AI</h3>
          <p>The hosted server downloads the model when needed. The downloaded model runs on the app server and no text is sent to an external AI API for semantic matching. The free hosted app has no user accounts or permanent case storage.</p></div>
          <div class="rp-ethics-card"><span>04 / LANGUAGE LIMITATIONS</span><h3>Test translations</h3>
          <p>Multilingual training does not guarantee reliable Luganda results. Review all matches and evaluate on actual local-language samples.</p></div>
        </div>''', unsafe_allow_html=True)
    st.caption(f"AI model: {MODEL_NAME}. Live news search is available; full-article extraction, direct platform ingestion, media forensics and automated truth verdicts are not implemented.")

st.markdown(
    '<div class="rp-main-footer">RUMOURPRINT AI <span>·</span> Powered by Fresh Exclusive Media <span>·</span> Version 0.8</div>',
    unsafe_allow_html=True,
)
