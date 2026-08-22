import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, clearToken, getToken, setToken, type User } from "../api/client";

type AuthState = {
  user: User | null;
  loading: boolean;
  loginWithPassword: (email: string, password: string) => Promise<void>;
  loginWithCode: (email: string, code: string) => Promise<void>;
  requestCode: (email: string) => Promise<{ demo_code: string }>;
  logout: () => void;
  refresh: () => Promise<void>;
  can: (capability: string) => boolean;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.me();
      setUser(me);
    } catch {
      clearToken();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      async loginWithPassword(email, password) {
        const res = await api.loginPassword(email, password);
        setToken(res.access_token);
        setUser(res.user);
      },
      async loginWithCode(email, code) {
        const res = await api.verifyCode(email, code);
        setToken(res.access_token);
        setUser(res.user);
      },
      async requestCode(email) {
        return api.requestCode(email);
      },
      logout() {
        clearToken();
        setUser(null);
      },
      refresh,
      can(capability) {
        return !!user?.capabilities?.includes(capability);
      },
    }),
    [user, loading, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
