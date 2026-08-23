import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

export function DashboardPage() {
  const { can } = useAuth();
  const [data, setData] = useState<Record<string, any> | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    void api
      .dashboard()
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="error">{error}</div>;
  if (!data) return <div className="muted">Loading dashboard…</div>;

  const stats = data.stats || {};

  return (
    <div>
      <h1 className="page-title">Home</h1>
      <p className="page-sub">Your vault snapshot — continue working, team activity, and quick stats.</p>

      <div className="grid-stats">
        <div className="stat"><span className="muted">Files</span><strong>{stats.files}</strong></div>
        <div className="stat"><span className="muted">Folders</span><strong>{stats.folders}</strong></div>
        <div className="stat"><span className="muted">Shares</span><strong>{stats.shares}</strong></div>
        <div className="stat"><span className="muted">Active users</span><strong>{stats.users}</strong></div>
      </div>

      <div className="dash-grid">
        <section className="panel">
          <h3>Continue working</h3>
          <div className="list">
            {(data.continue_working || []).length === 0 && (
              <div className="empty">No recent files yet. Upload something in Files.</div>
            )}
            {(data.continue_working || []).map((f: any) => (
              <div className="list-row" key={f.id}>
                <div>
                  <strong>{f.name}</strong>
                  <div className="muted">{f.extension || "file"} · {(f.size_bytes / 1024).toFixed(1)} KB</div>
                </div>
                <Link className="btn ghost" to="/files">Open</Link>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <h3>Team changes</h3>
          <div className="list">
            {(data.team_activity || []).slice(0, 8).map((a: any) => (
              <div className="list-row" key={a.id}>
                <div>
                  <strong>{a.actor}</strong>
                  <div className="muted">{a.action}{a.item_name ? ` · ${a.item_name}` : ""}</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="dash-grid" style={{ marginTop: 16 }}>
        <section className="panel">
          <h3>Vault legends</h3>
          <div className="list">
            {(data.vault_legends || []).map((l: any) => (
              <div className="list-row" key={l.actor}>
                <strong>{l.actor}</strong>
                <span className="pill">{l.score} actions</span>
              </div>
            ))}
          </div>
        </section>
        {can("users.manage") && (
          <section className="panel">
            <h3>Administration</h3>
            <div className="actions">
              <Link className="btn" to="/admin/users">Users</Link>
              <Link className="btn" to="/admin/settings">Sign-in settings</Link>
              <Link className="btn" to="/admin/audit">Audit log</Link>
              <Link className="btn" to="/indexes">Manage indexes</Link>
              <Link className="btn primary" to="/indexes/playground">Search playground</Link>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
