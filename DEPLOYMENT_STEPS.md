# Deployment walkthrough — RUMOURPRINT AI

## A. GitHub (Windows browser)
1. Open https://github.com/new and create a repository named `rumourprint-ai` (or a name you prefer).
2. Under the repository, click **Add file → Upload files**.
3. Extract the ZIP, open the extracted folder and drag the **contents** into the GitHub upload page. Make sure these appear in the repository root:
   - `app.py`
   - `engine.py`
   - `semantic.py`
   - `evidence.py`
   - `network.py`
   - `requirements.txt`
   - `assets/styles.css`
   - `.streamlit/config.toml`
   - `README.md`
4. Click **Commit changes**. If GitHub's browser upload does not include the hidden `.streamlit` folder, add that folder/files separately; the application will still work with default theme if the config is missing.

## B. Streamlit
1. Go to https://share.streamlit.io.
2. Sign in, connect GitHub, click **Create app**, then **Yup, I have an app**.
3. Repository: `<your-GitHub-username>/rumourprint-ai`.
4. Branch: `main` (or your actual default branch).
5. Main file path: `app.py`.
6. Desired app URL: try `rumourprint-ai` or `rumourprint-fem` (subject to availability; not reserved).
7. Advanced settings → Python version **3.12** if offered. No secrets required to search news.
8. Deploy and open the new URL.

## C. Acceptance checks
- Home loads with the logo and **Powered by Fresh Exclusive Media**.
- Investigation Desk accepts two *fictional, public* test messages and compares them.
- Relationship Map displays a graph and version comparison.
- Evidence Desk retrieves at least one live relevant headline and its clickable source link.
- Download CSV/brief works.
- If the model cannot load, switch to **Quick text matching** in the sidebar; the reduced capability must be disclosed.

## D. Critical notes
- Public Streamlit hosting is not private storage; avoid uploading confidential information.
- Session data is not persistent. App restarts lose browser-session evidence; export the library.
- The free instance may sleep and the embedding model may need to re-download.
- Similarity scores do not verify facts.
- If you later want user accounts, durable storage, stronger privacy and persistent case history, those require an additional backend and hosting design.
