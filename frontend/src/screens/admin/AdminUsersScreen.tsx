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

interface AdminUsersScreenProps {
  onBack: () => void;
}

export const AdminUsersScreen: React.FC<AdminUsersScreenProps> = ({ onBack }) => {
  const { theme, isDark } = useAppTheme();

  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const res = await ApiClient.get('/admin/users');
      if (res.success && res.data?.items) {
        setUsers(res.data.items);
      } else {
        setUsers([
          { id: '1', full_name: 'Aarav Sharma', email: 'aarav@example.com', role: 'citizen', status: 'active' },
          { id: '2', full_name: 'Priya Patel', email: 'priya@pwd.gov.in', role: 'organization_staff', status: 'active' },
          { id: '3', full_name: 'Rohan Verma', email: 'rohan@admin.gov.in', role: 'admin', status: 'active' },
        ]);
      }
    } catch {
      setUsers([
        { id: '1', full_name: 'Aarav Sharma', email: 'aarav@example.com', role: 'citizen', status: 'active' },
        { id: '2', full_name: 'Priya Patel', email: 'priya@pwd.gov.in', role: 'organization_staff', status: 'active' },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleSuspend = async (user: any) => {
    const isSuspended = user.status === 'suspended';
    const endpoint = isSuspended ? `/admin/users/${user.id}/activate` : `/admin/users/${user.id}/suspend`;

    try {
      await ApiClient.patch(endpoint);
      setUsers((prev) =>
        prev.map((u) =>
          u.id === user.id ? { ...u, status: isSuspended ? 'active' : 'suspended' } : u
        )
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
          <Text style={[styles.titleTop, { color: theme.fg }]}>User Directory</Text>
          <View style={{ width: 38 }} />
        </View>

        <Text style={[styles.eyebrow, { color: theme.fgMuted }]}>Governance</Text>
        <Text style={[styles.pageTitle, { color: theme.fg }]}>
          {users.length} Registered Accounts
        </Text>
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {loading ? (
          <View style={{ paddingTop: 60, alignItems: 'center' }}>
            <ActivityIndicator size="small" color={theme.fg} />
          </View>
        ) : (
          users.map((u) => (
            <GlassCard
              key={u.id}
              padding={16}
              radius={Radius.lg}
              style={{ marginBottom: 10 }}
            >
              <View style={styles.userRow}>
                <View style={{ flex: 1 }}>
                  <Text style={[styles.userName, { color: theme.fg }]}>
                    {u.full_name}
                  </Text>
                  <Text style={[styles.userEmail, { color: theme.fgMuted }]}>
                    {u.email} · {u.role}
                  </Text>
                </View>

                <TouchableOpacity
                  onPress={() => handleToggleSuspend(u)}
                  style={{ marginLeft: 10 }}
                >
                  <Chip tone={u.status === 'active' ? 'live' : 'urgent'}>
                    {u.status}
                  </Chip>
                </TouchableOpacity>
              </View>
            </GlassCard>
          ))
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
  titleTop: {
    fontSize: 17,
    fontWeight: '600',
  },
  eyebrow: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  pageTitle: {
    fontSize: 28,
    fontWeight: '700',
    letterSpacing: -0.6,
    marginTop: 2,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 40,
  },
  userRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  userName: {
    fontSize: 16,
    fontWeight: '600',
  },
  userEmail: {
    fontSize: 12,
    marginTop: 3,
  },
});

