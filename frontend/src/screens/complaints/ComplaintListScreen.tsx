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
import { GlassCard, Chip } from '../../components/common/UIComponents';
import { Icons } from '../../components/common/Icons';
import { Radius } from '../../theme/tokens';

interface ComplaintListScreenProps {
  onSelectComplaint: (id: string) => void;
  onNewComplaint: () => void;
}

export const ComplaintListScreen: React.FC<ComplaintListScreenProps> = ({
  onSelectComplaint,
  onNewComplaint,
}) => {
  const { theme, isDark } = useAppTheme();

  const [activeTab, setActiveTab] = useState<'All' | 'Active' | 'Resolved' | 'Urgent'>('All');
  const [complaints, setComplaints] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchComplaints();
  }, [activeTab]);

  const fetchComplaints = async () => {
    try {
      setLoading(true);
      let statusFilter = '';
      if (activeTab === 'Active') statusFilter = '&status=ONGOING';
      if (activeTab === 'Resolved') statusFilter = '&status=COMPLETED';

      const res = await ApiClient.get(`/complaints/my?page=1&page_size=20${statusFilter}`);
      if (res.success && res.data?.items) {
        setComplaints(res.data.items);
      }
    } catch {
      // Empty fallback
    } finally {
      setLoading(false);
    }
  };

  const getTone = (status: string) => {
    if (status === 'COMPLETED') return 'live';
    if (status === 'ONGOING' || status === 'PROCESSING') return 'pending';
    if (status === 'REJECTED') return 'urgent';
    return 'info';
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <MeshBG isDark={isDark} />

      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerTop}>
          <View>
            <Text style={[styles.eyebrow, { color: theme.fgMuted }]}>
              You've filed
            </Text>
            <Text style={[styles.headingCount, { color: theme.fg }]}>
              {complaints.length} complaints
            </Text>
          </View>

          <TouchableOpacity
            onPress={onNewComplaint}
            style={[
              styles.addBtn,
              {
                backgroundColor: theme.ctaBg,
              },
            ]}
          >
            <Icons.plus size={20} color={theme.ctaFg} />
          </TouchableOpacity>
        </View>

        {/* Filter Segmented Pills */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterRow}
        >
          {(['All', 'Active', 'Resolved', 'Urgent'] as const).map((tab) => {
            const isSelected = activeTab === tab;
            return (
              <TouchableOpacity
                key={tab}
                onPress={() => setActiveTab(tab)}
                style={[
                  styles.filterPill,
                  {
                    backgroundColor: isSelected
                      ? theme.fg
                      : theme.glassBgStrong,
                    borderColor: isSelected ? theme.fg : theme.glassBorder,
                  },
                ]}
              >
                <Text
                  style={[
                    styles.filterText,
                    { color: isSelected ? (isDark ? '#101012' : '#FAFAFA') : theme.fg },
                  ]}
                >
                  {tab}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* Complaints List */}
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.listContent}
      >
        {loading ? (
          <View style={styles.centerLoading}>
            <ActivityIndicator size="small" color={theme.fg} />
          </View>
        ) : complaints.length > 0 ? (
          complaints.map((c) => (
            <GlassCard
              key={c.id}
              padding={16}
              radius={Radius.lg}
              style={{ marginBottom: 10 }}
            >
              <TouchableOpacity onPress={() => onSelectComplaint(c.id)}>
                <View style={styles.cardTop}>
                  <Text style={[styles.cardId, { color: theme.fgMuted }]}>
                    {c.id.substring(0, 8).toUpperCase()}
                  </Text>
                  <Chip tone={getTone(c.status)}>{c.status}</Chip>
                </View>

                <Text style={[styles.cardTitle, { color: theme.fg }]}>
                  {c.title}
                </Text>

                <View style={styles.cardMetaRow}>
                  <Text style={[styles.cardMeta, { color: theme.fgMuted }]}>
                    {c.department?.name || 'Assigned Department'}
                  </Text>
                  <Text style={[styles.cardMeta, { color: theme.fgMuted }]}>
                    {new Date(c.created_at).toLocaleDateString()}
                  </Text>
                </View>
              </TouchableOpacity>
            </GlassCard>
          ))
        ) : (
          <GlassCard padding={32} radius={Radius.xl} style={{ alignItems: 'center' }}>
            <Icons.list size={48} color={theme.fgMuted} />
            <Text style={[styles.emptyTitle, { color: theme.fg, marginTop: 14 }]}>
              No complaints in this category
            </Text>
            <Text style={[styles.emptySub, { color: theme.fgMuted, marginTop: 6 }]}>
              Track your reported grievances in real-time.
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
  headerTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  eyebrow: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  headingCount: {
    fontSize: 32,
    fontWeight: '700',
    letterSpacing: -0.8,
    marginTop: 2,
  },
  addBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
  },
  filterRow: {
    gap: 8,
    paddingBottom: 4,
  },
  filterPill: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
  },
  filterText: {
    fontSize: 13,
    fontWeight: '600',
    letterSpacing: -0.1,
  },
  listContent: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 110,
  },
  cardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  cardId: {
    fontSize: 12,
    fontFamily: 'monospace',
    fontWeight: '600',
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '600',
    letterSpacing: -0.2,
    lineHeight: 22,
  },
  cardMetaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 10,
  },
  cardMeta: {
    fontSize: 12,
  },
  centerLoading: {
    paddingTop: 60,
    alignItems: 'center',
  },
  emptyTitle: {
    fontSize: 17,
    fontWeight: '600',
  },
  emptySub: {
    fontSize: 13,
    textAlign: 'center',
  },
});

