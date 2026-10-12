import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { GlassCard, Chip } from '../common/UIComponents';
import { Radius } from '../../theme/tokens';

export interface ComplaintCardProps {
  id: string;
  title: string;
  departmentName?: string;
  status: string;
  createdAt: string;
  priorityScore?: number;
  onPress: () => void;
}

export const ComplaintCard: React.FC<ComplaintCardProps> = ({
  id,
  title,
  departmentName = 'Municipal Department',
  status,
  createdAt,
  priorityScore,
  onPress,
}) => {
  const { theme } = useAppTheme();

  const getTone = (st: string) => {
    if (st === 'COMPLETED') return 'live';
    if (st === 'ONGOING' || st === 'PROCESSING') return 'pending';
    if (st === 'REJECTED') return 'urgent';
    return 'info';
  };

  return (
    <GlassCard padding={16} radius={Radius.lg} style={{ marginBottom: 10 }}>
      <TouchableOpacity onPress={onPress}>
        <View style={styles.topRow}>
          <Text style={[styles.idText, { color: theme.fgMuted }]}>
            {id.substring(0, 8).toUpperCase()}
          </Text>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            {priorityScore && priorityScore > 60 && (
              <Chip tone="urgent">Priority {Math.round(priorityScore)}</Chip>
            )}
            <Chip tone={getTone(status)}>{status}</Chip>
          </View>
        </View>

        <Text style={[styles.titleText, { color: theme.fg }]}>{title}</Text>

        <View style={styles.footerRow}>
          <Text style={[styles.metaText, { color: theme.fgMuted }]}>
            {departmentName}
          </Text>
          <Text style={[styles.metaText, { color: theme.fgMuted }]}>
            {new Date(createdAt).toLocaleDateString()}
          </Text>
        </View>
      </TouchableOpacity>
    </GlassCard>
  );
};

const styles = StyleSheet.create({
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  idText: {
    fontSize: 12,
    fontFamily: 'monospace',
    fontWeight: '600',
  },
  titleText: {
    fontSize: 16,
    fontWeight: '600',
    letterSpacing: -0.2,
    lineHeight: 22,
  },
  footerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 10,
  },
  metaText: {
    fontSize: 12,
  },
});

