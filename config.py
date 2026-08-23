import os
from dotenv import load_dotenv

load_dotenv()

BASE_EMBEDDING_MODEL = os.getenv(
    "BASE_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
INDEX_DB_URL = os.getenv("INDEX_DB_URL", "sqlite:///./data/powerhub.db")
INDEX_FOLDER_PATH = os.getenv("INDEX_FOLDER_PATH", "./data")
QUERY_CACHE_PATH = os.getenv("QUERY_CACHE_PATH", "data/cache.pkl")

# Power Hub document vault
POWERHUB_STORAGE_PATH = os.getenv("POWERHUB_STORAGE_PATH", "./data/powerhub/files")
POWERHUB_ENABLED = os.getenv("POWERHUB_ENABLED", "true").lower() in ("1", "true", "yes")

# Prefer POWERHUB_MILVUS_URI. Do not export MILVUS_URI as a filesystem path —
# pymilvus reads that env var at import time and only accepts http(s) URLs.
# Default uses embedded Milvus Lite (no Docker). For standalone Milvus:
#   POWERHUB_MILVUS_URI=http://localhost:19530
MILVUS_URI = (
    os.getenv("POWERHUB_MILVUS_URI")
    or os.getenv("MILVUS_URI")
    or "./data/milvus.db"
)
MILVUS_USER = os.getenv("MILVUS_USER", "")
MILVUS_PASSWORD = os.getenv("MILVUS_PASSWORD", "")
MILVUS_DB_NAME = os.getenv("MILVUS_DB_NAME", "default")
# Milvus Lite (default local file URI) supports IVF_FLAT reliably; use HNSW with full Milvus.
MILVUS_INDEX_TYPE = os.getenv("MILVUS_INDEX_TYPE", "IVF_FLAT")
MILVUS_METRIC_TYPE = os.getenv("MILVUS_METRIC_TYPE", "IP")
MILVUS_HNSW_M = int(os.getenv("MILVUS_HNSW_M", "16"))
MILVUS_HNSW_EF_CONSTRUCTION = int(os.getenv("MILVUS_HNSW_EF_CONSTRUCTION", "256"))
MILVUS_SEARCH_EF = int(os.getenv("MILVUS_SEARCH_EF", "64"))

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() in ("1", "true", "yes")

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:8000",
    ).split(",")
    if origin.strip()
]

# Multimodal RAG (Milvus tutorial: Visualized BGE + composed retrieval + LLM rerank)
MULTIMODAL_ENABLED = os.getenv("MULTIMODAL_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)
MULTIMODAL_UPLOAD_DIR = os.getenv("MULTIMODAL_UPLOAD_DIR", "./data/multimodal")
BGE_VISUAL_MODEL_NAME = os.getenv("BGE_VISUAL_MODEL_NAME", "BAAI/bge-base-en-v1.5")
BGE_VISUAL_MODEL_PATH = os.getenv(
    "BGE_VISUAL_MODEL_PATH", "./models/Visualized_base_en_v1.5.pth"
)
CLIP_FALLBACK_MODEL = os.getenv(
    "CLIP_FALLBACK_MODEL", "clip-ViT-B-32-multilingual-v1"
)
MULTIMODAL_METRIC_TYPE = os.getenv("MULTIMODAL_METRIC_TYPE", "COSINE")
MULTIMODAL_DEFAULT_TOP_K = int(os.getenv("MULTIMODAL_DEFAULT_TOP_K", "9"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
OPENAI_RERANK_MODEL = os.getenv("OPENAI_RERANK_MODEL", "gpt-4o")
MULTIMODAL_RERANK_ENABLED = os.getenv("MULTIMODAL_RERANK_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)
