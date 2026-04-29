import { Navigate, Outlet } from "react-router-dom";
import { isAuthenticated } from "../../services/api";

export function PrivateRoute() {
  return isAuthenticated() ? <Outlet /> : <Navigate to="/login" replace />;
}