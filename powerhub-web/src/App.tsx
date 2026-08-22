import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { Layout } from "./components/Layout";
import { useAuth } from "./context/AuthContext";
import { DashboardPage } from "./pages/DashboardPage";
import { FilesPage } from "./pages/FilesPage";
import { IndexesPage } from "./pages/IndexesPage";
import { LoginPage } from "./pages/LoginPage";
import {
  AdminAuditPage,
  AdminSettingsPage,
  AdminUsersPage,
  GroupsPage,
  NotificationsPage,
  ProfilePage,
  PublicSharePage,
  RecyclePage,
  SearchPage,
  SharesPage,
} from "./pages/MiscPages";

function ShareRoute() {
  const { token } = useParams();
  return <PublicSharePage token={token || ""} />;
}

function Protected() {
  const { user, loading } = useAuth();
  if (loading) return <div className="login-page"><div className="login-card">Loading Power Hub…</div></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!(user.full_name && user.full_name.trim())) {
    return <Navigate to="/profile?setup=1" replace />;
  }
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/files" element={<FilesPage />} />
        <Route path="/shares" element={<SharesPage />} />
        <Route path="/indexes" element={<IndexesPage />} />
        <Route path="/recycle" element={<RecyclePage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/groups" element={<GroupsPage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/admin/users" element={<AdminUsersPage />} />
        <Route path="/admin/settings" element={<AdminSettingsPage />} />
        <Route path="/admin/audit" element={<AdminAuditPage />} />
      </Routes>
    </Layout>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/s/:token" element={<ShareRoute />} />
      <Route path="/profile" element={<ProfileGate />} />
      <Route path="/*" element={<Protected />} />
    </Routes>
  );
}

function ProfileGate() {
  const { user, loading } = useAuth();
  if (loading) return <div className="login-page"><div className="login-card">Loading…</div></div>;
  if (!user) return <Navigate to="/login" replace />;
  return (
    <Layout>
      <ProfilePage />
    </Layout>
  );
}
