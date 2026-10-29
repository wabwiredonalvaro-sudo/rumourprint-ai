"""RUMOURPRINT AI v1 — one-tap, mobile-first, evidence-led public research.

The user decides. No automatic true/false verdict, no unverified face identity,
no invented AI-origin percentages. External providers have clearly stated limits.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from urllib.parse import urlencode

import streamlit as st

from public_research import (
    automatic_terms, investigate_text, social_discovery, PublicSearchError,
    PROVENANCE_OPTIONS,
)
from social_search import public_x_posts
from picture_research import (
    human_picture_story, read_words_in_picture, reverse_picture_search, PictureResearchError,
)
from image_provenance import analyse_image, ImageReviewError
from community_reviews import approved_reviews, submit_review, ReviewError, ROLES, claim_key
from institution_accounts import suggested_institution_accounts


APP_DIR = Path(__file__).resolve().parent
ORIGINAL_LOGO_BASE64 = base64.b64encode(
    (APP_DIR / "assets" / "rumourprint-logo.svg").read_bytes()
).decode("ascii")
st.set_page_config(
    page_title="RUMOURPRINT AI | Check the story yourself",
    page_icon="🔎",
    layout="centered",
    initial_sidebar_state="collapsed",
)
st.markdown(
    f"<style>{(APP_DIR / 'assets' / 'mobile.css').read_text(encoding='utf-8')}</style>",
    unsafe_allow_html=True,
)


def secret(name: str) -> str:
    """Only admin-set secrets; never request provider API credentials from visitors."""
    try:
        return str(st.secrets.get(name, "") or "").strip()
    except (FileNotFoundError, KeyError):
        return ""


def get_ocr_engine():
    from rapidocr import RapidOCR
    return RapidOCR()


@st.cache_resource(show_spinner=False)
def ocr_engine_cached():
    return get_ocr_engine()


def easy_title(text: str) -> str:
    return " ".join(str(text or "").split())[:180]


def result_card(item: dict, index: int, *, kind: str = "article") -> None:
    title = easy_title(item.get("title") or "Related public source")
    publisher = easy_title(item.get("publisher") or "Publication not specified")
    date = easy_title(item.get("date") or "Date not supplied")
    url = item.get("url", "")
    st.markdown(
        '<div class="rp-result-card"><div class="rp-result-num">SOURCE '
        + str(index) + '</div><div class="rp-result-title">' + escape(title)
        + '</div><div class="rp-result-meta">' + escape(publisher) + ' · ' + escape(date)
        + '</div></div>',
        unsafe_allow_html=True,
    )
    if url:
        st.link_button("Open original " + ("post" if kind == "post" else "article") + " ↗", url,
                       use_container_width=True)
    if item.get("description"):
        st.caption(easy_title(item["description"]))


def research_brief(claim: str, origin: str, news: dict | None, social: dict | None) -> str:
    lines = [
        "# RUMOURPRINT AI — Your research links",
        f"Made: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Claim as entered: {claim}",
        f"Where it was heard/seen: {origin}",
        f"Search words: {automatic_terms(claim)}",
        "",
        "These are related links, NOT a true/false decision. Read originals and check dates.",
        "",
        "## News and websites",
    ]
    for item in (news or {}).get("articles", [])[:80]:
        lines += ["- " + easy_title(item.get("title")) + " — " + str(item.get("url", ""))]
    for item in (news or {}).get("reviews", [])[:8]:
        lines += ["- Published fact-check: " + easy_title(item.get("title")) +
                  " — " + str(item.get("url", ""))]
    lines += ["", "## Public social posts and search links"]
    for item in (social or {}).get("posts", [])[:35]:
        lines += ["- " + str(item.get("platform")) + ": " + str(item.get("url"))]
    for platform, url in (social or {}).get("search_links", {}).items():
        lines += [f"- Search {platform}: {url}"]
    lines += ["", "## Limits",
              "Not every publication or public post is indexed; restricted or deleted content may be absent.",
              "A search result is not a verified account or a fact-check verdict.",
              "The app does not identify people by faces in photographs.",
              "Be careful with private or personal information."]
    return "\n".join(lines)


# One short page; no separate technical desks.
st.markdown(
    '<div class="rp-hero">'
    '<div class="rp-eyebrow">FRESH EXCLUSIVE MEDIA <span> / </span> COMMUNITY INFORMATION TOOL</div>'
    f'<div class="rp-logo-row"><div class="rp-logo-icon"><img src="data:image/svg+xml;base64,{ORIGINAL_LOGO_BASE64}" alt="Original RUMOURPRINT AI logo"></div>'
    '<div class="rp-brand">RUMOURPRINT<span> AI</span><small>Investigate the claim. You decide.</small></div></div>'
    '<h1>Seen something suspicious?<br><em>Check the story.</em></h1>'
    '<p>Copy a message or type something you heard. We will help you find reports, '
    'public posts and original sources so you can decide for yourself.</p>'
    '</div>',
    unsafe_allow_html=True,
)

st.link_button(
    "📚 Read helpful articles without internet (download once)",
    "https://tools.freshexclusivemedia.com/offline.html",
    use_container_width=True,
)
st.caption("The reading library saves guides on your phone after the first visit. Live investigations still need internet.")

if "public_claim" not in st.session_state:
    st.session_state.public_claim = ""
if "origin" not in st.session_state:
    st.session_state.origin = "WhatsApp"

with st.container(border=True):
    st.markdown("#### 1. What would you like to check?")
    claim = st.text_area(
        "Paste the message or type what you heard",
        key="public_claim",
        height=145,
        max_chars=2500,
        placeholder=(
            "Example (fictional): Makerere University has cancelled all examinations "
            "following an announcement by the Ministry of Education."
        ),
        label_visibility="collapsed",
    )
    st.markdown("#### 2. Where did you see or hear it?")
    origin = st.radio(
        "Choose where the message came from",
        PROVENANCE_OPTIONS,
        key="origin",
        horizontal=True,
        label_visibility="collapsed",
    )
    st.caption("You don't need to know any technical terms or write search keywords. We do that for you.")
    run = st.button(
        "🔎 Investigate",
        type="primary",
        use_container_width=True,
        disabled=len(claim.strip()) < 10,
    )
    if len(claim.strip()) < 10:
        st.caption("Paste or type a short statement first to activate Investigate.")

if run:
    clean_claim = " ".join(claim.split())
    st.session_state["investigated_claim"] = clean_claim
    st.session_state["investigated_origin"] = origin
    st.session_state["news_results"] = None
    st.session_state["social_results"] = None
    st.session_state["x_public_results"] = None
    st.session_state["picture_results"] = None
    with st.spinner("Searching news and public reports using automatically generated search words…"):
        try:
            st.session_state["news_results"] = investigate_text(
                clean_claim,
                brave_key=secret("BRAVE_SEARCH_API_KEY"),
                fact_key=secret("GOOGLE_FACTCHECK_API_KEY"),
            )
        except PublicSearchError as exc:
            st.session_state["news_error"] = str(exc)
    with st.spinner("Looking for related public social media posts…"):
        st.session_state["social_results"] = social_discovery(
            clean_claim, brave_key=secret("BRAVE_SEARCH_API_KEY"),
        )
        # Avoid unexpected charges on an open-access demo.
        if secret("ENABLE_PUBLIC_X_SEARCH").lower() == "true" and secret("X_BEARER_TOKEN"):
            st.session_state["x_public_results"] = public_x_posts(
                clean_claim, token=secret("X_BEARER_TOKEN"),
            )

saved_claim = st.session_state.get("investigated_claim", "")
news = st.session_state.get("news_results")
social = st.session_state.get("social_results")

if saved_claim:
    st.markdown(
        '<div class="rp-search-summary"><span class="rp-summary-mark">✓</span>'
        '<div><strong>Your search is ready</strong><small>Search words chosen for you: '
        + escape(automatic_terms(saved_claim)) + '</small></div></div>',
        unsafe_allow_html=True,
    )
    st.caption("You can change the message above and tap Investigate again to start a new check.")
else:
    st.markdown(
        '<div class="rp-intro-tip">👇 After you tap <strong>Investigate</strong>, '
        'open the News, Social media or Pictures section below to see what we found.</div>',
        unsafe_allow_html=True,
    )

news_tab, socials_tab, picture_tab = st.tabs(["📰 News", "💬 Social media search", "🖼️ Image search"])

with news_tab:
    st.markdown("### News and published stories")
    st.write("Find articles about the message. Open the original pages and compare what they actually say.")
    if not saved_claim:
        st.info("Enter a claim above and tap Investigate to search news.")
    elif news:
        items = news.get("articles", [])
        count = len(items)
        st.markdown(f"**{count} related article or website link{'s' if count != 1 else ''} found**")
        st.caption("This is what the enabled search services returned, not the number of all articles on the internet.")
        for i, item in enumerate(items[:12], 1):
            result_card(item, i)
        if len(items) > 12:
            with st.expander(f"See {len(items) - 12} more links"):
                for i, item in enumerate(items[12:90], 13):
                    result_card(item, i)
        reviews = news.get("reviews", [])
        if reviews:
            with st.expander(f"See {len(reviews)} published fact-check review(s)"):
                st.caption("These are other organisations' reviews, not RUMOURPRINT's conclusion.")
                for i, item in enumerate(reviews, 1):
                    result_card(item, i)
        if not items:
            st.warning("No results came back from the active sources. That does not mean the claim is false.")
        errors = [x.get("error") for x in news.get("status", []) if x.get("error")]
        if errors:
            with st.expander("Sources we couldn't search"):
                for warning in dict.fromkeys(errors):
                    st.caption(warning)
        with st.expander("Need to look further?"):
            st.caption("Some articles are missing from search indexes. You can expand your search yourself.")
            q = automatic_terms(saved_claim)
            st.link_button("Try Google Search", "https://www.google.com/search?" + urlencode({"q": q}))
            st.link_button("Try Bing Search", "https://www.bing.com/search?" + urlencode({"q": q}))
            st.caption(news["scope"])
    else:
        st.warning(st.session_state.get("news_error", "News search is not available right now. Please try again."))

with socials_tab:
    st.markdown("### What are people saying online?")
    st.write(
        "Look for public posts with similar words. Open the original post to check who posted it and when."
    )
    if not saved_claim:
        st.info("Enter a claim above and tap Investigate to look for public social media posts.")
    else:
        social = social or social_discovery(saved_claim)
        x_result = st.session_state.get("x_public_results") or {}
        x_posts = x_result.get("posts") or []
        if x_posts:
            st.markdown(f"**{len(x_posts)} recent public X posts returned**")
            for i, post in enumerate(x_posts[:8], 1):
                st.markdown(f"**@{post['handle']} — {post['display_name']}**")
                st.caption(f"{post['created_at']} · {post['post_kind']}")
                st.write("“" + " ".join(post["text"].split()[:38]) + "”")
                st.link_button("Open original post ↗", post["url"], use_container_width=True)
            if len(x_posts) > 8:
                with st.expander(f"See {len(x_posts) - 8} more X posts"):
                    for post in x_posts[8:]:
                        st.markdown(f"**@{post['handle']}** · {post['created_at']}")
                        st.link_button("Open original post ↗", post["url"])
        elif x_result.get("error"):
            st.caption("X could not return posts: " + x_result["error"])

        indexed = social.get("posts", [])
        if indexed:
            st.markdown(f"**{len(indexed)} public social post links also appeared in web search**")
            for i, hit in enumerate(indexed[:10], 1):
                result_card(hit, i, kind="post")
            if len(indexed) > 10:
                with st.expander(f"See {len(indexed) - 10} more post links"):
                    for i, hit in enumerate(indexed[10:], 11):
                        result_card(hit, i, kind="post")

        st.markdown("#### Search each social network")
        st.caption("These buttons open searches for your claim. Some social sites need you to sign in.")
        for platform, link in social["search_links"].items():
            st.link_button("Search on " + platform + " ↗", link, use_container_width=True)

        suggested_accounts = suggested_institution_accounts(saved_claim)
        if suggested_accounts:
            st.markdown("#### Accounts linked to people or organisations mentioned")
            st.caption(
                "These are possible official accounts named or linked from institutional sources. "
                "Always confirm the current account directly on the institution's own website."
            )
            for account in suggested_accounts:
                with st.container(border=True):
                    st.markdown(f"**{account['name']} — @{account['handle']}**")
                    st.caption(account["warning"])
                    st.link_button("Look for original posts by this account", account["x_search"],
                                   use_container_width=True)
                    st.link_button("Check the institution's own website or public notice",
                                   account["source"], use_container_width=True)

        people = social.get("possible_names") or []
        if people:
            st.markdown("#### People or organisations to check")
            st.caption("Names below are suggestions from the wording, not verified accounts or endorsements.")
            for person in people:
                st.link_button(
                    "Find public statements mentioning " + person,
                    "https://www.google.com/search?" + urlencode({
                        "q": person + " " + automatic_terms(saved_claim)[:85] + " site:x.com"
                    }),
                )
        st.info(
            "We cannot prove a social account belongs to a person just because it has their name or a badge. "
            "Check the original account against the person's official website or other independent source."
        )
        if not indexed and not x_posts:
            st.caption("No public post links returned by connected services. Use the social-search links above; empty results don't prove nobody posted it.")
        if social.get("warnings"):
            with st.expander("What we could and couldn't search"):
                for message in social["warnings"]:
                    st.caption(message)
        if not secret("BRAVE_SEARCH_API_KEY") or not secret("ENABLE_PUBLIC_X_SEARCH").lower() == "true":
            st.caption("Automatic social-media coverage is limited until additional provider connections are enabled.")

with picture_tab:
    st.markdown("### Check a picture")
    st.write("Upload a photo, flyer or screenshot. We can look for words in it and show what its file information says.")
    upload = st.file_uploader(
        "Choose a picture from your phone",
        type=["png", "jpg", "jpeg", "webp"],
        key="simple_image",
        help="You can use a photo or screenshot. Please avoid uploading other people's private pictures.",
    )
    st.caption("Your picture is read on this app's server. Don't upload confidential or private images.")
    vision_ready = bool(secret("GOOGLE_CLOUD_VISION_API_KEY"))
    ask_online = False
    if vision_ready:
        ask_online = st.checkbox(
            "Also look for this picture on the internet (sends the picture to Google)",
            value=False,
            key="share_picture_with_google",
        )
    else:
        st.caption("For reverse picture searches, you can also upload the same image directly to Google Lens.")
        st.link_button("Open Google Lens ↗", "https://lens.google.com/", use_container_width=True)
    if upload is not None:
        size_ok = upload.size <= 8 * 1024 * 1024
        if not size_ok:
            st.warning("Please choose a smaller picture, under 8 MB.")
        do_picture = st.button("🔎 Check this picture", type="primary",
                               use_container_width=True, disabled=not size_ok)
        if do_picture:
            content = upload.getvalue()
            try:
                with st.spinner("Checking picture details and looking for text…"):
                    details = analyse_image(content, upload.name)
                    story = human_picture_story(details)
                    reading = None
                    reading_error = ""
                    try:
                        reading = read_words_in_picture(content, engine=ocr_engine_cached())
                    except PictureResearchError as exc:
                        reading_error = str(exc)
                    reverse = None
                    reverse_error = ""
                    if ask_online:
                        try:
                            reverse = reverse_picture_search(content, secret("GOOGLE_CLOUD_VISION_API_KEY"))
                        except PictureResearchError as exc:
                            reverse_error = str(exc)
                    st.session_state["picture_results"] = {
                        "hash": sha256(content).hexdigest(), "info": details,
                        "story": story, "ocr": reading, "ocr_error": reading_error,
                        "reverse": reverse, "reverse_error": reverse_error,
                        "news": None,
                    }
            except ImageReviewError as exc:
                st.error(str(exc))
                st.session_state["picture_results"] = None

        picture = st.session_state.get("picture_results")
        if picture and picture["hash"] == sha256(upload.getvalue()).hexdigest():
            st.image(upload, caption="Picture you selected", use_container_width=True)
            st.markdown("#### What can we tell from this picture?")
            for message in picture["story"]:
                st.write("• " + message)
            st.caption(
                "The file's camera and software records can be removed or changed. "
                "We cannot tell what percentage of the picture was made with AI."
            )

            reading = picture.get("ocr") or {}
            st.markdown("#### Words found in your picture")
            if reading.get("found"):
                st.text_area("You can copy these words", value=reading["text"][:1800],
                             height=110, key="ocr_display")
                st.caption("Computer-read text may contain mistakes. Check it against the picture.")
                if st.button("🔎 Find news about these words", use_container_width=True):
                    with st.spinner("Searching related news and published reports…"):
                        try:
                            picture["news"] = investigate_text(
                                reading["text"][:800],
                                brave_key=secret("BRAVE_SEARCH_API_KEY"),
                                fact_key=secret("GOOGLE_FACTCHECK_API_KEY"),
                            )
                            picture["news_error"] = ""
                        except PublicSearchError as exc:
                            picture["news_error"] = str(exc)
                if picture.get("news"):
                    hits = picture["news"]["articles"]
                    st.markdown(f"**{len(hits)} related news links found**")
                    for i, hit in enumerate(hits[:10], 1):
                        result_card(hit, i)
                if picture.get("news_error"):
                    st.caption(picture["news_error"])
            else:
                st.caption(picture.get("ocr_error") or "We could not clearly read any words in this picture.")

            st.markdown("#### Where else has a similar picture appeared?")
            reverse = picture.get("reverse") or {}
            if reverse.get("pages"):
                st.caption(reverse["note"])
                for i, page in enumerate(reverse["pages"], 1):
                    st.markdown(f"**{i}. {easy_title(page['title'])}**")
                    st.link_button("Open matching page ↗", page["url"], use_container_width=True)
            elif picture.get("reverse_error"):
                st.warning(picture["reverse_error"])
            elif not vision_ready:
                st.caption("Online picture matching isn't connected yet. Google Lens can help you search using the image itself.")
                st.link_button("Upload this picture to Google Lens ↗", "https://lens.google.com/",
                               use_container_width=True)
            elif not ask_online:
                st.caption("Online picture matching was not requested. Tick the sharing option and check again if you want to use it.")
            else:
                st.caption("No matching pages were returned. That doesn't prove this is an original photo.")

            st.info(
                "We do not identify a person from their face. Matching web pages may contain descriptions "
                "to investigate, but a name on a page is not verified identification. Comparing two pictures "
                "also does not automatically prove that one was altered."
            )

if saved_claim:
    st.download_button(
        "↓ Save the links from this investigation",
        research_brief(
            saved_claim, st.session_state.get("investigated_origin", "Not specified"),
            news, social,
        ),
        file_name="rumourprint-research-links.md", mime="text/markdown",
        use_container_width=True,
    )


if saved_claim:
    st.divider()
    st.markdown("### 💬 What did other people find?")
    st.write(
        "Read what earlier visitors found when checking exactly this claim. "
        "These are reader notes, not final answers. Always open the original source."
    )
    review_url = secret("SUPABASE_URL")
    review_key = secret("SUPABASE_SERVICE_ROLE_KEY")
    reviews_ready = bool(review_url and review_key)
    if reviews_ready:
        try:
            @st.cache_data(ttl=120, show_spinner=False)
            def _community_lookup(claim_text: str, db_url: str, _db_key: str):
                return approved_reviews(claim_text, db_url, _db_key)

            with st.spinner("Checking earlier readers' notes…"):
                earlier_notes = _community_lookup(saved_claim, review_url, review_key)
            if earlier_notes:
                for i, note in enumerate(earlier_notes, 1):
                    with st.container(border=True):
                        st.markdown(f"**Earlier reader note {i}**")
                        st.write(note["text"])
                        st.caption(
                            f"{note['role']} (not independently verified) · "
                            f"{note['date'] or 'date not available'} · Approved for display by FEM"
                        )
                        if note["source"]:
                            st.link_button("Open the source shared by this reader ↗", note["source"])
            else:
                st.caption("No approved notes yet for this exact wording. You could be the first to help.")
        except ReviewError:
            st.caption("Earlier reader notes could not be loaded at the moment. Search results remain available.")
    else:
        st.info(
            "Community notes are not connected yet. We will only show other people's "
            "reviews after FEM enables secure storage and checks submissions before publication."
        )

    with st.expander("Share what you found — help the next reader"):
        st.write(
            "Summarise what the original articles or posts actually showed. "
            "Your note must be reviewed by FEM before it can appear for others. "
            "Please don't include phone numbers, personal details or private messages."
        )
        note_role = st.selectbox(
            "I am contributing as",
            ROLES,
            key="community_role",
            help="Self-described roles are not identity or professional-credential verification.",
        )
        note_text = st.text_area(
            "What did you find?",
            key="community_note",
            height=105,
            max_chars=700,
            placeholder="For example: I checked the university's official notice. It describes a timetable change. Source link below.",
        )
        note_source = st.text_input(
            "Link to the original source (optional)",
            key="community_source",
            placeholder="https://...",
        )
        consent = st.checkbox(
            "I agree that FEM may review this note and show it to other readers without my name.",
            key="community_consent",
        )
        if not reviews_ready:
            st.caption(
                "Publishing reader reviews requires FEM to connect a moderated database. "
                "You can still download your note for your own records."
            )
        current_key = claim_key(saved_claim)
        already_sent = current_key in st.session_state.get("community_submissions", [])
        if already_sent:
            st.success("You have already submitted a note for this claim in this session.")
        if st.button(
            "Send my note for review",
            disabled=not reviews_ready or not consent or already_sent or len(note_text.strip()) < 35,
            type="primary",
            key="send_community_note",
            use_container_width=True,
        ):
            try:
                message = submit_review(
                    saved_claim, note_text, note_role, note_source, review_url, review_key
                )
                if "community_submissions" not in st.session_state:
                    st.session_state["community_submissions"] = []
                st.session_state["community_submissions"].append(current_key)
                st.success(message)
            except ReviewError as exc:
                st.warning(str(exc))
        if note_text.strip():
            st.download_button(
                "Save my note to my phone",
                f"RUMOURPRINT AI — My own investigation note\n\n"
                f"Claim: {saved_claim}\n"
                f"Where I saw it: {st.session_state.get('investigated_origin', '')}\n"
                f"Source: {note_source}\n"
                f"What I found: {note_text}\n\n"
                "This is a personal note, not an independently verified fact-check.\n",
                file_name="rumourprint-my-review.txt",
                mime="text/plain",
                use_container_width=True,
            )

st.markdown(
    '<div class="rp-trust-strip"><strong>Our promise to you</strong>'
    '<p>No automatic “true” or “false” labels. We show related links, explain uncertainty '
    'and let you decide what the original sources mean.</p>'
    '<p>Private messages, screenshots and images may contain sensitive information. '
    'Only share material you have permission to investigate.</p></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="rp-footer"><strong>RUMOURPRINT AI</strong> · Powered by '
    '<strong>Fresh Exclusive Media</strong> · Ubuntu-inspired human-first design · '
    '<a href="https://tools.freshexclusivemedia.com/privacy.html" target="_blank">Privacy &amp; safe use</a>'
    '</div>',
    unsafe_allow_html=True,
)
