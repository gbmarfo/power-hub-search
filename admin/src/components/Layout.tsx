import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const navItems = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/indexes", label: "Indexes" },
  { to: "/search", label: "Search Playground" },
  { to: "/multimodal", label: "Multimodal RAG" },
  { to: "/users", label: "Users" },
  { to: "/organizations", label: "Organizations" },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const { username, logout } = useAuth();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">P</div>
          <div>
            <p className="brand-title">Power Hub Search</p>
            <p className="brand-sub">Milvus Enterprise</p>
          </div>
        </div>

        <nav className="nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <p className="user-label">Signed in</p>
          <p className="user-name">{username ?? "anonymous"}</p>
          <button className="btn btn-ghost" onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="main">{children}</main>
    </div>
  );
}
