import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';
import { ApiClient } from '../../api/client';
import { CloudBG } from '../../components/common/Backgrounds';
import { BigCTA, TextField } from '../../components/common/UIComponents';
import { Icons } from '../../components/common/Icons';

import { normalizeLoginIdentifier, parseAuthBackendError } from '../../utils/validation';

interface LoginScreenProps {
  onBack: () => void;
  onSuccess: () => void;
  onNavigateToVerification?: (data: {
    identifier: string;
    email?: string;
    phone?: string;
    fullName?: string;
  }) => void;
}

export const LoginScreen: React.FC<LoginScreenProps> = ({
  onBack,
  onSuccess,
  onNavigateToVerification,
}) => {
  const { theme, isDark } = useAppTheme();
  const { login } = useAuth();

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async () => {
    const trimmed = identifier.trim();
    if (!trimmed || !password) {
      setError('Please provide your email/phone and password');
      return;
    }
    setError(null);
    setLoading(true);

    try {
      const normalizedIdentifier = normalizeLoginIdentifier(trimmed);

      const res = await ApiClient.post('/auth/login', {
        identifier: normalizedIdentifier,
        password,
      });

      const loginData = res.data || (res as any);
      if (res.success && loginData?.access_token) {
        await login(loginData.access_token, loginData.refresh_token, loginData.user);
        onSuccess();
      } else {
        const parsed = parseAuthBackendError(res);
        if (
          res.error_code === 'PENDING_VERIFICATION' ||
          (res.message && res.message.toLowerCase().includes('verification'))
        ) {
          if (onNavigateToVerification) {
            onNavigateToVerification({
              identifier: normalizedIdentifier,
              email: res.details?.email || (normalizedIdentifier.includes('@') ? normalizedIdentifier : undefined),
              phone: res.details?.phone || (!normalizedIdentifier.includes('@') ? normalizedIdentifier : undefined),
              fullName: res.details?.full_name,
            });
            return;
          }
        }
        setError(parsed.message || 'Login failed. Please check your credentials.');
      }
    } catch (e: any) {
      setError(e?.message || 'Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <CloudBG isDark={isDark} opacity={0.65} />

      {/* Top Header */}
      <View style={styles.topHeader}>
        <TouchableOpacity
          onPress={onBack}
          style={[
            styles.backBtn,
            {
              backgroundColor: theme.glassBg,
              borderColor: theme.glassBorder,
            },
          ]}
        >
          <Icons.arrowLeft size={18} color={theme.fg} />
        </TouchableOpacity>
      </View>

      {/* Form Content */}
      <View style={styles.content}>
        <Text style={[styles.title, { color: theme.fg }]}>
          Sign in to your{'\n'}account.
        </Text>
        <Text style={[styles.sub, { color: theme.fgMuted }]}>
          Enter your registered email, mobile number, or name to sign in.
        </Text>

        <View style={styles.formFields}>
          <TextField
            placeholder="Email, phone, or name"
            value={identifier}
            onChangeText={setIdentifier}
            autoFocus
          />
          <View style={{ height: 12 }} />
          <TextField
            placeholder="Password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
          />
        </View>

        {error && (
          <Text style={[styles.errorText, { color: '#E5484D' }]}>{error}</Text>
        )}
      </View>

      {/* Bottom CTA */}
      <View style={styles.bottomCta}>
        <BigCTA
          onPress={handleLogin}
          disabled={loading || !identifier || !password}
          icon={loading ? <ActivityIndicator size="small" color={theme.ctaFg} /> : <Icons.arrowRight size={18} color={theme.ctaFg} />}
        >
          {loading ? 'Signing in...' : 'Sign in'}
        </BigCTA>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    position: 'relative',
    justifyContent: 'space-between',
  },
  topHeader: {
    marginTop: 64,
    paddingHorizontal: 20,
  },
  backBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth,
  },
  content: {
    paddingHorizontal: 28,
  },
  title: {
    fontSize: 34,
    fontWeight: '700',
    letterSpacing: -1,
    lineHeight: 38,
  },
  sub: {
    fontSize: 15,
    marginTop: 10,
    letterSpacing: -0.2,
    lineHeight: 22,
  },
  formFields: {
    marginTop: 28,
  },
  errorText: {
    fontSize: 13,
    marginTop: 12,
    fontWeight: '500',
  },
  bottomCta: {
    paddingHorizontal: 20,
    paddingBottom: 40,
  },
});

