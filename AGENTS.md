# AGENTS.md

## Cursor Cloud specific instructions

This repo is an enterprise multimodal search platform: a FastAPI backend (`main.py`)
+ Milvus vector DB (`docker-compose.yml`) + a React/Vite admin console (`admin/`).
The update script already installs Python deps into `.venv/` and admin deps into
`admin/node_modules/`. System packages (Docker, `unixodbc-dev` for `pyodbc`,
`fuse-overlayfs`) are baked into the environment snapshot, not the update script.

### Services and how to run them (dev)

- Backend (FastAPI): `source .venv/bin/activate && uvicorn main:app --host 127.0.0.1 --port 8001 --reload`
  Port `8001` is not documented in a script; it is required because `admin/vite.config.ts`
  proxies `/api` and `/health` to `http://127.0.0.1:8001`.
- Frontend (admin console): `npm --prefix admin run dev` → serves at `http://localhost:5173/admin/`.
- Build admin (also runs `tsc --noEmit` type-check): `npm --prefix admin run build`.
- Milvus: `sudo docker compose up -d milvus` (ports 19530 + 9091 health).
- Health check: `curl http://127.0.0.1:8001/health`.
- There is no automated test suite and no Python/JS lint config; `tsc --noEmit`
  (via the admin build) is the only static check.

### Non-obvious startup caveats (read before running)

- Docker daemon does NOT auto-start. Start it once per VM boot before Milvus:
  `sudo dockerd > /tmp/dockerd.log 2>&1 &` (a tmux session named `dockerd` is used
  during setup). The daemon is configured with the `fuse-overlayfs` storage driver
  and `iptables-legacy` so it works inside this containerized VM.
- `INDEX_DB_URL` is REQUIRED — the backend fails at import (`create_engine(None)`)
  without it. A `.env` file (gitignored, persisted on the VM disk) provides dev config.
  If `.env` is missing, recreate it with:
  ```
  INDEX_DB_URL=sqlite:///./data/search.db
  MILVUS_URI=http://localhost:19530
  JWT_SECRET_KEY=dev-secret-key
  AUTH_REQUIRED=true
  MULTIMODAL_ENABLED=true
  CLIP_FALLBACK_MODEL=clip-ViT-B-32
  ```
- Dev uses SQLite. The account-creation CRUD (`database/account_crud.py`) assigns
  `user_id`/`organization_id` as raw `uuid.uuid4()` objects, which SQLite's driver
  cannot bind — so `POST /api/v1/account/user/create` and `.../organization/create`
  return HTTP 500 on SQLite (the code's primary target is SQL Server via `pyodbc`).
  To get a login user in dev, seed the row directly with a string id, e.g.:
  ```
  .venv/bin/python -c "from database.database import SessionLocal, engine; from database import models; models.Base.metadata.create_all(bind=engine); db=SessionLocal(); db.add(models.User(username='admin', password='admin123', full_name='Admin User', email='admin@example.com', organization_id='org1', role='admin', is_active=1, user_id='u-admin-1')); db.commit()"
  ```
  Then log in via `POST /api/v1/account/token` (form fields `username`,`password`).
- Multimodal encoder: the default `CLIP_FALLBACK_MODEL` in `config.py`
  (`clip-ViT-B-32-multilingual-v1`) is TEXT-ONLY and raises
  "Modality 'image' is not supported" when indexing images with the installed
  `sentence-transformers`. Use `CLIP_FALLBACK_MODEL=clip-ViT-B-32` (set in `.env`)
  for a working image+text encoder, unless you supply Visualized BGE weights at
  `./models/Visualized_base_en_v1.5.pth`.
- First backend call to `/health` or any multimodal endpoint downloads the CLIP
  model from HuggingFace (needs network egress); subsequent calls are cached.
- `OPENAI_API_KEY` is only needed for the `.../search/rerank` GPT-4o path; base
  multimodal search works without it.
