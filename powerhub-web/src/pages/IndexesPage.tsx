import { FormEvent, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

type FolderOption = {
  id: string;
  name: string;
  path: string;
  file_count: number;
};

type Integration = {
  search_index_id: string;
  source: string;
  registered: boolean;
  text_index_ready: boolean;
  vector_index: { exists?: boolean; num_entities?: number };
  admin_search_url: string;
  admin_index_url: string;
  api_search_url: string;
};

type IndexLink = {
  id: string;
  title: string;
  description?: string;
  folder_id?: string | null;
  folder_path?: string;
  folder_name?: string;
  search_index_id: string;
  document_count: number;
  updated_at?: string;
  integration?: Integration;
};

type SearchResult = {
  id: string;
  name?: string;
  path?: string;
  score?: number;
  text?: string;
  download_url?: string;
  extension?: string;
};

const SEARCH_MODES = [
  { value: "similarity", label: "Similarity", hint: "Semantic vector search" },
  { value: "full_text", label: "Full text", hint: "Keyword BM25 search" },
  { value: "hybrid", label: "Hybrid", hint: "Combined vector + text" },
  { value: "ranked_naive", label: "Ranked", hint: "Simple ranked match" },
] as const;

function formatDate(value?: string) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function fileIcon(ext?: string) {
  const e = (ext || "").toLowerCase();
  if (e === "pdf") return "PDF";
  if (e === "docx" || e === "doc") return "DOC";
  if (e === "txt" || e === "md") return "TXT";
  if (["png", "jpg", "jpeg", "gif", "webp"].includes(e)) return "IMG";
  return "FILE";
}

function snippet(text: string, query: string, max = 180) {
  const clean = text.replace(/\s+/g, " ").trim();
  if (!query.trim()) return clean.slice(0, max) + (clean.length > max ? "…" : "");
  const lower = clean.toLowerCase();
  const q = query.toLowerCase();
  const idx = lower.indexOf(q);
  if (idx === -1) return clean.slice(0, max) + (clean.length > max ? "…" : "");
  const start = Math.max(0, idx - 40);
  const end = Math.min(clean.length, idx + q.length + 80);
  const slice = (start > 0 ? "…" : "") + clean.slice(start, end) + (end < clean.length ? "…" : "");
  return slice;
}

export function IndexesPage() {
  const { can } = useAuth();
  const [indexes, setIndexes] = useState<IndexLink[]>([]);
  const [folders, setFolders] = useState<FolderOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [folderId, setFolderId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("similarity");
  const [selected, setSelected] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searchMeta, setSearchMeta] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [createError, setCreateError] = useState("");
  const [busy, setBusy] = useState(false);
  const [searching, setSearching] = useState(false);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const selectedFolder = useMemo(
    () => folders.find((f) => f.id === folderId) || null,
    [folders, folderId],
  );

  const selectedIndex = useMemo(
    () => indexes.find((idx) => idx.id === selected) || null,
    [indexes, selected],
  );

  const stats = useMemo(() => {
    const docs = indexes.reduce((sum, idx) => sum + (idx.document_count || 0), 0);
    const vectorReady = indexes.filter((idx) => idx.integration?.vector_index?.exists).length;
    return { count: indexes.length, docs, vectorReady };
  }, [indexes]);

  const indexedFolderIds = useMemo(
    () => new Set(indexes.map((idx) => idx.folder_id).filter(Boolean)),
    [indexes],
  );

  async function load() {
    setLoading(true);
    try {
      const [list, folderList] = await Promise.all([api.indexes(), api.foldersForIndex()]);
      const typed = list as IndexLink[];
      setIndexes(typed);
      setFolders(folderList as FolderOption[]);
      setError("");
      setSelected((prev) => {
        if (prev && typed.some((idx) => idx.id === prev)) return prev;
        return typed.length ? String(typed[0].id) : "";
      });
      const indexedIds = new Set(typed.map((idx) => idx.folder_id).filter(Boolean));
      if (!folderId && folderList.length) {
        const available = (folderList as FolderOption[]).find(
          (f) => f.file_count > 0 && !indexedIds.has(f.id),
        );
        const fallback = (folderList as FolderOption[]).find((f) => f.file_count > 0);
        setFolderId((available || fallback || folderList[0]).id as string);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load indexes");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (!selectedFolder || !showCreate) return;
    setTitle((prev) => (prev.trim() ? prev : `${selectedFolder.name} index`));
    setDescription((prev) =>
      prev.trim()
        ? prev
        : `Search index for files in ${selectedFolder.path} (${selectedFolder.file_count} documents)`,
    );
  }, [selectedFolder, showCreate]);

  useEffect(() => {
    setResults([]);
    setSearchMeta(null);
    setQuery("");
  }, [selected]);

  function openCreate() {
    setCreateError("");
    setShowCreate(true);
  }

  function closeCreate() {
    setShowCreate(false);
    setCreateError("");
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!folderId) {
      setCreateError("Select a folder to index.");
      return;
    }
    setBusy(true);
    setCreateError("");
    try {
      const link = await api.createIndex({
        title: title || `${selectedFolder?.name || "Folder"} index`,
        description,
        folder_id: folderId,
      });
      setSelected(String(link.id));
      closeCreate();
      await load();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function onSync(linkId: string) {
    setSyncing(linkId);
    setError("");
    try {
      await api.syncIndex(linkId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncing(null);
    }
  }

  async function onDelete(linkId: string, titleLabel: string) {
    if (!confirm(`Delete “${titleLabel}”? This removes the search index and cannot be undone.`)) return;
    setError("");
    try {
      await api.deleteIndex(linkId);
      if (selected === linkId) setSelected("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function onSearch(e?: FormEvent) {
    e?.preventDefault();
    if (!selected || !query.trim()) return;
    setSearching(true);
    setError("");
    try {
      const payload = await api.searchIndex(selected, query.trim(), mode);
      setResults((payload.results as SearchResult[]) || []);
      setSearchMeta(payload as Record<string, unknown>);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
      setResults([]);
      setSearchMeta(null);
    } finally {
      setSearching(false);
    }
  }

  if (loading && !indexes.length) {
    return (
      <div className="indexes-page">
        <h1 className="page-title">Search Indexes</h1>
        <p className="page-sub muted">Loading your indexes…</p>
      </div>
    );
  }

  return (
    <div className="indexes-page">
      <header className="indexes-header">
        <div>
          <h1 className="page-title">Search Indexes</h1>
          <p className="page-sub">
            Turn vault folders into searchable indexes powered by power-hub-search.
          </p>
        </div>
        {can("indexes.create") && (
          <button className="btn primary" type="button" onClick={openCreate}>
            New index
          </button>
        )}
      </header>

      <div className="grid-stats indexes-stats">
        <div className="stat">
          <span className="muted">Indexes</span>
          <strong>{stats.count}</strong>
        </div>
        <div className="stat">
          <span className="muted">Documents indexed</span>
          <strong>{stats.docs}</strong>
        </div>
        <div className="stat">
          <span className="muted">Vector-ready</span>
          <strong>{stats.vectorReady}</strong>
        </div>
      </div>

      {error && <div className="error indexes-error">{error}</div>}

      <div className="indexes-layout">
        <aside className="indexes-sidebar panel">
          <div className="indexes-sidebar-head">
            <h3>Your indexes</h3>
            <span className="pill">{indexes.length}</span>
          </div>

          {indexes.length === 0 ? (
            <div className="indexes-empty">
              <p>No search indexes yet.</p>
              <p className="muted">
                Create an index from a vault folder to search across its documents with semantic
                or keyword search.
              </p>
              {can("indexes.create") && (
                <button className="btn primary" type="button" onClick={openCreate}>
                  Create your first index
                </button>
              )}
            </div>
          ) : (
            <ul className="index-list">
              {indexes.map((idx) => {
                const integration = idx.integration;
                const vectorOk = integration?.vector_index?.exists;
                const active = selected === idx.id;
                return (
                  <li key={idx.id}>
                    <button
                      type="button"
                      className={`index-card${active ? " active" : ""}`}
                      onClick={() => setSelected(idx.id)}
                    >
                      <div className="index-card-top">
                        <strong>{idx.title}</strong>
                        <span className="index-doc-count">{idx.document_count}</span>
                      </div>
                      <div className="index-card-folder muted">
                        {idx.folder_path || idx.folder_name || "Vault folder"}
                      </div>
                      <div className="index-card-status">
                        <span className={`status-dot ${integration?.registered ? "ok" : "warn"}`} />
                        <span className="status-label">
                          {integration?.text_index_ready ? "Text" : "No text"}
                        </span>
                        <span className={`status-dot ${vectorOk ? "ok" : "muted"}`} />
                        <span className="status-label">{vectorOk ? "Vector" : "Text only"}</span>
                      </div>
                      <div className="index-card-meta muted">
                        Updated {formatDate(idx.updated_at)}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </aside>

        <main className="indexes-workspace">
          {!selectedIndex ? (
            <section className="panel indexes-placeholder">
              <h3>Select an index</h3>
              <p className="muted">
                Choose an index from the list to search its documents, sync from the vault, or view
                integration details.
              </p>
            </section>
          ) : (
            <>
              <section className="panel index-detail">
                <div className="index-detail-head">
                  <div>
                    <h2>{selectedIndex.title}</h2>
                    {selectedIndex.description && (
                      <p className="muted index-detail-desc">{selectedIndex.description}</p>
                    )}
                  </div>
                  <div className="index-detail-actions">
                    {can("indexes.create") && (
                      <button
                        className="btn"
                        type="button"
                        disabled={syncing === selectedIndex.id}
                        onClick={() => void onSync(selectedIndex.id)}
                      >
                        {syncing === selectedIndex.id ? "Syncing…" : "Sync from vault"}
                      </button>
                    )}
                    {can("indexes.delete") && (
                      <button
                        className="btn danger"
                        type="button"
                        onClick={() => void onDelete(selectedIndex.id, selectedIndex.title)}
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </div>

                <dl className="index-meta-grid">
                  <div>
                    <dt>Source folder</dt>
                    <dd>{selectedIndex.folder_path || selectedIndex.folder_name || "—"}</dd>
                  </div>
                  <div>
                    <dt>Documents</dt>
                    <dd>{selectedIndex.document_count}</dd>
                  </div>
                  <div>
                    <dt>Last synced</dt>
                    <dd>{formatDate(selectedIndex.updated_at)}</dd>
                  </div>
                  <div>
                    <dt>Integration</dt>
                    <dd>
                      {selectedIndex.integration?.registered ? (
                        <span className="pill">Registered in power-hub-search</span>
                      ) : (
                        <span className="pill warn">Not registered</span>
                      )}
                    </dd>
                  </div>
                </dl>

                <button
                  type="button"
                  className="btn ghost indexes-advanced-toggle"
                  onClick={() => setShowAdvanced((v) => !v)}
                >
                  {showAdvanced ? "Hide" : "Show"} developer links
                </button>

                {showAdvanced && selectedIndex.integration && (
                  <div className="index-advanced muted">
                    <div>
                      <span>Search index ID</span>
                      <code>{selectedIndex.search_index_id}</code>
                    </div>
                    <div className="index-advanced-links">
                      <a href={selectedIndex.integration.admin_index_url} target="_blank" rel="noreferrer">
                        Admin detail
                      </a>
                      <a href={selectedIndex.integration.admin_search_url} target="_blank" rel="noreferrer">
                        Search playground
                      </a>
                      <code>{selectedIndex.integration.api_search_url}</code>
                    </div>
                  </div>
                )}
              </section>

              <section className="panel index-search">
                <h3>Search this index</h3>
                <form className="index-search-form" onSubmit={onSearch}>
                  <div className="index-search-bar">
                    <input
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="Ask a question or enter keywords…"
                      aria-label="Search query"
                    />
                    <button
                      className="btn primary"
                      type="submit"
                      disabled={searching || !query.trim()}
                    >
                      {searching ? "Searching…" : "Search"}
                    </button>
                  </div>

                  <div className="mode-chips" role="group" aria-label="Search mode">
                    {SEARCH_MODES.map((m) => (
                      <button
                        key={m.value}
                        type="button"
                        className={`mode-chip${mode === m.value ? " active" : ""}`}
                        title={m.hint}
                        onClick={() => setMode(m.value)}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>
                </form>

                {searchMeta && results.length === 0 && !searching && (
                  <div className="indexes-empty inline">
                    <p>No matches for “{query}”.</p>
                    <p className="muted">Try a different query or switch search mode.</p>
                  </div>
                )}

                {results.length > 0 && (
                  <div className="search-results">
                    <p className="search-results-meta muted">
                      {results.length} result{results.length === 1 ? "" : "s"}
                      {searchMeta?.mode ? ` · ${String(searchMeta.mode)}` : ""}
                    </p>
                    <ul className="result-list">
                      {results.map((hit, i) => (
                        <li key={String(hit.id)} className="result-card">
                          <div className="result-rank">{i + 1}</div>
                          <div className="result-body">
                            <div className="result-head">
                              <span className="result-icon">{fileIcon(hit.extension)}</span>
                              <div>
                                <strong>{hit.name || hit.id}</strong>
                                {hit.path && <div className="muted result-path">{hit.path}</div>}
                              </div>
                              {hit.score != null && (
                                <span className="result-score">
                                  {(hit.score * 100).toFixed(0)}% match
                                </span>
                              )}
                            </div>
                            {hit.text && (
                              <p className="result-snippet">{snippet(hit.text, query)}</p>
                            )}
                            {hit.download_url && (
                              <a className="result-download" href={hit.download_url}>
                                Download file
                              </a>
                            )}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </section>
            </>
          )}
        </main>
      </div>

      {showCreate && can("indexes.create") && (
        <div className="modal-backdrop" onClick={closeCreate}>
          <div
            className="modal indexes-modal"
            role="dialog"
            aria-labelledby="create-index-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="create-index-title">Create search index</h2>
            <p className="muted">
              Pick a vault folder. Files in that folder and its subfolders will be indexed.
            </p>

            <form onSubmit={onCreate}>
              <div className="field">
                <label htmlFor="index-folder">Source folder</label>
                <select
                  id="index-folder"
                  value={folderId}
                  onChange={(e) => {
                    setFolderId(e.target.value);
                    setTitle("");
                    setDescription("");
                  }}
                  required
                >
                  <option value="" disabled>
                    Select a folder…
                  </option>
                  {folders.map((folder) => {
                    const alreadyIndexed = indexedFolderIds.has(folder.id);
                    return (
                      <option
                        key={folder.id}
                        value={folder.id}
                        disabled={folder.file_count === 0 || alreadyIndexed}
                      >
                        {folder.path} ({folder.file_count} file{folder.file_count === 1 ? "" : "s"})
                        {alreadyIndexed ? " · indexed" : ""}
                      </option>
                    );
                  })}
                </select>
                {selectedFolder && (
                  <span className="muted">
                    {selectedFolder.file_count} file
                    {selectedFolder.file_count === 1 ? "" : "s"} under {selectedFolder.path}
                  </span>
                )}
              </div>
              <div className="field">
                <label htmlFor="index-title">Title</label>
                <input
                  id="index-title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="index-desc">Description</label>
                <textarea
                  id="index-desc"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={2}
                />
              </div>
              {createError && <div className="error">{createError}</div>}
              <div className="actions" style={{ marginTop: 8 }}>
                <button
                  className="btn primary"
                  disabled={busy || !folderId || (selectedFolder?.file_count ?? 0) === 0}
                >
                  {busy ? "Creating index…" : "Create index"}
                </button>
                <button className="btn ghost" type="button" onClick={closeCreate}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
