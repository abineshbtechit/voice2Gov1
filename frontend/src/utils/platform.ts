import { NativeModules, Platform } from 'react-native';

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

export const getPlatformApiHost = (): string => {
  // Check if an explicit EXPO_PUBLIC_API_URL is provided (sanitize double http:// if any)
  const envUrl = process.env.EXPO_PUBLIC_API_URL;
  if (envUrl) {
    const cleaned = envUrl.replace(/^(https?:\/\/)+/, 'http://').replace(/\/+$/, '');
    if (cleaned && cleaned !== 'http://') {
      return cleaned;
    }
  }

  const host = getDynamicHost();
  return `http://${host}:8000/api/v1`;
};

