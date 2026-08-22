import { FormEvent, useEffect, useState } from "react";
import { api } from "../api/client";
import type { UserRecord } from "../types";
import { Card, ErrorBanner, PageHeader } from "../components/ui";

export function UsersPage() {
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    username: "",
    password: "",
    full_name: "",
    email: "",
    organization_id: localStorage.getItem("admin_org_id") ?? "",
    role: "admin",
    is_active: 1,
  });

  async function loadUsers() {
    setError("");
    try {
      const data = await api.listUsers();
      setUsers(data.results);
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  useEffect(() => {
    void loadUsers();
  }, []);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setCreating(true);
    setError("");
    try {
      await api.createUser(form);
      setShowCreate(false);
      await loadUsers();
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Users"
        description="Manage API users and access credentials."
        action={
          <button className="btn btn-primary" onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? "Cancel" : "Create user"}
          </button>
        }
      />

      {error ? <ErrorBanner message={error} /> : null}

      {showCreate ? (
        <Card title="New user" className="mb">
          <form className="form-grid" onSubmit={handleCreate}>
            <label>
              Username
              <input
                required
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
              />
            </label>
            <label>
              Password
              <input
                type="password"
                required
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </label>
            <label>
              Full name
              <input
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              />
            </label>
            <label>
              Email
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </label>
            <label>
              Organization ID
              <input
                value={form.organization_id}
                onChange={(e) => setForm({ ...form, organization_id: e.target.value })}
              />
            </label>
            <label>
              Role
              <input
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
              />
            </label>
            <div className="full-width">
              <button className="btn btn-primary" disabled={creating}>
                {creating ? "Creating..." : "Create user"}
              </button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card>
        <table className="table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Name</th>
              <th>Email</th>
              <th>Org</th>
              <th>Role</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.user_id}>
                <td>{user.username}</td>
                <td>{user.full_name}</td>
                <td>{user.email}</td>
                <td><code>{user.organization_id}</code></td>
                <td>{user.role}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
