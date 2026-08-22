# syntax=docker/dockerfile:1

# ---------- Stage 1: build the admin console (React/Vite) ----------
FROM node:22-slim AS frontend
WORKDIR /app/admin

# Install deps first for better layer caching
COPY admin/package.json admin/package-lock.json ./
RUN npm ci

# Build the SPA (outputs to /app/admin/dist)
COPY admin/ ./
RUN npm run build


# ---------- Stage 2: Python runtime serving API + built UI ----------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Runtime system libraries:
#  - libgomp1        : OpenMP runtime required by torch / scikit-learn
#  - libglib2.0-0    : required by opencv-python-headless (cv2)
#  - unixodbc        : ODBC runtime for pyodbc (SQL Server backend option)
#  - curl            : used by the container healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 libglib2.0-0 unixodbc curl \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only torch/torchvision first to keep the image small and the
# build fast (avoids pulling multi-GB CUDA wheels), then the rest of the deps.
COPY requirements.txt ./
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

# Application source
COPY . .

# Built admin SPA from the frontend stage (served by FastAPI at /admin)
COPY --from=frontend /app/admin/dist ./admin/dist

# Default data locations live under a mounted volume (see docker-compose.yml)
EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=5 \
    CMD curl -fsS http://localhost:8001/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
