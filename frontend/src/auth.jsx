import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("cc_token");
    if (!token) {
      setReady(true);
      return;
    }
    api("/api/auth/me")
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("cc_token");
        setUser(null);
      })
      .finally(() => setReady(true));
  }, []);

  const value = useMemo(
    () => ({
      user,
      ready,
      setSession(token, nextUser) {
        localStorage.setItem("cc_token", token);
        setUser(nextUser);
      },
      logout() {
        localStorage.removeItem("cc_token");
        setUser(null);
      },
    }),
    [user, ready]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
