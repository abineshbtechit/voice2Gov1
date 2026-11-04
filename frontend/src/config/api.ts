/**
 * Centralized API Configuration for Voice2Gov Frontend.
 *
 * All frontend API calls MUST use this configuration.
 * Configured via EXPO_PUBLIC_API_URL in `frontend/.env`.
 *
 * Supported environments:
 * - Local development (Waydroid bridge): EXPO_PUBLIC_API_URL=http://192.168.240.1:8000
 * - Local development (LAN / Physical Android): EXPO_PUBLIC_API_URL=http://<YOUR_LAN_IP>:8000
 * - Team development: EXPO_PUBLIC_API_URL=https://dev-api.yourdomain.com
 * - Production: EXPO_PUBLIC_API_URL=https://api.yourdomain.com
 */

const rawApiUrl = process.env.EXPO_PUBLIC_API_URL;

if (!rawApiUrl || !rawApiUrl.trim()) {
  throw new Error(
    '[API Config Error] EXPO_PUBLIC_API_URL is missing.\n' +
      'Please create a "frontend/.env" file and define EXPO_PUBLIC_API_URL.\n' +
      'For Waydroid on Linux: EXPO_PUBLIC_API_URL=http://192.168.240.1:8000\n' +
      'For LAN / Physical Device: EXPO_PUBLIC_API_URL=http://<YOUR_LAN_IP>:8000\n' +
      'See frontend/.env.example for details.'
  );
}

// Normalize: preserve https/http scheme, remove repeated schemes and trailing slashes
const hasHttps = /^https:\/\//i.test(rawApiUrl.trim());
const strippedScheme = rawApiUrl.trim().replace(/^(https?:\/\/)+/i, '');
const normalizedHost = strippedScheme.replace(/\/+$/, '');
const sanitizedUrl = `${hasHttps ? 'https://' : 'http://'}${normalizedHost}`;

// Ensure /api/v1 is appended if not already present
export const API_BASE_URL: string = sanitizedUrl.endsWith('/api/v1')
  ? sanitizedUrl
  : `${sanitizedUrl}/api/v1`;

// Host origin URL without /api/v1 (useful for root health checks and static file URLs)
export const API_HOST_URL: string = sanitizedUrl.replace(/\/api\/v1$/, '');

// Default export as required by the centralized API configuration
export const API_URL: string = API_BASE_URL;
export default API_URL;
