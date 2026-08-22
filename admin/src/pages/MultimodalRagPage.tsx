import { FormEvent, useEffect, useState } from "react";
import { api } from "../api/client";
import type { MultimodalRerankResponse, MultimodalStatus } from "../types";
import { Card, ErrorBanner, PageHeader, StatusBadge } from "../components/ui";

const DEFAULT_ORG = localStorage.getItem("admin_org_id") ?? "";

export function MultimodalRagPage() {
  const [status, setStatus] = useState<MultimodalStatus | null>(null);
  const [orgId, setOrgId] = useState(DEFAULT_ORG);
  const [indexId, setIndexId] = useState("");
  const [title, setTitle] = useState("Multimodal catalog");
  const [queryText, setQueryText] = useState("phone case with this image theme");
  const [queryImage, setQueryImage] = useState<File | null>(null);
  const [uploadFiles, setUploadFiles] = useState<FileList | null>(null);
  const [directoryPath, setDirectoryPath] = useState("./images_folder/images");
  const [results, setResults] = useState<Record<string, unknown>[]>([]);
  const [rerank, setRerank] = useState<MultimodalRerankResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    void api.multimodalStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  async function handleCreateIndex(event: FormEvent) {
    event.preventDefault();
    setBusy("Creating index...");
    setError("");
    try {
      const response = await api.createMultimodalIndex({
        title,
        org_id: orgId,
        description: "Multimodal RAG image index",
      });
      setIndexId(response.id);
      localStorage.setItem("admin_org_id", orgId);
      setBusy("");
    } catch (err) {
      setError(String((err as Error).message));
      setBusy("");
    }
  }

  async function handleUpload(event: FormEvent) {
    event.preventDefault();
    if (!indexId || !uploadFiles?.length) return;
    setBusy("Indexing images...");
    setError("");
    try {
      await api.uploadMultimodalImages(indexId, Array.from(uploadFiles), orgId);
      setBusy("");
    } catch (err) {
      setError(String((err as Error).message));
      setBusy("");
    }
  }

  async function handleDirectoryIndex(event: FormEvent) {
    event.preventDefault();
    if (!indexId || !directoryPath) return;
    setBusy("Indexing directory...");
    setError("");
    try {
      await api.indexMultimodalDirectory(indexId, directoryPath, "*.jpg", orgId);
      setBusy("");
    } catch (err) {
      setError(String((err as Error).message));
      setBusy("");
    }
  }

  async function handleSearch(useRerank: boolean) {
    if (!indexId) return;
    setBusy(useRerank ? "Searching with rerank..." : "Searching...");
    setError("");
    setRerank(null);
    setResults([]);
    try {
      if (useRerank) {
        if (!queryImage) {
          throw new Error("Generative rerank requires a query image");
        }
        const response = await api.multimodalSearchRerank(
          indexId,
          queryText,
          queryImage,
          9,
          orgId,
        );
        setRerank(response);
        setResults(response.reranked_results);
      } else {
        const response = await api.multimodalSearch(
          indexId,
          queryText,
          queryImage,
          9,
          orgId,
        );
        setResults(response.results);
      }
      setBusy("");
    } catch (err) {
      setError(String((err as Error).message));
      setBusy("");
    }
  }

  return (
    <div>
      <PageHeader
        title="Multimodal RAG"
        description="Composed image+text retrieval with Milvus and optional GPT-4o reranking."
      />

      {error ? <ErrorBanner message={error} /> : null}
      {busy ? <p className="muted">{busy}</p> : null}

      <div className="grid-2">
        <Card title="Capabilities">
          <div className="stat-row">
            <span>Multimodal enabled</span>
            <StatusBadge
              status={status?.enabled ? "ok" : "error"}
              label={status?.enabled ? "yes" : "no"}
            />
          </div>
          <div className="stat-row">
            <span>Encoder</span>
            <StatusBadge
              status={status?.encoder?.available ? "ok" : "degraded"}
              label={status?.encoder?.backend ?? "unavailable"}
            />
          </div>
          <div className="stat-row">
            <span>GPT reranker</span>
            <StatusBadge
              status={status?.reranker_configured ? "ok" : "neutral"}
              label={status?.reranker_configured ? "configured" : "not set"}
            />
          </div>
          <div className="stat-row">
            <span>Metric</span>
            <code>{status?.metric_type ?? "COSINE"}</code>
          </div>
        </Card>

        <Card title="Create multimodal index">
          <form className="form-grid" onSubmit={handleCreateIndex}>
            <label>
              Title
              <input value={title} onChange={(e) => setTitle(e.target.value)} required />
            </label>
            <label>
              Organization ID
              <input value={orgId} onChange={(e) => setOrgId(e.target.value)} required />
            </label>
            <div className="full-width">
              <button className="btn btn-primary">Create index</button>
            </div>
          </form>
          {indexId ? (
            <p className="muted small">
              Active index: <code>{indexId}</code>
            </p>
          ) : null}
        </Card>
      </div>

      <Card title="Index images" className="mt">
        <form className="form-grid" onSubmit={handleUpload}>
          <label>
            Index ID
            <input value={indexId} onChange={(e) => setIndexId(e.target.value)} required />
          </label>
          <label>
            Upload images
            <input
              type="file"
              accept="image/*"
              multiple
              onChange={(e) => setUploadFiles(e.target.files)}
            />
          </label>
          <div className="full-width">
            <button className="btn">Upload & index</button>
          </div>
        </form>

        <form className="form-grid mt" onSubmit={handleDirectoryIndex}>
          <label className="full-width">
            Server directory path (batch index, e.g. Milvus tutorial dataset)
            <input
              value={directoryPath}
              onChange={(e) => setDirectoryPath(e.target.value)}
              placeholder="./images_folder/images"
            />
          </label>
          <div className="full-width">
            <button className="btn">Index directory</button>
          </div>
        </form>
      </Card>

      <Card title="Composed search" className="mt">
        <div className="form-grid">
          <label className="full-width">
            Instruction text
            <input
              value={queryText}
              onChange={(e) => setQueryText(e.target.value)}
              placeholder="phone case with this image theme"
            />
          </label>
          <label>
            Query image
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setQueryImage(e.target.files?.[0] ?? null)}
            />
          </label>
          <div className="actions">
            <button className="btn btn-primary" onClick={() => void handleSearch(false)}>
              Search
            </button>
            <button className="btn" onClick={() => void handleSearch(true)}>
              Search + GPT rerank
            </button>
          </div>
        </div>

        {rerank?.panoramic_url ? (
          <div className="mt">
            <p className="muted">Panoramic rerank view</p>
            <img
              className="preview-image"
              src={rerank.panoramic_url}
              alt="Panoramic rerank comparison"
            />
            <p>{rerank.explanation}</p>
          </div>
        ) : null}

        <div className="results-grid mt">
          {results.map((item, index) => (
            <article key={`${item.id}-${index}`} className="result-card">
              {item.image_url ? (
                <img
                  className="preview-image"
                  src={String(item.image_url)}
                  alt={String(item.caption ?? item.id)}
                />
              ) : null}
              <div className="result-meta">
                <code>#{String(item.id)}</code>
                {typeof item.score === "number" ? (
                  <span className="score">{item.score.toFixed(4)}</span>
                ) : null}
              </div>
              <p>{String(item.caption ?? "")}</p>
            </article>
          ))}
        </div>
      </Card>
    </div>
  );
}
