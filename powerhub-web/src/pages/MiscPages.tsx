import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

export function SharesPage() {
  const { can } = useAuth();
  const [scope, setScope] = useState<"mine" | "all">("mine");
  const [shares, setShares] = useState<any[]>([]);

  useEffect(() => {
    void api.shares(scope).then(setShares);
  }, [scope]);

  return (
    <div>
      <h1 className="page-title">My Shares</h1>
      <p className="page-sub">Links you created, with status and download usage.</p>
      <div className="toolbar">
        <button className={`btn ${scope === "mine" ? "primary" : ""}`} type="button" onClick={() => setScope("mine")}>
          My shares
        </button>
        {can("sharing.manage") && (
          <button className={`btn ${scope === "all" ? "primary" : ""}`} type="button" onClick={() => setScope("all")}>
            All shares
          </button>
        )}
      </div>
      <div className="panel">
        <table className="table">
          <thead>
            <tr>
              <th>Item</th>
              <th>Role</th>
              <th>Downloads</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {shares.map((s) => (
              <tr key={s.id}>
                <td>
                  <strong>{s.item_name || s.item_id}</strong>
                  <div className="muted">{s.url}</div>
                </td>
                <td>{s.role}</td>
                <td>
                  {s.download_count}
                  {s.download_limit != null ? ` / ${s.download_limit}` : ""}
                </td>
                <td>{s.is_active ? <span className="pill">Active</span> : "Revoked"}</td>
                <td>
                  {s.is_active && (
                    <button
                      className="btn danger"
                      type="button"
                      onClick={() => void api.revokeShare(s.id).then(() => api.shares(scope).then(setShares))}
                    >
                      Revoke
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!shares.length && (
              <tr><td colSpan={5} className="empty">No share links yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function RecyclePage() {
  const [items, setItems] = useState<any[]>([]);
  const load = () => void api.recycle().then(setItems);
  useEffect(() => { load(); }, []);

  return (
    <div>
      <h1 className="page-title">Recycle Bin</h1>
      <p className="page-sub">Deleted items remain restorable until retention expires.</p>
      <div className="panel">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Deleted by</th>
              <th>Days left</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={`${item.item_type}-${item.id}`}>
                <td>{item.name}</td>
                <td>{item.item_type}</td>
                <td>{item.deleted_by}</td>
                <td>{item.days_remaining}</td>
                <td className="actions">
                  <button className="btn" type="button" onClick={() => void api.restore(item.item_type, item.id).then(load)}>
                    Restore
                  </button>
                  <button className="btn danger" type="button" onClick={() => void api.purge(item.item_type, item.id).then(load)}>
                    Delete forever
                  </button>
                </td>
              </tr>
            ))}
            {!items.length && <tr><td colSpan={5} className="empty">Recycle bin is empty.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function SearchPage() {
  const [q, setQ] = useState(new URLSearchParams(window.location.search).get("q") || "");
  const [kind, setKind] = useState("all");
  const [hits, setHits] = useState<any[]>([]);

  useEffect(() => {
    void api.search(q, kind === "all" ? undefined : kind).then(setHits);
  }, [q, kind]);

  return (
    <div>
      <h1 className="page-title">Search</h1>
      <p className="page-sub">Find files and folders across everything you can access.</p>
      <div className="toolbar">
        <input
          style={{ flex: 1, minWidth: 200, borderRadius: 12, border: "1px solid var(--line)", padding: "10px 12px" }}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search…"
        />
        {["all", "folders", "documents", "images", "media"].map((k) => (
          <button key={k} className={`btn ${kind === k ? "primary" : ""}`} type="button" onClick={() => setKind(k)}>
            {k}
          </button>
        ))}
      </div>
      <div className="panel">
        <div className="list">
          {hits.map((h) => (
            <div className="list-row" key={`${h.item_type}-${h.id}`}>
              <div>
                <strong>{h.item_type === "folder" ? "📁" : "📄"} {h.name}</strong>
                <div className="muted">{h.path}</div>
              </div>
              <span className="pill">{h.item_type}</span>
            </div>
          ))}
          {!hits.length && <div className="empty">No matches.</div>}
        </div>
      </div>
    </div>
  );
}

export function ProfilePage() {
  const { user, refresh } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");

  return (
    <div>
      <h1 className="page-title">My Profile</h1>
      <p className="page-sub">How you appear across the vault, and your current capabilities.</p>
      <form
        className="panel"
        onSubmit={(e) => {
          e.preventDefault();
          void api.updateProfile({ full_name: fullName, password: password || undefined }).then(async () => {
            await refresh();
            setPassword("");
            setMessage("Saved");
          });
        }}
      >
        <div className="field">
          <label>Full name</label>
          <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
        </div>
        <div className="field">
          <label>Email</label>
          <input value={user?.email || ""} disabled />
        </div>
        <div className="field">
          <label>Set password (optional)</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        {message && <div className="muted">{message}</div>}
        <button className="btn primary">Save profile</button>
      </form>
      <div className="panel" style={{ marginTop: 16 }}>
        <h3>Permissions</h3>
        <p className="muted">Role: {user?.role}</p>
        <div className="actions">
          {(user?.capabilities || []).map((c) => (
            <span className="pill" key={c}>{c}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

export function NotificationsPage() {
  const [notes, setNotes] = useState<any[]>([]);
  const load = () => void api.notifications().then(setNotes);
  useEffect(() => { load(); }, []);

  return (
    <div>
      <h1 className="page-title">Notifications</h1>
      <p className="page-sub">Mentions, access changes, and expiring links.</p>
      <div className="toolbar">
        <button className="btn" type="button" onClick={() => void api.markNotificationsRead().then(load)}>
          Mark all read
        </button>
      </div>
      <div className="panel">
        <div className="list">
          {notes.map((n) => (
            <div className="list-row" key={n.id}>
              <div>
                <strong>{n.title}</strong>
                <div className="muted">{n.body}</div>
              </div>
              {!n.is_read && <span className="pill">New</span>}
            </div>
          ))}
          {!notes.length && <div className="empty">All caught up.</div>}
        </div>
      </div>
    </div>
  );
}

export function GroupsPage() {
  const [groups, setGroups] = useState<any[]>([]);
  const [name, setName] = useState("");
  const load = () => void api.groups().then(setGroups);
  useEffect(() => { load(); }, []);

  return (
    <div>
      <h1 className="page-title">Groups</h1>
      <p className="page-sub">Grant a group access once; every member inherits it.</p>
      <form
        className="toolbar"
        onSubmit={(e) => {
          e.preventDefault();
          void api.createGroup(name).then(() => { setName(""); load(); });
        }}
      >
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="New group name"
          style={{ borderRadius: 12, border: "1px solid var(--line)", padding: "10px 12px" }}
          required
        />
        <button className="btn primary">Create group</button>
      </form>
      <div className="panel">
        <div className="list">
          {groups.map((g) => (
            <div className="list-row" key={g.id}>
              <div>
                <strong>{g.name}</strong>
                <div className="muted">{g.description || "No description"}</div>
              </div>
              <span className="pill">{g.member_count} members</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function AdminUsersPage() {
  const [users, setUsers] = useState<any[]>([]);
  useEffect(() => {
    void api.users().then((r) => setUsers(r.results));
  }, []);
  return (
    <div>
      <h1 className="page-title">Users</h1>
      <p className="page-sub">Roster, roles, and account status.</p>
      <div className="panel">
        <table className="table">
          <thead>
            <tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th></tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.user_id}>
                <td>{u.full_name || u.username}</td>
                <td>{u.email}</td>
                <td>{u.role}</td>
                <td>{u.is_active ? "Active" : "Deactivated"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function AdminSettingsPage() {
  const [domains, setDomains] = useState("");
  const [allowPublic, setAllowPublic] = useState(false);
  const [retention, setRetention] = useState(30);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    void api.settings().then((s) => {
      setDomains(String(s.allowed_domains || ""));
      setAllowPublic(Boolean(s.allow_public_email));
      setRetention(Number(s.recycle_retention_days || 30));
    });
  }, []);

  return (
    <div>
      <h1 className="page-title">Settings</h1>
      <p className="page-sub">Sign-in policy and recycle bin retention.</p>
      <form
        className="panel"
        onSubmit={(e) => {
          e.preventDefault();
          void api.updateSettings({
            allowed_domains: domains,
            allow_public_email: allowPublic,
            recycle_retention_days: retention,
          }).then(() => setSaved(true));
        }}
      >
        <div className="field">
          <label>Allowed email domains (comma-separated)</label>
          <input value={domains} onChange={(e) => setDomains(e.target.value)} />
        </div>
        <label style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 14 }}>
          <input type="checkbox" checked={allowPublic} onChange={(e) => setAllowPublic(e.target.checked)} />
          Allow public email providers
        </label>
        <div className="field">
          <label>Recycle bin retention (days)</label>
          <input type="number" min={1} value={retention} onChange={(e) => setRetention(Number(e.target.value))} />
        </div>
        {saved && <div className="muted">Settings saved.</div>}
        <button className="btn primary">Save settings</button>
      </form>
    </div>
  );
}

export function AdminAuditPage() {
  const [events, setEvents] = useState<any[]>([]);
  useEffect(() => {
    void api.audit().then(setEvents);
  }, []);
  return (
    <div>
      <h1 className="page-title">Audit log</h1>
      <p className="page-sub">Who did what, and when.</p>
      <div className="panel">
        <table className="table">
          <thead>
            <tr><th>When</th><th>Actor</th><th>Action</th><th>Detail</th></tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id}>
                <td className="muted">{e.created_at ? new Date(e.created_at).toLocaleString() : ""}</td>
                <td>{e.actor}</td>
                <td>{e.action}</td>
                <td>{e.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function PublicSharePage({ token }: { token: string }) {
  const [meta, setMeta] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    void api.publicShare(token).then(setMeta).catch((e) => setError(e.message));
  }, [token]);

  if (error) return <div className="login-page"><div className="login-card"><h1>Share unavailable</h1><p>{error}</p></div></div>;
  if (!meta) return <div className="login-page"><div className="login-card">Loading…</div></div>;

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Power Hub</h1>
        <p>Shared {meta.item_type}</p>
        <h2 style={{ fontFamily: "var(--display)" }}>{meta.name}</h2>
        {meta.can_download && (
          <a className="btn primary" href={`/api/v1/powerhub/public/share/${token}/download`}>
            Download
          </a>
        )}
      </div>
    </div>
  );
}
