import { NativeModules, Platform } from 'react-native';

export const isWeb = Platform.OS === 'web';
export const isIOS = Platform.OS === 'ios';
export const isAndroid = Platform.OS === 'android';

/**
 * Dynamically retrieves the API host.
 * 1. An explicit EXPO_PUBLIC_API_URL takes precedence if provided.
 * 2. In Web: uses window.location.origin (e.g. http://localhost:8081, http://192.168.1.79:8081, or https://xxx.exp.direct)
 *    which proxies /api/v1 directly to the FastAPI backend without CORS or blocked ports!
 * 3. In Native (Expo Go): uses Metro server host (from scriptURL) to route through Metro proxy.
 * 4. Fallback: http://localhost:8000/api/v1
 */
export const getPlatformApiHost = (): string => {
  const envUrl = process.env.EXPO_PUBLIC_API_URL;
  if (envUrl) {
    const isHttps = /^https:\/\//i.test(envUrl);
    const prefix = isHttps ? 'https://' : 'http://';
    let cleaned = envUrl.replace(/^(https?:\/\/)+/i, prefix).replace(/\/+$/, '');
    if (cleaned && cleaned !== prefix) {
      if (!cleaned.endsWith('/api/v1')) {
        cleaned = `${cleaned}/api/v1`;
      }
      return cleaned;
    }
  }

  if (isWeb && typeof window !== 'undefined' && window.location?.origin) {
    return `${window.location.origin}/api/v1`;
  }

  const scriptURL = NativeModules.SourceCode?.scriptURL;
  if (scriptURL) {
    const match = scriptURL.match(/^(https?:\/\/[^/]+)/);
    if (match && match[1]) {
      return `${match[1]}/api/v1`;
    }
  }

  return 'http://localhost:8000/api/v1';
};
