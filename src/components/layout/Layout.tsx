import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { LocationModal } from './LocationModal';
import { useScrollToTopOnNavigate } from '../../hooks/useScrollToTopOnNavigate';
import { useAuth } from '../../context/AuthContext';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [collapsed, setCollapsed] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [locationOpen, setLocationOpen] = useState(false);
  const { isTenant } = useAuth();
  const { pathname } = useLocation();

  useScrollToTopOnNavigate();

  const handleRefresh = () => {
    setRefreshKey((prev) => prev + 1);
  };

  return (
    <div className="min-h-screen flex flex-col font-sans" style={{ background: 'var(--surface-1)', color: 'var(--text-primary)' }}>
      <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} />
      <Header
        collapsed={collapsed}
        setCollapsed={setCollapsed}
        onRefresh={handleRefresh}
        onOpenLocation={isTenant ? undefined : () => setLocationOpen(true)}
      />

      <main
        className="flex-1 pt-24 px-6 pb-12 transition-[margin] duration-300 ease-out"
        style={{ marginLeft: collapsed ? '70px' : '240px' }}
      >
        <div key={`${refreshKey}-${pathname}`} className="max-w-7xl mx-auto space-y-6 page-enter">
          {children}
        </div>
      </main>

      <LocationModal
        isOpen={locationOpen}
        onClose={() => setLocationOpen(false)}
        onLocationChanged={handleRefresh}
      />
    </div>
  );
};
