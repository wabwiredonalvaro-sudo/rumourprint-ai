# RUMOURPRINT AI

Evidence-first journalism research and narrative investigation workspace, **powered by Fresh Exclusive Media**.

## What it does

- **Investigation desk:** submit a publicly shareable claim and compare it with other messages in your session.
- **Evidence desk (default landing page):** search published claims, extract supported publisher article text and present cited passages with a conservative preliminary assessment for **mandatory human editorial review**.
- **Official social accounts:** check specified public X handles or direct post URLs for original statements using X's official API where newsroom access is configured. Explore manual public-search links for X, Facebook, Instagram and LinkedIn. An X badge or text match does **not** establish a person's identity.
- **Image provenance:** inspect uploaded JPG, PNG and WebP files for basic metadata and Content Credentials. No method here determines a reliable percentage of AI-generated or edited pixels.
- **Relationship map:** explore similarity connections and compare wording differences. This is **not** a chronology or a social-media propagation graph.
- **Claim library:** import/export CSV case material within your browser session.
- **About & ethics:** clear disclosure of limitations.

It does **not** automatically determine truth, verify real-world account identity, detect all AI-generated images, identify a disinformation origin, or prove real-world spread.

## Deploy (Streamlit Community Cloud)

1. Sign in to GitHub and create a repository (e.g. `rumourprint-ai`).
2. Upload **the contents of this directory**, including `.streamlit/` and `assets/`, to the repository root. Do **not** upload an outer ZIP file as the only item.
3. Open https://share.streamlit.io and sign in / connect GitHub.
4. Choose **Create app** → **Yup, I have an app**.
5. Select your GitHub repository, branch `main`, and entrypoint `app.py`.
6. Open **Advanced settings** and select **Python 3.12**, if available. No API secret is required for news search.
7. Deploy. Share the resulting `https://...streamlit.app` URL after confirming it loads successfully.

If the FastEmbed model download exceeds memory or fails on the free tier, switch the app sidebar engine to **Quick text matching** (labelled in the UI as Quick text matching). That is a less capable fallback. Check application logs for errors. Cloud hosting can sleep or restart. Results and session data are not guaranteed to persist.

### Optional official X post research (administrator setup)

Manual X account and post links are available without an API token. Live account-limited X post search and direct post author-ID lookups require an operator-provided X Developer API bearer token, endpoint permissions and any necessary X API usage credits/billing.

Configure `X_BEARER_TOKEN` in the Streamlit app's **Secrets**, never GitHub. For a public website, **also set** `X_SOCIAL_CHECK_ACCESS_CODE` and newsroom-side cost controls so strangers cannot trigger unlimited billable requests. The Evidence Desk displays a newsroom access code field if this setting is present.

The implementation checks public posts only, requires explicit button clicks and retrieves a maximum of 10 posts per search page. Recent lookup generally covers the last seven days; archive search depends on the X API's permissions. An absent result is not proof a person never made a claim.

See [Official Social Accounts setup](docs/official-social-accounts.md).

### Optional fact-check API

The Evidence desk can optionally use a Google Fact Check Tools API key pasted into the password field for that active session. Do not include keys in GitHub. News headlines work without an API key. An API key in this version is not stored permanently.

## Run locally

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Privacy and limitations

- This release is a **public demonstration**, not a secured production newsroom backend. It does not implement logins, role permissions, permanent encrypted case records, or a privacy-review workflow.
- Avoid submitting confidential sources, private WhatsApp content, names, phone numbers and other identifying information.
- `st.session_state` is used for each visitor session; it is not shared across visitors and is lost when a session expires/restarts. Export important records.
- The local embedding model is installed and executed **on the host server**; any remote news or fact-check search transmits query terms to those external services.
- A similarity score is **not a truth probability**. Luganda understanding remains experimental.
- Google News RSS, Google Fact Check Tools API and X API availability depend on third-party services, credentials, quotas and policies.
- Always compare attributed X statements with their original posts, dates, context and an independently verified source confirming the account holder. Do not use automatic matches as conclusive evidence.

## Tests

The repository includes offline regression tests and a GitHub Actions workflow for startup, article citations, X author ID verification, image uploads and other functionality. Run them locally with `python -m pip install pytest` and `python -m pytest -q tests/`. These checks do not guarantee that third-party news feeds, model downloads or browser rendering will succeed after deployment.

## Maintenance

Update files on the `main` branch and Streamlit Community Cloud should redeploy automatically. Back up the repository before major changes. For hosting instructions see `DEPLOYMENT_STEPS.md`.
