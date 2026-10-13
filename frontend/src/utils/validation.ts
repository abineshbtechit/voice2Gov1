/**
 * Input validation, normalization, and backend error parsing utilities
 * for Voice2Gov authentication & user profile management.
 */

// Matches ITU-T E.164 phone number pattern enforced by backend: ^\+[1-9]\d{1,14}$
export const E164_PHONE_REGEX = /^\+[1-9]\d{1,14}$/;

// Standard RFC-compliant email pattern
export const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Backend password special characters
export const SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?";

/**
 * Normalizes user input into a clean E.164 phone string.
 * Strips whitespace, hyphens, brackets, dots, etc.
 * Auto-prefixes +91 for standard 10-digit Indian numbers.
 */
export function normalizePhoneNumber(raw: string): string {
  if (!raw) return '';
  const trimmed = raw.trim();

  // If already starts with '+', keep '+' and strip any non-digits thereafter
  if (trimmed.startsWith('+')) {
    const digits = trimmed.slice(1).replace(/\D/g, '');
    return `+${digits}`;
  }

  // Strip all non-digit characters
  const digitsOnly = trimmed.replace(/\D/g, '');
  if (!digitsOnly) return trimmed;

  // 10 digits (Standard Indian mobile number without country code)
  if (digitsOnly.length === 10) {
    return `+91${digitsOnly}`;
  }

  // 11 digits starting with 0 (e.g. 09876543210)
  if (digitsOnly.length === 11 && digitsOnly.startsWith('0')) {
    return `+91${digitsOnly.slice(1)}`;
  }

  // 12 digits starting with 91 (e.g. 919876543210 without +)
  if (digitsOnly.length === 12 && digitsOnly.startsWith('91')) {
    return `+${digitsOnly}`;
  }

  // General fallback: prepend +
  return `+${digitsOnly}`;
}

/**
 * Normalizes login identifier (email or phone number).
 * - If contains '@', converts to lowercase trimmed email.
 * - If starts with '+' or has at least 7 digits, normalizes to E.164 phone.
 * - Otherwise preserves trimmed input, guaranteeing non-empty string is sent.
 */
export function normalizeLoginIdentifier(input: string): string {
  const trimmed = input.trim();
  if (!trimmed) return '';

  if (trimmed.includes('@')) {
    return trimmed.toLowerCase();
  }

  const digits = trimmed.replace(/\D/g, '');
  if (trimmed.startsWith('+') || digits.length >= 7) {
    const normalized = normalizePhoneNumber(trimmed);
    if (normalized) return normalized;
  }

  return trimmed;
}

/**
 * Checks if a string satisfies E.164 format.
 */
export function isValidE164Phone(phone: string): boolean {
  return E164_PHONE_REGEX.test(phone);
}

/**
 * Checks if a string is a valid email address.
 */
export function isValidEmail(email: string): boolean {
  return EMAIL_REGEX.test(email.trim());
}

export interface PasswordPolicyResult {
  isValid: boolean;
  errors: string[];
}

/**
 * Validates password against the backend security policy.
 * Requirements:
 * - 8 to 72 characters
 * - At least one uppercase letter (A-Z)
 * - At least one lowercase letter (a-z)
 * - At least one digit (0-9)
 * - At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
 */
export function validatePasswordPolicy(password: string): PasswordPolicyResult {
  const errors: string[] = [];

  if (!password || password.length < 8) {
    errors.push('Password must be at least 8 characters long');
  }

  if (password && password.length > 72) {
    errors.push('Password must not exceed 72 characters');
  }

  if (!/[A-Z]/.test(password)) {
    errors.push('Must contain at least one uppercase letter (A-Z)');
  }

  if (!/[a-z]/.test(password)) {
    errors.push('Must contain at least one lowercase letter (a-z)');
  }

  if (!/\d/.test(password)) {
    errors.push('Must contain at least one number (0-9)');
  }

  const hasSpecial = password.split('').some((char) => SPECIAL_CHARS.includes(char));
  if (!hasSpecial) {
    errors.push('Must contain at least one special character (!@#$%^&*...)');
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}

export interface ParsedBackendError {
  message: string;
  targetStep?: number;
}

/**
 * Translates backend API responses (including 422 validation errors,
 * 409 conflicts, and 401 unauth) into user-friendly messages and target steps.
 */
export function parseAuthBackendError(res: {
  success?: boolean;
  message?: string;
  error_code?: string;
  errors?: Array<{ field: string; message: string; code: string }>;
}): ParsedBackendError {
  // Check field-specific validation errors first
  if (res.errors && res.errors.length > 0) {
    const first = res.errors[0];
    const field = first.field.toLowerCase();

    if (field.includes('phone')) {
      return {
        message:
          'Please enter a valid phone number in international format (e.g. +919876543210).',
        targetStep: 2,
      };
    }

    if (field.includes('email')) {
      return {
        message: 'Please enter a valid email address (e.g. user@example.com).',
        targetStep: 2,
      };
    }

    if (field.includes('full_name') || field.includes('name')) {
      return {
        message: 'Please enter a valid full name (1 to 255 characters).',
        targetStep: 1,
      };
    }

    if (field.includes('identifier')) {
      return {
        message: 'Please enter your registered email or phone number.',
      };
    }

    if (field.includes('password')) {
      return {
        message:
          'Password requires at least 8 characters with uppercase, lowercase, digit, and a special character.',
        targetStep: 3,
      };
    }

    return {
      message: first.message || 'Validation failed. Please check your information.',
    };
  }

  const rawMsg = res.message || '';
  const lowerMsg = rawMsg.toLowerCase();

  // Handle duplicate conflict errors
  if (lowerMsg.includes('email already registered')) {
    return {
      message: 'This email is already registered. Please sign in or use a different email.',
      targetStep: 2,
    };
  }

  if (lowerMsg.includes('phone number already registered') || lowerMsg.includes('phone already registered')) {
    return {
      message: 'This phone number is already registered. Please sign in or use a different number.',
      targetStep: 2,
    };
  }

  if (lowerMsg.includes('account is not active') || res.error_code === 'ACCOUNT_INACTIVE') {
    return {
      message: 'Account is pending administrative verification. Please wait for activation.',
    };
  }

  if (lowerMsg.includes('invalid credentials') || res.error_code === 'INVALID_CREDENTIALS') {
    return {
      message: 'Invalid credentials. Please verify your email/phone and password.',
    };
  }

  if (lowerMsg.includes('account temporarily locked') || res.error_code === 'ACCOUNT_LOCKED') {
    return {
      message: 'Account is temporarily locked due to multiple failed login attempts. Please try again later.',
    };
  }

  return {
    message: rawMsg || 'An unexpected error occurred. Please try again.',
  };
}
