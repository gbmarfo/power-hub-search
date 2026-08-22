import logging
import os
from pathlib import Path

import numpy as np

import config

logger = logging.getLogger(__name__)

_encoder_instance = None


def _normalize(vector: np.ndarray) -> np.ndarray:
    arr = np.array(vector, dtype="float32").flatten()
    norm = np.linalg.norm(arr)
    if norm == 0:
        return arr
    return arr / norm


class MultimodalEncoder:
    """Visualized BGE composed retrieval with CLIP fallback."""

    BACKEND_VISUAL_BGE = "visual_bge"
    BACKEND_CLIP = "clip"

    def __init__(self) -> None:
        self.backend: str | None = None
        self._model = None
        self._dimension: int | None = None
        self._load_backend()

    def _load_backend(self) -> None:
        model_path = Path(config.BGE_VISUAL_MODEL_PATH)
        if model_path.exists():
            try:
                import torch
                from visual_bge.modeling import Visualized_BGE

                self._model = Visualized_BGE(
                    model_name_bge=config.BGE_VISUAL_MODEL_NAME,
                    model_weight=str(model_path),
                )
                self._model.eval()
                self.backend = self.BACKEND_VISUAL_BGE
                probe = self.encode_text("dimension probe")
                self._dimension = len(probe)
                logger.info(
                    "Loaded Visualized BGE encoder (dim=%s)", self._dimension
                )
                return
            except Exception as exc:
                logger.warning("Visualized BGE unavailable: %s", exc)

        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                config.CLIP_FALLBACK_MODEL,
                device=_get_device(),
            )
            self.backend = self.BACKEND_CLIP
            probe = self.encode_text("dimension probe")
            self._dimension = len(probe)
            logger.info("Loaded CLIP fallback encoder (dim=%s)", self._dimension)
        except Exception as exc:
            logger.error("No multimodal encoder available: %s", exc)
            self.backend = None

    @property
    def is_available(self) -> bool:
        return self.backend is not None

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            raise RuntimeError("Multimodal encoder is not initialized")
        return self._dimension

    def status(self) -> dict:
        return {
            "available": self.is_available,
            "backend": self.backend,
            "dimension": self._dimension,
            "visual_bge_weights": Path(config.BGE_VISUAL_MODEL_PATH).exists(),
            "clip_fallback_model": config.CLIP_FALLBACK_MODEL,
        }

    def encode_image(self, image_path: str) -> np.ndarray:
        self._ensure_available()
        if self.backend == self.BACKEND_VISUAL_BGE:
            import torch

            with torch.no_grad():
                embedding = self._model.encode(image=image_path)
            return _normalize(np.array(embedding).flatten())
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        embedding = self._model.encode(image, convert_to_tensor=False)
        return _normalize(np.array(embedding).flatten())

    def encode_text(self, text: str) -> np.ndarray:
        self._ensure_available()
        if self.backend == self.BACKEND_VISUAL_BGE:
            import torch

            with torch.no_grad():
                embedding = self._model.encode(text=text)
            return _normalize(np.array(embedding).flatten())
        embedding = self._model.encode(text, convert_to_tensor=False)
        return _normalize(np.array(embedding).flatten())

    def encode_query(self, image_path: str | None, text: str) -> np.ndarray:
        """Composed image+text query per Milvus multimodal RAG tutorial."""
        self._ensure_available()
        text = text.strip()

        if image_path and text:
            if self.backend == self.BACKEND_VISUAL_BGE:
                import torch

                with torch.no_grad():
                    embedding = self._model.encode(image=image_path, text=text)
                return _normalize(np.array(embedding).flatten())
            image_emb = self.encode_image(image_path)
            text_emb = self.encode_text(text)
            return _normalize((image_emb + text_emb) / 2.0)

        if image_path:
            return self.encode_image(image_path)
        if text:
            return self.encode_text(text)
        raise ValueError("Provide query text and/or a query image")

    def _ensure_available(self) -> None:
        if not self.is_available:
            raise RuntimeError(
                "Multimodal encoder is not available. Install dependencies and "
                "optionally download Visualized BGE weights to "
                f"{config.BGE_VISUAL_MODEL_PATH}"
            )


def _get_device() -> str:
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def get_multimodal_encoder() -> MultimodalEncoder:
    global _encoder_instance
    if _encoder_instance is None:
        _encoder_instance = MultimodalEncoder()
    return _encoder_instance
