# RUMOURPRINT AI

**Narrative investigation and evidence research, powered by Fresh Exclusive Media.**

RUMOURPRINT AI helps journalists compare suspected misinformation, discover related claims, visualise narrative relationships and research published evidence.

## Deployment

Hosted using [Streamlit Community Cloud](https://share.streamlit.io/).

- Repository: `wabwiredonalvaro-sudo/rumourprint-ai`
- Branch: `main`
- Main file: `app.py`
- Python: 3.12

### Application files

Upload the contents of **RUMOURPRINT_AI_Deploy_Ready_v08**, not the ZIP itself or a containing folder. Required: `app.py`, `engine.py`, `semantic.py`, `evidence.py`, `network.py`, `requirements.txt`, `assets/styles.css` and `.streamlit/config.toml`.

### Important limitations

A semantic similarity score is **not a truth verdict**. Search results are research leads, and all findings require human fact-checking. Claim data lives in the Streamlit session and is not durable across application restarts. Do not submit sensitive or identifying information to public-hosted search services.

### Local run

```bash
pip install -r requirements.txt
streamlit run app.py
```

The embedding model downloads at first use. The app has a quick wording comparison fallback if the model cannot load.
