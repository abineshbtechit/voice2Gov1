import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { Icons } from './Icons';

interface BackHeaderProps {
  title?: string;
  onBack: () => void;
  right?: React.ReactNode;
}

export const BackHeader: React.FC<BackHeaderProps> = ({
  title,
  onBack,
  right,
}) => {
  const { theme } = useAppTheme();

  return (
    <View style={styles.container}>
      <TouchableOpacity
        onPress={onBack}
        style={[
          styles.circleBtn,
          {
            backgroundColor: theme.glassBg,
            borderColor: theme.glassBorder,
          },
        ]}
      >
        <Icons.arrowLeft size={18} color={theme.fg} />
      </TouchableOpacity>

      {title ? (
        <Text style={[styles.titleText, { color: theme.fg }]}>{title}</Text>
      ) : (
        <View />
      )}

      <View style={styles.rightSlot}>{right || <View style={{ width: 38 }} />}</View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginTop: 64,
    paddingHorizontal: 20,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  circleBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth,
  },
  titleText: {
    fontSize: 17,
    fontWeight: '600',
    letterSpacing: -0.2,
  },
  rightSlot: {
    minWidth: 38,
    alignItems: 'flex-end',
  },
});

