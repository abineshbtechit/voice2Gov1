import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  TextInput,
  StyleSheet,
  ViewStyle,
  TextStyle,
  Platform,
} from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { Radius, Colors } from '../../theme/tokens';
import { Icons } from './Icons';

export interface GlassCardProps {
  children: React.ReactNode;
  style?: ViewStyle | ViewStyle[];
  radius?: number;
  padding?: number;
  strong?: boolean;
}

export const GlassCard: React.FC<GlassCardProps> = ({
  children,
  style,
  radius = Radius.lg,
  padding = 20,
  strong = false,
}) => {
  const { theme, isDark } = useAppTheme();

  return (
    <View
      style={[
        {
          borderRadius: radius,
          padding,
          backgroundColor: strong ? theme.glassBgStrong : theme.glassBg,
          borderWidth: StyleSheet.hairlineWidth,
          borderColor: theme.glassBorder,
          overflow: 'hidden',
          ...(Platform.OS === 'web'
            ? {
                // @ts-ignore
                backdropFilter: 'blur(30px) saturate(180%)',
                // @ts-ignore
                WebkitBackdropFilter: 'blur(30px) saturate(180%)',
              }
            : {}),
          shadowColor: isDark ? '#000000' : '#101012',
          shadowOffset: { width: 0, height: 8 },
          shadowOpacity: isDark ? 0.4 : 0.08,
          shadowRadius: 24,
          elevation: 4,
        },
        style,
      ]}
    >
      {children}
    </View>
  );
};

export interface BigCTAProps {
  children: React.ReactNode;
  onPress?: () => void;
  variant?: 'primary' | 'ghost' | 'destructive';
  icon?: React.ReactNode;
  disabled?: boolean;
  style?: ViewStyle;
}

export const BigCTA: React.FC<BigCTAProps> = ({
  children,
  onPress,
  variant = 'primary',
  icon,
  disabled = false,
  style,
}) => {
  const { theme, isDark } = useAppTheme();

  const isPrimary = variant === 'primary';
  const isDestructive = variant === 'destructive';

  const bgColor = isDestructive
    ? Colors.status.urgent
    : isPrimary
    ? theme.ctaBg
    : theme.glassBg;

  const textColor = isDestructive
    ? '#FFFFFF'
    : isPrimary
    ? theme.ctaFg
    : theme.fg;

  return (
    <TouchableOpacity
      activeOpacity={0.8}
      onPress={onPress}
      disabled={disabled}
      style={[
        {
          height: 54,
          borderRadius: Radius.pill,
          backgroundColor: bgColor,
          borderWidth: isPrimary || isDestructive ? 0 : StyleSheet.hairlineWidth,
          borderColor: theme.glassBorder,
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'center',
          paddingHorizontal: 24,
          opacity: disabled ? 0.5 : 1,
          shadowColor: isPrimary ? (isDark ? '#FFFFFF' : '#000000') : 'transparent',
          shadowOffset: { width: 0, height: 6 },
          shadowOpacity: isPrimary ? (isDark ? 0.08 : 0.16) : 0,
          shadowRadius: 18,
          elevation: isPrimary ? 3 : 0,
        },
        style,
      ]}
    >
      <Text
        style={{
          fontSize: 16,
          fontWeight: '600',
          letterSpacing: -0.2,
          color: textColor,
          marginRight: icon ? 8 : 0,
        }}
      >
        {children}
      </Text>
      {icon}
    </TouchableOpacity>
  );
};

export interface ChipProps {
  children: React.ReactNode;
  tone?: 'live' | 'pending' | 'urgent' | 'info' | 'neutral';
  style?: ViewStyle;
  onPress?: () => void;
}

export const Chip: React.FC<ChipProps> = ({
  children,
  tone = 'neutral',
  style,
  onPress,
}) => {
  const { theme, isDark } = useAppTheme();

  const colorMap = {
    live: Colors.status.live,
    pending: Colors.status.pending,
    urgent: Colors.status.urgent,
    info: Colors.status.info,
    neutral: theme.fgMuted,
  };

  const accentColor = colorMap[tone];
  const isNeutral = tone === 'neutral';

  const Container = onPress ? TouchableOpacity : View;

  return (
    <Container
      onPress={onPress}
      style={[
        {
          flexDirection: 'row',
          alignItems: 'center',
          paddingHorizontal: 12,
          paddingVertical: 6,
          borderRadius: Radius.pill,
          backgroundColor: isNeutral
            ? isDark
              ? 'rgba(255,255,255,0.08)'
              : 'rgba(0,0,0,0.05)'
            : `${accentColor}18`,
          borderWidth: StyleSheet.hairlineWidth,
          borderColor: isNeutral ? theme.hairline : `${accentColor}33`,
        },
        style,
      ]}
    >
      {!isNeutral && (
        <View
          style={{
            width: 6,
            height: 6,
            borderRadius: 3,
            backgroundColor: accentColor,
            marginRight: 6,
          }}
        />
      )}
      <Text
        style={{
          fontSize: 12,
          fontWeight: '600',
          letterSpacing: -0.1,
          color: isNeutral ? theme.fg : accentColor,
        }}
      >
        {children}
      </Text>
    </Container>
  );
};

export interface TextFieldProps {
  value?: string;
  onChangeText?: (text: string) => void;
  placeholder?: string;
  secureTextEntry?: boolean;
  keyboardType?: any;
  autoCapitalize?: any;
  autoFocus?: boolean;
  icon?: React.ReactNode;
  rightAction?: React.ReactNode;
  style?: ViewStyle;
}

export const TextField: React.FC<TextFieldProps> = ({
  value,
  onChangeText,
  placeholder,
  secureTextEntry,
  keyboardType,
  autoCapitalize = 'none',
  autoFocus,
  icon,
  rightAction,
  style,
}) => {
  const { theme, isDark } = useAppTheme();
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);

  return (
    <View
      style={[
        {
          height: 54,
          borderRadius: Radius.md,
          backgroundColor: theme.glassBgStrong,
          borderWidth: StyleSheet.hairlineWidth,
          borderColor: theme.glassBorder,
          flexDirection: 'row',
          alignItems: 'center',
          paddingHorizontal: 16,
          ...(Platform.OS === 'web'
            ? {
                // @ts-ignore
                backdropFilter: 'blur(20px)',
              }
            : {}),
        },
        style,
      ]}
    >
      {icon && <View style={{ marginRight: 10 }}>{icon}</View>}
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={theme.fgFaint}
        secureTextEntry={secureTextEntry ? !isPasswordVisible : false}
        keyboardType={keyboardType}
        autoCapitalize={autoCapitalize}
        autoFocus={autoFocus}
        style={{
          flex: 1,
          fontSize: 16,
          fontWeight: '500',
          letterSpacing: -0.2,
          color: theme.fg,
          padding: 0,
          ...(Platform.OS === 'web' ? ({ outlineStyle: 'none' } as any) : {}),
        }}
      />
      {secureTextEntry ? (
        <TouchableOpacity
          onPress={() => setIsPasswordVisible((prev) => !prev)}
          hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          activeOpacity={0.7}
          style={{ padding: 4, marginLeft: 8 }}
        >
          {isPasswordVisible ? (
            <Icons.eyeOff size={20} color={theme.fgMuted} />
          ) : (
            <Icons.eye size={20} color={theme.fgMuted} />
          )}
        </TouchableOpacity>
      ) : rightAction ? (
        <View style={{ marginLeft: 8 }}>{rightAction}</View>
      ) : null}
    </View>
  );
};

