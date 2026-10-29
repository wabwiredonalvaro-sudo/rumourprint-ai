# Community reviews and offline reader

## Shared reviews
The app can store consent-based reader notes in a Supabase table named rumourprint_reviews. All submissions start pending and are visible to later readers only after an FEM moderator approves them. Without database configuration, people can download their own note but cannot publish it to other users.

The backend expects two private Streamlit settings: SUPABASE_URL (the HTTPS project URL) and SUPABASE_SERVICE_ROLE_KEY (a server-side key). Never expose the key in GitHub or frontend code. Enable row-level security and disallow anonymous direct table access.

Required table columns: id (UUID, primary key), claim_hash (text), reviewer_role (text), review_text (text), source_url (nullable text), origin (text), status (pending / approved / rejected), created_at (timestamp). Default status must be pending. Index claim_hash, status and created_at. FEM moderators use the database admin panel to review the quoted source before approving a note.

Production readiness requires global spam limits, moderation capacity, reporting and deletion procedures, and privacy review. The reader's role is self-described, not validated professional accreditation. An approved reader note is not a truth verdict.

## Offline reading
The website contains 20 fully readable original RUMOURPRINT educational explainers. These are cached by the browser after a connected visit. Android beta 2 contains the same guides in the APK and can show them when live verification cannot load. It checks for changed guides on reopening online.

Visitors can paste stories they are permitted to retain into a personal, on-device list. The library does not redistribute copyrighted publisher archives. Future full news archive bundles require permission or compatible licences and intact publisher attribution.

Offline reading does not mean offline internet search, reverse-image lookup, social account lookup or shared review retrieval. Phone storage clearance can delete browser-cached material. Updates occur when the app is opened with network access, not continuously while closed.

## Additional integration settings
BRAVE_SEARCH_API_KEY enables broader web indexing; GOOGLE_FACTCHECK_API_KEY adds public fact-check reviews; X_BEARER_TOKEN plus ENABLE_PUBLIC_X_SEARCH enables recent public X post lookup; GOOGLE_CLOUD_VISION_API_KEY enables opt-in web matches for pictures. Provider access and costs vary. Never ask public users to supply administrator keys.