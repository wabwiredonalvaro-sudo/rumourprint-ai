# Official Social Accounts — X verification

RUMOURPRINT AI / Fresh Exclusive Media — October 2026.

## What this feature does
The **Evidence Desk → Official social accounts** tab helps journalists investigate whether the public X account associated with a person or institution actually published a quoted statement.

1. Paste or select a public claim.
2. Enter the target public X **@handle**. A real name is not enough to establish an account.
3. Without developer access, open the X profile and the targeted live X search links for manual verification.
4. With the newsroom's official X API bearer token configured, select **Recent 7 days** or **Full archive** (subject to X endpoint access and credits), and click **Check X account for this claim**.
5. Review the original post links, dates and short exact excerpts. Search comparisons are *wording similarity*, not proof of truth or intent.
6. If a forwarded message contains an exact post URL, paste it and select **Verify author of supplied post**. The app compares the X API post's `author_id` to the profile's stable X user ID. A mismatch is a strong warning that the post is not from the queried account.
7. Independently confirm that the X account is genuinely controlled by the alleged person or institution, using an authoritative website or an on-record confirmation, and save an evidence brief with reviewer notes.

## Enabling the real X API lookup

**This step requires the Fresh Exclusive Media administrator**. The public app **does not** have an X API token configured automatically by the code change. Users can open manual search links without developer credentials.

1. Obtain X developer access at https://developer.x.com/ and determine whether the necessary read endpoints and billing or usage credits are enabled. Developer access is *different* from merely having an X user account or an X Premium subscription.
2. Open the Streamlit Community Cloud dashboard for `rumourprint-fem` and navigate to **App settings → Secrets** (the UI wording may vary).
3. Add secrets in TOML format, for example:

```toml
X_BEARER_TOKEN = "PASTE_YOUR_PRIVATE_X_DEVELOPER_BEARER_TOKEN_HERE"
X_SOCIAL_CHECK_ACCESS_CODE = "SET_A_SEPARATE_SECRET_FOR_AUTHORISING_NEWSROOM_LOOKUPS"
```

4. Save your secrets and restart/redeploy the app if Streamlit prompts you. **Do not paste real tokens into GitHub files, screenshots, messages, social posts or the public Evidence Desk.**
5. Use the newsroom access code in the tab to authorise paid lookups. If you omit `X_SOCIAL_CHECK_ACCESS_CODE`, a configured X token may allow any visitor to trigger billable lookups. In a public-facing deployment, **always configure an access code and X-side usage limits/budget**.
6. Test a public account with a direct post you already know exists and verify both matching and mismatching author IDs.

## Facebook, Instagram and LinkedIn cross-checks

The same tab offers **manual public web discovery links** for Facebook, Instagram and LinkedIn, when a person or organisation name is provided. Those links run site-scoped web searches for relevant public pages/posts.

These other-platform links do **not** access private accounts, authenticate anyone, retrieve content through those networks' official APIs or conclusively establish who made a statement. Always open the original social post and independently verify ownership. Google or other search engine indexing can be partial or outdated.

## API operations (public only)
- `GET https://api.x.com/2/users/by/username/:username` resolves the current handle to a stable user ID.
- `GET https://api.x.com/2/tweets/search/recent` searches approximately seven days of indexed public X posts.
- `GET https://api.x.com/2/tweets/search/all` searches older posts **if your X developer access permits**.
- `GET https://api.x.com/2/tweets/:id` retrieves a particular post and its `author_id`.

The app requests **one page of up to 10 posts per click**, filters for author-ID equality, excludes retweets from origin attribution, sends requests only to `api.x.com`, and does not scrape restricted profiles, login to X as a user, look at DMs or infer deleted posts. X API requests can incur charges or hit rate limits.

## Editorial limitations
- **Account identity:** X's blue checkmark usually reflects Premium status, not independent verification of the person's real-world identity. A website controlled by the named person or institution, official records, or direct confirmation is more relevant.
- **Wording ≠ meaning:** The target account may be debunking, quoting, denying, joking about or responding to a claim; a high wording match does not prove endorsement.
- **Search is not exhaustive:** No result may mean the wrong search terms, insufficient time range, API restriction, limited page of results, deletion, handle changes, unavailable accounts or edited posts.
- **Published date:** X API date is the public post time, not necessarily when an alleged statement was first spoken.
- **Privacy:** Do not search private messages, sensitive personal information or confidential sources. Account handles, X search queries and post IDs are transmitted to X when automatic lookup is enabled.
- **Human review:** Final attribution and any related news story must be reviewed by a journalist. The downloaded brief marks final attribution as pending.

## Smoke checks
1. With no X API secret, the tab renders without error and offers manual X links. Automated search buttons stay disabled.
2. With authorised access, recent search identifies a known public post from the specified account ID.
3. A direct URL authored by a different account returns an explicit author-ID mismatch.
4. Full archive should be used only when the account's X developer plan permits access and the newsroom accepts the credit cost.
5. A retweet must not be presented as an original statement by the target account.
6. An empty result cannot be presented as proof the named person never made the statement.

## Relevant official documentation
- X Developer Platform: https://developer.x.com/
- X developer API recent search: https://docs.x.com/x-api/posts/search/introduction
- X account badge definitions: https://help.x.com/en/rules-and-policies/profile-labels
