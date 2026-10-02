"""
Embedding model abstraction — independent from the generation model.
"""
from __future__ import annotations

from typing import List

import structlog

from config import settings

logger = structlog.get_logger(__name__)


class EmbeddingModel:
    """
    Provider-independent embedding interface.
    Supports: openai, sentence_transformers (local), or any future provider.
    """

    def __init__(self):
        self._model = None
        self._provider = settings.EMBEDDING_PROVIDER

    def _load(self):
        if self._model is not None:
            return

        if self._provider == "openai":
            from langchain_openai import OpenAIEmbeddings
            self._model = OpenAIEmbeddings(
                model=settings.EMBEDDING_MODEL,
                api_key=settings.OPENAI_API_KEY,
            )
        elif self._provider in ("sentence_transformers", "local"):
            from langchain_community.embeddings import HuggingFaceEmbeddings
            self._model = HuggingFaceEmbeddings(
                model_name=settings.EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        else:
            raise ValueError(f"Unknown embedding provider: {self._provider}")

        logger.info("embedding_model_loaded", provider=self._provider, model=settings.EMBEDDING_MODEL)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        self._load()
        return self._model.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        self._load()
        return self._model.embed_query(text)

    @property
    def langchain_embeddings(self):
        """Return the underlying LangChain embeddings object for use in vector stores."""
        self._load()
        return self._model


# Singleton
embedding_model = EmbeddingModel()
