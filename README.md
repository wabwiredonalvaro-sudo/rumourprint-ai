# RUMOURPRINT AI — Community Edition

**RUMOURPRINT AI — Built for everyone** · Hackathon theme: **AI against disinformation**

RUMOURPRINT AI helps everyday smartphone users investigate suspicious messages **without issuing automatic true/false verdicts**. It shows original source links so each visitor can examine the information and make their own decision.

## How people use it

1. Open the app and paste a public text claim or type something they heard.
2. Select where it came from (WhatsApp, Instagram, X, Facebook or spoken rumour).
3. Tap **Investigate**. Search terms are created automatically.
4. Browse three simple areas:
   - **News:** related articles and public fact-check links.
   - **Social media search:** public posts, search links, and institution-linked account candidates.
   - **Image search:** extract text from a screenshot, examine photo information and, when enabled with consent, find sites containing matching photos.
5. Read original sources, download a link summary, and optionally share what they found for RUMOURPRINT moderation.

No special terms, model/API keys or accounts are required for the basic public investigation flow.

## Offline reading for low-connectivity users

- **Website:** visit https://tools.freshexclusivemedia.com/offline.html online once. A service worker saves 20 original, complete media-literacy reading guides for offline browsing. The guides automatically check for updates when the page is visited online again.
- **Android beta 2:** includes these same guides **inside the APK** and offers a book button. The guides work without a network, and updates are downloaded when the app is reopened online.
- **Your own reading:** visitors may paste and save stories they have permission to keep into their device's local browser storage.
- **Important:** copyrighted publisher archives are not redistributed without permission. The guides are original authored explainers, not offline copies of BBC, Daily Monitor, Nile Post or Reuters.
- **Live search, new social posts, shared reviews and image web matching still need internet.** Browser caches can be cleared.

## External integrations — configured only by the app operator

No public user needs to enter an API key. The app owner may configure these private Streamlit secrets:

| Private setting | Enables |
| --- | --- |
| BRAVE_SEARCH_API_KEY | Additional general web results and indexed public social posts |
| GOOGLE_FACTCHECK_API_KEY | Published third-party fact-check reviews |
| X_BEARER_TOKEN + ENABLE_PUBLIC_X_SEARCH=true | Recent public X posts from official X API |
| GOOGLE_CLOUD_VISION_API_KEY | Consented picture matches using Google Cloud Vision WEB_DETECTION |
| SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY | Optional shared reader notes, pending RUMOURPRINT moderation |

The app still searches Google News RSS without any paid search key. It does not promise complete internet coverage. X accounts and names require external identity confirmation. The image tool does not identify faces or estimate a reliable percentage of AI-generated pixels.

## Shared community notes

Readers can add a short description of what they found and a public source URL. If RUMOURPRINT has enabled a secure database, the note is sent for moderation and becomes visible only after approval. Otherwise visitors can download their own note for personal use. Reviewer roles are self-described, not authenticated. Approved notes are not official verdicts.

See [Community review and offline setup](docs/community-offline.md).

## Project structure

| Location | Purpose |
| --- | --- |
| app.py | The one-tap mobile-first Streamlit interface |
| public_research.py | Automatic query variants and multi-source links |
| social_search.py | X public search integration |
| institution_accounts.py | Institution-linked X account search suggestions |
| picture_research.py, image_provenance.py | Text reading, image provenance and consented web matches |
| community_reviews.py | Pending moderation of optional reader notes |
| offline.html, offline-library.json, sw.js | Offline browser reader and PWA caching |
| fem-tools-site/ | Cloudflare Pages copy of the official RUMOURPRINT Tools portal |
| android-app/ | Android WebView wrapper and bundled offline reader |
| tests/ | Offline unit and Streamlit startup tests |

## Run locally with Python 3.12

Install Python 3.12, then in the repository folder:

~~~bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
~~~

Open http://localhost:8501 if the browser does not launch automatically. The first OCR/model setup may require downloads. Results from a running web investigation require internet access.

## Trust and safety

RUMOURPRINT AI does not determine who originally wrote a rumour, which posts are true, who appears in a photograph, how much of a picture was AI-generated, or whether a person actually controls an X account. Public results require individual source checking and journalistic review. Never submit confidential sources, private WhatsApp chats or personal identifying information. Static stories are stored on the visitor's device; external query providers receive the public search terms when used.

GitHub Actions runs Python regression tests and builds the Android **debug beta**, which is not a Play Store release. Device testing and security/moderation review are needed before public mass promotion.
