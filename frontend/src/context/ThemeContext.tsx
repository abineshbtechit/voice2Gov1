import React, { createContext, useContext, useState, useEffect } from 'react';
import { useColorScheme } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { LightTheme, DarkTheme, ThemeType } from '../theme/tokens';

interface ThemeContextProps {
  theme: ThemeType;
  isDark: boolean;
  toggleTheme: () => void;
  setScheme: (mode: 'light' | 'dark' | 'system') => void;
}

const THEME_STORAGE_KEY = '@voice2gov_theme_preference';

const ThemeContext = createContext<ThemeContextProps>({
  theme: DarkTheme,
  isDark: true,
  toggleTheme: () => {},
  setScheme: () => {},
});

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const systemScheme = useColorScheme();
  const [preference, setPreference] = useState<'light' | 'dark' | 'system'>('dark');

  useEffect(() => {
    AsyncStorage.getItem(THEME_STORAGE_KEY).then((stored) => {
      if (stored === 'light' || stored === 'dark' || stored === 'system') {
        setPreference(stored);
      }
    });
  }, []);

  const isDark =
    preference === 'system' ? systemScheme === 'dark' : preference === 'dark';

  const theme = isDark ? DarkTheme : LightTheme;

  const toggleTheme = () => {
    const next = isDark ? 'light' : 'dark';
    setPreference(next);
    AsyncStorage.setItem(THEME_STORAGE_KEY, next);
  };

  const setScheme = (mode: 'light' | 'dark' | 'system') => {
    setPreference(mode);
    AsyncStorage.setItem(THEME_STORAGE_KEY, mode);
  };

  return (
    <ThemeContext.Provider value={{ theme, isDark, toggleTheme, setScheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useAppTheme = () => useContext(ThemeContext);

