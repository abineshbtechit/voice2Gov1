import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { AIOrb } from '../../components/common/Backgrounds';

interface AIProcessingScreenProps {
  onComplete: () => void;
}

export const AIProcessingScreen: React.FC<AIProcessingScreenProps> = ({ onComplete }) => {
  const { theme, isDark } = useAppTheme();
  const [currentStep, setCurrentStep] = useState(0);

  const steps = [
    'Transcribing multi-dialect voice…',
    'Translating to official English…',
    'Extracting civic category & department…',
    'Analyzing severity & calculating priority score…',
  ];

  useEffect(() => {
    const timer1 = setTimeout(() => setCurrentStep(1), 800);
    const timer2 = setTimeout(() => setCurrentStep(2), 1700);
    const timer3 = setTimeout(() => setCurrentStep(3), 2600);
    const timer4 = setTimeout(() => onComplete(), 3400);

    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
      clearTimeout(timer4);
    };
  }, []);

  return (
    <View
      style={[
        styles.container,
        { backgroundColor: isDark ? '#050507' : '#FAFAFA' },
      ]}
    >
      <View style={styles.centerBox}>
        <AIOrb size={150} spinning pulse />

        <View style={styles.textWrapper}>
          <Text style={[styles.mainHeading, { color: theme.fg }]}>
            AI Processing
          </Text>
          <Text style={[styles.subHeading, { color: theme.fgMuted }]}>
            {steps[currentStep]}
          </Text>
        </View>

        {/* Step dots */}
        <View style={styles.dotsRow}>
          {steps.map((_, i) => (
            <View
              key={i}
              style={[
                styles.dot,
                {
                  backgroundColor:
                    i <= currentStep
                      ? theme.fg
                      : isDark
                      ? 'rgba(255,255,255,0.15)'
                      : 'rgba(0,0,0,0.1)',
                },
              ]}
            />
          ))}
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  centerBox: {
    alignItems: 'center',
    gap: 32,
  },
  textWrapper: {
    alignItems: 'center',
    gap: 8,
  },
  mainHeading: {
    fontSize: 28,
    fontWeight: '700',
    letterSpacing: -0.6,
  },
  subHeading: {
    fontSize: 15,
    textAlign: 'center',
    lineHeight: 22,
  },
  dotsRow: {
    flexDirection: 'row',
    gap: 8,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
});

