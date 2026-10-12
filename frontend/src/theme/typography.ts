import { TextStyle } from 'react-native';

export const Typography: Record<string, TextStyle> = {
  display: {
    fontSize: 44,
    fontWeight: '700',
    letterSpacing: -1.2,
    lineHeight: 46,
  },
  title1: {
    fontSize: 34,
    fontWeight: '700',
    letterSpacing: -1,
    lineHeight: 38,
  },
  title2: {
    fontSize: 28,
    fontWeight: '700',
    letterSpacing: -0.8,
    lineHeight: 32,
  },
  headline: {
    fontSize: 22,
    fontWeight: '600',
    letterSpacing: -0.4,
    lineHeight: 28,
  },
  body: {
    fontSize: 17,
    fontWeight: '400',
    letterSpacing: -0.2,
    lineHeight: 24,
  },
  bodyEm: {
    fontSize: 17,
    fontWeight: '600',
    letterSpacing: -0.2,
    lineHeight: 24,
  },
  callout: {
    fontSize: 15,
    fontWeight: '400',
    letterSpacing: -0.1,
    lineHeight: 22,
  },
  caption: {
    fontSize: 13,
    fontWeight: '500',
    letterSpacing: 0,
    lineHeight: 18,
  },
  micro: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
  },
  mono: {
    fontFamily: 'monospace',
    fontSize: 13,
    letterSpacing: 0,
  },
};

