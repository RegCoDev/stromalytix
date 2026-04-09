"""
Knowledge Vault — sentence-transformers embedding wrapper.

Lazy-loads the model on first use to keep startup fast.
"""


class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None  # lazy load

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)

    def embed_text(self, text: str) -> list[float]:
        self._load()
        return self._model.encode(text, normalize_embeddings=True).tolist()

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        self._load()
        embeddings = self._model.encode(texts, batch_size=batch_size, normalize_embeddings=True)
        return embeddings.tolist()

    @property
    def dims(self) -> int:
        return 384

    @property
    def model_name(self) -> str:
        return self._model_name
