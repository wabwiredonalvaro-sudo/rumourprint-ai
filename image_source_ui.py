"""Streamlit image-source workflow; external searches require an explicit click."""
from hashlib import sha256
import hmac
import html
import time

import streamlit as st

from image_provenance import MAX_UPLOAD_BYTES
from image_source_search import ImageSearchError, image_source_report, search_image, search_summary

SESSION_LIMIT = 10
COOLDOWN_SECONDS = 10


def _settings() -> tuple[str, str]:
    try:
        return (str(st.secrets.get("SERPAPI_API_KEY", "") or "").strip(),
                str(st.secrets.get("IMAGE_SEARCH_ACCESS_CODE", "") or "").strip())
    except (FileNotFoundError, KeyError):
        return "", ""


def _show_matches(rows: list[dict], exact: bool = False) -> None:
    if not rows:
        st.caption("No results to display in this section.")
        return
    columns = st.columns(3)
    for index, item in enumerate(rows):
        with columns[index % 3]:
            with st.container(border=True):
                if item["thumbnail"]:
                    st.image(item["thumbnail"], use_container_width=True)
                st.caption("Candidate exact match · Google Lens" if exact else "Visual match · similarity only")
                st.text(item["title"] or item["source"] or "Matching page")
                if item["source"]:
                    st.caption(item["source"])
                if item["date_reported"]:
                    st.caption("Search-reported date (unverified): " + item["date_reported"])
                st.link_button("Open source page", item["url"], use_container_width=True)


def render_image_source_trace(upload) -> None:
    st.divider()
    st.subheader("Image source search & AI explanation")
    st.caption(
        "Search Google Lens results for earlier copies, related pictures and Google's AI explanation, when available. "
        "A matching page is a research lead; it does not confirm the original creator or prove fabrication."
    )
    api_key, access_code = _settings()
    configured = bool(api_key and access_code)
    supplied = ""
    if configured:
        supplied = st.text_input(
            "Newsroom access code for image search", type="password", key="image_source_access",
            help="Provided by Fresh Exclusive Media; do not enter a Google password or API key.",
        )
    else:
        st.info("Automatic image source search is not configured yet. You can still inspect metadata above or search directly in Google Lens.")
        st.link_button("Open Google Lens for a manual search", "https://lens.google/")
    authorised = configured and hmac.compare_digest(supplied.encode(), access_code.encode())
    if upload is None:
        st.caption("Upload an image above to prepare a source search. No external image search has run.")
        st.session_state.pop("image_source_result", None)
        return
    content = upload.getvalue()
    image_hash = sha256(content).hexdigest()
    query = st.text_input(
        "Additional search words (optional)", max_chars=500, key="image_source_query",
        placeholder="For example: original photo, fact check, or the caption being checked",
    )
    include_overview = st.checkbox("Include Google's AI Overview if available", value=True, key="image_source_overview")
    consent = st.checkbox(
        "I can share this image and agree to send a search copy and these search words to SerpApi and Google Lens.",
        key="image_source_consent_" + image_hash[:16],
    )
    st.caption(
        "The original upload stays unchanged. A resized copy with embedded metadata removed is sent for search. "
        "These services may retain search data under their own policies. Use publicly shareable images only. "
        "Each click can use up to three search credits, plus one image upload; no searches run automatically."
    )
    request_id = sha256((image_hash + "\n" + query.strip() + "\n" + str(include_overview)).encode()).hexdigest()
    attempts = st.session_state.get("image_source_attempts", 0)
    ready = authorised and consent and bool(content) and len(content) <= MAX_UPLOAD_BYTES and attempts < SESSION_LIMIT
    if st.button("Search image sources", key="image_source_search", disabled=not ready, type="primary"):
        # Clear an older result before a new request, including a failed request.
        st.session_state.pop("image_source_result", None)
        last_attempt = st.session_state.get("image_source_last_attempt", 0)
        if time.monotonic() - last_attempt < COOLDOWN_SECONDS:
            st.warning("Please wait a few seconds before starting another image search.")
        else:
            st.session_state.image_source_attempts = attempts + 1
            st.session_state.image_source_last_attempt = time.monotonic()
            try:
                with st.spinner("Searching Google Lens matches and retrieving available explanation..."):
                    result = search_image(content, api_key, query, include_overview)
                st.session_state.image_source_result = {"request_id": request_id, "data": result}
            except ImageSearchError as exc:
                st.error(str(exc))
    if configured and not authorised:
        st.caption("Enter the newsroom access code to enable external image search.")
    if attempts >= SESSION_LIMIT:
        st.caption("This session has reached its image-search limit.")
    stored = st.session_state.get("image_source_result")
    if not stored or stored["request_id"] != request_id or not authorised or not consent:
        st.caption("No completed source-search result is displayed for this image and these search settings.")
        return
    result = stored["data"]
    st.image(content, caption="Uploaded image — compare with the source matches below", width=450)
    st.info(search_summary(result))
    st.caption("Google Lens results via SerpApi · checked " + result["checked_at"])
    for notice in result["notices"]:
        st.warning(notice)
    overview_tab, exact_tab, visual_tab = st.tabs(["AI explanation", "Exact matches", "Visual matches"])
    with overview_tab:
        st.markdown("**Google's AI Overview**")
        st.caption("An external automated assessment, retrieved with this image search. RumourPrint has not independently verified its claims. Results may differ from your browser.")
        overview = result["overview"]
        references = {ref["index"]: ref for ref in overview["references"]}
        if overview["blocks"]:
            for block in overview["blocks"]:
                citations = " ".join(
                    '<a target="_blank" rel="noopener noreferrer" href="' + html.escape(references[i]["url"], quote=True) + '">[' + str(i + 1) + ']</a>'
                    for i in block["reference_indexes"] if i in references
                )
                if not citations:
                    citations = "<small>No supporting link returned for this passage.</small>"
                st.html("<p>" + html.escape(block["text"]) + " " + citations + "</p>")
            for ref in overview["references"]:
                st.link_button(f"[{ref['index'] + 1}] {ref['title'] or ref['source'] or 'Overview source'}", ref["url"])
        elif result["overview_status"] == "Not requested":
            st.caption("AI Overview was not requested for this search.")
        else:
            st.info("No AI Overview was retrieved for this image. The source matches remain available; no fabrication assessment has been established.")
        st.caption("A similar product image or an AI-generated description does not establish that the uploaded picture is edited. Confirm any claimed manipulation against the original and reliable reporting.")
    with exact_tab:
        st.caption("Candidate matches classified by Google Lens. Compare the actual pictures, page context, credits and dates before attributing an origin.")
        if result["exact_status"] != "Completed":
            st.warning("The exact-match lookup is unavailable, so its absence cannot be interpreted as no matches.")
        _show_matches(result["exact_matches"], exact=True)
    with visual_tab:
        st.caption("These may show different pictures with similar subjects. They are not evidence of a shared source or manipulation.")
        _show_matches(result["visual_matches"])
    st.download_button(
        "Download image source brief (.md)", image_source_report(result),
        file_name="rumourprint_image_source_brief.md", mime="text/markdown", key="image_source_download",
    )
