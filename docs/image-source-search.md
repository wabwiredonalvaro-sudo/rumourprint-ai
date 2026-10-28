# Image source research with Google Lens results

The Evidence Desk's **Image provenance** tab includes optional **Image source search & AI explanation**. Users upload a photo, supply optional search words, agree to external processing and click **Search image sources**. The workflow retrieves candidate exact matches, visually similar images and Google's AI Overview, when Google supplies one.

## Administrator setup

Create a SerpApi account with access to its Image API, Google Lens API and Google AI Overview API. Review its current pricing and provider retention policies. In Streamlit Community Cloud **App settings → Secrets**, add:

```toml
SERPAPI_API_KEY = "replace-with-your-provider-key"
IMAGE_SEARCH_ACCESS_CODE = "replace-with-a-long-random-newsroom-code"
```

Keep both values out of GitHub. Share only the access code with authorised newsroom users. Both are required; configuring only a key does not enable public billable searches. Set provider-side credit caps and alerts. The app limits each session to ten attempts with a ten-second cooldown, but refreshing or opening another session can bypass session limits. This demo does not provide production authentication or global billing controls.

Without configuration, local metadata/C2PA inspection and a manual Google Lens link remain available. There is no automatic fallback to a fabricated explanation. This integration does not require a separate Gemini/OpenAI key.

## Requests and privacy

- No external image search occurs at upload or page load. A user must agree to external processing and click the search button.
- JPG, PNG and WebP inputs remain limited to 8 MB and 24 million pixels. Search uses the first frame, honours EXIF orientation, removes embedded metadata and creates a copy no larger than 1600 pixels on its longest side and 480,000 bytes. Transparency is composited on white. The original upload is not overwritten. Resizing/recompression can affect matching.
- The copy is sent by multipart POST to `https://serpapi.com/image`. The returned `image_id` is used to search `https://serpapi.com/search.json?engine=google_lens&type=all` and `type=exact_matches`, with auto-cropping disabled, English results and SafeSearch enabled.
- Optional user search words refine the `all` search only. The exact-match lookup remains image-only.
- If Google supplies an overview token, the app immediately retrieves it through `engine=google_ai_overview` before the exact search because the token expires after one minute. If no overview is supplied, the app reports that clearly.
- One attempt uses at most one upload and three search requests. There are no background retries or pagination. Check current provider pricing; the earlier Cloud Vision free allowance does not apply to SerpApi.
- SerpApi says upload IDs expire after ten minutes. That is an identifier lifetime, **not** a guarantee that all provider data is deleted then. SerpApi/Google policies govern external handling. Do not submit confidential images or identifying information without appropriate permission.
- Results stay in the visitor's Streamlit session. They are not globally cached. Briefs include original/search-copy hashes, retrieval time, search words, overview source references and source links; credentials, upload IDs and raw provider responses are not exported. Changing the image or search settings hides stale results.
- Returned source pages are links for users to inspect. The backend does not crawl arbitrary matching pages. Thumbnail requests are restricted to SerpApi and Google's image proxy; an image/search provider may observe those requests.

## What the results establish

The AI explanation is labelled **Google's AI Overview**, an external automated assessment retrieved via SerpApi, not RumourPrint's independent verdict. Overview passages retain the returned reference indexes, with clickable supporting links. A passage with no returned supporting link is labelled accordingly. Similar products or clothing can be useful leads but do not substantiate a face-swap or fabrication claim.

Exact matches are provider-classified candidates, not independently verified pixel identity. Visual matches may be entirely different images. Search-reported dates may be relative or refer to a page, so they are shown as unverified and are never used to declare the earliest publication or photograph's capture date. The original creator, original source and authenticity remain **Not established** pending human editorial review. An empty result does not prove authenticity or fabrication; a failed exact lookup is explicitly shown as incomplete.

This fetches Google Lens results through a third-party service. It does not reproduce Google's private ranking/model pipeline or guarantee identical browser results, coverage or an overview for every image. Existing metadata/C2PA findings remain a separate evidence stream. No reliable percentage of AI-generated pixels is claimed.

## Validation

Run `python -m pytest -q tests/`. The image-source tests use synthetic images and mocked provider responses to verify preprocessing, request limits, overview references, failure reporting, access/consent gating and stale-result handling. They do not establish live API compatibility, visual forensic accuracy or agreement with Google Lens. A live acceptance check needs configured credentials and provider credit.

Provider documentation:

- https://serpapi.com/google-lens-api
- https://serpapi.com/google-lens-upload-an-image
- https://serpapi.com/image-api
- https://serpapi.com/google-lens-exact-matches-api
- https://serpapi.com/google-ai-overview-api
