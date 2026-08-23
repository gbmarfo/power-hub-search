import { NavLink, useNavigate } from "react-router-dom";
import { FormEvent, ReactNode, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../api/client";

type NavItem = {
  to: string;
  label: string;
  end?: boolean;
};

function NavItems({ items }: { items: NavItem[] }) {
  return (
    <>
      {items.map((item) => (
        <NavLink
          key={item.to}
          className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
          to={item.to}
          end={item.end}
        >
          {item.label}
        </NavLink>
      ))}
    </>
  );
}

const PRIMARY_NAV: NavItem[] = [
  { to: "/", label: "Home", end: true },
  { to: "/files", label: "Files" },
  { to: "/shares", label: "Shares" },
  { to: "/indexes/playground", label: "Search" },
  { to: "/indexes", label: "Indexes", end: true },
  { to: "/groups", label: "Groups" },
  { to: "/recycle", label: "Recycle bin" },
];

const ACCOUNT_NAV: NavItem[] = [
  { to: "/notifications", label: "Notifications" },
  { to: "/profile", label: "Profile" },
];

const ADMIN_NAV: NavItem[] = [
  { to: "/admin/users", label: "Users" },
  { to: "/admin/settings", label: "Settings" },
  { to: "/admin/audit", label: "Audit log" },
];

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

        <nav className="nav nav-main" aria-label="Main">
          <NavItems items={PRIMARY_NAV} />
        </nav>

        <div className="sidebar-foot">
          <nav className="nav nav-foot" aria-label="Account">
            <NavItems items={ACCOUNT_NAV} />
          </nav>

          {can("users.manage") && (
            <nav className="nav nav-admin" aria-label="Administration">
              <p className="nav-admin-label">Admin</p>
              <NavItems items={ADMIN_NAV} />
            </nav>
          )}

          <div className="storage-meter">
            <div className="storage-meter-head">
              <span>Storage</span>
              <span>{pct}%</span>
            </div>
            <div className="bar">
              <div className="fill" style={{ width: `${pct}%` }} />
            </div>
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
          <button
            className="btn ghost"
            type="button"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            Sign out
          </button>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
