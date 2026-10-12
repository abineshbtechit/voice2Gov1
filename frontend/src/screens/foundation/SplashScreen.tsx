import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated, Easing, Platform } from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { CloudBG, AIOrb } from '../../components/common/Backgrounds';

interface SplashScreenProps {
  onFinish: () => void;
}

export const SplashScreen: React.FC<SplashScreenProps> = ({ onFinish }) => {
  const { theme, isDark } = useAppTheme();
  const progressAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(progressAnim, {
      toValue: 1,
      duration: 2200,
      easing: Easing.inOut(Easing.ease),
      useNativeDriver: false,
    }).start(() => {
      setTimeout(onFinish, 300);
    });
  }, []);

  const progressWidth = progressAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['10%', '100%'],
  });

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <CloudBG isDark={isDark} opacity={0.9} />

      {/* Centered Logo Mark */}
      <View style={styles.centerMark}>
        <AIOrb size={130} spinning pulse />
        <View style={styles.titleWrapper}>
          <Text style={[styles.brandTitle, { color: theme.fg }]}>Voice2Gov</Text>
          <Text style={[styles.brandTagline, { color: theme.fgMuted }]}>
            Speak. Be heard.
          </Text>
        </View>
      </View>

      {/* Bottom Shimmer Progress */}
      <View style={styles.bottomLoader}>
        <View
          style={[
            styles.loaderTrack,
            { backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)' },
          ]}
        >
          <Animated.View
            style={[
              styles.loaderBar,
              {
                width: progressWidth,
                backgroundColor: theme.fg,
              },
            ]}
          />
        </View>
        <Text style={[styles.poweredBy, { color: theme.fgFaint }]}>
          POWERED BY AI · भारत सरकार
        </Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    position: 'relative',
    alignItems: 'center',
    justifyContent: 'center',
  },
  centerMark: {
    alignItems: 'center',
    gap: 24,
  },
  titleWrapper: {
    alignItems: 'center',
    marginTop: 8,
  },
  brandTitle: {
    fontSize: 34,
    fontWeight: '700',
    letterSpacing: -1,
  },
  brandTagline: {
    fontSize: 15,
    marginTop: 6,
    letterSpacing: 0.2,
    fontWeight: '500',
  },
  bottomLoader: {
    position: 'absolute',
    bottom: 60,
    alignItems: 'center',
    gap: 14,
  },
  loaderTrack: {
    width: 88,
    height: 3,
    borderRadius: 999,
    overflow: 'hidden',
  },
  loaderBar: {
    height: '100%',
    borderRadius: 999,
  },
  poweredBy: {
    fontSize: 11,
    letterSpacing: 1.2,
    fontWeight: '600',
  },
});

