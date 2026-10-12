import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { CloudBG, AIOrb } from '../../components/common/Backgrounds';
import { GlassCard, BigCTA } from '../../components/common/UIComponents';
import { Icons } from '../../components/common/Icons';
import { Radius } from '../../theme/tokens';

interface ComplaintSubmittedScreenProps {
  complaintId?: string;
  onTrackProgress: () => void;
  onReturnHome: () => void;
}

export const ComplaintSubmittedScreen: React.FC<ComplaintSubmittedScreenProps> = ({
  complaintId = 'GRV-2841',
  onTrackProgress,
  onReturnHome,
}) => {
  const { theme, isDark } = useAppTheme();

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <CloudBG isDark={isDark} opacity={0.8} />

      <View style={styles.centerBox}>
        <View style={styles.orbWrapper}>
          <AIOrb size={150} spinning={false} pulse={false} />
          <View
            style={[
              styles.checkCircle,
              { backgroundColor: isDark ? '#0E0E12' : '#FAFAFA' },
            ]}
          >
            <Icons.check size={36} color="#2FBF71" strokeWidth={2.5} />
          </View>
        </View>

        <View style={styles.textWrap}>
          <Text style={[styles.title, { color: theme.fg }]}>Complaint filed.</Text>
          <Text style={[styles.sub, { color: theme.fgMuted }]}>
            We've received your complaint and routed it to the right department.
          </Text>
        </View>

        {/* Tracking Reference Glass Card */}
        <GlassCard padding={20} radius={Radius.xl} style={{ width: '100%' }}>
          <View style={styles.referenceRow}>
            <View>
              <Text style={[styles.refLabel, { color: theme.fgMuted }]}>
                Tracking ID
              </Text>
              <Text style={[styles.refValue, { color: theme.fg }]}>
                {complaintId.substring(0, 8).toUpperCase()}
              </Text>
            </View>
            <View style={{ width: 1, backgroundColor: theme.hairline }} />
            <View>
              <Text style={[styles.refLabel, { color: theme.fgMuted }]}>
                SLA Target
              </Text>
              <Text style={[styles.refValue, { color: '#2FBF71' }]}>48 Hours</Text>
            </View>
          </View>
        </GlassCard>
      </View>

      {/* Action Buttons */}
      <View style={styles.bottomCta}>
        <BigCTA onPress={onTrackProgress} icon={<Icons.arrowRight size={18} color={theme.ctaFg} />}>
          Track progress
        </BigCTA>
        <BigCTA
          onPress={onReturnHome}
          variant="ghost"
          style={{ marginTop: 10 }}
        >
          Return home
        </BigCTA>
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
    gap: 28,
  },
  orbWrapper: {
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
  },
  checkCircle: {
    position: 'absolute',
    width: 68,
    height: 68,
    borderRadius: 34,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
  },
  textWrap: {
    alignItems: 'center',
  },
  title: {
    fontSize: 34,
    fontWeight: '700',
    letterSpacing: -1,
  },
  sub: {
    fontSize: 15,
    textAlign: 'center',
    marginTop: 10,
    lineHeight: 22,
    maxWidth: 290,
  },
  referenceRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
  },
  refLabel: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
  refValue: {
    fontSize: 17,
    fontWeight: '700',
    fontFamily: 'monospace',
    marginTop: 4,
  },
  bottomCta: {
    paddingHorizontal: 20,
    paddingBottom: 40,
  },
});

