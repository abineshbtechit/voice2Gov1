import React, { createContext, useContext, useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  ApiClient,
  ACCESS_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
  USER_INFO_KEY,
} from '../api/client';

export interface User {
  id: string;
  email: string;
  phone?: string;
  full_name: string;
  role: 'citizen' | 'organization_staff' | 'organization_admin' | 'admin';
  organization_id?: string | null;
  department_id?: string | null;
  is_verified?: boolean;
}

interface AuthContextProps {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string, refreshToken: string, user?: User) => Promise<void>;
  logout: () => Promise<void>;
  updateUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextProps>({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  login: async () => {},
  logout: async () => {},
  updateUser: () => {},
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadUserFromStorage();
  }, []);

  const loadUserFromStorage = async () => {
    try {
      const storedUser = await AsyncStorage.getItem(USER_INFO_KEY);
      const token = await AsyncStorage.getItem(ACCESS_TOKEN_KEY);
      if (storedUser && token) {
        setUser(JSON.parse(storedUser));
        // Verify token with /auth/me in background
        ApiClient.get<User>('/auth/me').then((res) => {
          if (res.success && res.data) {
            setUser(res.data);
            AsyncStorage.setItem(USER_INFO_KEY, JSON.stringify(res.data));
          }
        });
      }
    } catch {
      // Storage empty
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (token: string, refreshToken: string, userData?: User) => {
    await AsyncStorage.setItem(ACCESS_TOKEN_KEY, token);
    await AsyncStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);

    let resolvedUser = userData;
    if (!resolvedUser) {
      try {
        const profileRes = await ApiClient.get<User>('/auth/me');
        if (profileRes.success && profileRes.data) {
          resolvedUser = profileRes.data;
        } else {
          resolvedUser = {
            id: 'citizen',
            email: '',
            full_name: 'Citizen',
            role: 'citizen',
          };
        }
      } catch {
        resolvedUser = {
          id: 'citizen',
          email: '',
          full_name: 'Citizen',
          role: 'citizen',
        };
      }
    }

    await AsyncStorage.setItem(USER_INFO_KEY, JSON.stringify(resolvedUser));
    setUser(resolvedUser);
  };

  const logout = async () => {
    try {
      const refreshToken = await AsyncStorage.getItem(REFRESH_TOKEN_KEY);
      if (refreshToken) {
        await ApiClient.post('/auth/logout', { refresh_token: refreshToken });
      }
    } catch {}
    await AsyncStorage.removeItem(ACCESS_TOKEN_KEY);
    await AsyncStorage.removeItem(REFRESH_TOKEN_KEY);
    await AsyncStorage.removeItem(USER_INFO_KEY);
    setUser(null);
  };

  const updateUser = (updatedUser: User) => {
    setUser(updatedUser);
    AsyncStorage.setItem(USER_INFO_KEY, JSON.stringify(updatedUser));
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        updateUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);

