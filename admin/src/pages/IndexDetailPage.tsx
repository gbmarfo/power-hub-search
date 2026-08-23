import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { IndexDetailResponse } from "../types";
import { Card, ErrorBanner, PageHeader, StatusBadge } from "../components/ui";

export function IndexDetailPage() {
  const { indexId = "" } = useParams();
  const [detail, setDetail] = useState<IndexDetailResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!indexId) return;
    void api
      .getIndex(indexId)
      .then(setDetail)
      .catch((err) => setError(String(err.message ?? err)));
  }, [indexId]);

  const index = detail?.index;
  const stats = detail?.vector_stats;

  return (
    <div>
      <PageHeader
        title={index?.title ?? "Index details"}
        description={index?.description ?? "Milvus collection and source metadata."}
        action={
          index ? (
            <Link
              className="btn btn-primary"
              to={`/search?index=${index.global_id}&org=${index.org_id ?? ""}`}
            >
              Open in playground
            </Link>
          ) : null
        }
      />

      {error ? <ErrorBanner message={error} /> : null}

      {!index ? (
        <p className="muted">Loading index...</p>
      ) : (
        <div className="grid-2">
          <Card title="Metadata">
            <dl className="detail-list">
              <dt>Global ID</dt>
              <dd><code>{index.global_id}</code></dd>
              <dt>Organization</dt>
              <dd><code>{index.org_id}</code></dd>
              <dt>Source</dt>
              <dd><code>{index.source ?? "sql"}</code></dd>
              <dt>Source table</dt>
              <dd>
                <code>
                  {index.source === "powerhub"
                    ? index.table_name
                    : `${index.schema_name ?? "dbo"}.${index.table_name}`}
                </code>
              </dd>
              <dt>ID column</dt>
              <dd><code>{index.id_col}</code></dd>
              <dt>Text columns</dt>
              <dd><code>{index.text_columns}</code></dd>
            </dl>
          </Card>

          <Card title="Milvus vector store">
            <div className="stat-row">
              <span>Collection exists</span>
              <StatusBadge
                status={stats?.exists ? "ok" : "error"}
                label={stats?.exists ? "yes" : "no"}
              />
            </div>
            <div className="stat-row">
              <span>Collection name</span>
              <code>{stats?.collection ?? "—"}</code>
            </div>
            <div className="stat-row">
              <span>Entities</span>
              <strong>{stats?.num_entities ?? 0}</strong>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
