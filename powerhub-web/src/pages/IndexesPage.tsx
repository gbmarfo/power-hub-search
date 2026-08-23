import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

type FolderOption = {
  id: string;
  name: string;
  path: string;
  file_count: number;
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
  integration?: {
    registered: boolean;
    text_index_ready: boolean;
    vector_index: { exists?: boolean; num_entities?: number };
    admin_search_url: string;
    admin_index_url: string;
    api_search_url: string;
  };
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

type View = "search" | "manage";

const MODES = [
  { value: "similarity", label: "Similarity" },
  { value: "full_text", label: "Keywords" },
  { value: "hybrid", label: "Hybrid" },
  { value: "ranked_naive", label: "Ranked" },
] as const;

const SUGGESTIONS = ["checklist", "onboarding", "policy", "report"];

function relTime(value?: string) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  const mins = Math.round((Date.now() - d.getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 48) return `${hrs}h ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function snippet(text: string, query: string, max = 160) {
  const clean = text.replace(/\s+/g, " ").trim();
  if (!query.trim()) return clean.slice(0, max) + (clean.length > max ? "…" : "");
  const lower = clean.toLowerCase();
  const q = query.toLowerCase();
  const idx = lower.indexOf(q);
  if (idx === -1) return clean.slice(0, max) + (clean.length > max ? "…" : "");
  const start = Math.max(0, idx - 36);
  const end = Math.min(clean.length, idx + q.length + 72);
  return (start > 0 ? "…" : "") + clean.slice(start, end) + (end < clean.length ? "…" : "");
}

export function IndexesPage() {
  const { can } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);

  const [view, setView] = useState<View>("search");
  const [indexes, setIndexes] = useState<IndexLink[]>([]);
  const [folders, setFolders] = useState<FolderOption[]>([]);
  const [loading, setLoading] = useState(true);

  const [selected, setSelected] = useState("");
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("similarity");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [hasSearched, setHasSearched] = useState(false);

  const [error, setError] = useState("");
  const [searching, setSearching] = useState(false);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const [createFolderId, setCreateFolderId] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);

  const selectedIndex = useMemo(
    () => indexes.find((i) => i.id === selected) ?? null,
    [indexes, selected],
  );

  const indexedFolderIds = useMemo(
    () => new Set(indexes.map((i) => i.folder_id).filter(Boolean)),
    [indexes],
  );

  const availableFolders = useMemo(
    () => folders.filter((f) => f.file_count > 0 && !indexedFolderIds.has(f.id)),
    [folders, indexedFolderIds],
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [list, folderList] = await Promise.all([api.indexes(), api.foldersForIndex()]);
      const typed = list as IndexLink[];
      setIndexes(typed);
      setFolders(folderList as FolderOption[]);
      setError("");
      setSelected((prev) => {
        if (prev && typed.some((i) => i.id === prev)) return prev;
        return typed[0]?.id ?? "";
      });
      const indexed = new Set(typed.map((i) => i.folder_id).filter(Boolean));
      const nextFolder = (folderList as FolderOption[]).find(
        (f) => f.file_count > 0 && !indexed.has(f.id),
      );
      setCreateFolderId((prev) => prev || nextFolder?.id || "");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runSearch = useCallback(
    async (q: string, indexId: string, searchMode: string) => {
      if (!indexId || !q.trim()) return;
      setSearching(true);
      setError("");
      setHasSearched(true);
      try {
        const payload = await api.searchIndex(indexId, q.trim(), searchMode);
        setResults((payload.results as SearchResult[]) || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Search failed");
        setResults([]);
      } finally {
        setSearching(false);
      }
    },
    [],
  );

  // Re-run when index or mode changes if user already searched
  const prevSearchCtx = useRef({ selected: "", mode: "" });
  useEffect(() => {
    const prev = prevSearchCtx.current;
    const ctxChanged = prev.selected !== selected || prev.mode !== mode;
    prevSearchCtx.current = { selected, mode };
    if (ctxChanged && hasSearched && query.trim() && selected) {
      void runSearch(query, selected, mode);
    }
  }, [selected, mode, hasSearched, query, runSearch]);

  useEffect(() => {
    if (view === "search" && selected && !loading) {
      inputRef.current?.focus();
    }
  }, [view, selected, loading]);

  useEffect(() => {
    if (!menuOpen) return;
    const close = () => setMenuOpen(false);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [menuOpen]);

  function onSubmitSearch(e?: FormEvent) {
    e?.preventDefault();
    void runSearch(query, selected, mode);
  }

  function pickSuggestion(s: string) {
    setQuery(s);
    void runSearch(s, selected, mode);
  }

  async function quickCreate() {
    if (!createFolderId) return;
    const folder = folders.find((f) => f.id === createFolderId);
    if (!folder) return;
    setCreating(true);
    setError("");
    try {
      const link = await api.createIndex({
        title: `${folder.name} index`,
        description: `Files in ${folder.path}`,
        folder_id: createFolderId,
      });
      await load();
      setSelected(String(link.id));
      setView("search");
      setQuery("");
      setResults([]);
      setHasSearched(false);
      requestAnimationFrame(() => inputRef.current?.focus());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setCreating(false);
    }
  }

  async function onSync(id: string) {
    setSyncing(id);
    setError("");
    try {
      await api.syncIndex(id);
      await load();
      if (hasSearched && query.trim() && selected === id) {
        void runSearch(query, id, mode);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncing(null);
    }
  }

  async function onDelete(id: string, label: string) {
    if (!confirm(`Delete “${label}”?`)) return;
    setMenuOpen(false);
    try {
      await api.deleteIndex(id);
      if (selected === id) {
        setSelected("");
        setResults([]);
        setHasSearched(false);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  if (loading) {
    return (
      <div className="idx-hub">
        <p className="muted">Loading indexes…</p>
      </div>
    );
  }

  return (
    <div className="idx-hub">
      <div className="idx-hub-top">
        <div>
          <h1 className="page-title">Search</h1>
          <p className="page-sub idx-hub-sub">
            Search indexed vault folders — switch index, type, and go.
          </p>
        </div>
        <div className="idx-segments" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={view === "search"}
            className={view === "search" ? "active" : ""}
            onClick={() => setView("search")}
          >
            Search
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={view === "manage"}
            className={view === "manage" ? "active" : ""}
            onClick={() => setView("manage")}
          >
            Manage{indexes.length ? ` (${indexes.length})` : ""}
          </button>
        </div>
      </div>

      {error && <div className="error idx-error">{error}</div>}

      {view === "search" && (
        <>
          {indexes.length === 0 ? (
            <section className="panel idx-onboard">
              <h2>Index a folder to start searching</h2>
              <p className="muted">
                Pick a vault folder with documents. Indexing usually takes a few seconds.
              </p>
              {can("indexes.create") ? (
                <div className="idx-quick-create">
                  <select
                    value={createFolderId}
                    onChange={(e) => setCreateFolderId(e.target.value)}
                    aria-label="Folder to index"
                  >
                    <option value="" disabled>
                      Choose folder…
                    </option>
                    {folders
                      .filter((f) => f.file_count > 0)
                      .map((f) => (
                        <option key={f.id} value={f.id}>
                          {f.path} ({f.file_count} files)
                        </option>
                      ))}
                  </select>
                  <button
                    className="btn primary"
                    type="button"
                    disabled={creating || !createFolderId}
                    onClick={() => void quickCreate()}
                  >
                    {creating ? "Indexing…" : "Create index & search"}
                  </button>
                </div>
              ) : (
                <p className="muted">Ask an admin to create a search index.</p>
              )}
            </section>
          ) : (
            <>
              <form className="idx-command panel" onSubmit={onSubmitSearch}>
                <div className="idx-command-row">
                  <select
                    className="idx-picker"
                    value={selected}
                    onChange={(e) => setSelected(e.target.value)}
                    aria-label="Search index"
                  >
                    {indexes.map((idx) => (
                      <option key={idx.id} value={idx.id}>
                        {idx.title} ({idx.document_count})
                      </option>
                    ))}
                  </select>
                  <input
                    ref={inputRef}
                    className="idx-query"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search this index…"
                    aria-label="Search query"
                  />
                  <button
                    className="btn primary idx-go"
                    type="submit"
                    disabled={searching || !query.trim() || !selected}
                  >
                    {searching ? "…" : "Search"}
                  </button>
                </div>
                <div className="idx-command-meta">
                  <div className="mode-chips compact" role="group" aria-label="Search mode">
                    {MODES.map((m) => (
                      <button
                        key={m.value}
                        type="button"
                        className={`mode-chip${mode === m.value ? " active" : ""}`}
                        onClick={() => setMode(m.value)}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>
                  {selectedIndex && (
                    <div className="idx-context">
                      <span className="muted">
                        {selectedIndex.folder_path || selectedIndex.folder_name}
                        {" · "}
                        {selectedIndex.document_count} docs
                        {selectedIndex.updated_at && ` · ${relTime(selectedIndex.updated_at)}`}
                      </span>
                      {can("indexes.create") && (
                        <button
                          type="button"
                          className="btn ghost idx-sync-btn"
                          disabled={syncing === selectedIndex.id}
                          onClick={() => void onSync(selectedIndex.id)}
                        >
                          {syncing === selectedIndex.id ? "Syncing…" : "Sync"}
                        </button>
                      )}
                      <div className="idx-menu-wrap">
                        <button
                          type="button"
                          className="btn ghost idx-menu-btn"
                          aria-expanded={menuOpen}
                          onClick={(e) => {
                            e.stopPropagation();
                            setMenuOpen((v) => !v);
                          }}
                        >
                          ⋯
                        </button>
                        {menuOpen && (
                          <div className="idx-menu" onClick={(e) => e.stopPropagation()}>
                            {selectedIndex.integration && (
                              <>
                                <a
                                  href={selectedIndex.integration.admin_search_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  onClick={() => setMenuOpen(false)}
                                >
                                  Open in playground
                                </a>
                                <a
                                  href={selectedIndex.integration.admin_index_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  onClick={() => setMenuOpen(false)}
                                >
                                  Index details
                                </a>
                              </>
                            )}
                            {can("indexes.delete") && (
                              <button
                                type="button"
                                className="danger"
                                onClick={() =>
                                  void onDelete(selectedIndex.id, selectedIndex.title)
                                }
                              >
                                Delete index
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </form>

              {!hasSearched && !searching && (
                <div className="idx-suggestions">
                  <span className="muted">Try:</span>
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      className="idx-suggestion"
                      onClick={() => pickSuggestion(s)}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}

              {searching && (
                <p className="muted idx-status">Searching…</p>
              )}

              {hasSearched && !searching && results.length === 0 && (
                <p className="muted idx-status">
                  No results for “{query}”. Try another term or mode.
                </p>
              )}

              {results.length > 0 && (
                <ul className="idx-results">
                  {results.map((hit) => (
                    <li key={String(hit.id)} className="idx-result">
                      <div className="idx-result-main">
                        <a
                          className="idx-result-title"
                          href={hit.download_url || "#"}
                          onClick={(e) => !hit.download_url && e.preventDefault()}
                        >
                          {hit.name || hit.id}
                        </a>
                        {hit.path && <span className="muted idx-result-path">{hit.path}</span>}
                        {hit.text && (
                          <p className="idx-result-snippet">{snippet(hit.text, query)}</p>
                        )}
                      </div>
                      {hit.score != null && (
                        <span className="idx-result-score">
                          {Math.round(hit.score * 100)}%
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </>
      )}

      {view === "manage" && (
        <section className="panel idx-manage">
          {can("indexes.create") && availableFolders.length > 0 && (
            <div className="idx-manage-create">
              <h3>Add index</h3>
              <div className="idx-quick-create">
                <select
                  value={createFolderId}
                  onChange={(e) => setCreateFolderId(e.target.value)}
                >
                  {availableFolders.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.path} ({f.file_count} files)
                    </option>
                  ))}
                </select>
                <button
                  className="btn primary"
                  type="button"
                  disabled={creating || !createFolderId}
                  onClick={() => void quickCreate()}
                >
                  {creating ? "Creating…" : "Index folder"}
                </button>
              </div>
            </div>
          )}

          <h3>Your indexes</h3>
          {indexes.length === 0 ? (
            <p className="muted">No indexes yet. Add one above or from the Search tab.</p>
          ) : (
            <ul className="idx-manage-list">
              {indexes.map((idx) => {
                const vector = idx.integration?.vector_index?.exists;
                return (
                  <li key={idx.id} className="idx-manage-row">
                    <button
                      type="button"
                      className="idx-manage-info"
                      onClick={() => {
                        setSelected(idx.id);
                        setView("search");
                        requestAnimationFrame(() => inputRef.current?.focus());
                      }}
                    >
                      <strong>{idx.title}</strong>
                      <span className="muted">
                        {idx.folder_path} · {idx.document_count} docs
                        {vector ? " · vector" : " · text only"}
                      </span>
                    </button>
                    <div className="idx-manage-actions">
                      {can("indexes.create") && (
                        <button
                          type="button"
                          className="btn ghost"
                          disabled={syncing === idx.id}
                          onClick={() => void onSync(idx.id)}
                        >
                          {syncing === idx.id ? "…" : "Sync"}
                        </button>
                      )}
                      {can("indexes.delete") && (
                        <button
                          type="button"
                          className="btn danger"
                          onClick={() => void onDelete(idx.id, idx.title)}
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
