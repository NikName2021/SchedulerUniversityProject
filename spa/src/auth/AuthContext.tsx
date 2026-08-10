import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  API_BASE_URL,
  AUTH_UNAUTHORIZED_EVENT,
  apiFetch,
  setCsrfToken,
} from "../api/apiConfig";
import { AuthContext, type AuthUser } from "./authContextValue";

type AuthPayload = {
  user: AuthUser;
  csrf_token: string;
};

const readError = async (response: Response): Promise<string> => {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    return typeof payload.detail === "string"
      ? payload.detail
      : "Не удалось выполнить вход";
  } catch {
    return "Сервис авторизации временно недоступен";
  }
};

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const clearAuth = useCallback(() => {
    setCsrfToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    const restoreSession = async () => {
      try {
        const response = await apiFetch(`${API_BASE_URL}/api/v1/auth/me`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          clearAuth();
          return;
        }
        const payload = (await response.json()) as AuthPayload;
        setCsrfToken(payload.csrf_token);
        setUser(payload.user);
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          clearAuth();
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    };

    void restoreSession();
    return () => controller.abort();
  }, [clearAuth]);

  useEffect(() => {
    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, clearAuth);
    return () => window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, clearAuth);
  }, [clearAuth]);

  const login = useCallback(async (username: string, password: string) => {
    const response = await apiFetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      throw new Error(await readError(response));
    }
    const payload = (await response.json()) as AuthPayload;
    setCsrfToken(payload.csrf_token);
    setUser(payload.user);
  }, []);

  const logout = useCallback(async () => {
    const response = await apiFetch(`${API_BASE_URL}/api/v1/auth/logout`, {
      method: "POST",
    });
    if (!response.ok && response.status !== 401) {
      throw new Error("Не удалось завершить сессию");
    }
    clearAuth();
  }, [clearAuth]);

  const value = useMemo(
    () => ({ user, isLoading, login, logout }),
    [isLoading, login, logout, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
