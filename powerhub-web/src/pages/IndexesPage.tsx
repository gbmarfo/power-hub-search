import { FormEvent, useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

export function IndexesPage() {
  const { can } = useAuth();
  const [indexes, setIndexes] = useState<any[]>([]);
  const [title, setTitle] = useState("Vault documents");
  const [description, setDescription] = useState("Index of Power Hub library for power-hub-search");
  const [query, setQuery] = useState("checklist");
  const [selected, setSelected] = useState<string>("");
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setIndexes(await api.indexes());
  }

  useEffect(() => {
    void load().catch((e) => setError(e.message));
  }, []);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const link = await api.createIndex({ title, description, folder_id: null });
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
    setResults(await api.searchIndex(selected, query, "full_text"));
  }

  return (
    <div>
      <h1 className="page-title">Search Indexes</h1>
      <p className="page-sub">
        Create indexes from vault documents that integrate with power-hub-search (BM25 + Milvus).
      </p>

      {can("indexes.create") && (
        <form className="panel" onSubmit={onCreate}>
          <h3>Create index from vault</h3>
          <div className="field">
            <label>Title</label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} required />
          </div>
          <div className="field">
            <label>Description</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
          </div>
          {error && <div className="error">{error}</div>}
          <button className="btn primary" disabled={busy}>
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
              <th>Search index ID</th>
              <th>Documents</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {indexes.map((idx) => (
              <tr key={idx.id}>
                <td>
                  <strong>{idx.title}</strong>
                  <div className="muted">{idx.description}</div>
                </td>
                <td className="mono muted">{idx.search_index_id}</td>
                <td>{idx.document_count}</td>
                <td className="actions">
                  <button className="btn" type="button" onClick={() => setSelected(idx.id)}>
                    Use
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
                <td colSpan={4} className="empty">No indexes yet. Create one from your vault files.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selected && (
        <form className="panel" style={{ marginTop: 16 }} onSubmit={onSearch}>
          <h3>Query via power-hub-search</h3>
          <p className="muted">Selected link: {selected}</p>
          <div className="field">
            <label>Query</label>
            <input value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
          <button className="btn primary">Search</button>
          {results && (
            <pre style={{ marginTop: 14, whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
              {JSON.stringify(results, null, 2)}
            </pre>
          )}
        </form>
      )}
    </div>
  );
}
