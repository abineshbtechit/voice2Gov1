import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { AIOrb, CloudBG } from '../../components/common/Backgrounds';
import { BigCTA } from '../../components/common/UIComponents';

interface AuthWelcomeScreenProps {
  onStartRegister: () => void;
  onStartLogin: () => void;
}

export const AuthWelcomeScreen: React.FC<AuthWelcomeScreenProps> = ({
  onStartRegister,
  onStartLogin,
}) => {
  const { theme, isDark } = useAppTheme();

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <CloudBG isDark={isDark} opacity={0.7} />

      {/* Hero Mark & AI Orb */}
      <View style={styles.heroCenter}>
        <AIOrb size={130} />
        <View style={styles.titleWrapper}>
          <Text
            style={[
              styles.displayTitle,
              { color: theme.fg },
            ]}
          >
            Welcome to{'\n'}Voice2Gov.
          </Text>
          <Text style={[styles.subTitle, { color: theme.fgMuted }]}>
            The premium way to raise your voice with the government.
          </Text>
        </View>
      </View>

      {/* CTAs */}
      <View style={styles.ctaBottom}>
        <BigCTA onPress={onStartRegister} variant="primary">
          Create account
        </BigCTA>
        <BigCTA onPress={onStartLogin} variant="ghost" style={{ marginTop: 10 }}>
          Sign in
        </BigCTA>
        <Text style={[styles.disclaimer, { color: theme.fgFaint }]}>
          By continuing you accept the Terms and Privacy Policy.
        </Text>
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
  heroCenter: {
    marginTop: 120,
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  titleWrapper: {
    alignItems: 'center',
    marginTop: 32,
  },
  displayTitle: {
    fontSize: 40,
    fontWeight: '700',
    letterSpacing: -1.2,
    lineHeight: 44,
    textAlign: 'center',
  },
  subTitle: {
    fontSize: 16,
    marginTop: 12,
    letterSpacing: -0.2,
    textAlign: 'center',
    maxWidth: 280,
    lineHeight: 22,
  },
  ctaBottom: {
    paddingHorizontal: 20,
    paddingBottom: 44,
  },
  disclaimer: {
    textAlign: 'center',
    fontSize: 12,
    marginTop: 14,
    letterSpacing: -0.1,
  },
});

