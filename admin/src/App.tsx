import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { useAuth } from "./context/AuthContext";
import { DashboardPage } from "./pages/DashboardPage";
import { IndexDetailPage } from "./pages/IndexDetailPage";
import { IndexesPage } from "./pages/IndexesPage";
import { LoginPage } from "./pages/LoginPage";
import { MultimodalRagPage } from "./pages/MultimodalRagPage";
import { OrganizationsPage } from "./pages/OrganizationsPage";
import { SearchPlaygroundPage } from "./pages/SearchPlaygroundPage";
import { UsersPage } from "./pages/UsersPage";

function ProtectedRoutes() {
  const { username, loading } = useAuth();

  if (loading) {
    return <div className="loading-screen">Loading admin console...</div>;
  }

  if (!username) {
    return <Navigate to="/login" replace />;
  }

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/indexes" element={<IndexesPage />} />
        <Route path="/indexes/:indexId" element={<IndexDetailPage />} />
        <Route path="/search" element={<SearchPlaygroundPage />} />
        <Route path="/multimodal" element={<MultimodalRagPage />} />
        <Route path="/users" element={<UsersPage />} />
        <Route path="/organizations" element={<OrganizationsPage />} />
      </Routes>
    </Layout>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/*" element={<ProtectedRoutes />} />
    </Routes>
  );
}
