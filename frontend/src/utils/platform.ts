import { NativeModules, Platform } from 'react-native';

import API_URL from '../config/api';

export const isWeb = Platform.OS === 'web';
export const isIOS = Platform.OS === 'ios';
export const isAndroid = Platform.OS === 'android';

/**
 * Dynamically retrieves the development host IP address.
 * 1. Web: uses window.location.hostname (works on localhost or LAN)
 * 2. Expo Go (Mobile): dynamically extracts PC's connected IP from Metro bundler's scriptURL
 * 3. Fallback: 'localhost'
 */
export const getDynamicHost = (): string => {
  if (isWeb) {
    if (typeof window !== 'undefined' && window.location?.hostname) {
      return window.location.hostname;
    }
    return 'localhost';
  }

  const scriptURL = NativeModules.SourceCode?.scriptURL;
  if (scriptURL) {
    const match = scriptURL.match(/https?:\/\/([^:/]+)/);
    if (match && match[1] && match[1] !== 'localhost' && match[1] !== '127.0.0.1') {
      return match[1];
    }
  }

  return 'localhost';
};

/**
 * Returns the centralized API Base URL.
 * All API networking routes through frontend/src/config/api.ts.
 */
export const getPlatformApiHost = (): string => {
  return API_URL;
};

