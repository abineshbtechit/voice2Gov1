import React from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';
import { MeshBG } from '../../components/common/Backgrounds';
import { GlassCard, BigCTA } from '../../components/common/UIComponents';
import { Icons } from '../../components/common/Icons';
import { Radius } from '../../theme/tokens';

interface ProfileScreenProps {
  onBack: () => void;
}

export const ProfileScreen: React.FC<ProfileScreenProps> = ({ onBack }) => {
  const { theme, isDark, toggleTheme } = useAppTheme();
  const { user, logout } = useAuth();

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
      <MeshBG isDark={isDark} />

      {/* Header */}
      <View style={styles.header}>
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
        <Text style={[styles.headerTitle, { color: theme.fg }]}>Profile</Text>
        <View style={{ width: 38 }} />
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {/* User Card */}
        <GlassCard strong radius={Radius.xl} padding={22}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 16 }}>
            <View
              style={[
                styles.avatarCircle,
                { backgroundColor: isDark ? '#38383D' : '#D6D6D9' },
              ]}
            >
              <Text
                style={[
                  styles.avatarText,
                  { color: isDark ? '#FAFAFA' : '#101012' },
                ]}
              >
                {initials}
              </Text>
            </View>

            <View style={{ flex: 1 }}>
              <Text style={[styles.profileName, { color: theme.fg }]}>
                {user?.full_name || 'Citizen User'}
              </Text>
              <Text style={[styles.profileEmail, { color: theme.fgMuted }]}>
                {user?.email || 'citizen@voice2gov.in'}
              </Text>
              <Text style={[styles.profileRole, { color: theme.fgMuted }]}>
                Role: {user?.role || 'Citizen'}
              </Text>
            </View>
          </View>
        </GlassCard>

        {/* Preferences Section */}
        <Text style={[styles.sectionHeading, { color: theme.fgMuted, marginTop: 28 }]}>
          Preferences & Interface
        </Text>

        <GlassCard padding={16} radius={Radius.lg}>
          <TouchableOpacity
            onPress={toggleTheme}
            style={{
              flexDirection: 'row',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
              <Icons.sparkle size={20} color={theme.fg} />
              <Text style={{ fontSize: 15, fontWeight: '600', color: theme.fg }}>
                Theme mode
              </Text>
            </View>
            <Text style={{ fontSize: 13, color: theme.fgMuted }}>
              {isDark ? 'Dark mode' : 'Light mode'} (Tap to switch)
            </Text>
          </TouchableOpacity>
        </GlassCard>

        {/* Civic Statistics */}
        <Text style={[styles.sectionHeading, { color: theme.fgMuted, marginTop: 24 }]}>
          Civic Contribution
        </Text>
        <GlassCard padding={18} radius={Radius.lg}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-around' }}>
            <View style={{ alignItems: 'center' }}>
              <Text style={[styles.statNumber, { color: theme.fg }]}>14</Text>
              <Text style={[styles.statLabel, { color: theme.fgMuted }]}>
                Reported
              </Text>
            </View>
            <View style={{ width: 1, backgroundColor: theme.hairline }} />
            <View style={{ alignItems: 'center' }}>
              <Text style={[styles.statNumber, { color: '#2FBF71' }]}>9</Text>
              <Text style={[styles.statLabel, { color: theme.fgMuted }]}>
                Resolved
              </Text>
            </View>
            <View style={{ width: 1, backgroundColor: theme.hairline }} />
            <View style={{ alignItems: 'center' }}>
              <Text style={[styles.statNumber, { color: '#F5A524' }]}>5</Text>
              <Text style={[styles.statLabel, { color: theme.fgMuted }]}>
                Ongoing
              </Text>
            </View>
          </View>
        </GlassCard>

        {/* Security & Logout */}
        <View style={{ marginTop: 32 }}>
          <BigCTA
            variant="destructive"
            onPress={logout}
            icon={<Icons.logout size={18} color="#FFFFFF" />}
          >
            Sign out
          </BigCTA>
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
  header: {
    marginTop: 64,
    paddingHorizontal: 20,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
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
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 110,
  },
  avatarCircle: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 20,
    fontWeight: '700',
  },
  profileName: {
    fontSize: 18,
    fontWeight: '700',
    letterSpacing: -0.2,
  },
  profileEmail: {
    fontSize: 13,
    marginTop: 2,
  },
  profileRole: {
    fontSize: 12,
    marginTop: 2,
  },
  sectionHeading: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  statNumber: {
    fontSize: 24,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: 12,
    marginTop: 2,
  },
});

