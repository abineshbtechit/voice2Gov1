import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  TextInput,
} from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { ApiClient } from '../../api/client';
import { CloudBG } from '../../components/common/Backgrounds';
import { GlassCard, Chip } from '../../components/common/UIComponents';
import { Icons } from '../../components/common/Icons';
import { Radius } from '../../theme/tokens';

interface AdminAuditLogsScreenProps {
  onBack: () => void;
}

export const AdminAuditLogsScreen: React.FC<AdminAuditLogsScreenProps> = ({ onBack }) => {
  const { theme, isDark } = useAppTheme();

  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterAction, setFilterAction] = useState<string>('');
  const [page, setPage] = useState(1);
  const [totalLogs, setTotalLogs] = useState(0);

  useEffect(() => {
    fetchLogs();
  }, [page, filterAction]);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      let url = `/admin/audit-logs?page=${page}&page_size=25`;
      if (filterAction.trim()) {
        url += `&action=${encodeURIComponent(filterAction.trim())}`;
      }
      const res = await ApiClient.get(url);
      if (res.success && res.data?.items) {
        setLogs(res.data.items);
        setTotalLogs((res as any).pagination?.total_items || res.data.items.length);
      }
    } catch {
      // Fallback empty
    } finally {
      setLoading(false);
    }
  };

  const getActionColor = (action: string) => {
    const act = (action || '').toLowerCase();
    if (act.includes('delete') || act.includes('suspend') || act.includes('reject')) return 'urgent';
    if (act.includes('create') || act.includes('activate') || act.includes('complete')) return 'live';
    if (act.includes('assign') || act.includes('update')) return 'pending';
    return 'info';
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <CloudBG isDark={isDark} opacity={0.5} />

      {/* Header */}
      <View style={styles.topHeader}>
        <TouchableOpacity
          onPress={onBack}
          style={[
            styles.backBtn,
            { backgroundColor: theme.glassBg, borderColor: theme.glassBorder },
          ]}
        >
          <Icons.arrowLeft size={18} color={theme.fg} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: theme.fg }]}>Audit Logs</Text>
        <View style={{ width: 38 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Subtitle */}
        <Text style={[styles.subtitle, { color: theme.fgMuted }]}>
          Immutable security and compliance event log ({totalLogs} events recorded).
        </Text>

        {/* Action Filter Input */}
        <GlassCard padding={12} radius={Radius.lg} style={{ marginTop: 14 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <Icons.search size={16} color={theme.fgMuted} />
            <TextInput
              placeholder="Filter by action (e.g., user_suspend, status_change)"
              placeholderTextColor={theme.fgMuted}
              value={filterAction}
              onChangeText={(t) => {
                setFilterAction(t);
                setPage(1);
              }}
              style={[styles.filterInput, { color: theme.fg }]}
            />
            {filterAction.length > 0 && (
              <TouchableOpacity onPress={() => setFilterAction('')}>
                <Icons.close size={16} color={theme.fgMuted} />
              </TouchableOpacity>
            )}
          </View>
        </GlassCard>

        {/* Logs List */}
        {loading ? (
          <View style={{ paddingVertical: 40, alignItems: 'center' }}>
            <ActivityIndicator size="small" color={theme.fg} />
          </View>
        ) : logs.length === 0 ? (
          <View style={{ paddingVertical: 40, alignItems: 'center' }}>
            <Icons.clock size={32} color={theme.fgMuted} />
            <Text style={{ color: theme.fgMuted, marginTop: 10, fontSize: 14 }}>
              No audit logs found matching criteria.
            </Text>
          </View>
        ) : (
          <View style={{ marginTop: 16, gap: 10 }}>
            {logs.map((log, index) => (
              <GlassCard key={log.id || index} padding={14} radius={Radius.lg}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Chip tone={getActionColor(log.action)}>
                    {log.action || 'ACTION'}
                  </Chip>
                  <Text style={{ fontSize: 11, color: theme.fgMuted, fontFamily: 'monospace' }}>
                    {log.created_at ? new Date(log.created_at).toLocaleString() : 'Just now'}
                  </Text>
                </View>

                <View style={{ marginTop: 8 }}>
                  <Text style={{ fontSize: 13, fontWeight: '600', color: theme.fg }}>
                    Actor: <Text style={{ fontWeight: '400', color: theme.fgMuted }}>{log.actor_name || log.actor_id || 'System'}</Text>
                  </Text>
                  {log.entity_type && (
                    <Text style={{ fontSize: 12, color: theme.fgMuted, marginTop: 2 }}>
                      Entity: <Text style={{ fontFamily: 'monospace', color: theme.fg }}>{log.entity_type} ({log.entity_id?.substring(0, 8)})</Text>
                    </Text>
                  )}
                  {log.details && (
                    <Text style={{ fontSize: 11, color: theme.fgMuted, marginTop: 4, fontFamily: 'monospace' }}>
                      {typeof log.details === 'object' ? JSON.stringify(log.details) : String(log.details)}
                    </Text>
                  )}
                </View>
              </GlassCard>
            ))}
          </View>
        )}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1 },
  topHeader: {
    marginTop: 54,
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
  headerTitle: { fontSize: 17, fontWeight: '700' },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 40,
  },
  subtitle: { fontSize: 13, lineHeight: 18 },
  filterInput: { flex: 1, fontSize: 13, paddingVertical: 4 },
});
