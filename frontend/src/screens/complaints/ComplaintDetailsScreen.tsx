import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { ApiClient } from '../../api/client';
import { CloudBG } from '../../components/common/Backgrounds';
import { GlassCard, Chip } from '../../components/common/UIComponents';
import { Waveform } from '../../components/voice/Waveform';
import { Icons } from '../../components/common/Icons';
import { Radius } from '../../theme/tokens';

interface ComplaintDetailsScreenProps {
  complaintId: string;
  onBack: () => void;
}

export const ComplaintDetailsScreen: React.FC<ComplaintDetailsScreenProps> = ({
  complaintId,
  onBack,
}) => {
  const { theme, isDark } = useAppTheme();

  const [complaint, setComplaint] = useState<any>(null);
  const [updates, setUpdates] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);

  useEffect(() => {
    fetchComplaintDetails();
  }, [complaintId]);

  const fetchComplaintDetails = async () => {
    try {
      setLoading(true);
      const res = await ApiClient.get(`/complaints/${complaintId}`);
      if (res.success && res.data) {
        setComplaint(res.data);
      }

      const updatesRes = await ApiClient.get(`/complaints/${complaintId}/updates`);
      if (updatesRes.success && updatesRes.data?.items) {
        setUpdates(updatesRes.data.items);
      }
    } catch {
      // Fallback details
    } finally {
      setLoading(false);
    }
  };

  const getTone = (status: string) => {
    if (status === 'COMPLETED') return 'live';
    if (status === 'ONGOING' || status === 'PROCESSING') return 'pending';
    return 'info';
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <CloudBG isDark={isDark} opacity={0.5} />

      {/* Top Header */}
      <View style={styles.topHeader}>
        <TouchableOpacity
          onPress={onBack}
          style={[
            styles.backBtn,
            {
              backgroundColor: theme.glassBg,
              borderColor: theme.glassBorder,
            },
          ]}
        >
          <Icons.arrowLeft size={18} color={theme.fg} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: theme.fg }]}>
          {complaintId.substring(0, 8).toUpperCase()}
        </Text>
        <View style={{ width: 38 }} />
      </View>

      {loading ? (
        <View style={styles.centerLoading}>
          <ActivityIndicator size="small" color={theme.fg} />
        </View>
      ) : complaint ? (
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.scrollContent}
        >
          {/* Hero Card */}
          <GlassCard strong radius={Radius.xl} padding={22}>
            <View style={styles.chipRow}>
              <Chip tone={getTone(complaint.status)}>{complaint.status}</Chip>
              {complaint.priority_score && complaint.priority_score > 60 && (
                <Chip tone="urgent">High priority ({Math.round(complaint.priority_score)})</Chip>
              )}
            </View>

            <Text style={[styles.complaintTitle, { color: theme.fg }]}>
              {complaint.title}
            </Text>

            <View style={styles.metaRow}>
              <View style={styles.metaItem}>
                <Icons.building size={14} color={theme.fgMuted} />
                <Text style={[styles.metaText, { color: theme.fgMuted }]}>
                  {complaint.department?.name || 'Department'}
                </Text>
              </View>
              <View style={styles.metaItem}>
                <Icons.clock size={14} color={theme.fgMuted} />
                <Text style={[styles.metaText, { color: theme.fgMuted }]}>
                  {new Date(complaint.created_at).toLocaleDateString()}
                </Text>
              </View>
            </View>
          </GlassCard>

          {/* Audio Player Card */}
          <GlassCard padding={14} radius={Radius.lg} style={{ marginTop: 12 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
              <TouchableOpacity
                onPress={() => setIsPlayingAudio(!isPlayingAudio)}
                style={[
                  styles.audioPlayBtn,
                  { backgroundColor: theme.ctaBg },
                ]}
              >
                {isPlayingAudio ? (
                  <Icons.pause size={18} color={theme.ctaFg} />
                ) : (
                  <Icons.play size={18} color={theme.ctaFg} />
                )}
              </TouchableOpacity>
              <View style={{ flex: 1 }}>
                <Waveform isDark={isDark} bars={28} height={28} active={isPlayingAudio} />
                <Text
                  style={{
                    fontSize: 10,
                    color: theme.fgMuted,
                    fontFamily: 'monospace',
                    marginTop: 4,
                  }}
                >
                  0:24 · Original Voice File
                </Text>
              </View>
            </View>
          </GlassCard>

          {/* Detailed Description */}
          <Text style={[styles.sectionHeading, { color: theme.fgMuted, marginTop: 24 }]}>
            Complaint description
          </Text>
          <GlassCard padding={16} radius={Radius.lg}>
            <Text style={{ fontSize: 14, color: theme.fg, lineHeight: 22 }}>
              {complaint.description}
            </Text>
          </GlassCard>

          {/* Location Card */}
          <Text style={[styles.sectionHeading, { color: theme.fgMuted, marginTop: 20 }]}>
            Location
          </Text>
          <GlassCard padding={16} radius={Radius.lg}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <Icons.pin size={20} color={theme.fg} />
              <Text style={{ fontSize: 14, color: theme.fg, flex: 1 }}>
                {complaint.address || 'Address recorded'}
              </Text>
            </View>
          </GlassCard>

          {/* Timeline & Progress Updates */}
          <Text style={[styles.sectionHeading, { color: theme.fgMuted, marginTop: 24 }]}>
            Official lifecycle timeline
          </Text>
          <GlassCard padding={16} radius={Radius.xl}>
            <View style={{ gap: 16 }}>
              {/* Submitted Stage */}
              <View style={{ flexDirection: 'row', gap: 12 }}>
                <View style={[styles.timelineDot, { backgroundColor: '#2FBF71' }]} />
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: '600', color: theme.fg }}>
                    Complaint Registered
                  </Text>
                  <Text style={{ fontSize: 12, color: theme.fgMuted, marginTop: 2 }}>
                    Successfully received and routed to department.
                  </Text>
                </View>
              </View>

              {/* Ongoing / In Progress */}
              <View style={{ flexDirection: 'row', gap: 12 }}>
                <View
                  style={[
                    styles.timelineDot,
                    {
                      backgroundColor:
                        complaint.status !== 'SUBMITTED' ? '#F5A524' : theme.hairline,
                    },
                  ]}
                />
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: '600', color: theme.fg }}>
                    Staff Assigned & Triage
                  </Text>
                  <Text style={{ fontSize: 12, color: theme.fgMuted, marginTop: 2 }}>
                    {complaint.assigned_to
                      ? `Assigned to ${complaint.assigned_to.name}`
                      : 'Awaiting field staff assignment'}
                  </Text>
                </View>
              </View>

              {/* Completion Stage */}
              <View style={{ flexDirection: 'row', gap: 12 }}>
                <View
                  style={[
                    styles.timelineDot,
                    {
                      backgroundColor:
                        complaint.status === 'COMPLETED' ? '#2FBF71' : theme.hairline,
                    },
                  ]}
                />
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: '600', color: theme.fg }}>
                    Resolution & Proof
                  </Text>
                  <Text style={{ fontSize: 12, color: theme.fgMuted, marginTop: 2 }}>
                    {complaint.status === 'COMPLETED'
                      ? 'Issue verified and marked resolved by municipal team.'
                      : 'Pending completion evidence'}
                  </Text>
                </View>
              </View>
            </View>
          </GlassCard>
        </ScrollView>
      ) : (
        <View style={styles.centerLoading}>
          <Text style={{ color: theme.fgMuted }}>Complaint not found</Text>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    position: 'relative',
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
    fontFamily: 'monospace',
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 110,
  },
  chipRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 12,
  },
  complaintTitle: {
    fontSize: 22,
    fontWeight: '700',
    letterSpacing: -0.4,
    lineHeight: 28,
  },
  metaRow: {
    flexDirection: 'row',
    gap: 16,
    marginTop: 14,
  },
  metaItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  metaText: {
    fontSize: 12,
    fontWeight: '500',
  },
  audioPlayBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sectionHeading: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  timelineDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginTop: 4,
  },
  centerLoading: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
});

