import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform } from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { Icons } from './Icons';
import { Radius } from '../../theme/tokens';

export type TabKey = 'home' | 'complaints' | 'voice' | 'notifications' | 'feed';

interface BottomNavProps {
  activeTab: TabKey;
  onTabPress: (tab: TabKey) => void;
  unreadCount?: number;
}

export const BottomNav: React.FC<BottomNavProps> = ({
  activeTab,
  onTabPress,
  unreadCount = 0,
}) => {
  const { theme, isDark } = useAppTheme();

  return (
    <View
      style={{
        position: 'absolute',
        bottom: 24,
        left: 20,
        right: 20,
        height: 68,
        borderRadius: Radius.pill,
        backgroundColor: theme.glassBgStrong,
        borderWidth: StyleSheet.hairlineWidth,
        borderColor: theme.glassBorder,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-around',
        paddingHorizontal: 8,
        zIndex: 100,
        ...(Platform.OS === 'web'
          ? {
              // @ts-ignore
              backdropFilter: 'blur(30px) saturate(180%)',
              // @ts-ignore
              WebkitBackdropFilter: 'blur(30px) saturate(180%)',
            }
          : {}),
        shadowColor: '#000000',
        shadowOffset: { width: 0, height: 10 },
        shadowOpacity: isDark ? 0.45 : 0.12,
        shadowRadius: 28,
        elevation: 10,
      }}
    >
      {/* Home */}
      <TouchableOpacity
        onPress={() => onTabPress('home')}
        activeOpacity={0.7}
        style={styles.tabButton}
      >
        <Icons.home
          size={22}
          color={activeTab === 'home' ? theme.fg : theme.fgMuted}
        />
      </TouchableOpacity>

      {/* Complaints List */}
      <TouchableOpacity
        onPress={() => onTabPress('complaints')}
        activeOpacity={0.7}
        style={styles.tabButton}
      >
        <Icons.list
          size={22}
          color={activeTab === 'complaints' ? theme.fg : theme.fgMuted}
        />
      </TouchableOpacity>

      {/* Center Floating Mic Button */}
      <TouchableOpacity
        onPress={() => onTabPress('voice')}
        activeOpacity={0.85}
        style={{
          width: 50,
          height: 50,
          borderRadius: 25,
          backgroundColor: theme.ctaBg,
          alignItems: 'center',
          justifyContent: 'center',
          shadowColor: isDark ? '#FFFFFF' : '#000000',
          shadowOffset: { width: 0, height: 4 },
          shadowOpacity: isDark ? 0.15 : 0.25,
          shadowRadius: 12,
          elevation: 6,
        }}
      >
        <Icons.mic size={24} color={theme.ctaFg} />
      </TouchableOpacity>

      {/* Notifications */}
      <TouchableOpacity
        onPress={() => onTabPress('notifications')}
        activeOpacity={0.7}
        style={[styles.tabButton, { position: 'relative' }]}
      >
        <Icons.bell
          size={22}
          color={activeTab === 'notifications' ? theme.fg : theme.fgMuted}
        />
        {unreadCount > 0 && (
          <View
            style={{
              position: 'absolute',
              top: 10,
              right: 14,
              width: 8,
              height: 8,
              borderRadius: 4,
              backgroundColor: '#E5484D',
              borderWidth: 1.5,
              borderColor: theme.bg,
            }}
          />
        )}
      </TouchableOpacity>

      {/* Community Feed */}
      <TouchableOpacity
        onPress={() => onTabPress('feed')}
        activeOpacity={0.7}
        style={styles.tabButton}
      >
        <Icons.users
          size={22}
          color={activeTab === 'feed' ? theme.fg : theme.fgMuted}
        />
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  tabButton: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
});

