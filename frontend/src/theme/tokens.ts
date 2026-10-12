// Voice2Gov Design Tokens (Faithfully ported from design handoff tokens.css)

export const Colors = {
  // Neutral Scale (Apple pure grays)
  n0: '#FFFFFF',
  n25: '#FBFBFB', // light bg default
  n50: '#F6F6F7', // light bg sunk
  n100: '#EEEEEF',
  n150: '#E4E4E6',
  n200: '#D6D6D9',
  n300: '#B8B8BC',
  n400: '#94949A', // light fg faint
  n500: '#72727A', // light fg muted
  n600: '#525258',
  n700: '#38383D',
  n800: '#242428',
  n850: '#18181B',
  n900: '#101012', // light fg default / dark button fg
  n950: '#08080A', // dark bg default
  n1000: '#000000',

  // Status (The ONLY allowed colors)
  status: {
    live: '#2FBF71',    // green: resolved, active indicator
    pending: '#F5A524', // amber: processing, in progress
    urgent: '#E5484D',  // red: urgent, recording, delete
    info: '#4C8DFF',    // blue: informational, AI updates
  },

  // Signature AI Gradient tokens (AI orb & voice waveform only)
  ai: {
    lavender: '#E9E4FF',
    periwinkle: '#C8D6FF',
    nearWhite: '#F5F1FF',
    paleCyan: '#D9F0FF',
  },
};

export const LightTheme = {
  dark: false,
  bg: '#FBFBFB',
  bgElev: '#FFFFFF',
  bgSunk: '#F6F6F7',
  fg: '#101012',
  fgMuted: '#72727A',
  fgFaint: '#94949A',
  hairline: 'rgba(0,0,0,0.08)',
  hairlineStrong: 'rgba(0,0,0,0.14)',
  glassBg: 'rgba(255,255,255,0.72)',
  glassBgStrong: 'rgba(255,255,255,0.85)',
  glassBorder: 'rgba(255,255,255,0.90)',
  ctaBg: '#101012',
  ctaFg: '#FAFAFA',
};

export const DarkTheme = {
  dark: true,
  bg: '#08080A',
  bgElev: '#131316',
  bgSunk: '#050507',
  fg: '#FAFAFA',
  fgMuted: '#8A8A92',
  fgFaint: '#5A5A62',
  hairline: 'rgba(255,255,255,0.08)',
  hairlineStrong: 'rgba(255,255,255,0.16)',
  glassBg: 'rgba(28,28,32,0.65)',
  glassBgStrong: 'rgba(38,38,44,0.80)',
  glassBorder: 'rgba(255,255,255,0.10)',
  ctaBg: '#FAFAFA',
  ctaFg: '#101012',
};

export type ThemeType = typeof LightTheme;

export const Radius = {
  xs: 8,
  sm: 12,
  md: 16,
  lg: 22,
  xl: 28,
  pill: 999,
};

export const Spacing = {
  s1: 4,
  s2: 8,
  s3: 12,
  s4: 16,
  s5: 20,
  s6: 24,
  s8: 32,
  s10: 40,
  s12: 48,
  s16: 64,
};

