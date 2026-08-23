import { NavLink, useNavigate } from "react-router-dom";
import { FormEvent, ReactNode, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../api/client";

type NavItem = {
  to: string;
  label: string;
  end?: boolean;
};

type NavSection = {
  title: string;
  items: NavItem[];
};

function NavSectionBlock({ title, items }: NavSection) {
  return (
    <div className="nav-section">
      <p className="nav-section-title">{title}</p>
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
    </div>
  );
}

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

  const navSections: NavSection[] = [
    {
      title: "Overview",
      items: [{ to: "/", label: "Home", end: true }],
    },
    {
      title: "Library",
      items: [
        { to: "/files", label: "Files" },
        { to: "/recycle", label: "Recycle bin" },
      ],
    },
    {
      title: "Search",
      items: [
        { to: "/search", label: "Library search" },
        { to: "/indexes/playground", label: "Search playground" },
        { to: "/indexes", label: "Manage indexes", end: true },
      ],
    },
    {
      title: "Collaboration",
      items: [
        { to: "/shares", label: "My shares" },
        { to: "/groups", label: "Groups" },
      ],
    },
    {
      title: "Account",
      items: [
        { to: "/notifications", label: "Notifications" },
        { to: "/profile", label: "Profile" },
      ],
    },
  ];

  const adminSection: NavSection = {
    title: "Administration",
    items: [
      { to: "/admin/users", label: "Users" },
      { to: "/admin/settings", label: "Settings" },
      { to: "/admin/audit", label: "Audit log" },
    ],
  };

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
          {navSections.map((section) => (
            <NavSectionBlock key={section.title} {...section} />
          ))}
          {can("users.manage") && <NavSectionBlock {...adminSection} />}
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
