import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';
import { ApiClient } from '../../api/client';
import { CloudBG } from '../../components/common/Backgrounds';
import { BigCTA, TextField } from '../../components/common/UIComponents';
import { Icons } from '../../components/common/Icons';
import {
  normalizePhoneNumber,
  isValidE164Phone,
  isValidEmail,
  validatePasswordPolicy,
  parseAuthBackendError,
} from '../../utils/validation';

interface RegisterScreenProps {
  onBack: () => void;
  onSuccess: () => void;
  onNavigateToVerification?: (data: {
    identifier: string;
    email?: string;
    phone?: string;
    fullName?: string;
  }) => void;
}

export const RegisterScreen: React.FC<RegisterScreenProps> = ({
  onBack,
  onSuccess,
  onNavigateToVerification,
}) => {
  const { theme, isDark } = useAppTheme();
  const { login } = useAuth();

  // Multi-step Apple setup
  const [step, setStep] = useState(1);
  const totalSteps = 4;

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleNext = async () => {
    setError(null);

    // Step 1: Full name
    if (step === 1) {
      const trimmedName = fullName.trim();
      if (!trimmedName) {
        return setError('Please enter your full name');
      }
      if (trimmedName.length < 2) {
        return setError('Full name must be at least 2 characters');
      }
      return setStep(2);
    }

    // Step 2: Contact Info (Email & E.164 Phone)
    if (step === 2) {
      const cleanEmail = email.trim().toLowerCase();
      if (!cleanEmail) {
        return setError('Please enter your email address');
      }
      if (!isValidEmail(cleanEmail)) {
        return setError('Please enter a valid email address (e.g. name@example.com)');
      }

      const normalizedPhone = normalizePhoneNumber(phone);
      if (!normalizedPhone) {
        return setError('Please enter your phone number');
      }
      if (!isValidE164Phone(normalizedPhone)) {
        return setError('Please enter a valid phone number with country code (e.g. +919876543210)');
      }

      // Update state with normalized values
      setEmail(cleanEmail);
      setPhone(normalizedPhone);
      return setStep(3);
    }

    // Step 3: Password & Account Registration
    if (step === 3) {
      const pwdPolicy = validatePasswordPolicy(password);
      if (!pwdPolicy.isValid) {
        return setError(pwdPolicy.errors[0]);
      }

      if (!confirmPassword) {
        return setError('Please confirm your password');
      }

      if (password !== confirmPassword) {
        return setError('Passwords do not match. Please re-enter.');
      }

      setLoading(true);

      const cleanName = fullName.trim();
      const cleanEmail = email.trim().toLowerCase();
      const cleanPhone = normalizePhoneNumber(phone);

      try {
        const res = await ApiClient.post('/auth/register', {
          full_name: cleanName,
          email: cleanEmail,
          phone: cleanPhone,
          password,
        });

        if (res.success) {
          // Advance to completed step
          setStep(4);
        } else {
          const parsed = parseAuthBackendError(res);
          setError(parsed.message);
          if (parsed.targetStep) {
            setStep(parsed.targetStep);
          }
        }
      } catch (e: any) {
        setError(e?.message || 'Network error. Please try again.');
      } finally {
        setLoading(false);
      }
      return;
    }

    // Step 4: Finalize & Navigate to OTP Verification
    if (step === 4) {
      const cleanEmail = email.trim().toLowerCase();
      const cleanPhone = normalizePhoneNumber(phone);
      if (onNavigateToVerification) {
        onNavigateToVerification({
          identifier: cleanEmail,
          email: cleanEmail,
          phone: cleanPhone,
          fullName: fullName.trim(),
        });
      } else {
        onSuccess();
      }
      return;
    }
  };

  const handleStepBack = () => {
    setError(null);
    if (step > 1) {
      setStep(step - 1);
    } else {
      onBack();
    }
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <CloudBG isDark={isDark} opacity={0.7} />

      {/* Progress Top Bar */}
      <View style={styles.topBar}>
        <TouchableOpacity
          onPress={handleStepBack}
          style={[
            styles.circleBtn,
            {
              backgroundColor: theme.glassBg,
              borderColor: theme.glassBorder,
            },
          ]}
        >
          <Icons.arrowLeft size={16} color={theme.fg} />
        </TouchableOpacity>

        {/* Progress track */}
        <View
          style={[
            styles.progressTrack,
            { backgroundColor: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)' },
          ]}
        >
          <View
            style={[
              styles.progressBar,
              {
                width: `${(step / totalSteps) * 100}%`,
                backgroundColor: theme.fg,
              },
            ]}
          />
        </View>

        <Text style={[styles.stepCount, { color: theme.fgMuted }]}>
          {step}/{totalSteps}
        </Text>
      </View>

      {/* Step Content */}
      <View style={styles.stepBody}>
        {step === 1 && (
          <>
            <Text style={[styles.title, { color: theme.fg }]}>
              What should we{'\n'}call you?
            </Text>
            <Text style={[styles.sub, { color: theme.fgMuted }]}>
              Your name appears on complaints so departments know who to respond to.
            </Text>
            <View style={{ marginTop: 28 }}>
              <TextField
                placeholder="Aarav Sharma"
                value={fullName}
                onChangeText={setFullName}
                autoFocus
              />
            </View>
          </>
        )}

        {step === 2 && (
          <>
            <Text style={[styles.title, { color: theme.fg }]}>
              Your contact{'\n'}information.
            </Text>
            <Text style={[styles.sub, { color: theme.fgMuted }]}>
              Used to send official progress alerts and verify identity.
            </Text>
            <View style={{ marginTop: 28, gap: 12 }}>
              <TextField
                placeholder="name@example.com"
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoCapitalize="none"
                autoFocus
              />
              <TextField
                placeholder="+919876543210"
                value={phone}
                onChangeText={setPhone}
                keyboardType="phone-pad"
              />
              <Text style={[styles.helperText, { color: theme.fgMuted }]}>
                Include country code (e.g. +91 for India, +1 for US)
              </Text>
            </View>
          </>
        )}

        {step === 3 && (
          <>
            <Text style={[styles.title, { color: theme.fg }]}>
              Create a secure{'\n'}password.
            </Text>
            <Text style={[styles.sub, { color: theme.fgMuted }]}>
              Must be at least 8 characters to safeguard your civic account.
            </Text>
            <View style={{ marginTop: 24 }}>
              <TextField
                placeholder="Create password"
                value={password}
                onChangeText={(val) => {
                  setPassword(val);
                  if (error) setError(null);
                }}
                secureTextEntry
                autoFocus
              />
              <View style={{ height: 12 }} />
              <TextField
                placeholder="Confirm password"
                value={confirmPassword}
                onChangeText={(val) => {
                  setConfirmPassword(val);
                  if (error) setError(null);
                }}
                secureTextEntry
              />

              {confirmPassword.length > 0 && (
                <View style={{ marginTop: 8, paddingHorizontal: 4 }}>
                  <Text
                    style={{
                      fontSize: 12,
                      fontWeight: '600',
                      color: password === confirmPassword ? '#2FBF71' : '#E5484D',
                    }}
                  >
                    {password === confirmPassword
                      ? '✓ Passwords match'
                      : '• Passwords do not match'}
                  </Text>
                </View>
              )}

              <View style={styles.pwdHints}>
                <Text
                  style={[
                    styles.pwdHintItem,
                    { color: password.length >= 8 ? '#2FBF71' : theme.fgMuted },
                  ]}
                >
                  • At least 8 characters
                </Text>
                <Text
                  style={[
                    styles.pwdHintItem,
                    {
                      color:
                        /[A-Z]/.test(password) && /[a-z]/.test(password)
                          ? '#2FBF71'
                          : theme.fgMuted,
                    },
                  ]}
                >
                  • Uppercase & lowercase
                </Text>
                <Text
                  style={[
                    styles.pwdHintItem,
                    { color: /\d/.test(password) ? '#2FBF71' : theme.fgMuted },
                  ]}
                >
                  • At least one number
                </Text>
                <Text
                  style={[
                    styles.pwdHintItem,
                    {
                      color: /[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]/.test(password)
                        ? '#2FBF71'
                        : theme.fgMuted,
                    },
                  ]}
                >
                  • Special character (!@#$)
                </Text>
              </View>
            </View>
          </>
        )}

        {step === 4 && (
          <>
            <Text style={[styles.title, { color: theme.fg }]}>
              Welcome to{'\n'}Voice2Gov.
            </Text>
            <Text style={[styles.sub, { color: theme.fgMuted }]}>
              Your account has been registered for {fullName || 'Citizen'}.
            </Text>
            <View style={{ marginTop: 28 }}>
              <View
                style={[
                  styles.successCard,
                  {
                    backgroundColor: theme.glassBg,
                    borderColor: theme.glassBorder,
                  },
                ]}
              >
                <View style={styles.successRow}>
                  <Icons.check size={22} color="#2FBF71" />
                  <Text style={[styles.successText, { color: theme.fg }]}>
                    Registration submitted
                  </Text>
                </View>
                <Text style={[styles.successDetail, { color: theme.fgMuted }]}>
                  Email: {email}
                </Text>
                <Text style={[styles.successDetail, { color: theme.fgMuted }]}>
                  Phone: {normalizePhoneNumber(phone)}
                </Text>
                <Text style={[styles.successNote, { color: theme.fgFaint }]}>
                  Click continue below to enter your account.
                </Text>
              </View>
            </View>
          </>
        )}

        {error && (
          <Text style={[styles.errorText, { color: '#E5484D' }]}>{error}</Text>
        )}
      </View>

      {/* Bottom CTA */}
      <View style={styles.bottomCta}>
        <BigCTA
          onPress={handleNext}
          disabled={loading}
          icon={
            loading ? (
              <ActivityIndicator size="small" color={theme.ctaFg} />
            ) : (
              <Icons.arrowRight size={18} color={theme.ctaFg} />
            )
          }
        >
          {step === 4
            ? 'Verify Account with OTP'
            : step === 3
            ? loading
              ? 'Creating account...'
              : 'Create account'
            : 'Continue'}
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
  topBar: {
    marginTop: 68,
    paddingHorizontal: 20,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  circleBtn: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth,
  },
  progressTrack: {
    flex: 1,
    height: 4,
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressBar: {
    height: '100%',
    borderRadius: 2,
  },
  stepCount: {
    fontSize: 12,
    fontWeight: '600',
    minWidth: 32,
    textAlign: 'right',
  },
  stepBody: {
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
  helperText: {
    fontSize: 12,
    marginTop: 4,
    paddingHorizontal: 4,
  },
  pwdHints: {
    marginTop: 14,
    paddingHorizontal: 4,
    gap: 4,
  },
  pwdHintItem: {
    fontSize: 12,
    fontWeight: '500',
  },
  successCard: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: 16,
    padding: 20,
    gap: 8,
  },
  successRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 4,
  },
  successText: {
    fontSize: 16,
    fontWeight: '600',
    letterSpacing: -0.3,
  },
  successDetail: {
    fontSize: 13,
  },
  successNote: {
    fontSize: 12,
    marginTop: 6,
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
