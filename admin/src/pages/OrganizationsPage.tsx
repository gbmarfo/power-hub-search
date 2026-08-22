import { FormEvent, useEffect, useState } from "react";
import { api } from "../api/client";
import type { OrganizationRecord } from "../types";
import { Card, ErrorBanner, PageHeader } from "../components/ui";

export function OrganizationsPage() {
  const [organizations, setOrganizations] = useState<OrganizationRecord[]>([]);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    name: "",
    description: "",
    contact_email: "",
    organization_type: "enterprise",
  });

  async function loadOrganizations() {
    setError("");
    try {
      const data = await api.listOrganizations();
      setOrganizations(data.results);
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  useEffect(() => {
    void loadOrganizations();
  }, []);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setCreating(true);
    setError("");
    try {
      await api.createOrganization(form);
      setShowCreate(false);
      await loadOrganizations();
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Organizations"
        description="Tenants used to scope indexes and search filters."
        action={
          <button className="btn btn-primary" onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? "Cancel" : "Create organization"}
          </button>
        }
      />

      {error ? <ErrorBanner message={error} /> : null}

      {showCreate ? (
        <Card title="New organization" className="mb">
          <form className="form-grid" onSubmit={handleCreate}>
            <label>
              Name
              <input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </label>
            <label>
              Type
              <input
                value={form.organization_type}
                onChange={(e) => setForm({ ...form, organization_type: e.target.value })}
              />
            </label>
            <label>
              Contact email
              <input
                type="email"
                value={form.contact_email}
                onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
              />
            </label>
            <label className="full-width">
              Description
              <textarea
                rows={3}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </label>
            <div className="full-width">
              <button className="btn btn-primary" disabled={creating}>
                {creating ? "Creating..." : "Create organization"}
              </button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card>
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Org ID</th>
              <th>Type</th>
              <th>Email</th>
            </tr>
          </thead>
          <tbody>
            {organizations.map((org) => (
              <tr key={org.organization_id}>
                <td>{org.name}</td>
                <td>
                  <code>{org.organization_id}</code>
                </td>
                <td>{org.organization_type}</td>
                <td>{org.contact_email}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
