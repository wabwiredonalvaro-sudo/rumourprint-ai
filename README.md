# RUMOURPRINT AI

Professional narrative investigation and evidence-discovery workspace, **powered by Fresh Exclusive Media**.

## What it does

- **Investigation desk:** submit a publicly shareable claim and compare it with other messages in your session.
- **Evidence desk:** research indexed news headlines and optional published fact-check reviews. All links require human verification.
- **Relationship map:** explore similarity connections and compare wording differences. This is **not** a chronology or a social-media propagation graph.
- **Claim library:** import/export CSV case material within your browser session.
- **About & ethics:** clear disclosure of limitations.

It does **not** automatically determine truth, identify a disinformation origin, or prove real-world spread.

## Deploy (Streamlit Community Cloud)

1. Sign in to GitHub and create a repository (e.g. `rumourprint-ai`).
2. Upload **the contents of this directory**, including `.streamlit/` and `assets/`, to the repository root. Do **not** upload an outer ZIP file as the only item.
3. Open https://share.streamlit.io and sign in / connect GitHub.
4. Choose **Create app** → **Yup, I have an app**.
5. Select your GitHub repository, branch `main`, and entrypoint `app.py`.
6. Open **Advanced settings** and select **Python 3.12**, if available. No API secret is required for news search.
7. Deploy. Share the resulting `https://...streamlit.app` URL after confirming it loads successfully.

If the FastEmbed model download exceeds memory or fails on the free tier, switch the app sidebar engine to **Quick text matching** (labelled in the UI as Quick text matching). That is a less capable fallback. Check application logs for errors. Cloud hosting can sleep or restart. Results and session data are not guaranteed to persist.

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
- Google News RSS and Google Fact Check Tools API availability depend on third-party services and policies.

## Tests

The repository includes 19 lightweight offline unit checks and a GitHub Actions workflow. Run them locally with `python -m pip install pytest` and `python -m pytest -q tests/`. These checks do not guarantee that third-party news feeds, model downloads or browser rendering will succeed after deployment.

## Maintenance

Update files on the `main` branch and Streamlit Community Cloud should redeploy automatically. Back up the repository before major changes. For hosting instructions see `DEPLOYMENT_STEPS.md`.
