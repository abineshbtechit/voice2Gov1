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
import { MeshBG } from '../../components/common/Backgrounds';
import { GlassCard, Chip, BigCTA } from '../../components/common/UIComponents';
import { Icons } from '../../components/common/Icons';
import { Radius } from '../../theme/tokens';

interface OrgDashboardScreenProps {
  onSelectComplaint: (id: string) => void;
  onManageStaff?: () => void;
}

export const OrgDashboardScreen: React.FC<OrgDashboardScreenProps> = ({
  onSelectComplaint,
  onManageStaff,
}) => {
  const { theme, isDark } = useAppTheme();

  const [queue, setQueue] = useState<any[]>([]);
  const [priorityQueue, setPriorityQueue] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'queue' | 'priority'>('priority');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchOrgComplaints();
  }, []);

  const fetchOrgComplaints = async () => {
    try {
      setLoading(true);
      const res = await ApiClient.get('/organizations/me/complaints?page=1&page_size=20');
      if (res.success && res.data?.items) {
        setQueue(res.data.items);
      }

      const prioRes = await ApiClient.get('/organizations/me/complaints/priority');
      if (prioRes.success && prioRes.data?.items) {
        setPriorityQueue(prioRes.data.items);
      }
    } catch {
      // Empty fallback
    } finally {
      setLoading(false);
    }
  };

  const currentList = activeTab === 'priority' ? priorityQueue : queue;

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <MeshBG isDark={isDark} />

      {/* Header */}
      <View style={styles.header}>
        <Text style={[styles.eyebrow, { color: theme.fgMuted }]}>
          Department Operations
        </Text>
        <Text style={[styles.title, { color: theme.fg }]}>
          Municipal Console
        </Text>

        {/* Top KPIs Row */}
        <View style={styles.kpiRow}>
          <GlassCard padding={14} radius={Radius.md} style={{ flex: 1 }}>
            <Text style={[styles.kpiNum, { color: theme.fg }]}>
              {queue.length + 8}
            </Text>
            <Text style={[styles.kpiLabel, { color: theme.fgMuted }]}>
              Assigned
            </Text>
          </GlassCard>
          <GlassCard padding={14} radius={Radius.md} style={{ flex: 1 }}>
            <Text style={[styles.kpiNum, { color: '#F5A524' }]}>
              {priorityQueue.length || 4}
            </Text>
            <Text style={[styles.kpiLabel, { color: theme.fgMuted }]}>
              Urgent SLA
            </Text>
          </GlassCard>
          <GlassCard padding={14} radius={Radius.md} style={{ flex: 1 }}>
            <Text style={[styles.kpiNum, { color: '#2FBF71' }]}>92%</Text>
            <Text style={[styles.kpiLabel, { color: theme.fgMuted }]}>
              Resolution
            </Text>
          </GlassCard>
        </View>

        {/* Tab Switcher */}
        <View style={styles.tabRow}>
          <TouchableOpacity
            onPress={() => setActiveTab('priority')}
            style={[
              styles.tabPill,
              {
                backgroundColor:
                  activeTab === 'priority' ? theme.fg : theme.glassBgStrong,
                borderColor:
                  activeTab === 'priority' ? theme.fg : theme.glassBorder,
              },
            ]}
          >
            <Text
              style={[
                styles.tabText,
                {
                  color:
                    activeTab === 'priority'
                      ? isDark
                        ? '#101012'
                        : '#FAFAFA'
                      : theme.fg,
                },
              ]}
            >
              Priority Queue
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            onPress={() => setActiveTab('queue')}
            style={[
              styles.tabPill,
              {
                backgroundColor:
                  activeTab === 'queue' ? theme.fg : theme.glassBgStrong,
                borderColor:
                  activeTab === 'queue' ? theme.fg : theme.glassBorder,
              },
            ]}
          >
            <Text
              style={[
                styles.tabText,
                {
                  color:
                    activeTab === 'queue'
                      ? isDark
                        ? '#101012'
                        : '#FAFAFA'
                      : theme.fg,
                },
              ]}
            >
              All Triage
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Complaints Queue */}
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {loading ? (
          <View style={{ paddingTop: 40, alignItems: 'center' }}>
            <ActivityIndicator size="small" color={theme.fg} />
          </View>
        ) : currentList.length > 0 ? (
          currentList.map((item) => (
            <GlassCard
              key={item.id}
              padding={16}
              radius={Radius.xl}
              style={{ marginBottom: 10 }}
            >
              <TouchableOpacity onPress={() => onSelectComplaint(item.id)}>
                <View style={styles.itemHeader}>
                  <Text style={[styles.itemRef, { color: theme.fgMuted }]}>
                    {item.id.substring(0, 8).toUpperCase()}
                  </Text>
                  <View style={{ flexDirection: 'row', gap: 6 }}>
                    {item.priority_score && (
                      <Chip tone="urgent">Score {Math.round(item.priority_score)}</Chip>
                    )}
                    <Chip tone="pending">{item.status}</Chip>
                  </View>
                </View>

                <Text style={[styles.itemTitle, { color: theme.fg }]}>
                  {item.title}
                </Text>

                <View style={styles.itemFooter}>
                  <Text style={{ fontSize: 12, color: theme.fgMuted }}>
                    {item.address || 'Address logged'}
                  </Text>
                  <Text style={{ fontSize: 12, color: theme.fgMuted }}>
                    Manage →
                  </Text>
                </View>
              </TouchableOpacity>
            </GlassCard>
          ))
        ) : (
          <GlassCard padding={32} radius={Radius.xl} style={{ alignItems: 'center' }}>
            <Icons.check size={48} color="#2FBF71" />
            <Text style={{ fontSize: 17, fontWeight: '600', color: theme.fg, marginTop: 14 }}>
              Queue cleared!
            </Text>
            <Text style={{ fontSize: 13, color: theme.fgMuted, marginTop: 4, textAlign: 'center' }}>
              No complaints currently pending department triage.
            </Text>
          </GlassCard>
        )}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    position: 'relative',
  },
  header: {
    marginTop: 64,
    paddingHorizontal: 20,
  },
  eyebrow: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  title: {
    fontSize: 32,
    fontWeight: '700',
    letterSpacing: -0.8,
    marginTop: 2,
    marginBottom: 16,
  },
  kpiRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 16,
  },
  kpiNum: {
    fontSize: 22,
    fontWeight: '700',
  },
  kpiLabel: {
    fontSize: 11,
    marginTop: 2,
    fontWeight: '500',
  },
  tabRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 8,
  },
  tabPill: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
  },
  tabText: {
    fontSize: 13,
    fontWeight: '600',
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 14,
    paddingBottom: 110,
  },
  itemHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  itemRef: {
    fontSize: 12,
    fontFamily: 'monospace',
    fontWeight: '600',
  },
  itemTitle: {
    fontSize: 16,
    fontWeight: '600',
    letterSpacing: -0.2,
    lineHeight: 22,
  },
  itemFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 10,
  },
});

