import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { AIOrb } from '../../components/common/Backgrounds';
import { Waveform } from '../../components/voice/Waveform';
import { Icons } from '../../components/common/Icons';
import { BigCTA } from '../../components/common/UIComponents';

interface VoiceComplaintScreenProps {
  onCancel: () => void;
  onProceedToAIReview: (recordedData: {
    audioText: string;
    language: string;
    seconds: number;
  }) => void;
}

export const VoiceComplaintScreen: React.FC<VoiceComplaintScreenProps> = ({
  onCancel,
  onProceedToAIReview,
}) => {
  const { theme, isDark } = useAppTheme();

  const [isRecording, setIsRecording] = useState(true);
  const [seconds, setSeconds] = useState(14);
  const [selectedLang, setSelectedLang] = useState('Hindi · हिन्दी');
  const [transcript, setTranscript] = useState(
    'मेरे इलाके में सड़क पर पानी भर गया है, सीवेज लाइन ब्लॉक है और गाड़ियां नहीं निकल पा रही हैं…'
  );

  useEffect(() => {
    let interval: any;
    if (isRecording) {
      interval = setInterval(() => {
        setSeconds((prev) => prev + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isRecording]);

  const formatTimer = (totalSec: number) => {
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  const handleStopAndProceed = () => {
    setIsRecording(false);
    onProceedToAIReview({
      audioText: transcript,
      language: selectedLang,
      seconds,
    });
  };

  return (
    <View
      style={[
        styles.container,
        { backgroundColor: isDark ? '#050507' : '#FAFAFA' },
      ]}
    >
      {/* Top Header */}
      <View style={styles.topHeader}>
        <TouchableOpacity
          onPress={onCancel}
          style={[
            styles.backBtn,
            {
              backgroundColor: theme.glassBg,
              borderColor: theme.glassBorder,
            },
          ]}
        >
          <Icons.close size={18} color={theme.fg} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: theme.fg }]}>Voice complaint</Text>
        <TouchableOpacity>
          <Text style={[styles.helpText, { color: theme.fgMuted }]}>Help</Text>
        </TouchableOpacity>
      </View>

      {/* Language Selector Pill */}
      <View style={styles.langPillWrapper}>
        <View
          style={[
            styles.langPill,
            {
              backgroundColor: theme.glassBgStrong,
              borderColor: theme.glassBorder,
            },
          ]}
        >
          <View
            style={[
              styles.globeIconCircle,
              { backgroundColor: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.06)' },
            ]}
          >
            <Icons.globe size={14} color={theme.fg} />
          </View>
          <Text style={[styles.langText, { color: theme.fg }]}>{selectedLang}</Text>
          <Icons.chevronDown size={14} color={theme.fgMuted} />
        </View>
      </View>

      {/* Central Spinning AI Orb & Wave */}
      <View style={styles.centerArea}>
        <AIOrb size={170} spinning={isRecording} pulse={isRecording} />

        {/* Timer */}
        <View style={styles.timerWrapper}>
          <Text style={[styles.timerDigits, { color: theme.fg }]}>
            {formatTimer(seconds)}
          </Text>
          <Text style={[styles.recordingStatus, { color: '#E5484D' }]}>
            {isRecording ? '• RECORDING' : 'PAUSED'}
          </Text>
        </View>

        {/* Dynamic Waveform */}
        <View style={styles.waveformContainer}>
          <Waveform isDark={isDark} bars={38} height={52} active={isRecording} />
        </View>

        {/* Live Transcript Preview Box */}
        <View
          style={[
            styles.transcriptBox,
            {
              backgroundColor: theme.glassBgStrong,
              borderColor: theme.glassBorder,
            },
          ]}
        >
          <Text style={[styles.transcriptEyebrow, { color: theme.fgMuted }]}>
            Live transcript
          </Text>
          <Text style={[styles.transcriptContent, { color: theme.fg }]}>
            "{transcript}"
          </Text>
        </View>
      </View>

      {/* Floating Bottom Controls */}
      <View style={styles.bottomControls}>
        <TouchableOpacity
          onPress={onCancel}
          style={styles.actionCtrl}
        >
          <View
            style={[
              styles.ctrlCircle,
              { backgroundColor: theme.glassBg, borderColor: theme.glassBorder },
            ]}
          >
            <Icons.close size={20} color={theme.fg} />
          </View>
          <Text style={[styles.ctrlLabel, { color: theme.fgMuted }]}>Cancel</Text>
        </TouchableOpacity>

        {/* Primary Finish / Stop Button */}
        <TouchableOpacity
          onPress={handleStopAndProceed}
          activeOpacity={0.85}
          style={styles.recordCircleBtn}
        >
          <View style={styles.stopSquare} />
        </TouchableOpacity>

        {/* Pause / Resume */}
        <TouchableOpacity
          onPress={() => setIsRecording(!isRecording)}
          style={styles.actionCtrl}
        >
          <View
            style={[
              styles.ctrlCircle,
              { backgroundColor: theme.glassBg, borderColor: theme.glassBorder },
            ]}
          >
            {isRecording ? (
              <Icons.pause size={20} color={theme.fg} />
            ) : (
              <Icons.play size={20} color={theme.fg} />
            )}
          </View>
          <Text style={[styles.ctrlLabel, { color: theme.fgMuted }]}>
            {isRecording ? 'Pause' : 'Resume'}
          </Text>
        </TouchableOpacity>
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
  topHeader: {
    marginTop: 64,
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
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    letterSpacing: -0.2,
  },
  helpText: {
    fontSize: 14,
    fontWeight: '600',
  },
  langPillWrapper: {
    alignItems: 'center',
    marginTop: 10,
  },
  langPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 7,
    paddingHorizontal: 14,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
  },
  globeIconCircle: {
    width: 26,
    height: 26,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
  },
  langText: {
    fontSize: 13,
    fontWeight: '600',
  },
  centerArea: {
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  timerWrapper: {
    alignItems: 'center',
    marginTop: 22,
  },
  timerDigits: {
    fontSize: 44,
    fontWeight: '700',
    letterSpacing: -1,
  },
  recordingStatus: {
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.8,
    marginTop: 4,
  },
  waveformContainer: {
    width: '100%',
    marginVertical: 18,
  },
  transcriptBox: {
    padding: 16,
    borderRadius: 20,
    borderWidth: StyleSheet.hairlineWidth,
    width: '100%',
    alignItems: 'center',
  },
  transcriptEyebrow: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 6,
  },
  transcriptContent: {
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
  },
  bottomControls: {
    paddingBottom: 48,
    paddingHorizontal: 36,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  actionCtrl: {
    alignItems: 'center',
    gap: 6,
  },
  ctrlCircle: {
    width: 54,
    height: 54,
    borderRadius: 27,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth,
  },
  ctrlLabel: {
    fontSize: 12,
    fontWeight: '500',
  },
  recordCircleBtn: {
    width: 76,
    height: 76,
    borderRadius: 38,
    backgroundColor: '#E5484D',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#E5484D',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.45,
    shadowRadius: 20,
    elevation: 8,
  },
  stopSquare: {
    width: 26,
    height: 26,
    borderRadius: 5,
    backgroundColor: '#FAFAFA',
  },
});

