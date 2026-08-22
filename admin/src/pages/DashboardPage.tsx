import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { HealthResponse, SearchIndex } from "../types";
import { Card, PageHeader, StatusBadge } from "../components/ui";

const DEFAULT_ORG = localStorage.getItem("admin_org_id") ?? "";

export function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [indexes, setIndexes] = useState<SearchIndex[]>([]);
  const [orgId, setOrgId] = useState(DEFAULT_ORG);
  const [error, setError] = useState("");

  useEffect(() => {
    void api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    if (!orgId) return;
    localStorage.setItem("admin_org_id", orgId);
    void api
      .listIndexes(orgId)
      .then((data) => setIndexes(data.results))
      .catch((err) => setError(String(err.message ?? err)));
  }, [orgId]);

  const milvusStatus =
    health?.milvus.status === "ok"
      ? "ok"
      : health?.milvus.status === "error"
        ? "error"
        : "degraded";

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="System health and recent index activity."
      />

      <div className="grid-2">
        <Card title="Service health">
          <div className="stat-row">
            <span>API</span>
            <StatusBadge
              status={health?.status === "ok" ? "ok" : "degraded"}
              label={health?.status ?? "unknown"}
            />
          </div>
          <div className="stat-row">
            <span>Milvus</span>
            <StatusBadge status={milvusStatus} label={health?.milvus.status ?? "unknown"} />
          </div>
          <div className="stat-row">
            <span>Version</span>
            <code>{health?.version ?? "—"}</code>
          </div>
          {health?.milvus.version ? (
            <div className="stat-row">
              <span>Milvus version</span>
              <code>{health.milvus.version}</code>
            </div>
          ) : null}
        </Card>

        <Card title="Organization scope">
          <label className="field-label">
            Org ID for index queries
            <input
              value={orgId}
              onChange={(e) => setOrgId(e.target.value)}
              placeholder="org-uuid or tenant id"
            />
          </label>
          <p className="muted">
            Indexes are listed per organization. Set this to match your tenant.
          </p>
        </Card>
      </div>

      <Card title="Indexes" className="mt">
        {error ? <p className="error-text">{error}</p> : null}
        {!orgId ? (
          <p className="muted">Enter an organization ID to load indexes.</p>
        ) : indexes.length === 0 ? (
          <p className="muted">No indexes found for this organization.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Table</th>
                <th>ID</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {indexes.map((index) => (
                <tr key={index.global_id}>
                  <td>{index.title ?? "Untitled"}</td>
                  <td>
                    <code>
                      {index.schema_name}.{index.table_name}
                    </code>
                  </td>
                  <td>
                    <code className="truncate">{index.global_id}</code>
                  </td>
                  <td>
                    <Link className="link" to={`/indexes/${index.global_id}`}>
                      View
                    </Link>
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
