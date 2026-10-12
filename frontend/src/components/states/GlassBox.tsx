import React from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { Radius } from '../../theme/tokens';

export const GlassBox: React.FC<{
  size?: number;
  children: React.ReactNode;
  style?: ViewStyle;
}> = ({ size = 140, children, style }) => {
  const { theme, isDark } = useAppTheme();

  return (
    <View
      style={[
        {
          width: size,
          height: size,
          borderRadius: Radius.xl,
          backgroundColor: theme.glassBgStrong,
          borderWidth: StyleSheet.hairlineWidth,
          borderColor: theme.glassBorder,
          alignItems: 'center',
          justifyContent: 'center',
          shadowColor: '#000000',
          shadowOffset: { width: 0, height: 10 },
          shadowOpacity: isDark ? 0.4 : 0.08,
          shadowRadius: 24,
          elevation: 6,
        },
        style,
      ]}
    >
      {children}
    </View>
  );
};

