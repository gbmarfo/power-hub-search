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

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="login-page">
        <div className="login-card">Loading Power Hub…</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RequireProfile({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!(user?.full_name && user.full_name.trim())) {
    return <Navigate to="/profile?setup=1" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/s/:token" element={<ShareRoute />} />
      <Route
        path="/profile"
        element={
          <RequireAuth>
            <Layout>
              <ProfilePage />
            </Layout>
          </RequireAuth>
        }
      />
      <Route
        path="/"
        element={
          <RequireAuth>
            <RequireProfile>
              <Layout>
                <DashboardPage />
              </Layout>
            </RequireProfile>
          </RequireAuth>
        }
      />
      <Route
        path="/files"
        element={
          <RequireAuth>
            <RequireProfile>
              <Layout>
                <FilesPage />
              </Layout>
            </RequireProfile>
          </RequireAuth>
        }
      />
      <Route
        path="/shares"
        element={
          <RequireAuth>
            <RequireProfile>
              <Layout>
                <SharesPage />
              </Layout>
            </RequireProfile>
          </RequireAuth>
        }
      />
      <Route
        path="/indexes"
        element={
          <RequireAuth>
            <RequireProfile>
              <Layout>
                <IndexesPage />
              </Layout>
            </RequireProfile>
          </RequireAuth>
        }
      />
      <Route
        path="/recycle"
        element={
          <RequireAuth>
            <RequireProfile>
              <Layout>
                <RecyclePage />
              </Layout>
            </RequireProfile>
          </RequireAuth>
        }
      />
      <Route
        path="/search"
        element={
          <RequireAuth>
            <RequireProfile>
              <Layout>
                <SearchPage />
              </Layout>
            </RequireProfile>
          </RequireAuth>
        }
      />
      <Route
        path="/groups"
        element={
          <RequireAuth>
            <RequireProfile>
              <Layout>
                <GroupsPage />
              </Layout>
            </RequireProfile>
          </RequireAuth>
        }
      />
      <Route
        path="/notifications"
        element={
          <RequireAuth>
            <RequireProfile>
              <Layout>
                <NotificationsPage />
              </Layout>
            </RequireProfile>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/users"
        element={
          <RequireAuth>
            <RequireProfile>
              <Layout>
                <AdminUsersPage />
              </Layout>
            </RequireProfile>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/settings"
        element={
          <RequireAuth>
            <RequireProfile>
              <Layout>
                <AdminSettingsPage />
              </Layout>
            </RequireProfile>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/audit"
        element={
          <RequireAuth>
            <RequireProfile>
              <Layout>
                <AdminAuditPage />
              </Layout>
            </RequireProfile>
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
