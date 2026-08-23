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
};

const SEARCH_MODES = [
  { value: "similarity", label: "Similarity (vector)" },
  { value: "full_text", label: "Full text (BM25)" },
  { value: "hybrid", label: "Hybrid" },
  { value: "ranked_naive", label: "Ranked naive" },
];

export function IndexesPage() {
  const { can } = useAuth();
  const [indexes, setIndexes] = useState<IndexLink[]>([]);
  const [folders, setFolders] = useState<FolderOption[]>([]);
  const [folderId, setFolderId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [query, setQuery] = useState("checklist");
  const [mode, setMode] = useState("similarity");
  const [selected, setSelected] = useState<string>("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searchMeta, setSearchMeta] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [syncing, setSyncing] = useState<string | null>(null);

  const selectedFolder = useMemo(
    () => folders.find((f) => f.id === folderId) || null,
    [folders, folderId],
  );

  const selectedIndex = useMemo(
    () => indexes.find((idx) => idx.id === selected) || null,
    [indexes, selected],
  );

  async function load() {
    const [list, folderList] = await Promise.all([
      api.indexes(),
      api.foldersForIndex(),
    ]);
    setIndexes(list as IndexLink[]);
    setFolders(folderList as FolderOption[]);
    if (!selected && list.length) {
      setSelected(String((list[0] as IndexLink).id));
    }
    if (!folderId && folderList.length) {
      const withFiles = (folderList as FolderOption[]).find((f) => f.file_count > 0);
      setFolderId((withFiles || folderList[0]).id as string);
    }
  }

  useEffect(() => {
    void load().catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!selectedFolder) return;
    setTitle((prev) => (prev.trim() ? prev : `${selectedFolder.name} index`));
    setDescription((prev) =>
      prev.trim()
        ? prev
        : `Search index for files in ${selectedFolder.path} (${selectedFolder.file_count} documents)`,
    );
  }, [selectedFolder]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!folderId) {
      setError("Select a folder to index.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const link = await api.createIndex({
        title: title || `${selectedFolder?.name || "Folder"} index`,
        description,
        folder_id: folderId,
      });
      setSelected(String(link.id));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
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

  async function onSearch(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setError("");
    const payload = await api.searchIndex(selected, query, mode);
    setResults((payload.results as SearchResult[]) || []);
    setSearchMeta(payload as Record<string, unknown>);
  }

  return (
    <div>
      <h1 className="page-title">Search Indexes</h1>
      <p className="page-sub">
        Vault indexes are registered in power-hub-search and searchable via the unified search API.
      </p>

      {can("indexes.create") && (
        <form className="panel" onSubmit={onCreate}>
          <h3>Create index from folder</h3>
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
              {folders.map((folder) => (
                <option key={folder.id} value={folder.id} disabled={folder.file_count === 0}>
                  {folder.path} ({folder.file_count} file{folder.file_count === 1 ? "" : "s"})
                </option>
              ))}
            </select>
            {selectedFolder && (
              <span className="muted">
                Indexing {selectedFolder.file_count} file
                {selectedFolder.file_count === 1 ? "" : "s"} under {selectedFolder.path}
              </span>
            )}
          </div>
          <div className="field">
            <label>Title</label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} required />
          </div>
          <div className="field">
            <label>Description</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
          </div>
          {error && <div className="error">{error}</div>}
          <button
            className="btn primary"
            disabled={busy || !folderId || (selectedFolder?.file_count ?? 0) === 0}
          >
            {busy ? "Indexing…" : "Create search index"}
          </button>
        </form>
      )}

      <div className="panel" style={{ marginTop: 16 }}>
        <h3>Your indexes</h3>
        <table className="table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Source folder</th>
              <th>Integration</th>
              <th>Documents</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {indexes.map((idx) => {
              const integration = idx.integration;
              const vectorOk = integration?.vector_index?.exists;
              return (
                <tr key={idx.id} className={selected === idx.id ? "list-row" : undefined}>
                  <td>
                    <strong>{idx.title}</strong>
                    <div className="muted">{idx.description}</div>
                    <div className="mono muted" style={{ fontSize: "0.75rem" }}>
                      {idx.search_index_id}
                    </div>
                  </td>
                  <td>
                    <span className="pill">{idx.folder_path || idx.folder_name || "—"}</span>
                  </td>
                  <td>
                    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                      <span className="pill">
                        {integration?.registered ? "Registered" : "Missing"}
                      </span>
                      <span className="muted" style={{ fontSize: "0.8rem" }}>
                        Text: {integration?.text_index_ready ? "ready" : "—"} · Vector:{" "}
                        {vectorOk ? `${integration?.vector_index?.num_entities ?? 0} docs` : "text only"}
                      </span>
                      {integration && (
                        <span style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                          <a href={integration.admin_index_url} target="_blank" rel="noreferrer">
                            Admin detail
                          </a>
                          <a href={integration.admin_search_url} target="_blank" rel="noreferrer">
                            Search playground
                          </a>
                        </span>
                      )}
                    </div>
                  </td>
                  <td>{idx.document_count}</td>
                  <td className="actions">
                    <button
                      className={`btn ${selected === idx.id ? "primary" : ""}`}
                      type="button"
                      onClick={() => setSelected(String(idx.id))}
                    >
                      {selected === idx.id ? "Selected" : "Search"}
                    </button>
                    {can("indexes.create") && (
                      <button
                        className="btn"
                        type="button"
                        disabled={syncing === idx.id}
                        onClick={() => void onSync(idx.id)}
                      >
                        {syncing === idx.id ? "Syncing…" : "Sync"}
                      </button>
                    )}
                    {can("indexes.delete") && (
                      <button
                        className="btn danger"
                        type="button"
                        onClick={() => void api.deleteIndex(idx.id).then(load)}
                      >
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
            {!indexes.length && (
              <tr>
                <td colSpan={5} className="empty">
                  No indexes yet. Choose a folder above and create one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <form className="panel" style={{ marginTop: 16 }} onSubmit={onSearch} id="index-search-panel">
        <h3>Query via power-hub-search</h3>
        {!selectedIndex ? (
          <p className="muted">Select an index with “Search”, or create one above.</p>
        ) : (
          <p className="muted">
            Index <strong>{selectedIndex.title}</strong> · API{" "}
            <code>{selectedIndex.integration?.api_search_url}</code>
          </p>
        )}
        <div className="field">
          <label>Query</label>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={!selected}
            placeholder={selected ? "Search indexed documents…" : "Select an index first"}
          />
        </div>
        <div className="field">
          <label>Search mode</label>
          <select value={mode} onChange={(e) => setMode(e.target.value)} disabled={!selected}>
            {SEARCH_MODES.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
        <button className="btn primary" disabled={!selected}>
          Search
        </button>

        {results.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <p className="muted">
              {results.length} result{results.length === 1 ? "" : "s"}
              {searchMeta?.mode ? ` · mode: ${String(searchMeta.mode)}` : ""}
            </p>
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {results.map((hit) => (
                <li
                  key={String(hit.id)}
                  style={{
                    padding: "10px 0",
                    borderBottom: "1px solid var(--border, #e5e7eb)",
                  }}
                >
                  <strong>{hit.name || hit.id}</strong>
                  {hit.path && <span className="muted"> · {hit.path}</span>}
                  {hit.score != null && (
                    <span className="muted"> · score {hit.score.toFixed(3)}</span>
                  )}
                  {hit.download_url && (
                    <>
                      {" "}
                      <a href={hit.download_url}>Download</a>
                    </>
                  )}
                  {hit.text && (
                    <div className="muted" style={{ fontSize: "0.85rem", marginTop: 4 }}>
                      {(hit.text || "").slice(0, 200)}
                      {(hit.text || "").length > 200 ? "…" : ""}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </form>
    </div>
  );
}
