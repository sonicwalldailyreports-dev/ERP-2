import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../app/AuthContext";
import { LoadingState } from "./LoadingState";

export function ProtectedRoute() {
  const { user, isLoading } = useAuth();
  if (isLoading) return <LoadingState />;
  return user ? <Outlet /> : <Navigate to="/login" replace />;
}
