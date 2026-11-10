import { Navigate } from "react-router-dom";
import { useAuth } from "./auth";

export function RequireAuth({ children }) {
  const { user, ready } = useAuth();
  if (!ready) {
    return <p className="status">Checking your session…</p>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return children;
}
