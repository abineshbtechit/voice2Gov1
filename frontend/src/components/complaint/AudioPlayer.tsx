import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { GlassCard } from '../common/UIComponents';
import { Icons } from '../common/Icons';
import { Waveform } from '../voice/Waveform';
import { Radius } from '../../theme/tokens';

export interface AudioPlayerProps {
  durationLabel?: string;
  languageLabel?: string;
}

export const AudioPlayer: React.FC<AudioPlayerProps> = ({
  durationLabel = '0:24',
  languageLabel = 'Original Voice (Hindi)',
}) => {
  const { theme, isDark } = useAppTheme();
  const [isPlaying, setIsPlaying] = useState(false);

  return (
    <GlassCard padding={14} radius={Radius.lg}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
        <TouchableOpacity
          onPress={() => setIsPlaying(!isPlaying)}
          style={[
            styles.playCircle,
            { backgroundColor: theme.ctaBg },
          ]}
        >
          {isPlaying ? (
            <Icons.pause size={18} color={theme.ctaFg} />
          ) : (
            <Icons.play size={18} color={theme.ctaFg} />
          )}
        </TouchableOpacity>

        <View style={{ flex: 1 }}>
          <Waveform isDark={isDark} bars={30} height={30} active={isPlaying} />
          <Text style={[styles.metaText, { color: theme.fgMuted }]}>
            {durationLabel} · {languageLabel}
          </Text>
        </View>
      </View>
    </GlassCard>
  );
};

const styles = StyleSheet.create({
  playCircle: {
    width: 42,
    height: 42,
    borderRadius: 21,
    alignItems: 'center',
    justifyContent: 'center',
  },
  metaText: {
    fontSize: 10,
    fontFamily: 'monospace',
    marginTop: 4,
  },
});

