import { FormEvent, useMemo, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function LoginPage() {
  const { user, loginWithPassword, loginWithCode, requestCode } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [mode, setMode] = useState<"email" | "password">("email");
  const [email, setEmail] = useState(params.get("email") || "admin@aya.collective");
  const [password, setPassword] = useState("Admin!23");
  const [code, setCode] = useState(params.get("code") || "");
  const [codeSent, setCodeSent] = useState(!!params.get("code"));
  const [demoCode, setDemoCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const needsProfile = useMemo(
    () => !!user && !(user.full_name && user.full_name.trim()),
    [user],
  );

  if (user && !needsProfile) return <Navigate to="/" replace />;
  if (user && needsProfile) return <Navigate to="/profile?setup=1" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "password") {
        await loginWithPassword(email, password);
      } else if (!codeSent) {
        const res = await requestCode(email);
        setDemoCode(res.demo_code);
        setCode(res.demo_code);
        setCodeSent(true);
      } else {
        await loginWithCode(email, code);
      }
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={onSubmit}>
        <h1>Power Hub</h1>
        <p>Secure files, folders, and search indexes for your organization.</p>

        {mode === "email" ? (
          <>
            <div className="field">
              <label htmlFor="email">Work email</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            {codeSent && (
              <div className="field">
                <label htmlFor="code">6-digit code</label>
                <input
                  id="code"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  required
                />
                {demoCode && (
                  <span className="muted">Demo code (SMTP not configured): {demoCode}</span>
                )}
              </div>
            )}
          </>
        ) : (
          <>
            <div className="field">
              <label htmlFor="email2">Email or username</label>
              <input
                id="email2"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </>
        )}

        {error && <div className="error">{error}</div>}

        <button className="btn primary" style={{ width: "100%" }} disabled={busy}>
          {busy
            ? "Please wait…"
            : mode === "password"
              ? "Sign in"
              : codeSent
                ? "Verify code"
                : "Continue with email"}
        </button>

        <button
          type="button"
          className="btn ghost"
          style={{ width: "100%", marginTop: 10 }}
          onClick={() => {
            setMode(mode === "email" ? "password" : "email");
            setError("");
            setCodeSent(false);
          }}
        >
          {mode === "email" ? "Sign in with a password" : "Use email code instead"}
        </button>
      </form>
    </div>
  );
}
