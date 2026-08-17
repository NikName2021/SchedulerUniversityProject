import { createContext } from "react";

export type AuthUser = {
  id: number;
  username: string;
  display_name: string;
  role: "admin" | "operator";
};

export type AuthContextValue = {
  user: AuthUser | null;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);
