import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  TextInput,
  Platform,
  Linking,
  ScrollView,
} from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';
import { AuthApi } from '../../api/auth';
import { CloudBG } from '../../components/common/Backgrounds';
import { GlassCard, BigCTA } from '../../components/common/UIComponents';
import { Icons } from '../../components/common/Icons';
import { Radius } from '../../theme/tokens';

interface OTPVerificationScreenProps {
  identifier: string;
  email?: string;
  phone?: string;
  fullName?: string;
  onBack: () => void;
  onSuccess: () => void;
}

type VerificationStep = 'select_channel' | 'verify_code';

export const OTPVerificationScreen: React.FC<OTPVerificationScreenProps> = ({
  identifier,
  email,
  phone,
  fullName,
  onBack,
  onSuccess,
}) => {
  const { theme, isDark } = useAppTheme();
  const { login } = useAuth();

  // Navigation step: 1 = choose method, 2 = real-time verification
  const [step, setStep] = useState<VerificationStep>('select_channel');

  // Channel: 'email' or 'whatsapp'
  const [channel, setChannel] = useState<'email' | 'whatsapp'>('email');

  // OTP and focus state
  const [otp, setOtp] = useState('');
  const [isInputFocused, setIsInputFocused] = useState(false);
  const [showCursor, setShowCursor] = useState(true);

  // Real-time 60-second expiration timer
  const [timeLeft, setTimeLeft] = useState<number>(60);
  const [isExpired, setIsExpired] = useState<boolean>(false);

  // Network and action states
  const [sendingOtp, setSendingOtp] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [whatsappUrl, setWhatsappUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);

  const inputRef = useRef<TextInput | null>(null);

  const userEmail = email || (identifier.includes('@') ? identifier : '');
  const userPhone = phone || (!identifier.includes('@') ? identifier : '');
  const activeIdentifier =
    channel === 'email' ? userEmail || identifier : userPhone || identifier;

  // Real-time 60s countdown timer on Step 2
  useEffect(() => {
    if (step !== 'verify_code') return;

    if (timeLeft <= 0) {
      setIsExpired(true);
      return;
    }

    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          setIsExpired(true);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [step, timeLeft]);

  // Blinking cursor in active box
  useEffect(() => {
    if (!isInputFocused) return;
    const interval = setInterval(() => {
      setShowCursor((prev) => !prev);
    }, 530);
    return () => clearInterval(interval);
  }, [isInputFocused]);

  // Autofocus input when arriving on step 2
  useEffect(() => {
    if (step === 'verify_code') {
      const timer = setTimeout(() => {
        inputRef.current?.focus();
      }, 350);
      return () => clearTimeout(timer);
    }
  }, [step]);

  // Send OTP handler
  const handleSendOtp = async (targetChannel: 'email' | 'whatsapp') => {
    setError(null);
    setSendingOtp(true);
    setWhatsappUrl(null);

    try {
      const targetIdentifier =
        targetChannel === 'email' ? userEmail || identifier : userPhone || identifier;

      const res = await AuthApi.sendVerificationOtp(targetIdentifier, targetChannel);

      if (res.success && res.data) {
        // Reset timer to 60s and mark active
        setTimeLeft(60);
        setIsExpired(false);
        setOtp('');
        setError(null);

        if (targetChannel === 'whatsapp' && res.data.whatsapp_url) {
          setWhatsappUrl(res.data.whatsapp_url);
          setInfoMessage('WhatsApp verification link created. Tap Open to view code.');
          if (Platform.OS !== 'web') {
            Linking.openURL(res.data.whatsapp_url).catch(() => {});
          }
        } else {
          setInfoMessage(`Code sent to ${userEmail || targetIdentifier} via Google SMTP.`);
        }

        // Navigate to Step 2
        setStep('verify_code');
      } else {
        setError(res.message || 'Failed to send verification code. Please try again.');
      }
    } catch (e: any) {
      setError(e?.message || 'Network error sending verification code.');
    } finally {
      setSendingOtp(false);
    }
  };

  const handleOpenWhatsApp = () => {
    if (whatsappUrl) {
      Linking.openURL(whatsappUrl).catch(() => {
        setError('Could not open WhatsApp on this device.');
      });
    }
  };

  const handleOtpChange = (value: string) => {
    if (isExpired) return;
    const cleaned = value.replace(/[^0-9]/g, '').slice(0, 6);
    setOtp(cleaned);
    if (error) setError(null);
  };

  const handleVerify = async () => {
    if (isExpired) {
      return;
    }

    if (otp.length < 6) {
      setError('Please enter all 6 digits of your verification code.');
      return;
    }

    setError(null);
    setVerifying(true);

    try {
      const res = await AuthApi.verifyAccountOtp(activeIdentifier, otp);

      if (res.success && res.data?.access_token) {
        await login(res.data.access_token, res.data.refresh_token, res.data.user);
        onSuccess();
      } else {
        setError(res.message || 'Invalid or expired verification code.');
      }
    } catch (e: any) {
      setError(e?.message || 'Verification failed. Please try again.');
    } finally {
      setVerifying(false);
    }
  };

  // Format seconds to MM:SS
  const formattedTime = `00:${timeLeft < 10 ? '0' : ''}${timeLeft}`;

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <CloudBG isDark={isDark} opacity={0.7} />

      {/* Top Header */}
      <View style={styles.topHeader}>
        <TouchableOpacity
          onPress={() => {
            if (step === 'verify_code') {
              setStep('select_channel');
              setError(null);
            } else {
              onBack();
            }
          }}
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
        <Text style={[styles.headerEyebrow, { color: theme.fgMuted }]}>
          {step === 'select_channel'
            ? 'Step 1 of 2 · Choose Delivery Method'
            : 'Step 2 of 2 · Real-Time Verification'}
        </Text>
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        {/* =================================================================== */}
        {/* PAGE 1: HOW TO SEND OTP (CHANNEL SELECTION)                        */}
        {/* =================================================================== */}
        {step === 'select_channel' ? (
          <View>
            <View style={styles.titleSection}>
              <Text style={[styles.title, { color: theme.fg }]}>
                Verify your{'\n'}account.
              </Text>
              <Text style={[styles.sub, { color: theme.fgMuted }]}>
                {fullName ? `Welcome ${fullName}. ` : ''}Choose where you want us to send your 6-digit one-time code to activate citizen access:
              </Text>
            </View>

            {/* Delivery Method Cards */}
            <View style={styles.methodList}>
              {/* Email Option */}
              <TouchableOpacity
                onPress={() => setChannel('email')}
                activeOpacity={0.85}
                style={[
                  styles.methodCard,
                  {
                    backgroundColor: channel === 'email' ? theme.glassBgStrong : theme.glassBg,
                    borderColor: channel === 'email' ? theme.fg : theme.glassBorder,
                    borderWidth: channel === 'email' ? 1.8 : StyleSheet.hairlineWidth,
                  },
                ]}
              >
                <View style={styles.methodIconWrapper}>
                  <Icons.mail size={24} color={channel === 'email' ? theme.fg : theme.fgMuted} />
                </View>

                <View style={styles.methodDetails}>
                  <View style={styles.methodTitleRow}>
                    <Text style={[styles.methodTitle, { color: theme.fg }]}>Email Address</Text>
                    <View
                      style={[
                        styles.radioOuter,
                        { borderColor: channel === 'email' ? theme.fg : theme.glassBorder },
                      ]}
                    >
                      {channel === 'email' && (
                        <View style={[styles.radioInner, { backgroundColor: theme.fg }]} />
                      )}
                    </View>
                  </View>
                  <Text numberOfLines={1} style={[styles.methodTarget, { color: theme.fgMuted }]}>
                    {userEmail || 'Registered email'}
                  </Text>
                  <Text style={[styles.methodBadge, { color: theme.fgMuted }]}>
                    Google SMTP · Free delivery · 1 min expiry
                  </Text>
                </View>
              </TouchableOpacity>

              {/* WhatsApp Option */}
              <TouchableOpacity
                onPress={() => setChannel('whatsapp')}
                activeOpacity={0.85}
                style={[
                  styles.methodCard,
                  {
                    backgroundColor: channel === 'whatsapp' ? theme.glassBgStrong : theme.glassBg,
                    borderColor: channel === 'whatsapp' ? '#2FBF71' : theme.glassBorder,
                    borderWidth: channel === 'whatsapp' ? 1.8 : StyleSheet.hairlineWidth,
                  },
                ]}
              >
                <View style={[styles.methodIconWrapper, { backgroundColor: 'rgba(47, 191, 113, 0.12)' }]}>
                  <Icons.whatsapp size={24} color="#2FBF71" />
                </View>

                <View style={styles.methodDetails}>
                  <View style={styles.methodTitleRow}>
                    <Text style={[styles.methodTitle, { color: theme.fg }]}>WhatsApp</Text>
                    <View
                      style={[
                        styles.radioOuter,
                        { borderColor: channel === 'whatsapp' ? '#2FBF71' : theme.glassBorder },
                      ]}
                    >
                      {channel === 'whatsapp' && (
                        <View style={[styles.radioInner, { backgroundColor: '#2FBF71' }]} />
                      )}
                    </View>
                  </View>
                  <Text numberOfLines={1} style={[styles.methodTarget, { color: theme.fgMuted }]}>
                    {userPhone || 'Registered mobile'}
                  </Text>
                  <Text style={[styles.methodBadge, { color: theme.fgMuted }]}>
                    Click-to-chat · Free message · 1 min expiry
                  </Text>
                </View>
              </TouchableOpacity>
            </View>

            {/* Error Message */}
            {error && (
              <Text style={[styles.errorText, { color: '#E5484D', marginTop: 12 }]}>{error}</Text>
            )}

            {/* Send Code CTA */}
            <View style={styles.ctaWrapper}>
              <BigCTA
                onPress={() => handleSendOtp(channel)}
                disabled={sendingOtp}
                icon={
                  sendingOtp ? (
                    <ActivityIndicator size="small" color={theme.ctaFg} />
                  ) : (
                    <Icons.arrowRight size={18} color={theme.ctaFg} />
                  )
                }
              >
                {sendingOtp ? 'Sending code...' : 'Send Verification Code'}
              </BigCTA>
            </View>
          </View>
        ) : (
          /* =================================================================== */
          /* PAGE 2: REAL-TIME OTP CODE ENTRY & VERIFICATION                    */
          /* =================================================================== */
          <View>
            <View style={styles.titleSection}>
              <Text style={[styles.title, { color: theme.fg }]}>
                Enter 6-digit{'\n'}code.
              </Text>
              <Text style={[styles.sub, { color: theme.fgMuted }]}>
                We sent a real-time verification code to:
              </Text>

              {/* Chosen target pill with 'Change' option */}
              <View
                style={[
                  styles.targetBadge,
                  {
                    backgroundColor: theme.glassBgStrong,
                    borderColor: theme.glassBorder,
                  },
                ]}
              >
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
                  {channel === 'email' ? (
                    <Icons.mail size={16} color={theme.fg} />
                  ) : (
                    <Icons.whatsapp size={16} color="#2FBF71" />
                  )}
                  <Text
                    numberOfLines={1}
                    style={[styles.targetBadgeText, { color: theme.fg }]}
                  >
                    {channel === 'email' ? userEmail || activeIdentifier : userPhone || activeIdentifier}
                  </Text>
                </View>

                <TouchableOpacity
                  onPress={() => {
                    setStep('select_channel');
                    setError(null);
                  }}
                  hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                >
                  <Text style={[styles.changeLink, { color: '#FFFFFF' }]}>Change</Text>
                </TouchableOpacity>
              </View>
            </View>

            {/* WhatsApp Launcher Card */}
            {channel === 'whatsapp' && whatsappUrl && (
              <GlassCard padding={14} radius={Radius.lg} style={{ marginBottom: 16 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                  <Icons.whatsapp size={26} color="#2FBF71" />
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <Text style={{ fontSize: 13, fontWeight: '600', color: theme.fg }}>
                      WhatsApp Link Ready
                    </Text>
                    <Text style={{ fontSize: 11, color: theme.fgMuted, marginTop: 1 }}>
                      Tap open to receive code
                    </Text>
                  </View>
                  <TouchableOpacity
                    onPress={handleOpenWhatsApp}
                    style={[styles.openWhatsAppBtn, { backgroundColor: '#2FBF71' }]}
                  >
                    <Text style={styles.openWhatsAppText}>Open</Text>
                  </TouchableOpacity>
                </View>
              </GlassCard>
            )}

            {/* Info Notice */}
            {infoMessage && (
              <View style={styles.infoRow}>
                <Text style={[styles.infoText, { color: theme.fgMuted }]}>{infoMessage}</Text>
              </View>
            )}

            {/* 6-Digit Responsive Boxes */}
            <TouchableOpacity
              activeOpacity={1}
              onPress={() => inputRef.current?.focus()}
              style={styles.otpContainer}
            >
              <View style={styles.otpGrid}>
                {[0, 1, 2, 3, 4, 5].map((index) => {
                  const char = otp[index] || '';
                  const isFocusedBox =
                    isInputFocused &&
                    !isExpired &&
                    (otp.length === index || (index === 5 && otp.length === 6));

                  return (
                    <View
                      key={index}
                      style={[
                        styles.otpBox,
                        {
                          backgroundColor: theme.glassBgStrong,
                          borderColor: isExpired
                            ? '#E5484D'
                            : isFocusedBox
                            ? theme.fg
                            : char
                            ? (isDark ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)')
                            : theme.glassBorder,
                          borderWidth: isFocusedBox ? 2 : 1,
                        },
                      ]}
                    >
                      <Text
                        style={[
                          styles.otpDigit,
                          {
                            color: isExpired ? '#E5484D' : theme.fg,
                          },
                        ]}
                      >
                        {char}
                      </Text>
                      {isFocusedBox && !char && showCursor && (
                        <View style={[styles.cursor, { backgroundColor: theme.fg }]} />
                      )}
                    </View>
                  );
                })}
              </View>

              <TextInput
                ref={inputRef}
                value={otp}
                onChangeText={handleOtpChange}
                onFocus={() => setIsInputFocused(true)}
                onBlur={() => setIsInputFocused(false)}
                keyboardType="number-pad"
                textContentType="oneTimeCode"
                autoComplete="one-time-code"
                maxLength={6}
                editable={!isExpired}
                style={styles.hiddenInput}
                caretHidden
              />
            </TouchableOpacity>

            {/* Real-time Expiration Status Badge or Active Timer */}
            <View style={styles.timerContainer}>
              {isExpired ? (
                <View style={[styles.expiredBadge, { backgroundColor: 'rgba(229, 72, 77, 0.12)' }]}>
                  <Text style={styles.expiredBadgeText}>
                    ⚠️ Verification code expired. Tap "Resend Code" below.
                  </Text>
                </View>
              ) : (
                <View
                  style={[
                    styles.activeTimerBadge,
                    {
                      backgroundColor: theme.glassBgStrong,
                      borderColor: theme.glassBorder,
                    },
                  ]}
                >
                  <Icons.clock size={14} color={theme.fgMuted} />
                  <Text style={[styles.activeTimerText, { color: theme.fg }]}>
                    Valid for 1 min · Expires in{' '}
                    <Text style={{ fontWeight: '700', color: timeLeft <= 10 ? '#E5484D' : theme.fg }}>
                      {formattedTime}
                    </Text>
                  </Text>
                </View>
              )}
            </View>

            {/* Error Message from API (only show if not expired to prevent duplicate messages) */}
            {error && !isExpired && (
              <Text style={[styles.errorText, { color: '#E5484D' }]}>{error}</Text>
            )}

            {/* Resend Action: styled identical to 'Change' button (white color, underline, bold text) */}
            <View style={styles.resendRow}>
              <Text style={[styles.resendPrompt, { color: theme.fgMuted }]}>
                Didn't receive code?{' '}
              </Text>
              <TouchableOpacity
                onPress={() => handleSendOtp(channel)}
                disabled={!isExpired || sendingOtp}
                hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                activeOpacity={0.7}
              >
                <Text
                  style={[
                    styles.resendLink,
                    {
                      color: '#FFFFFF',
                      opacity: isExpired ? 1.0 : 0.4,
                    },
                  ]}
                >
                  {sendingOtp ? 'Sending...' : isExpired ? 'Resend Code' : `Resend in ${timeLeft}s`}
                </Text>
              </TouchableOpacity>
            </View>

            {/* Verify CTA */}
            <View style={styles.ctaWrapper}>
              <BigCTA
                onPress={handleVerify}
                disabled={verifying || otp.length < 6 || isExpired}
                icon={
                  verifying ? (
                    <ActivityIndicator size="small" color={theme.ctaFg} />
                  ) : isExpired ? undefined : (
                    <Icons.check size={18} color={theme.ctaFg} />
                  )
                }
              >
                {verifying
                  ? 'Activating account...'
                  : isExpired
                  ? 'Code Expired'
                  : 'Verify & Continue'}
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
    position: 'relative',
  },
  topHeader: {
    marginTop: 64,
    paddingHorizontal: 20,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    maxWidth: 480,
    width: '100%',
    alignSelf: 'center',
  },
  headerEyebrow: {
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.5,
  },
  backBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 24,
    paddingBottom: 40,
    maxWidth: 480,
    width: '100%',
    alignSelf: 'center',
  },
  titleSection: {
    marginBottom: 24,
  },
  title: {
    fontSize: 34,
    fontWeight: '700',
    letterSpacing: -0.8,
    lineHeight: 40,
  },
  sub: {
    fontSize: 15,
    marginTop: 8,
    lineHeight: 22,
  },
  methodList: {
    gap: 14,
    marginVertical: 12,
  },
  methodCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 18,
    borderRadius: Radius.lg,
    gap: 16,
  },
  methodIconWrapper: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  methodDetails: {
    flex: 1,
    minWidth: 0,
  },
  methodTitleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  methodTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
  radioOuter: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioInner: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  methodTarget: {
    fontSize: 14,
    marginTop: 3,
    fontWeight: '500',
  },
  methodBadge: {
    fontSize: 11,
    marginTop: 4,
  },
  targetBadge: {
    marginTop: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: Radius.md,
    borderWidth: StyleSheet.hairlineWidth,
  },
  targetBadgeText: {
    fontSize: 13,
    fontWeight: '600',
  },
  changeLink: {
    fontSize: 12,
    fontWeight: '700',
    textDecorationLine: 'underline',
    marginLeft: 10,
  },
  openWhatsAppBtn: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: Radius.pill,
  },
  openWhatsAppText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 12,
  },
  infoRow: {
    marginBottom: 14,
    paddingHorizontal: 4,
  },
  infoText: {
    fontSize: 12,
    lineHeight: 18,
  },
  otpContainer: {
    position: 'relative',
    width: '100%',
    marginVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  otpGrid: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    width: '100%',
    gap: 8,
  },
  otpBox: {
    flex: 1,
    minWidth: 0,
    maxWidth: 48,
    height: 56,
    borderRadius: Radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
  },
  otpDigit: {
    fontSize: 22,
    fontWeight: '700',
    textAlign: 'center',
  },
  cursor: {
    position: 'absolute',
    width: 2,
    height: 22,
    borderRadius: 1,
    opacity: 0.8,
  },
  hiddenInput: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    width: '100%',
    height: '100%',
    opacity: 0.001,
    color: 'transparent',
    ...(Platform.OS === 'web'
      ? ({
          outlineStyle: 'none',
          cursor: 'pointer',
          caretColor: 'transparent',
        } as any)
      : {}),
  },
  timerContainer: {
    marginVertical: 8,
    alignItems: 'center',
  },
  activeTimerBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: Radius.pill,
    borderWidth: StyleSheet.hairlineWidth,
  },
  activeTimerText: {
    fontSize: 12,
  },
  expiredBadge: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: Radius.md,
    width: '100%',
    alignItems: 'center',
  },
  expiredBadgeText: {
    color: '#E5484D',
    fontSize: 12,
    fontWeight: '600',
    textAlign: 'center',
  },
  errorText: {
    fontSize: 13,
    fontWeight: '500',
    textAlign: 'center',
    marginTop: 6,
    marginBottom: 8,
  },
  resendRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 14,
    marginBottom: 20,
  },
  resendPrompt: {
    fontSize: 13,
  },
  resendLink: {
    fontSize: 13,
    fontWeight: '700',
    textDecorationLine: 'underline',
  },
  ctaWrapper: {
    marginTop: 10,
  },
});
