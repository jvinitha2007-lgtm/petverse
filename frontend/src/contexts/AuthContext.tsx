import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, getToken, saveToken } from "../services/api";
import type { User } from "../types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  error: string;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (name: string, email: string, password: string) => Promise<string>;
  signOut: () => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(Boolean(getToken()));
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) return;
    api.me().then(setUser).catch(() => {
      saveToken(null);
      setUser(null);
    }).finally(() => setLoading(false));
  }, []);

  async function authenticate(operation: Promise<{ access_token: string; user: User }>) {
    setError("");
    try {
      const result = await operation;
      saveToken(result.access_token);
      setUser(result.user);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to sign in. Please try again.");
      throw reason;
    }
  }

  async function register(name: string, email: string, password: string) {
    setError("");
    try {
      const result = await api.register({ full_name: name, email, password });
      return result.message;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create your account. Please try again.");
      throw reason;
    }
  }

  const value = useMemo<AuthContextValue>(() => ({
    user,
    loading,
    error,
    signIn: (email, password) => authenticate(api.login({ email, password })),
    signUp: register,
    signOut: () => {
      saveToken(null);
      setUser(null);
      setError("");
    },
    clearError: () => setError(""),
  }), [user, loading, error]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
