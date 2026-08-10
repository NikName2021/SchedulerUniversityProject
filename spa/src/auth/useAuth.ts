import { useContext } from "react";

import { AuthContext, type AuthContextValue } from "./authContextValue";

export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
};
