import React, { createContext, useContext, useState, useEffect } from 'react';
import { UserRead } from '../types/api';
import { api } from '../api/client';

interface AuthContextType {
  user: UserRead | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<UserRead>;
  logout: () => void;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isTenant: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserRead | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('solarshare_token'));
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const initAuth = async () => {
      const storedToken = localStorage.getItem('solarshare_token');
      if (storedToken) {
        try {
          const userData = await api.getMe();
          setUser(userData);
          setToken(storedToken);
        } catch {
          localStorage.removeItem('solarshare_token');
          setToken(null);
          setUser(null);
        }
      }
      setLoading(false);
    };
    initAuth();
  }, []);

  const login = async (username: string, password: string): Promise<UserRead> => {
    const res = await api.login(username, password);
    localStorage.setItem('solarshare_token', res.access_token);
    setToken(res.access_token);
    const userData = await api.getMe();
    setUser(userData);
    return userData;
  };

  const logout = () => {
    localStorage.removeItem('solarshare_token');
    setToken(null);
    setUser(null);
  };

  const isAuthenticated = !!user;
  const isAdmin = user?.role === 'ADMIN';
  const isTenant = user?.role === 'TENANT';

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        logout,
        isAuthenticated,
        isAdmin,
        isTenant,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
