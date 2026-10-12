import React from 'react';
import { View, StyleSheet, Dimensions } from 'react-native';

interface WaveformProps {
  isDark: boolean;
  bars?: number;
  height?: number;
  active?: boolean;
}

export const Waveform: React.FC<WaveformProps> = ({
  isDark,
  bars = 36,
  height = 50,
  active = true,
}) => {
  // Patterned heights representing natural speech frequencies
  const defaultHeights = [
    0.2, 0.35, 0.7, 0.45, 0.85, 0.95, 0.6, 0.4, 0.8, 0.9, 0.5, 0.3, 0.75, 0.88,
    0.65, 0.4, 0.7, 0.85, 0.45, 0.3, 0.6, 0.9, 0.8, 0.5, 0.35, 0.7, 0.85, 0.4,
    0.25, 0.6, 0.75, 0.9, 0.65, 0.4, 0.3, 0.2,
  ];

  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        height,
        width: '100%',
        gap: 4,
      }}
    >
      {Array.from({ length: bars }).map((_, i) => {
        const factor = defaultHeights[i % defaultHeights.length];
        const barHeight = Math.max(6, factor * height);

        return (
          <View
            key={i}
            style={{
              width: 3.5,
              height: barHeight,
              borderRadius: 2,
              backgroundColor: active
                ? isDark
                  ? '#FAFAFA'
                  : '#101012'
                : isDark
                ? 'rgba(255,255,255,0.2)'
                : 'rgba(0,0,0,0.15)',
              opacity: active ? 0.9 : 0.4,
            }}
          />
        );
      })}
    </View>
  );
};

