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

interface CommunityFeedScreenProps {
  onSelectComplaint: (id: string) => void;
}

export const CommunityFeedScreen: React.FC<CommunityFeedScreenProps> = ({
  onSelectComplaint,
}) => {
  const { theme, isDark } = useAppTheme();

  const [sort, setSort] = useState<'recent' | 'popular' | 'priority' | 'nearby'>('recent');
  const [feedItems, setFeedItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchFeed();
  }, [sort]);

  const fetchFeed = async () => {
    try {
      setLoading(true);
      const res = await ApiClient.get(`/feed?sort=${sort}&page=1&page_size=20`);
      if (res.success && res.data?.items) {
        setFeedItems(res.data.items);
      }
    } catch {
      // Empty fallback
    } finally {
      setLoading(false);
    }
  };

  const handleToggleLike = async (item: any) => {
    try {
      const isLiked = item.user_liked;
      const updatedList = feedItems.map((fi) => {
        if (fi.id === item.id) {
          return {
            ...fi,
            user_liked: !isLiked,
            like_count: isLiked ? Math.max(0, (fi.like_count || 1) - 1) : (fi.like_count || 0) + 1,
          };
        }
        return fi;
      });
      setFeedItems(updatedList);

      if (isLiked) {
        await ApiClient.delete(`/complaints/${item.id}/like`);
      } else {
        await ApiClient.post(`/complaints/${item.id}/like`);
      }
    } catch {}
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <MeshBG isDark={isDark} />

      {/* Header */}
      <View style={styles.header}>
        <Text style={[styles.eyebrow, { color: theme.fgMuted }]}>
          Civic Transparency
        </Text>
        <Text style={[styles.title, { color: theme.fg }]}>Community Feed</Text>

        {/* Filter Pills */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterRow}
        >
          {(['recent', 'popular', 'priority', 'nearby'] as const).map((s) => {
            const isSelected = sort === s;
            return (
              <TouchableOpacity
                key={s}
                onPress={() => setSort(s)}
                style={[
                  styles.filterPill,
                  {
                    backgroundColor: isSelected ? theme.fg : theme.glassBgStrong,
                    borderColor: isSelected ? theme.fg : theme.glassBorder,
                  },
                ]}
              >
                <Text
                  style={[
                    styles.filterText,
                    {
                      color: isSelected
                        ? isDark
                          ? '#101012'
                          : '#FAFAFA'
                        : theme.fg,
                    },
                  ]}
                >
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* Feed List */}
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {loading ? (
          <View style={styles.centerLoading}>
            <ActivityIndicator size="small" color={theme.fg} />
          </View>
        ) : feedItems.length > 0 ? (
          feedItems.map((item) => (
            <GlassCard
              key={item.id}
              padding={18}
              radius={Radius.xl}
              style={{ marginBottom: 12 }}
            >
              <TouchableOpacity onPress={() => onSelectComplaint(item.id)}>
                <View style={styles.feedCardHeader}>
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.deptText, { color: theme.fgMuted }]}>
                      {item.department?.name || 'Department'}
                    </Text>
                    <Text style={[styles.itemTitle, { color: theme.fg }]}>
                      {item.title}
                    </Text>
                  </View>
                  <Chip
                    tone={
                      item.status === 'COMPLETED'
                        ? 'live'
                        : item.status === 'ONGOING'
                        ? 'pending'
                        : 'info'
                    }
                  >
                    {item.status}
                  </Chip>
                </View>

                {item.address && (
                  <View style={styles.locationRow}>
                    <Icons.pin size={14} color={theme.fgMuted} />
                    <Text style={[styles.addressText, { color: theme.fgMuted }]}>
                      {item.address} {item.distance_km ? `(${item.distance_km} km away)` : ''}
                    </Text>
                  </View>
                )}

                <View style={styles.feedCardFooter}>
                  <TouchableOpacity
                    onPress={() => handleToggleLike(item)}
                    style={[
                      styles.likeBtn,
                      {
                        backgroundColor: item.user_liked
                          ? 'rgba(229,72,77,0.15)'
                          : isDark
                          ? 'rgba(255,255,255,0.06)'
                          : 'rgba(0,0,0,0.04)',
                      },
                    ]}
                  >
                    <Icons.heart
                      size={18}
                      color={item.user_liked ? '#E5484D' : theme.fg}
                      filled={item.user_liked}
                    />
                    <Text
                      style={[
                        styles.likeCount,
                        {
                          color: item.user_liked ? '#E5484D' : theme.fg,
                        },
                      ]}
                    >
                      {item.like_count || 0}
                    </Text>
                  </TouchableOpacity>

                  <Text style={[styles.timeText, { color: theme.fgMuted }]}>
                    {new Date(item.created_at).toLocaleDateString()}
                  </Text>
                </View>
              </TouchableOpacity>
            </GlassCard>
          ))
        ) : (
          <GlassCard padding={32} radius={Radius.xl} style={{ alignItems: 'center' }}>
            <Icons.globe size={48} color={theme.fgMuted} />
            <Text style={{ fontSize: 17, fontWeight: '600', color: theme.fg, marginTop: 14 }}>
              No public complaints yet
            </Text>
            <Text style={{ fontSize: 13, color: theme.fgMuted, marginTop: 6, textAlign: 'center' }}>
              Complaints submitted by citizens will be visible in the live community feed.
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
    marginBottom: 14,
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
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 110,
  },
  feedCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 12,
  },
  deptText: {
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 4,
  },
  itemTitle: {
    fontSize: 17,
    fontWeight: '600',
    letterSpacing: -0.3,
    lineHeight: 22,
  },
  locationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 10,
  },
  addressText: {
    fontSize: 12,
  },
  feedCardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 14,
    paddingTop: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'rgba(255,255,255,0.06)',
  },
  likeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
  },
  likeCount: {
    fontSize: 13,
    fontWeight: '600',
  },
  timeText: {
    fontSize: 12,
  },
  centerLoading: {
    paddingTop: 60,
    alignItems: 'center',
  },
});

