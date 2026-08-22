import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, clearToken, getToken, setToken } from "../api/client";

interface AuthContextValue {
  username: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [username, setUsername] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const bootstrap = useCallback(async () => {
    try {
      const token = getToken();
      const info = await api.info(Boolean(token));
      setUsername(info.user);
    } catch {
      clearToken();
      setUsername(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  const login = useCallback(async (user: string, password: string) => {
    const response = await api.login(user, password);
    setToken(response.access_token);
    const info = await api.info(true);
    setUsername(info.user);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUsername(null);
  }, []);

  const value = useMemo(
    () => ({ username, loading, login, logout }),
    [username, loading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
