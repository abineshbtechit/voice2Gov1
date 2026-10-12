import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { CloudBG, AIOrb } from '../../components/common/Backgrounds';
import { Icons } from '../../components/common/Icons';
import { BigCTA } from '../../components/common/UIComponents';
import { Waveform } from '../../components/voice/Waveform';

interface OnboardingScreenProps {
  onComplete: () => void;
}

export const OnboardingScreen: React.FC<OnboardingScreenProps> = ({ onComplete }) => {
  const { theme, isDark } = useAppTheme();
  const [page, setPage] = useState(1);

  const steps = [
    {
      eyebrow: '01 · VOICE FIRST',
      title: 'File complaints\nin your voice.',
      body: 'Speak in Hindi, English, Tamil, Bengali, or any of 22 Indian languages. We handle the rest.',
      type: 'mic',
    },
    {
      eyebrow: '02 · AI INTELLIGENCE',
      title: 'AI understands\nwhat you mean.',
      body: 'Our AI transcribes, translates, categorises and routes your complaint to the right civic department.',
      type: 'orb',
    },
    {
      eyebrow: '03 · LIVE TRACKING',
      title: 'Track progress\nin real time.',
      body: 'See every step from voice recording to completion. Receive transparent official progress updates.',
      type: 'timeline',
    },
  ];

  const current = steps[page - 1];

  const handleNext = () => {
    if (page < 3) {
      setPage(page + 1);
    } else {
      onComplete();
    }
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <CloudBG isDark={isDark} opacity={0.8} />

      {/* Top Bar */}
      <View style={styles.topBar}>
        <Text style={[styles.logoBrand, { color: theme.fg }]}>Voice2Gov</Text>
        <TouchableOpacity onPress={onComplete}>
          <Text style={[styles.skipText, { color: theme.fgMuted }]}>Skip</Text>
        </TouchableOpacity>
      </View>

      {/* Center Illustration Area */}
      <View style={styles.centerIllustration}>
        {current.type === 'mic' && (
          <View style={styles.illusCircle}>
            <Icons.mic size={68} color={theme.fg} strokeWidth={1.4} />
            <View style={{ width: '80%', marginTop: 24 }}>
              <Waveform isDark={isDark} bars={24} height={40} active />
            </View>
          </View>
        )}
        {current.type === 'orb' && (
          <View style={{ alignItems: 'center' }}>
            <AIOrb size={170} spinning pulse />
          </View>
        )}
        {current.type === 'timeline' && (
          <View style={[styles.timelineCard, { backgroundColor: theme.glassBgStrong, borderColor: theme.glassBorder }]}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <Icons.check size={20} color="#2FBF71" />
              <Text style={{ fontSize: 14, fontWeight: '600', color: theme.fg }}>Submitted & Verified</Text>
            </View>
            <View style={{ height: 16, width: 2, backgroundColor: theme.fgMuted, marginLeft: 9 }} />
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <Icons.clock size={20} color="#F5A524" />
              <Text style={{ fontSize: 14, fontWeight: '600', color: theme.fg }}>Work in progress</Text>
            </View>
            <View style={{ height: 16, width: 2, backgroundColor: theme.hairline, marginLeft: 9 }} />
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <View style={{ width: 18, height: 18, borderRadius: 9, borderWidth: 2, borderColor: theme.fgMuted }} />
              <Text style={{ fontSize: 14, fontWeight: '500', color: theme.fgMuted }}>Resolution confirmed</Text>
            </View>
          </View>
        )}
      </View>

      {/* Bottom Sheet */}
      <View style={styles.bottomSheet}>
        <Text style={[styles.eyebrowText, { color: theme.fgMuted }]}>
          {current.eyebrow}
        </Text>
        <Text style={[styles.titleText, { color: theme.fg }]}>
          {current.title}
        </Text>
        <Text style={[styles.bodyText, { color: theme.fgMuted }]}>
          {current.body}
        </Text>

        <View style={styles.footerRow}>
          {/* Progress dots */}
          <View style={styles.dotsRow}>
            {[1, 2, 3].map((stepIndex) => (
              <View
                key={stepIndex}
                style={[
                  styles.dot,
                  {
                    width: stepIndex === page ? 22 : 8,
                    backgroundColor:
                      stepIndex === page
                        ? theme.fg
                        : isDark
                        ? 'rgba(255,255,255,0.15)'
                        : 'rgba(0,0,0,0.1)',
                  },
                ]}
              />
            ))}
          </View>

          {/* Next / Get Started */}
          <BigCTA
            onPress={handleNext}
            icon={<Icons.arrowRight size={18} color={theme.ctaFg} />}
            style={{ width: 150 }}
          >
            {page === 3 ? 'Get started' : 'Next'}
          </BigCTA>
        </View>
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
    marginTop: 64,
    paddingHorizontal: 24,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  logoBrand: {
    fontSize: 16,
    fontWeight: '700',
    letterSpacing: -0.3,
  },
  skipText: {
    fontSize: 14,
    fontWeight: '500',
  },
  centerIllustration: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  illusCircle: {
    width: 240,
    height: 240,
    borderRadius: 120,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(200,214,255,0.12)',
  },
  timelineCard: {
    padding: 24,
    borderRadius: 24,
    borderWidth: StyleSheet.hairlineWidth,
    width: '85%',
  },
  bottomSheet: {
    paddingHorizontal: 28,
    paddingBottom: 48,
    gap: 16,
  },
  eyebrowText: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.4,
  },
  titleText: {
    fontSize: 38,
    fontWeight: '700',
    letterSpacing: -1.2,
    lineHeight: 42,
  },
  bodyText: {
    fontSize: 16,
    lineHeight: 23,
    letterSpacing: -0.2,
  },
  footerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 16,
  },
  dotsRow: {
    flexDirection: 'row',
    gap: 6,
  },
  dot: {
    height: 8,
    borderRadius: 4,
  },
});

