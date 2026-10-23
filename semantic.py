"""Optional, fully local multilingual semantic embeddings powered by FastEmbed.

First use fetches the published ONNX model into the app's model cache.
Subsequent uses work offline. No input texts are sent to an AI API.
"""

from pathlib import Path
import os

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def load_local_model(app_dir: Path):
    from fastembed import TextEmbedding

    # Store heavy model files outside the checked-out repository. The cache is
    # instance-local and may be cleared by the cloud host when it restarts.
    cache_dir = Path(os.environ.get("RUMOURPRINT_MODEL_CACHE", str(Path.home() / ".cache" / "rumourprint-ai" / "fastembed")))
    cache_dir.mkdir(parents=True, exist_ok=True)
    return TextEmbedding(model_name=MODEL_NAME, cache_dir=str(cache_dir))
