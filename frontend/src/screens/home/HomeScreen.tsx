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
import { useAuth } from '../../context/AuthContext';
import { ApiClient } from '../../api/client';
import { CloudBG } from '../../components/common/Backgrounds';
import { GlassCard, Chip } from '../../components/common/UIComponents';
import { Icons } from '../../components/common/Icons';
import { Radius } from '../../theme/tokens';

interface HomeScreenProps {
  onStartVoice: () => void;
  onStartText: () => void;
  onViewComplaints: () => void;
  onOpenNotifications: () => void;
  onSelectComplaint: (id: string) => void;
  onOpenProfile?: () => void;
}

export const HomeScreen: React.FC<HomeScreenProps> = ({
  onStartVoice,
  onStartText,
  onViewComplaints,
  onOpenNotifications,
  onSelectComplaint,
  onOpenProfile,
}) => {
  const { theme, isDark } = useAppTheme();
  const { user } = useAuth();

  const [activeComplaint, setActiveComplaint] = useState<any>(null);
  const [recentComplaints, setRecentComplaints] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHomeData();
  }, []);

  const fetchHomeData = async () => {
    try {
      setLoading(true);
      const res = await ApiClient.get('/complaints/my?page=1&page_size=5');
      if (res.success && res.data?.items) {
        const items = res.data.items;
        if (items.length > 0) {
          setActiveComplaint(items[0]);
          setRecentComplaints(items.slice(1, 4));
        }
      }
    } catch {
      // Fallback empty
    } finally {
      setLoading(false);
    }
  };

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  };

  const initials = user?.full_name
    ? user.full_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .substring(0, 2)
        .toUpperCase()
    : 'AS';

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <CloudBG isDark={isDark} opacity={0.85} />

      {/* Top Bar: Greeting + Avatar */}
      <View style={styles.topRow}>
        <View style={{ flex: 1 }}>
          <Text style={[styles.greetingEyebrow, { color: theme.fgMuted }]}>
            {getGreeting()}
          </Text>
          <Text style={[styles.userName, { color: theme.fg }]}>
            {user?.full_name || 'Citizen'}
          </Text>
        </View>

        <TouchableOpacity
          onPress={onOpenNotifications}
          style={[
            styles.iconCircle,
            {
              backgroundColor: theme.glassBg,
              borderColor: theme.glassBorder,
            },
          ]}
        >
          <Icons.bell size={20} color={theme.fg} />
          <View style={styles.unreadDot} />
        </TouchableOpacity>

        <TouchableOpacity
          onPress={onOpenProfile}
          activeOpacity={0.8}
          style={[
            styles.avatarCircle,
            {
              backgroundColor: isDark ? '#38383D' : '#D6D6D9',
            },
          ]}
        >
          <Text style={[styles.avatarText, { color: isDark ? '#FAFAFA' : '#101012' }]}>
            {initials}
          </Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {/* Hero Card: Active Complaint Status */}
        {activeComplaint ? (
          <GlassCard strong radius={Radius.xl} padding={22}>
            <View style={styles.cardHeader}>
              <Text style={[styles.cardEyebrow, { color: theme.fgMuted }]}>
                Your active complaint
              </Text>
              <Chip
                tone={
                  activeComplaint.status === 'COMPLETED'
                    ? 'live'
                    : activeComplaint.status === 'PROCESSING' || activeComplaint.status === 'ONGOING'
                    ? 'pending'
                    : 'info'
                }
              >
                {activeComplaint.status}
              </Chip>
            </View>

            <TouchableOpacity onPress={() => onSelectComplaint(activeComplaint.id)}>
              <Text style={[styles.complaintTitle, { color: theme.fg }]}>
                {activeComplaint.title}
              </Text>
              <Text style={[styles.complaintMeta, { color: theme.fgMuted }]}>
                {activeComplaint.id.substring(0, 8)} ·{' '}
                {activeComplaint.department?.name || 'Assigned Department'}
              </Text>

              {/* 5-Stage Progress Bar */}
              <View style={styles.progressRow}>
                {[1, 2, 3, 4, 5].map((stage) => {
                  const stageMap: Record<string, number> = {
                    SUBMITTED: 1,
                    ONGOING: 2,
                    PROCESSING: 3,
                    COMPLETED: 5,
                  };
                  const current = stageMap[activeComplaint.status] || 1;
                  const isFilled = stage <= current;

                  return (
                    <View
                      key={stage}
                      style={[
                        styles.progressBarSegment,
                        {
                          backgroundColor: isFilled
                            ? theme.fg
                            : isDark
                            ? 'rgba(255,255,255,0.1)'
                            : 'rgba(0,0,0,0.08)',
                        },
                      ]}
                    />
                  );
                })}
              </View>

              <View style={styles.progressFooter}>
                <Text style={[styles.progressLabel, { color: theme.fgMuted }]}>
                  Stage tracking active
                </Text>
                <Text style={[styles.progressLabel, { color: theme.fgMuted }]}>
                  View details →
                </Text>
              </View>
            </TouchableOpacity>
          </GlassCard>
        ) : (
          <GlassCard strong radius={Radius.xl} padding={22}>
            <Text style={[styles.cardEyebrow, { color: theme.fgMuted }]}>
              Civil Grievance Platform
            </Text>
            <Text style={[styles.complaintTitle, { color: theme.fg, marginTop: 8 }]}>
              No active issues reported
            </Text>
            <Text style={[styles.complaintMeta, { color: theme.fgMuted, marginTop: 4 }]}>
              Report potholes, water leaks, or power outages instantly with your voice.
            </Text>
          </GlassCard>
        )}

        {/* Quick Action Grid */}
        <View style={styles.actionGrid}>
          {/* Voice Action */}
          <TouchableOpacity
            activeOpacity={0.85}
            onPress={onStartVoice}
            style={[
              styles.actionTile,
              {
                backgroundColor: theme.ctaBg,
                shadowColor: isDark ? '#FFFFFF' : '#000000',
                shadowOpacity: isDark ? 0.08 : 0.16,
              },
            ]}
          >
            <Icons.mic size={26} color={theme.ctaFg} />
            <View>
              <Text style={[styles.actionTitle, { color: theme.ctaFg }]}>Voice</Text>
              <Text style={[styles.actionSub, { color: isDark ? '#94949A' : '#72727A' }]}>
                Speak it
              </Text>
            </View>
          </TouchableOpacity>

          {/* Text Action */}
          <TouchableOpacity
            activeOpacity={0.85}
            onPress={onStartText}
            style={[
              styles.actionTile,
              {
                backgroundColor: theme.glassBgStrong,
                borderWidth: StyleSheet.hairlineWidth,
                borderColor: theme.glassBorder,
              },
            ]}
          >
            <Icons.edit size={24} color={theme.fg} />
            <View>
              <Text style={[styles.actionTitle, { color: theme.fg }]}>Text</Text>
              <Text style={[styles.actionSub, { color: theme.fgMuted }]}>Type it</Text>
            </View>
          </TouchableOpacity>
        </View>

        {/* Recent Complaints */}
        <View style={styles.sectionHeader}>
          <Text style={[styles.sectionTitle, { color: theme.fg }]}>Recent</Text>
          <TouchableOpacity onPress={onViewComplaints}>
            <Text style={[styles.seeAllText, { color: theme.fgMuted }]}>See all</Text>
          </TouchableOpacity>
        </View>

        <View style={{ gap: 10 }}>
          {recentComplaints.length > 0 ? (
            recentComplaints.map((item) => (
              <GlassCard
                key={item.id}
                padding={16}
                radius={Radius.lg}
                style={{ marginBottom: 4 }}
              >
                <TouchableOpacity onPress={() => onSelectComplaint(item.id)}>
                  <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Text style={{ fontSize: 15, fontWeight: '600', color: theme.fg, flex: 1, marginRight: 10 }}>
                      {item.title}
                    </Text>
                    <Chip tone={item.status === 'COMPLETED' ? 'live' : 'pending'}>
                      {item.status}
                    </Chip>
                  </View>
                  <Text style={{ fontSize: 12, color: theme.fgMuted, marginTop: 4 }}>
                    {item.department?.name || 'Department'} · {new Date(item.created_at).toLocaleDateString()}
                  </Text>
                </TouchableOpacity>
              </GlassCard>
            ))
          ) : (
            <GlassCard padding={20} radius={Radius.lg}>
              <Text style={{ fontSize: 14, color: theme.fgMuted, textAlign: 'center' }}>
                Your submitted complaints will appear here
              </Text>
            </GlassCard>
          )}
        </View>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    position: 'relative',
  },
  topRow: {
    marginTop: 64,
    paddingHorizontal: 20,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  greetingEyebrow: {
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.6,
    textTransform: 'uppercase',
  },
  userName: {
    fontSize: 26,
    fontWeight: '700',
    letterSpacing: -0.6,
    marginTop: 2,
  },
  iconCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth,
    position: 'relative',
  },
  unreadDot: {
    position: 'absolute',
    top: 10,
    right: 12,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#E5484D',
  },
  avatarCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontWeight: '700',
    fontSize: 16,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 110,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  cardEyebrow: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
  },
  complaintTitle: {
    fontSize: 20,
    fontWeight: '600',
    letterSpacing: -0.3,
    lineHeight: 26,
    marginBottom: 6,
  },
  complaintMeta: {
    fontSize: 13,
    marginBottom: 18,
  },
  progressRow: {
    flexDirection: 'row',
    gap: 4,
    marginBottom: 8,
  },
  progressBarSegment: {
    flex: 1,
    height: 5,
    borderRadius: 2.5,
  },
  progressFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  progressLabel: {
    fontSize: 11,
    fontWeight: '500',
  },
  actionGrid: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 16,
  },
  actionTile: {
    flex: 1,
    minHeight: 108,
    borderRadius: Radius.lg,
    padding: 18,
    justifyContent: 'space-between',
    shadowOffset: { width: 0, height: 6 },
    shadowRadius: 18,
    elevation: 3,
  },
  actionTitle: {
    fontSize: 17,
    fontWeight: '600',
    letterSpacing: -0.2,
  },
  actionSub: {
    fontSize: 12,
    marginTop: 2,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 28,
    marginBottom: 14,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '700',
    letterSpacing: -0.4,
  },
  seeAllText: {
    fontSize: 14,
    fontWeight: '500',
  },
});

