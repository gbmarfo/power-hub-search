# Power Hub

SharePoint-style document vault built on top of **power-hub-search**.

## What it includes

- Passwordless email-code sign-in (demo returns the code) plus password fallback
- Home dashboard (continue working, team activity, vault legends, storage)
- Files & folders: upload, organize, rename, star, context menu, download
- Sharing: link creation, My Shares / All Shares, public preview + download
- Internal access grants and groups
- Recycle bin with restore / purge and configurable retention
- Library search with type filters
- **Search Indexes** that materialize vault documents and create indexes in power-hub-search (text + Milvus when available)
- Administration: users, sign-in domains, audit log
- Profile with live capability list

## Quick start

```bash
# Python deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional: Milvus for vector indexes
docker compose up -d

# Frontend
cd powerhub-web && npm install && npm run build && cd ..

# API + UI
uvicorn main:app --host 0.0.0.0 --port 8000
```

Open:

- Power Hub UI: http://localhost:8000/hub
- Search admin console: http://localhost:8000/admin
- API docs: http://localhost:8000/docs

### Seeded accounts

| Email | Username | Password | Role |
|-------|----------|----------|------|
| admin@aya.collective | admin | Admin!23 | admin |
| superuser@aya.collective | superuser | SuperUser!23 | superuser |
| maya@aya.collective | maya | Manager!23 | manager |
| noah@aya.collective | noah | Member!23 | member |

## Document parsing (PDF / Word)

On upload and when building a folder search index, Power Hub richly parses:

- **PDF** (`.pdf`): page text (PyMuPDF), structured tables (pdfplumber), figure captions, embedded images + OCR (Tesseract)
- **Word** (`.docx`): paragraphs, tables, caption-like text, embedded images + OCR
- Extracted images are stored under `data/powerhub/extracted/<org>/<file_id>/` and their OCR text is included in the searchable `content_text`

From **Search Indexes** in Power Hub:

1. Upload documents into the vault
2. Select a folder and click **Create search index**
3. Power Hub syncs file text into `powerhub_search_docs`, registers a `search_index` row (`source=powerhub`), builds the text inverted index, and (when Milvus is up) a vector collection
4. Query that index from Power Hub, the search admin playground, or via `/api/v1/search/{index_id}`

### power-hub-search integration

Each vault index is fully registered in power-hub-search:

| Component | Location |
|-----------|----------|
| Search metadata | `search_index` table (`source=powerhub`) |
| Materialized docs | `powerhub_search_docs` |
| Vault link | `powerhub_search_index_link` |
| Text index | `data/{search_index_id}_ivf.pkl` |
| Vector index | Milvus collection `idx_{search_index_id}` |

**Sync:** Use the **Sync** button in Power Hub (or `POST /api/v1/powerhub/indexes/{link_id}/sync`) to rebuild from vault files. Uploads, deletes, renames, and moves in indexed folders trigger auto-sync.

**Admin:** Power Hub indexes appear in the search admin at `/admin/indexes` with `source=powerhub`. Links to the search playground and index detail page are shown on each index row.

**Search modes:** similarity, full_text, hybrid, and ranked_naive are available from Power Hub and the unified search API.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `INDEX_DB_URL` | `sqlite:///./data/powerhub.db` | Shared metadata DB |
| `POWERHUB_STORAGE_PATH` | `./data/powerhub/files` | Uploaded file storage |
| `POWERHUB_ENABLED` | `true` | Toggle Power Hub routes |
| `POWERHUB_MILVUS_URI` | `./data/milvus.db` | Vector backend (Milvus Lite by default). Use `http://localhost:19530` with `docker compose up -d`. Avoid exporting `MILVUS_URI` as a file path. |
| `MILVUS_INDEX_TYPE` | `IVF_FLAT` | Vector index type (`HNSW` ok on full Milvus) |
| `JWT_SECRET_KEY` | `change-me-in-production` | Auth tokens |
