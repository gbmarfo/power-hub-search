import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import {
  INDEX_SEARCH_MODES,
  type IndexLink,
  type IndexSearchResult,
} from "./indexTypes";

function snippet(text: string, query: string, max = 200) {
  const clean = text.replace(/\s+/g, " ").trim();
  if (!query.trim()) return clean.slice(0, max) + (clean.length > max ? "…" : "");
  const lower = clean.toLowerCase();
  const q = query.toLowerCase();
  const idx = lower.indexOf(q);
  if (idx === -1) return clean.slice(0, max) + (clean.length > max ? "…" : "");
  const start = Math.max(0, idx - 40);
  const end = Math.min(clean.length, idx + q.length + 80);
  return (start > 0 ? "…" : "") + clean.slice(start, end) + (end < clean.length ? "…" : "");
}

export function IndexPlaygroundPage() {
  const [params, setParams] = useSearchParams();
  const [indexes, setIndexes] = useState<IndexLink[]>([]);
  const [selected, setSelected] = useState(params.get("index") || "");
  const [query, setQuery] = useState(params.get("q") || "");
  const [mode, setMode] = useState(params.get("mode") || "similarity");
  const [topK, setTopK] = useState(Number(params.get("top_k") || 10));
  const [results, setResults] = useState<IndexSearchResult[]>([]);
  const [searchMeta, setSearchMeta] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);

  const selectedIndex = useMemo(
    () => indexes.find((idx) => idx.id === selected) ?? null,
    [indexes, selected],
  );

  useEffect(() => {
    void api
      .indexes()
      .then((list) => {
        const typed = list as IndexLink[];
        setIndexes(typed);
        setSelected((prev) => {
          if (prev && typed.some((i) => i.id === prev)) return prev;
          const fromUrl = params.get("index");
          if (fromUrl && typed.some((i) => i.id === fromUrl)) return fromUrl;
          return typed[0]?.id ?? "";
        });
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load indexes"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const next = new URLSearchParams();
    if (selected) next.set("index", selected);
    if (query) next.set("q", query);
    if (mode !== "similarity") next.set("mode", mode);
    if (topK !== 10) next.set("top_k", String(topK));
    setParams(next, { replace: true });
  }, [selected, query, mode, topK, setParams]);

  async function onSearch(e?: FormEvent) {
    e?.preventDefault();
    if (!selected || !query.trim()) return;
    setSearching(true);
    setError("");
    try {
      const payload = await api.searchIndex(selected, query.trim(), mode, topK);
      setResults((payload.results as IndexSearchResult[]) || []);
      setSearchMeta(payload as Record<string, unknown>);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
      setResults([]);
      setSearchMeta(null);
    } finally {
      setSearching(false);
    }
  }

  // Auto-run when landing with index + query in URL
  useEffect(() => {
    const q = params.get("q");
    const idx = params.get("index");
    if (!loading && idx && q?.trim() && indexes.some((i) => i.id === idx)) {
      void onSearch();
    }
  }, [loading]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div>
        <h1 className="page-title">Search playground</h1>
        <p className="muted">Loading indexes…</p>
      </div>
    );
  }

  return (
    <div className="playground-page">
      <div className="page-head-row">
        <div>
          <h1 className="page-title">Search</h1>
          <p className="page-sub">
            Query indexed vault folders with power-hub-search.
          </p>
        </div>
        <Link className="btn ghost" to="/indexes">
          Indexes
        </Link>
      </div>

      {error && <div className="error">{error}</div>}

      {indexes.length === 0 ? (
        <div className="panel empty">
          <p>No search indexes yet.</p>
          <Link className="btn primary" to="/indexes">
            Create an index
          </Link>
        </div>
      ) : (
        <>
          <form className="panel playground-form" onSubmit={onSearch}>
            <div className="playground-grid">
              <div className="field">
                <label htmlFor="playground-index">Index</label>
                <select
                  id="playground-index"
                  value={selected}
                  onChange={(e) => setSelected(e.target.value)}
                >
                  {indexes.map((idx) => (
                    <option key={idx.id} value={idx.id}>
                      {idx.title} ({idx.document_count} docs)
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="playground-mode">Mode</label>
                <select
                  id="playground-mode"
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                >
                  {INDEX_SEARCH_MODES.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="playground-topk">Top K</label>
                <input
                  id="playground-topk"
                  type="number"
                  min={1}
                  max={50}
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value) || 10)}
                />
              </div>
            </div>

            <div className="field">
              <label htmlFor="playground-query">Query</label>
              <div className="playground-query-row">
                <input
                  id="playground-query"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Enter keywords or a natural-language question…"
                  autoFocus
                />
                <button className="btn primary" type="submit" disabled={searching || !query.trim()}>
                  {searching ? "Searching…" : "Run search"}
                </button>
              </div>
            </div>

            {selectedIndex && (
              <p className="muted playground-context">
                Folder: {selectedIndex.folder_path || selectedIndex.folder_name} ·{" "}
                {selectedIndex.document_count} documents
                {selectedIndex.integration?.embedding_model && (
                  <>
                    {" · "}
                    {selectedIndex.integration.embedding_model.split("/").pop()}
                    {selectedIndex.integration.chunk_size != null && (
                      <> · chunk {selectedIndex.integration.chunk_size}</>
                    )}
                    {selectedIndex.integration.chunk_overlap != null && (
                      <> / overlap {selectedIndex.integration.chunk_overlap}</>
                    )}
                  </>
                )}
                {selectedIndex.integration?.api_search_url && (
                  <>
                    {" · "}
                    <code>{selectedIndex.integration.api_search_url}</code>
                  </>
                )}
              </p>
            )}
          </form>

          {searchMeta && (
            <p className="muted playground-meta">
              {results.length} result{results.length === 1 ? "" : "s"}
              {searchMeta.mode ? ` · ${String(searchMeta.mode)}` : ""}
            </p>
          )}

          {results.length > 0 && (
            <ul className="playground-results">
              {results.map((hit, i) => (
                <li key={String(hit.id)} className="panel playground-hit">
                  <div className="playground-hit-head">
                    <span className="playground-rank">{i + 1}</span>
                    <div>
                      <strong>{hit.name || hit.id}</strong>
                      {hit.path && <div className="muted">{hit.path}</div>}
                    </div>
                    {hit.score != null && (
                      <span className="pill">score {hit.score.toFixed(4)}</span>
                    )}
                  </div>
                  {hit.text && (
                    <p className="muted playground-snippet">{snippet(hit.text, query)}</p>
                  )}
                  {hit.download_url && (
                    <a className="playground-download" href={hit.download_url}>
                      Download file
                    </a>
                  )}
                </li>
              ))}
            </ul>
          )}

          {searchMeta && results.length === 0 && !searching && (
            <div className="panel empty">
              No results for “{query}”. Try another mode or query.
            </div>
          )}
        </>
      )}
    </div>
  );
}
