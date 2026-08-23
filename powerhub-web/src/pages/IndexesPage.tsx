import { FormEvent, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

type FolderOption = {
  id: string;
  name: string;
  path: string;
  file_count: number;
};

export function IndexesPage() {
  const { can } = useAuth();
  const [indexes, setIndexes] = useState<any[]>([]);
  const [folders, setFolders] = useState<FolderOption[]>([]);
  const [folderId, setFolderId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [query, setQuery] = useState("checklist");
  const [selected, setSelected] = useState<string>("");
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const selectedFolder = useMemo(
    () => folders.find((f) => f.id === folderId) || null,
    [folders, folderId],
  );

  async function load() {
    const [list, folderList] = await Promise.all([
      api.indexes(),
      api.foldersForIndex(),
    ]);
    setIndexes(list);
    setFolders(folderList as FolderOption[]);
    if (!selected && list.length) {
      setSelected(String(list[0].id));
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

  async function onSearch(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setResults(await api.searchIndex(selected, query, "similarity"));
  }

  return (
    <div>
      <h1 className="page-title">Search Indexes</h1>
      <p className="page-sub">
        Create a power-hub-search index from a specific vault folder (includes files in subfolders).
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
            {!folders.length && (
              <span className="muted">No folders yet. Create a folder and upload files first.</span>
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
              <th>Search index ID</th>
              <th>Documents</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {indexes.map((idx) => (
              <tr key={idx.id} className={selected === idx.id ? "list-row" : undefined}>
                <td>
                  <strong>{idx.title}</strong>
                  <div className="muted">{idx.description}</div>
                </td>
                <td>
                  <span className="pill">{idx.folder_path || idx.folder_name || "—"}</span>
                </td>
                <td className="mono muted">{idx.search_index_id}</td>
                <td>{idx.document_count}</td>
                <td className="actions">
                  <button
                    className={`btn ${selected === idx.id ? "primary" : ""}`}
                    type="button"
                    onClick={() => setSelected(String(idx.id))}
                  >
                    {selected === idx.id ? "Selected" : "Use for search"}
                  </button>
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
            ))}
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
        {!selected ? (
          <p className="muted">Select an index with “Use for search”, or create one above.</p>
        ) : (
          <p className="muted">Selected link: {selected}</p>
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
        <button className="btn primary" disabled={!selected}>
          Search
        </button>
        {results && (
          <pre style={{ marginTop: 14, whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
            {JSON.stringify(results, null, 2)}
          </pre>
        )}
      </form>
    </div>
  );
}
