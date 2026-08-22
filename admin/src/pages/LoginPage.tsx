import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { ErrorBanner } from "../components/ui";

export function LoginPage() {
  const { username, loading, login } = useAuth();
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!loading && username) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await login(user, password);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Unable to sign in";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <div className="brand login-brand">
          <div className="brand-mark">S</div>
          <div>
            <p className="brand-title">Search Admin</p>
            <p className="brand-sub">Enterprise search console</p>
          </div>
        </div>

        <h1>Sign in</h1>
        <p className="login-copy">
          Manage Milvus indexes, run queries, and administer users.
        </p>

        {error ? <ErrorBanner message={error} /> : null}

        <label>
          Username
          <input
            value={user}
            onChange={(e) => setUser(e.target.value)}
            autoComplete="username"
            required
          />
        </label>

        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>

        <button className="btn btn-primary" disabled={submitting}>
          {submitting ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </div>
  );
}
