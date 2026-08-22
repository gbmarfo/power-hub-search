import { NavLink, useNavigate } from "react-router-dom";
import { FormEvent, ReactNode, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../api/client";

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout, can } = useAuth();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [used, setUsed] = useState(0);
  const [quota, setQuota] = useState(1);

  useEffect(() => {
    void api.settings().then((s) => {
      setUsed(Number(s.storage_used_bytes || 0));
      setQuota(Number(s.storage_quota_bytes || 1));
    }).catch(() => undefined);
  }, []);

  function onSearch(e: FormEvent) {
    e.preventDefault();
    navigate(`/search?q=${encodeURIComponent(q)}`);
  }

  const pct = Math.min(100, Math.round((used / Math.max(quota, 1)) * 100));

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">P</div>
          <div>
            <p className="brand-title">Power Hub</p>
            <p className="brand-sub">Document vault</p>
          </div>
        </div>
        <nav className="nav">
          <NavLink className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} to="/" end>
            Home
          </NavLink>
          <NavLink className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} to="/files">
            Files
          </NavLink>
          <NavLink className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} to="/shares">
            My Shares
          </NavLink>
          <NavLink className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} to="/indexes">
            Search Indexes
          </NavLink>
          <NavLink className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} to="/recycle">
            Recycle Bin
          </NavLink>
          <NavLink className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} to="/groups">
            Groups
          </NavLink>
          <NavLink className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} to="/notifications">
            Notifications
          </NavLink>
          <NavLink className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} to="/profile">
            Profile
          </NavLink>
          {can("users.manage") && (
            <>
              <div className="muted" style={{ padding: "12px 12px 4px", fontSize: "0.75rem" }}>
                ADMINISTRATION
              </div>
              <NavLink className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} to="/admin/users">
                Users
              </NavLink>
              <NavLink className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} to="/admin/settings">
                Settings
              </NavLink>
              <NavLink className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} to="/admin/audit">
                Audit log
              </NavLink>
            </>
          )}
        </nav>
        <div className="storage-meter">
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
            <span>Storage</span>
            <span>{pct}%</span>
          </div>
          <div className="bar">
            <div className="fill" style={{ width: `${pct}%` }} />
          </div>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <form className="search-box" onSubmit={onSearch}>
            <span aria-hidden>⌕</span>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search files and folders"
            />
          </form>
          <span className="pill">{user?.full_name || user?.username}</span>
          <button className="btn ghost" type="button" onClick={() => { logout(); navigate("/login"); }}>
            Sign out
          </button>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
