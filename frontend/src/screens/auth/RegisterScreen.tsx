import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';
import { ApiClient } from '../../api/client';
import { CloudBG } from '../../components/common/Backgrounds';
import { BigCTA, TextField } from '../../components/common/UIComponents';
import { Icons } from '../../components/common/Icons';

interface RegisterScreenProps {
  onBack: () => void;
  onSuccess: () => void;
}

export const RegisterScreen: React.FC<RegisterScreenProps> = ({ onBack, onSuccess }) => {
  const { theme, isDark } = useAppTheme();
  const { login } = useAuth();

  // Multi-step Apple setup
  const [step, setStep] = useState(1);
  const totalSteps = 4;

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleNext = async () => {
    setError(null);

    if (step === 1) {
      if (!fullName.trim()) return setError('Please enter your full name');
      return setStep(2);
    }

    if (step === 2) {
      if (!email.trim() || !phone.trim()) return setError('Please enter both email and phone number');
      return setStep(3);
    }

    if (step === 3) {
      if (!password || password.length < 8) return setError('Password must be at least 8 characters');
      setLoading(true);

      try {
        const res = await ApiClient.post('/auth/register', {
          full_name: fullName,
          email,
          phone,
          password,
        });

        if (res.success) {
          // Advance to OTP verification
          setStep(4);
        } else {
          setError(res.message || 'Registration failed');
        }
      } catch (e: any) {
        setError(e?.message || 'Network error');
      } finally {
        setLoading(false);
      }
      return;
    }

    if (step === 4) {
      if (!otp || otp.length < 4) return setError('Please enter the verification code');
      setLoading(true);

      try {
        const verifyRes = await ApiClient.post('/auth/verify-otp', {
          identifier: email,
          otp,
        });

        if (verifyRes.success) {
          // Login automatically
          const loginRes = await ApiClient.post('/auth/login', {
            identifier: email,
            password,
          });
          if (loginRes.success && loginRes.data) {
            await login(loginRes.data.access_token, loginRes.data.refresh_token, loginRes.data.user);
            onSuccess();
          } else {
            onSuccess();
          }
        } else {
          setError(verifyRes.message || 'Invalid code');
        }
      } catch (e: any) {
        setError(e?.message || 'Verification error');
      } finally {
        setLoading(false);
      }
    }
  };

  const handleStepBack = () => {
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
                placeholder="email@example.com"
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoFocus
              />
              <TextField
                placeholder="+91 98765 43210"
                value={phone}
                onChangeText={setPhone}
                keyboardType="phone-pad"
              />
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
            <View style={{ marginTop: 28 }}>
              <TextField
                placeholder="Password (min 8 chars)"
                value={password}
                onChangeText={setPassword}
                secureTextEntry
                autoFocus
              />
            </View>
          </>
        )}

        {step === 4 && (
          <>
            <Text style={[styles.title, { color: theme.fg }]}>
              Enter the code{'\n'}we sent.
            </Text>
            <Text style={[styles.sub, { color: theme.fgMuted }]}>
              Check your email/messages for the 6-digit confirmation code.
            </Text>
            <View style={{ marginTop: 28 }}>
              <TextField
                placeholder="123456"
                value={otp}
                onChangeText={setOtp}
                keyboardType="number-pad"
                autoFocus
              />
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
          icon={loading ? <ActivityIndicator size="small" color={theme.ctaFg} /> : <Icons.arrowRight size={18} color={theme.ctaFg} />}
        >
          {step === 4 ? (loading ? 'Verifying...' : 'Complete setup') : (loading ? 'Submitting...' : 'Continue')}
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

