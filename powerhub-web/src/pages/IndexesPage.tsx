import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { FolderOption, IndexLink } from "./indexTypes";

function formatUpdated(value?: string) {
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

export function IndexesPage() {
  const { can } = useAuth();
  const [indexes, setIndexes] = useState<IndexLink[]>([]);
  const [folders, setFolders] = useState<FolderOption[]>([]);
  const [folderId, setFolderId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const selectedFolder = useMemo(
    () => folders.find((f) => f.id === folderId) || null,
    [folders, folderId],
  );

  const indexedFolderIds = useMemo(
    () => new Set(indexes.map((idx) => idx.folder_id).filter(Boolean)),
    [indexes],
  );

  async function load() {
    setLoading(true);
    try {
      const [list, folderList] = await Promise.all([
        api.indexes(),
        api.foldersForIndex(),
      ]);
      setIndexes(list as IndexLink[]);
      setFolders(folderList as FolderOption[]);
      setError("");
      const indexed = new Set((list as IndexLink[]).map((i) => i.folder_id).filter(Boolean));
      if (!folderId && folderList.length) {
        const available = (folderList as FolderOption[]).find(
          (f) => f.file_count > 0 && !indexed.has(f.id),
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
      await api.createIndex({
        title: title || `${selectedFolder?.name || "Folder"} index`,
        description,
        folder_id: folderId,
      });
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

  async function onDelete(linkId: string, label: string) {
    if (!confirm(`Delete “${label}”? This removes the search index.`)) return;
    setError("");
    try {
      await api.deleteIndex(linkId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  if (loading) {
    return (
      <div>
        <h1 className="page-title">Manage indexes</h1>
        <p className="muted">Loading…</p>
      </div>
    );
  }

  return (
    <div>
      <div className="page-head-row">
        <div>
          <h1 className="page-title">Manage indexes</h1>
          <p className="page-sub">
            Create and maintain vault search indexes registered in power-hub-search.
          </p>
        </div>
        <Link className="btn primary" to="/indexes/playground">
          Open search playground
        </Link>
      </div>

      {error && <div className="error">{error}</div>}

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
              {folders.map((folder) => {
                const indexed = indexedFolderIds.has(folder.id);
                return (
                  <option
                    key={folder.id}
                    value={folder.id}
                    disabled={folder.file_count === 0 || indexed}
                  >
                    {folder.path} ({folder.file_count} file{folder.file_count === 1 ? "" : "s"})
                    {indexed ? " · already indexed" : ""}
                  </option>
                );
              })}
            </select>
            {selectedFolder && (
              <span className="muted">
                Indexing {selectedFolder.file_count} file
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
              <th>Status</th>
              <th>Documents</th>
              <th>Updated</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {indexes.map((idx) => {
              const integration = idx.integration;
              const vectorOk = integration?.vector_index?.exists;
              return (
                <tr key={idx.id}>
                  <td>
                    <strong>{idx.title}</strong>
                    {idx.description && <div className="muted">{idx.description}</div>}
                  </td>
                  <td>
                    <span className="pill">{idx.folder_path || idx.folder_name || "—"}</span>
                  </td>
                  <td>
                    <span className="pill">
                      {integration?.registered ? "Registered" : "Missing"}
                    </span>
                    <div className="muted" style={{ fontSize: "0.8rem", marginTop: 4 }}>
                      Text: {integration?.text_index_ready ? "ready" : "—"} · Vector:{" "}
                      {vectorOk ? `${integration?.vector_index?.num_entities ?? 0} docs` : "text only"}
                    </div>
                  </td>
                  <td>{idx.document_count}</td>
                  <td className="muted">{formatUpdated(idx.updated_at)}</td>
                  <td className="actions">
                    <Link
                      className="btn primary"
                      to={`/indexes/playground?index=${encodeURIComponent(idx.id)}`}
                    >
                      Search
                    </Link>
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
                        onClick={() => void onDelete(idx.id, idx.title)}
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
                <td colSpan={6} className="empty">
                  No indexes yet. Create one above, then try the{" "}
                  <Link to="/indexes/playground">search playground</Link>.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
