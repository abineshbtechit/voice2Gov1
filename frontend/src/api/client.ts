import AsyncStorage from '@react-native-async-storage/async-storage';
import API_URL, { API_BASE_URL, API_HOST_URL } from '../config/api';

export const getApiBaseUrl = () => API_BASE_URL;
export { API_URL, API_BASE_URL, API_HOST_URL };

export const ACCESS_TOKEN_KEY = '@v2g_access_token';
export const REFRESH_TOKEN_KEY = '@v2g_refresh_token';
export const USER_INFO_KEY = '@v2g_user_info';

export interface ApiResponse<T = any> {
  success: boolean;
  message: string;
  data: T;
  error_code?: string;
  errors?: Array<{ field: string; message: string; code: string }>;
  details?: any;
}

/**
 * Diagnostic helper to format connection errors into human-friendly messages
 * with clear troubleshooting guidance.
 */
function formatNetworkError(error: any, url: string): { message: string; errorCode: string } {
  const errStr = String(error?.message || error || '');
  const base = API_BASE_URL;

  if (
    errStr.includes('ConnectException') ||
    errStr.includes('ECONNREFUSED') ||
    errStr.includes('Failed to connect')
  ) {
    return {
      message:
        `Connection refused to backend at ${base}.\n` +
        `• Ensure FastAPI is running on host 0.0.0.0:8000.\n` +
        `• If using Waydroid, set EXPO_PUBLIC_API_URL=http://192.168.240.1:8000.\n` +
        `• If using physical Android, set EXPO_PUBLIC_API_URL to your PC's LAN IP.`,
      errorCode: 'CONNECTION_REFUSED',
    };
  }

  if (
    errStr.includes('Timeout') ||
    errStr.includes('ETIMEDOUT') ||
    errStr.includes('AbortError')
  ) {
    return {
      message: `Connection timed out reaching backend at ${base}. Please verify network connectivity and firewall rules.`,
      errorCode: 'CONNECTION_TIMEOUT',
    };
  }

  return {
    message: `Network request failed connecting to ${base}. Please check device connectivity and backend status.`,
    errorCode: 'NETWORK_ERROR',
  };
}

export class ApiClient {
  private static async getAuthHeaders(): Promise<Record<string, string>> {
    const token = await AsyncStorage.getItem(ACCESS_TOKEN_KEY);
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  /**
   * Health check diagnostic helper
   */
  static async checkHealth(): Promise<{ ok: boolean; statusText: string; url: string; data?: any }> {
    const url = `${API_BASE_URL}/health`;
    try {
      const res = await fetch(url, { method: 'GET' });
      const data = await res.json().catch(() => null);
      return {
        ok: res.ok,
        statusText: `HTTP ${res.status}`,
        url,
        data,
      };
    } catch (err: any) {
      return {
        ok: false,
        statusText: err?.message || 'Network error',
        url,
      };
    }
  }

  static async request<T = any>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    const url = `${API_BASE_URL}${cleanEndpoint}`;
    const defaultHeaders = await this.getAuthHeaders();

    const config: RequestInit = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...(options.headers || {}),
      },
    };

    let response: Response;
    try {
      response = await fetch(url, config);
    } catch (networkError: any) {
      const diag = formatNetworkError(networkError, url);
      console.warn(`[ApiClient Network Error] ${diag.message} (Raw: ${networkError?.message})`);
      return {
        success: false,
        message: diag.message,
        error_code: diag.errorCode,
        data: null as any,
        details: {
          configuredApiUrl: API_BASE_URL,
          attemptedEndpoint: cleanEndpoint,
          error: networkError?.message,
        },
      };
    }

    // If 401 Unauthorized, attempt refresh token rotation
    if (response.status === 401 && !endpoint.includes('/auth/')) {
      const refreshed = await this.refreshToken();
      if (refreshed) {
        const retryHeaders = await this.getAuthHeaders();
        try {
          response = await fetch(url, {
            ...options,
            headers: {
              ...retryHeaders,
              ...(options.headers || {}),
            },
          });
        } catch (retryError: any) {
          const diag = formatNetworkError(retryError, url);
          return {
            success: false,
            message: diag.message,
            error_code: diag.errorCode,
            data: null as any,
          };
        }
      }
    }

    let data: any;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    if (response.ok) {
      if (typeof data === 'object' && data !== null) {
        return {
          success: data.success !== undefined ? Boolean(data.success) : true,
          message: data.message || 'Success',
          data: data.data !== undefined ? data.data : data,
          ...data,
        };
      }
      return {
        success: true,
        message: 'Success',
        data: data as T,
      };
    } else {
      if (typeof data === 'object' && data !== null) {
        return {
          success: false,
          message:
            data.message ||
            (data.errors && data.errors[0]?.message) ||
            `HTTP error ${response.status}`,
          error_code: data.error_code,
          errors: data.errors || [],
          data: data.data || null,
          details: data.details,
          ...data,
        };
      }
      return {
        success: false,
        message: `HTTP error ${response.status}`,
        data: null as any,
      };
    }
  }

  static async refreshToken(): Promise<boolean> {
    try {
      const refreshToken = await AsyncStorage.getItem(REFRESH_TOKEN_KEY);
      if (!refreshToken) return false;

      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      const res: ApiResponse<{ access_token: string; refresh_token: string }> =
        await response.json();

      if (res.success && res.data?.access_token) {
        await AsyncStorage.setItem(ACCESS_TOKEN_KEY, res.data.access_token);
        if (res.data.refresh_token) {
          await AsyncStorage.setItem(REFRESH_TOKEN_KEY, res.data.refresh_token);
        }
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }

  static async get<T = any>(endpoint: string) {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  static async post<T = any>(endpoint: string, body?: any) {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  static async put<T = any>(endpoint: string, body?: any) {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  static async patch<T = any>(endpoint: string, body?: any) {
    return this.request<T>(endpoint, {
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  static async delete<T = any>(endpoint: string) {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }

  static async uploadImages(complaintId: string, files: any[]) {
    try {
      const token = await AsyncStorage.getItem(ACCESS_TOKEN_KEY);
      const formData = new FormData();

      files.forEach((file, index) => {
        // @ts-ignore
        formData.append('files', {
          uri: file.uri,
          name: file.name || `evidence_${index}.jpg`,
          type: file.type || 'image/jpeg',
        });
      });
      formData.append('image_type', 'evidence');

      const res = await fetch(`${API_BASE_URL}/complaints/${complaintId}/images`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });
      let data: any;
      try {
        data = await res.json();
      } catch {
        data = null;
      }

      if (res.ok) {
        return {
          success: data?.success !== undefined ? Boolean(data.success) : true,
          message: data?.message || 'Images uploaded successfully',
          data: data?.data !== undefined ? data.data : data,
          ...data,
        };
      }
      return {
        success: false,
        message: data?.message || `Image upload failed (${res.status})`,
        errors: data?.errors || [],
        ...data,
      };
    } catch (err: any) {
      const diag = formatNetworkError(err, `${API_BASE_URL}/complaints/${complaintId}/images`);
      return {
        success: false,
        message: diag.message,
        errors: [],
      };
    }
  }
}
