import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  TextInput,
  ScrollView,
} from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { AuthApi } from '../../api/auth';
import { CloudBG } from '../../components/common/Backgrounds';
import { GlassCard, BigCTA } from '../../components/common/UIComponents';
import { Icons } from '../../components/common/Icons';
import { Radius } from '../../theme/tokens';

interface ForgotPasswordScreenProps {
  onBack: () => void;
  onSuccess: () => void;
}

type RecoveryStep = 'request_otp' | 'verify_otp' | 'new_password' | 'completed';

export const ForgotPasswordScreen: React.FC<ForgotPasswordScreenProps> = ({
  onBack,
  onSuccess,
}) => {
  const { theme, isDark } = useAppTheme();

  const [step, setStep] = useState<RecoveryStep>('request_otp');
  const [identifier, setIdentifier] = useState('');
  const [otp, setOtp] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);

  // 1. Request recovery OTP
  const handleRequestOTP = async () => {
    if (!identifier.trim()) {
      setError('Please enter your registered email or phone.');
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await AuthApi.forgotPassword(identifier.trim());
      if (res.success) {
        setInfoMessage(res.message || 'OTP sent to your registered email/phone.');
        setStep('verify_otp');
      } else {
        setError(res.message || 'Failed to send OTP. Please check your identifier.');
      }
    } catch (e: any) {
      setError(e?.message || 'Network error while requesting recovery code.');
    } finally {
      setLoading(false);
    }
  };

  // 2. Verify OTP code
  const handleVerifyOTP = async () => {
    if (otp.trim().length < 6) {
      setError('Please enter the full 6-digit OTP.');
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await AuthApi.verifyOtp(identifier.trim(), otp.trim());
      if (res.success && res.data?.reset_token) {
        setResetToken(res.data.reset_token);
        setInfoMessage('Code verified! Enter your new password.');
        setStep('new_password');
      } else {
        setError(res.message || 'Invalid or expired OTP code.');
      }
    } catch (e: any) {
      setError(e?.message || 'Verification failed. Try again.');
    } finally {
      setLoading(false);
    }
  };

  // 3. Reset password
  const handleResetPassword = async () => {
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await AuthApi.resetPassword(resetToken, newPassword);
      if (res.success) {
        setStep('completed');
      } else {
        setError(res.message || 'Failed to reset password. Token may have expired.');
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to reset password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <CloudBG isDark={isDark} opacity={0.6} />

      {/* Header */}
      <View style={styles.topHeader}>
        <TouchableOpacity
          onPress={onBack}
          style={[
            styles.backBtn,
            { backgroundColor: theme.glassBg, borderColor: theme.glassBorder },
          ]}
        >
          <Icons.arrowLeft size={18} color={theme.fg} />
        </TouchableOpacity>
        <Text style={[styles.screenHeaderTitle, { color: theme.fg }]}>
          Password Recovery
        </Text>
        <View style={{ width: 38 }} />
      </View>

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {step === 'request_otp' && (
          <>
            <Text style={[styles.title, { color: theme.fg }]}>Forgot Password?</Text>
            <Text style={[styles.sub, { color: theme.fgMuted }]}>
              Enter your registered email address or phone number to receive a 6-digit recovery code.
            </Text>

            <GlassCard padding={16} radius={Radius.lg} style={{ marginTop: 24 }}>
              <Text style={[styles.inputLabel, { color: theme.fgMuted }]}>Email or Mobile Number</Text>
              <TextInput
                value={identifier}
                onChangeText={(t) => {
                  setIdentifier(t);
                  setError(null);
                }}
                placeholder="citizen@example.com or 9876543210"
                placeholderTextColor={theme.fgMuted}
                autoCapitalize="none"
                style={[styles.input, { color: theme.fg, borderColor: theme.glassBorder }]}
              />
            </GlassCard>

            {error && <Text style={[styles.errorText, { color: '#FF4D4F' }]}>{error}</Text>}

            <View style={{ marginTop: 32 }}>
              <BigCTA
                onPress={handleRequestOTP}
                disabled={loading || !identifier.trim()}
                icon={loading ? <ActivityIndicator size="small" color={theme.ctaFg} /> : <Icons.arrowRight size={18} color={theme.ctaFg} />}
              >
                {loading ? 'Sending Code...' : 'Send Recovery Code'}
              </BigCTA>
            </View>
          </>
        )}

        {step === 'verify_otp' && (
          <>
            <Text style={[styles.title, { color: theme.fg }]}>Enter Recovery Code</Text>
            <Text style={[styles.sub, { color: theme.fgMuted }]}>
              We sent a 6-digit verification code to <Text style={{ fontWeight: '700', color: theme.fg }}>{identifier}</Text>.
            </Text>

            <GlassCard padding={16} radius={Radius.lg} style={{ marginTop: 24 }}>
              <Text style={[styles.inputLabel, { color: theme.fgMuted }]}>6-Digit OTP</Text>
              <TextInput
                value={otp}
                onChangeText={(t) => {
                  setOtp(t);
                  setError(null);
                }}
                keyboardType="number-pad"
                maxLength={6}
                placeholder="000000"
                placeholderTextColor={theme.fgMuted}
                style={[
                  styles.input,
                  {
                    color: theme.fg,
                    borderColor: theme.glassBorder,
                    fontSize: 24,
                    letterSpacing: 6,
                    textAlign: 'center',
                  },
                ]}
              />
            </GlassCard>

            {infoMessage && <Text style={[styles.infoText, { color: '#2FBF71' }]}>{infoMessage}</Text>}
            {error && <Text style={[styles.errorText, { color: '#FF4D4F' }]}>{error}</Text>}

            <View style={{ marginTop: 32 }}>
              <BigCTA
                onPress={handleVerifyOTP}
                disabled={loading || otp.length < 6}
                icon={loading ? <ActivityIndicator size="small" color={theme.ctaFg} /> : <Icons.arrowRight size={18} color={theme.ctaFg} />}
              >
                {loading ? 'Verifying...' : 'Verify Code'}
              </BigCTA>
            </View>

            <TouchableOpacity
              onPress={handleRequestOTP}
              style={{ alignItems: 'center', marginTop: 16 }}
            >
              <Text style={{ fontSize: 13, color: theme.fgMuted }}>
                Didn't receive code? <Text style={{ color: theme.fg, fontWeight: '600' }}>Resend</Text>
              </Text>
            </TouchableOpacity>
          </>
        )}

        {step === 'new_password' && (
          <>
            <Text style={[styles.title, { color: theme.fg }]}>Set New Password</Text>
            <Text style={[styles.sub, { color: theme.fgMuted }]}>
              Choose a strong password with at least 8 characters.
            </Text>

            <GlassCard padding={16} radius={Radius.lg} style={{ marginTop: 24 }}>
              <Text style={[styles.inputLabel, { color: theme.fgMuted }]}>New Password</Text>
              <TextInput
                value={newPassword}
                onChangeText={(t) => {
                  setNewPassword(t);
                  setError(null);
                }}
                secureTextEntry
                placeholder="Min 8 characters"
                placeholderTextColor={theme.fgMuted}
                style={[styles.input, { color: theme.fg, borderColor: theme.glassBorder }]}
              />

              <Text style={[styles.inputLabel, { color: theme.fgMuted, marginTop: 14 }]}>
                Confirm Password
              </Text>
              <TextInput
                value={confirmPassword}
                onChangeText={(t) => {
                  setConfirmPassword(t);
                  setError(null);
                }}
                secureTextEntry
                placeholder="Repeat new password"
                placeholderTextColor={theme.fgMuted}
                style={[styles.input, { color: theme.fg, borderColor: theme.glassBorder }]}
              />
            </GlassCard>

            {error && <Text style={[styles.errorText, { color: '#FF4D4F' }]}>{error}</Text>}

            <View style={{ marginTop: 32 }}>
              <BigCTA
                onPress={handleResetPassword}
                disabled={loading || !newPassword || !confirmPassword}
                icon={loading ? <ActivityIndicator size="small" color={theme.ctaFg} /> : <Icons.arrowRight size={18} color={theme.ctaFg} />}
              >
                {loading ? 'Updating Password...' : 'Save New Password'}
              </BigCTA>
            </View>
          </>
        )}

        {step === 'completed' && (
          <View style={{ alignItems: 'center', marginTop: 40 }}>
            <View
              style={{
                width: 68,
                height: 68,
                borderRadius: 34,
                backgroundColor: 'rgba(47, 191, 113, 0.15)',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: 20,
              }}
            >
              <Icons.check size={32} color="#2FBF71" />
            </View>
            <Text style={[styles.title, { color: theme.fg, textAlign: 'center' }]}>
              Password Reset!
            </Text>
            <Text style={[styles.sub, { color: theme.fgMuted, textAlign: 'center' }]}>
              Your password has been securely updated. You can now log in with your new credentials.
            </Text>

            <View style={{ width: '100%', marginTop: 32 }}>
              <BigCTA onPress={onSuccess} icon={<Icons.arrowRight size={18} color={theme.ctaFg} />}>
                Proceed to Login
              </BigCTA>
            </View>
          </View>
        )}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  topHeader: {
    marginTop: 54,
    paddingHorizontal: 20,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  backBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth,
  },
  screenHeaderTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
  content: {
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 40,
  },
  title: {
    fontSize: 30,
    fontWeight: '700',
    letterSpacing: -0.8,
  },
  sub: {
    fontSize: 14,
    marginTop: 8,
    lineHeight: 20,
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: '500',
    marginBottom: 6,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  input: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
  },
  errorText: {
    fontSize: 13,
    marginTop: 12,
    fontWeight: '500',
  },
  infoText: {
    fontSize: 13,
    marginTop: 12,
    fontWeight: '500',
  },
});
