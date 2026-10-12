import { StyleSheet, ViewStyle } from 'react-native';
import { Radius, Spacing } from './tokens';

export const CommonStyles = StyleSheet.create({
  fullFlex: {
    flex: 1,
  },
  centerContent: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  rowCenter: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  safeTopPadding: {
    paddingTop: 64,
  },
  screenHorizontalPadding: {
    paddingHorizontal: 20,
  },
  floatingBottomCta: {
    position: 'absolute',
    bottom: 40,
    left: 20,
    right: 20,
  },
});

