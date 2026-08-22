import { FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { SearchIndex, SearchMode, SearchResult } from "../types";
import { Card, ErrorBanner, PageHeader } from "../components/ui";

const MODES: { value: SearchMode; label: string }[] = [
  { value: "similarity", label: "Vector similarity" },
  { value: "hybrid", label: "Hybrid (BM25 + vector)" },
  { value: "full_text", label: "BM25 full text" },
  { value: "ranked_naive", label: "TF-IDF" },
  { value: "boolean_ranked", label: "Boolean + TF-IDF" },
  { value: "exact", label: "Exact boolean" },
  { value: "exact_similarity", label: "Boolean + vector rerank" },
  { value: "fuzzy", label: "Fuzzy" },
];

const DEFAULT_ORG = localStorage.getItem("admin_org_id") ?? "";

export function SearchPlaygroundPage() {
  const [params] = useSearchParams();
  const [orgId, setOrgId] = useState(params.get("org") ?? DEFAULT_ORG);
  const [indexes, setIndexes] = useState<SearchIndex[]>([]);
  const [indexId, setIndexId] = useState(params.get("index") ?? "");
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("similarity");
  const [topK, setTopK] = useState(10);
  const [vectorWeight, setVectorWeight] = useState(0.5);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [meta, setMeta] = useState("");
  const [error, setError] = useState("");
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (!orgId) return;
    void api.listIndexes(orgId).then((data) => {
      setIndexes(data.results);
      if (!indexId && data.results[0]) {
        setIndexId(data.results[0].global_id);
      }
    });
  }, [orgId, indexId]);

  const selectedIndex = useMemo(
    () => indexes.find((item) => item.global_id === indexId),
    [indexes, indexId],
  );

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    if (!indexId || !query.trim()) return;
    setSearching(true);
    setError("");
    try {
      const response = await api.search(indexId, {
        query,
        mode,
        top_k: topK,
        org_id: orgId || selectedIndex?.org_id,
        vector_weight: vectorWeight,
      });
      setResults(response.results);
      setMeta(`${response.total_returned} results · mode ${response.mode}`);
    } catch (err) {
      setError(String((err as Error).message));
      setResults([]);
      setMeta("");
    } finally {
      setSearching(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Search playground"
        description="Test enterprise search modes against live indexes."
      />

      {error ? <ErrorBanner message={error} /> : null}

      <Card>
        <form className="form-grid" onSubmit={handleSearch}>
          <label>
            Organization ID
            <input value={orgId} onChange={(e) => setOrgId(e.target.value)} />
          </label>
          <label>
            Index
            <select
              value={indexId}
              onChange={(e) => setIndexId(e.target.value)}
              required
            >
              <option value="">Select index</option>
              {indexes.map((index) => (
                <option key={index.global_id} value={index.global_id}>
                  {index.title ?? index.global_id}
                </option>
              ))}
            </select>
          </label>
          <label>
            Mode
            <select value={mode} onChange={(e) => setMode(e.target.value as SearchMode)}>
              {MODES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Top K
            <input
              type="number"
              min={1}
              max={100}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
            />
          </label>
          {mode === "hybrid" ? (
            <label>
              Vector weight
              <input
                type="number"
                min={0}
                max={1}
                step={0.1}
                value={vectorWeight}
                onChange={(e) => setVectorWeight(Number(e.target.value))}
              />
            </label>
          ) : null}
          <label className="full-width">
            Query
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter search query"
              required
            />
          </label>
          <div className="full-width">
            <button className="btn btn-primary" disabled={searching}>
              {searching ? "Searching..." : "Run search"}
            </button>
          </div>
        </form>
      </Card>

      <Card title="Results" className="mt">
        {meta ? <p className="muted">{meta}</p> : null}
        {results.length === 0 ? (
          <p className="muted">Run a query to see results.</p>
        ) : (
          <div className="results-list">
            {results.map((result, index) => (
              <article key={`${result.id}-${index}`} className="result-item">
                <div className="result-meta">
                  <code>#{result.id}</code>
                  {typeof result.score === "number" ? (
                    <span className="score">{result.score.toFixed(4)}</span>
                  ) : null}
                </div>
                <p>{result.text}</p>
              </article>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
