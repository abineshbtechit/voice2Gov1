import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { CloudBG } from '../../components/common/Backgrounds';
import { GlassCard, BigCTA } from '../../components/common/UIComponents';
import { Icons } from '../../components/common/Icons';
import { Radius } from '../../theme/tokens';

export interface StateScreenProps {
  type: 'empty_complaints' | 'empty_notifications' | 'offline' | 'error_404' | 'error_generic';
  onPrimaryAction?: () => void;
  onSecondaryAction?: () => void;
}

export const StateScreen: React.FC<StateScreenProps> = ({
  type,
  onPrimaryAction,
  onSecondaryAction,
}) => {
  const { theme, isDark } = useAppTheme();

  const configs = {
    empty_complaints: {
      icon: <Icons.list size={48} color={theme.fg} />,
      title: 'No complaints\nyet.',
      sub: "When you file your first complaint, it'll show up here — tracked from voice to resolution.",
      primaryText: 'File your first',
      primaryIcon: <Icons.mic size={18} color={theme.ctaFg} />,
      secondaryText: null,
    },
    empty_notifications: {
      icon: <Icons.bell size={48} color={theme.fg} />,
      title: "You're all\ncaught up.",
      sub: "No new updates from any department. We'll notify you the moment something changes.",
      primaryText: 'Back to home',
      primaryIcon: null,
      secondaryText: null,
    },
    offline: {
      icon: <Icons.wifiOff size={48} color={theme.fg} />,
      title: "You're offline.",
      sub: 'Your draft is saved on this device. We will sync it as soon as you are back online.',
      primaryText: 'Retry connection',
      primaryIcon: null,
      secondaryText: 'View saved drafts',
    },
    error_404: {
      icon: <Text style={{ fontSize: 56, fontWeight: '800', color: theme.fgMuted }}>404</Text>,
      title: 'Page not\nfound.',
      sub: 'The resource you requested may have been moved or resolved.',
      primaryText: 'Back to home',
      primaryIcon: null,
      secondaryText: null,
    },
    error_generic: {
      icon: <Icons.wifiOff size={48} color="#E5484D" />,
      title: 'Something\nwent wrong.',
      sub: 'An unexpected issue occurred while contacting the server. Please try again.',
      primaryText: 'Try again',
      primaryIcon: null,
      secondaryText: 'Contact support',
    },
  };

  const current = configs[type];

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <CloudBG isDark={isDark} opacity={0.5} />

      <View style={styles.centerBox}>
        {/* Glass illustration container */}
        <GlassCard
          radius={Radius.xl}
          padding={32}
          style={styles.illusCard}
        >
          {current.icon}
        </GlassCard>

        <Text style={[styles.title, { color: theme.fg }]}>{current.title}</Text>
        <Text style={[styles.sub, { color: theme.fgMuted }]}>{current.sub}</Text>
      </View>

      <View style={styles.bottomCta}>
        {current.primaryText && (
          <BigCTA onPress={onPrimaryAction} icon={current.primaryIcon}>
            {current.primaryText}
          </BigCTA>
        )}
        {current.secondaryText && (
          <BigCTA
            onPress={onSecondaryAction}
            variant="ghost"
            style={{ marginTop: 10 }}
          >
            {current.secondaryText}
          </BigCTA>
        )}
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
  centerBox: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 28,
  },
  illusCard: {
    width: 140,
    height: 140,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  },
  title: {
    fontSize: 32,
    fontWeight: '700',
    letterSpacing: -0.8,
    textAlign: 'center',
    lineHeight: 36,
  },
  sub: {
    fontSize: 15,
    marginTop: 12,
    textAlign: 'center',
    lineHeight: 22,
    maxWidth: 290,
  },
  bottomCta: {
    paddingHorizontal: 20,
    paddingBottom: 40,
  },
});

