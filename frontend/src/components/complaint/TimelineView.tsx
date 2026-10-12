import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { GlassCard } from '../common/UIComponents';
import { Icons } from '../common/Icons';
import { Radius } from '../../theme/tokens';

export interface TimelineEvent {
  title: string;
  description: string;
  status: 'done' | 'active' | 'pending';
  timestamp?: string;
}

export const TimelineView: React.FC<{ events: TimelineEvent[] }> = ({ events }) => {
  const { theme, isDark } = useAppTheme();

  return (
    <GlassCard padding={18} radius={Radius.xl}>
      <View style={{ gap: 18 }}>
        {events.map((event, index) => {
          const isDone = event.status === 'done';
          const isActive = event.status === 'active';

          return (
            <View key={index} style={{ flexDirection: 'row', gap: 14 }}>
              {/* Indicator Dot */}
              <View style={styles.dotContainer}>
                <View
                  style={[
                    styles.dot,
                    {
                      backgroundColor: isDone
                        ? '#2FBF71'
                        : isActive
                        ? '#F5A524'
                        : isDark
                        ? 'rgba(255,255,255,0.15)'
                        : 'rgba(0,0,0,0.1)',
                    },
                  ]}
                />
                {index < events.length - 1 && (
                  <View
                    style={[
                      styles.connectorLine,
                      {
                        backgroundColor: isDone
                          ? '#2FBF71'
                          : theme.hairline,
                      },
                    ]}
                  />
                )}
              </View>

              {/* Event Body */}
              <View style={{ flex: 1, paddingBottom: index < events.length - 1 ? 8 : 0 }}>
                <View style={styles.eventHeader}>
                  <Text
                    style={[
                      styles.eventTitle,
                      {
                        color: theme.fg,
                        fontWeight: isActive ? '700' : '600',
                      },
                    ]}
                  >
                    {event.title}
                  </Text>
                  {event.timestamp && (
                    <Text style={[styles.eventTime, { color: theme.fgMuted }]}>
                      {event.timestamp}
                    </Text>
                  )}
                </View>
                <Text style={[styles.eventDesc, { color: theme.fgMuted }]}>
                  {event.description}
                </Text>
              </View>
            </View>
          );
        })}
      </View>
    </GlassCard>
  );
};

const styles = StyleSheet.create({
  dotContainer: {
    alignItems: 'center',
    width: 14,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginTop: 4,
  },
  connectorLine: {
    width: 2,
    flex: 1,
    marginTop: 4,
  },
  eventHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 2,
  },
  eventTitle: {
    fontSize: 14,
  },
  eventTime: {
    fontSize: 11,
    fontFamily: 'monospace',
  },
  eventDesc: {
    fontSize: 12,
    lineHeight: 18,
  },
});

