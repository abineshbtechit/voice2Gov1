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

interface NotificationsScreenProps {
  onBack: () => void;
  onSelectComplaint?: (id: string) => void;
}

export const NotificationsScreen: React.FC<NotificationsScreenProps> = ({
  onBack,
  onSelectComplaint,
}) => {
  const { theme, isDark } = useAppTheme();

  const [notifications, setNotifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchNotifications();
  }, []);

  const fetchNotifications = async () => {
    try {
      setLoading(true);
      const res = await ApiClient.get('/notifications?page=1&page_size=30');
      if (res.success && res.data?.items) {
        setNotifications(res.data.items);
      }
    } catch {
      // Empty fallback
    } finally {
      setLoading(false);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await ApiClient.patch('/notifications/read-all');
      setNotifications((prev) =>
        prev.map((n) => ({ ...n, is_read: true }))
      );
    } catch {}
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <MeshBG isDark={isDark} />

      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerTop}>
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
          <TouchableOpacity onPress={handleMarkAllRead}>
            <Text style={[styles.markAllText, { color: theme.fg }]}>
              Mark all read
            </Text>
          </TouchableOpacity>
        </View>

        <Text style={[styles.eyebrow, { color: theme.fgMuted }]}>Alerts</Text>
        <Text style={[styles.pageTitle, { color: theme.fg }]}>Notifications</Text>
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {loading ? (
          <View style={styles.centerLoading}>
            <ActivityIndicator size="small" color={theme.fg} />
          </View>
        ) : notifications.length > 0 ? (
          notifications.map((n) => (
            <GlassCard
              key={n.id}
              padding={14}
              radius={Radius.lg}
              style={{ marginBottom: 10 }}
            >
              <TouchableOpacity
                onPress={() => n.complaint_id && onSelectComplaint?.(n.complaint_id)}
                style={{ flexDirection: 'row', gap: 12 }}
              >
                <View
                  style={[
                    styles.iconCircle,
                    {
                      backgroundColor: n.is_read
                        ? isDark
                          ? 'rgba(255,255,255,0.06)'
                          : 'rgba(0,0,0,0.05)'
                        : 'rgba(47,191,113,0.15)',
                    },
                  ]}
                >
                  <Icons.bell
                    size={18}
                    color={n.is_read ? theme.fgMuted : '#2FBF71'}
                  />
                </View>

                <View style={{ flex: 1 }}>
                  <View style={styles.notifTop}>
                    <Text
                      style={[
                        styles.notifTitle,
                        { color: theme.fg, fontWeight: n.is_read ? '500' : '700' },
                      ]}
                    >
                      {n.title}
                    </Text>
                    <Text style={[styles.timeText, { color: theme.fgMuted }]}>
                      {new Date(n.created_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </Text>
                  </View>
                  <Text style={[styles.notifMessage, { color: theme.fgMuted }]}>
                    {n.message}
                  </Text>
                </View>
              </TouchableOpacity>
            </GlassCard>
          ))
        ) : (
          <GlassCard padding={32} radius={Radius.xl} style={{ alignItems: 'center' }}>
            <Icons.bell size={48} color={theme.fgMuted} />
            <Text style={[styles.emptyHeading, { color: theme.fg, marginTop: 14 }]}>
              You're all caught up.
            </Text>
            <Text style={[styles.emptySub, { color: theme.fgMuted, marginTop: 6 }]}>
              No new updates from municipal departments.
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
    marginBottom: 8,
  },
  headerTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  backBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth,
  },
  markAllText: {
    fontSize: 13,
    fontWeight: '600',
  },
  eyebrow: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  pageTitle: {
    fontSize: 32,
    fontWeight: '700',
    letterSpacing: -0.8,
    marginTop: 2,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 14,
    paddingBottom: 110,
  },
  iconCircle: {
    width: 40,
    height: 40,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  notifTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  notifTitle: {
    fontSize: 14,
    flex: 1,
    marginRight: 8,
  },
  timeText: {
    fontSize: 11,
    fontFamily: 'monospace',
  },
  notifMessage: {
    fontSize: 13,
    marginTop: 3,
    lineHeight: 18,
  },
  centerLoading: {
    paddingTop: 60,
    alignItems: 'center',
  },
  emptyHeading: {
    fontSize: 17,
    fontWeight: '600',
  },
  emptySub: {
    fontSize: 13,
    textAlign: 'center',
  },
});

