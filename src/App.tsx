import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { EstateProvider } from './context/EstateContext';
import { RequireAdmin, RequireTenant } from './components/auth/ProtectedRoutes';
import { Layout } from './components/layout/Layout';
import { LoginPage } from './pages/LoginPage';
import { OverviewPage } from './pages/OverviewPage';
import { TenantDashboardPage } from './pages/TenantDashboardPage';
import { LoadProfilesPage } from './pages/LoadProfilesPage';
import { SolarGenerationPage } from './pages/SolarGenerationPage';
import { ForecastingPage } from './pages/ForecastingPage';
import { AllocationPage } from './pages/AllocationPage';
import { BatteryPage } from './pages/BatteryPage';
import { BillingPage } from './pages/BillingPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { TenantPortalPage } from './pages/TenantPortalPage';

const AppRoutes: React.FC = () => {
  const { isAuthenticated, isTenant } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      {/* Admin Module Routes */}
      <Route
        path="/"
        element={
          <RequireAdmin>
            <Layout>
              <OverviewPage />
            </Layout>
          </RequireAdmin>
        }
      />
      <Route
        path="/tenants"
        element={
          <RequireAdmin>
            <Layout>
              <TenantDashboardPage />
            </Layout>
          </RequireAdmin>
        }
      />
      <Route
        path="/load-profiles"
        element={
          <RequireAdmin>
            <Layout>
              <LoadProfilesPage />
            </Layout>
          </RequireAdmin>
        }
      />
      <Route
        path="/solar"
        element={
          <RequireAdmin>
            <Layout>
              <SolarGenerationPage />
            </Layout>
          </RequireAdmin>
        }
      />
      <Route
        path="/forecasting"
        element={
          <RequireAdmin>
            <Layout>
              <ForecastingPage />
            </Layout>
          </RequireAdmin>
        }
      />
      <Route
        path="/allocation"
        element={
          <RequireAdmin>
            <Layout>
              <AllocationPage />
            </Layout>
          </RequireAdmin>
        }
      />
      <Route
        path="/battery"
        element={
          <RequireAdmin>
            <Layout>
              <BatteryPage />
            </Layout>
          </RequireAdmin>
        }
      />
      <Route
        path="/billing"
        element={
          <RequireAdmin>
            <Layout>
              <BillingPage />
            </Layout>
          </RequireAdmin>
        }
      />
      <Route
        path="/analytics"
        element={
          <RequireAdmin>
            <Layout>
              <AnalyticsPage />
            </Layout>
          </RequireAdmin>
        }
      />

      {/* Tenant Portal Route */}
      <Route
        path="/portal"
        element={
          <RequireTenant>
            <Layout>
              <TenantPortalPage />
            </Layout>
          </RequireTenant>
        }
      />

      {/* Wildcard Fallback */}
      <Route
        path="*"
        element={
          isAuthenticated ? (
            isTenant ? (
              <Navigate to="/portal" replace />
            ) : (
              <Navigate to="/" replace />
            )
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
    </Routes>
  );
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <EstateProvider>
          <AppRoutes />
        </EstateProvider>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;

