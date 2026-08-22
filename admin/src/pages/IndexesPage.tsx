import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { SearchIndex } from "../types";
import { Card, ErrorBanner, PageHeader } from "../components/ui";

const DEFAULT_ORG = localStorage.getItem("admin_org_id") ?? "";

export function IndexesPage() {
  const [orgId, setOrgId] = useState(DEFAULT_ORG);
  const [indexes, setIndexes] = useState<SearchIndex[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    title: "",
    description: "",
    table_name: "",
    text_columns: "",
    id_col: "",
    schema_name: "dbo",
    org_id: DEFAULT_ORG,
    source: "sql",
  });
  const [creating, setCreating] = useState(false);

  async function loadIndexes(targetOrg = orgId) {
    if (!targetOrg) return;
    setLoading(true);
    setError("");
    try {
      const data = await api.listIndexes(targetOrg);
      setIndexes(data.results);
      localStorage.setItem("admin_org_id", targetOrg);
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadIndexes();
  }, []);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setCreating(true);
    setError("");
    try {
      await api.createIndex(form);
      setShowCreate(false);
      setOrgId(form.org_id);
      await loadIndexes(form.org_id);
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(indexId: string) {
    if (!confirm("Delete this index and its Milvus collection?")) return;
    setError("");
    try {
      await api.deleteIndex(indexId);
      await loadIndexes();
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  return (
    <div>
      <PageHeader
        title="Indexes"
        description="Create and manage search indexes backed by Milvus."
        action={
          <button className="btn btn-primary" onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? "Cancel" : "Create index"}
          </button>
        }
      />

      {error ? <ErrorBanner message={error} /> : null}

      {showCreate ? (
        <Card title="New index" className="mb">
          <form className="form-grid" onSubmit={handleCreate}>
            <label>
              Title
              <input
                required
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </label>
            <label>
              Organization ID
              <input
                required
                value={form.org_id}
                onChange={(e) => setForm({ ...form, org_id: e.target.value })}
              />
            </label>
            <label>
              Schema
              <input
                required
                value={form.schema_name}
                onChange={(e) => setForm({ ...form, schema_name: e.target.value })}
              />
            </label>
            <label>
              Table name
              <input
                required
                value={form.table_name}
                onChange={(e) => setForm({ ...form, table_name: e.target.value })}
              />
            </label>
            <label>
              ID column
              <input
                required
                value={form.id_col}
                onChange={(e) => setForm({ ...form, id_col: e.target.value })}
              />
            </label>
            <label>
              Text columns (comma-separated)
              <input
                required
                value={form.text_columns}
                onChange={(e) => setForm({ ...form, text_columns: e.target.value })}
                placeholder="title,body"
              />
            </label>
            <label className="full-width">
              Description
              <textarea
                rows={3}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </label>
            <div className="full-width">
              <button className="btn btn-primary" disabled={creating}>
                {creating ? "Creating..." : "Create index"}
              </button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card>
        <div className="toolbar">
          <label>
            Org ID
            <input value={orgId} onChange={(e) => setOrgId(e.target.value)} />
          </label>
          <button className="btn" onClick={() => void loadIndexes()} disabled={loading}>
            Refresh
          </button>
        </div>

        {loading ? (
          <p className="muted">Loading indexes...</p>
        ) : indexes.length === 0 ? (
          <p className="muted">No indexes for this organization.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Source table</th>
                <th>Columns</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {indexes.map((index) => (
                <tr key={index.global_id}>
                  <td>
                    <strong>{index.title}</strong>
                    <p className="muted small">{index.description}</p>
                  </td>
                  <td>
                    <code>
                      {index.schema_name}.{index.table_name}
                    </code>
                  </td>
                  <td>
                    <code>{index.text_columns}</code>
                  </td>
                  <td className="actions">
                    <Link to={`/indexes/${index.global_id}`} className="link">
                      Details
                    </Link>
                    <Link
                      to={`/search?index=${index.global_id}&org=${index.org_id ?? ""}`}
                      className="link"
                    >
                      Search
                    </Link>
                    <button
                      className="btn btn-danger btn-small"
                      onClick={() => void handleDelete(index.global_id)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
