import { ApiClient } from './client';

export interface RegisterPayload {
  email: string;
  phone: string;
  password: string;
  full_name: string;
}

export interface LoginPayload {
  identifier: string;
  password: string;
  device_token?: string;
}

export const AuthApi = {
  register: (payload: RegisterPayload) =>
    ApiClient.post('/auth/register', payload),

  login: (payload: LoginPayload) =>
    ApiClient.post('/auth/login', payload),

  logout: () =>
    ApiClient.post('/auth/logout'),

  refresh: (refreshToken: string) =>
    ApiClient.post('/auth/refresh', { refresh_token: refreshToken }),

  forgotPassword: (identifier: string) =>
    ApiClient.post('/auth/forgot-password', { identifier }),

  verifyOtp: (identifier: string, otp: string) =>
    ApiClient.post('/auth/verify-otp', { identifier, otp }),

  resetPassword: (resetToken: string, newPassword: string) =>
    ApiClient.post('/auth/reset-password', {
      reset_token: resetToken,
      new_password: newPassword,
    }),

  getMe: () =>
    ApiClient.get('/auth/me'),
};

