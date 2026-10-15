import AsyncStorage from '@react-native-async-storage/async-storage';
import { getPlatformApiHost } from '../utils/platform';

const API_BASE_URL = getPlatformApiHost();

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

  static async request<T = any>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const url = `${API_BASE_URL}${endpoint}`;
    const defaultHeaders = await this.getAuthHeaders();

    const config: RequestInit = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...(options.headers || {}),
      },
    };

    let response = await fetch(url, config);

    // If 401 Unauthorized, attempt refresh token rotation
    if (response.status === 401 && !endpoint.includes('/auth/')) {
      const refreshed = await this.refreshToken();
      if (refreshed) {
        const retryHeaders = await this.getAuthHeaders();
        response = await fetch(url, {
          ...options,
          headers: {
            ...retryHeaders,
            ...(options.headers || {}),
          },
        });
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
  }
}

