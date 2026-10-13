import React from 'react';
import Svg, { Path, Rect, Circle, G } from 'react-native-svg';

export interface IconProps {
  size?: number;
  color?: string;
  strokeWidth?: number;
}

export const Icons = {
  mic: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Rect x="9" y="3" width="6" height="12" rx="3" stroke={color} strokeWidth={strokeWidth} />
      <Path d="M5 11a7 7 0 0 0 14 0M12 18v3" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
    </Svg>
  ),
  edit: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M4 20h4L20 8l-4-4L4 16v4z" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  home: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1v-9z" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  list: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
    </Svg>
  ),
  bell: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M6 8a6 6 0 0 1 12 0c0 7 3 8 3 8H3s3-1 3-8M10 21a2 2 0 0 0 4 0" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  user: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx="12" cy="8" r="4" stroke={color} strokeWidth={strokeWidth} />
      <Path d="M4 21c1-4 4-6 8-6s7 2 8 6" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
    </Svg>
  ),
  users: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
      <Circle cx="9" cy="7" r="4" stroke={color} strokeWidth={strokeWidth} />
      <Path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  mail: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Rect x="3" y="5" width="18" height="14" rx="2" stroke={color} strokeWidth={strokeWidth} />
      <Path d="M3 7l9 6 9-6" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  whatsapp: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M9.5 9.5c.2-.5.5-.5.8-.5h.6c.2 0 .4.1.5.3l.8 1.8c.1.3.1.5-.1.7l-.4.5c-.1.2-.2.3-.1.5.4.8 1 1.4 1.8 1.8.2.1.3 0 .5-.1l.5-.4c.2-.2.4-.2.7-.1l1.8.8c.2.1.3.3.3.5v.6c0 .3-.1.6-.5.8-.5.2-1.3.3-2.6-.3-1.6-.7-2.9-2-3.6-3.6-.6-1.3-.5-2.1-.3-2.6z"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  ),
  search: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx="11" cy="11" r="7" stroke={color} strokeWidth={strokeWidth} />
      <Path d="M20 20l-4-4" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
    </Svg>
  ),
  arrowLeft: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M19 12H5M11 6l-6 6 6 6" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  arrowRight: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M5 12h14M13 6l6 6-6 6" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  check: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M5 12l5 5L20 7" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  close: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M6 6l12 12M18 6L6 18" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
    </Svg>
  ),
  plus: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M12 5v14M5 12h14" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
    </Svg>
  ),
  filter: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M4 5h16l-6 8v6l-4-2v-4L4 5z" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  map: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2-6-2z M9 4v14 M15 6v14" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  pin: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M12 22s7-7 7-12a7 7 0 0 0-14 0c0 5 7 12 7 12z" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
      <Circle cx="12" cy="10" r="2.5" stroke={color} strokeWidth={strokeWidth} />
    </Svg>
  ),
  clock: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx="12" cy="12" r="9" stroke={color} strokeWidth={strokeWidth} />
      <Path d="M12 7v5l3 2" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
    </Svg>
  ),
  sparkle: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l3 3M15 15l3 3M18 6l-3 3M9 15l-3 3" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
    </Svg>
  ),
  globe: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx="12" cy="12" r="9" stroke={color} strokeWidth={strokeWidth} />
      <Path d="M3 12h18M12 3c2.5 3 4 6 4 9s-1.5 6-4 9c-2.5-3-4-6-4-9s1.5-6 4-9z" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
    </Svg>
  ),
  chevronDown: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M6 9l6 6 6-6" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  chevronRight: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M9 6l6 6-6 6" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  play: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M7 5l12 7-12 7V5z" fill={color} stroke={color} strokeWidth={strokeWidth} strokeLinejoin="round" />
    </Svg>
  ),
  pause: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Rect x="7" y="5" width="3" height="14" rx="1" fill={color} />
      <Rect x="14" y="5" width="3" height="14" rx="1" fill={color} />
    </Svg>
  ),
  heart: ({ size = 22, color = 'currentColor', strokeWidth = 1.7, filled = false }: IconProps & { filled?: boolean }) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill={filled ? color : 'none'}>
      <Path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  building: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M4 21V7l8-4 8 4v14M4 21h16M9 21v-6h6v6" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  camera: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M4 8h3l2-3h6l2 3h3v11H4V8z" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
      <Circle cx="12" cy="13" r="4" stroke={color} strokeWidth={strokeWidth} />
    </Svg>
  ),
  trash: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  water: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M12 3s7 8 7 13a7 7 0 0 1-14 0c0-5 7-13 7-13z" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  road: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M8 3L4 21M16 3l4 18M12 3v3M12 10v3M12 17v3" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
    </Svg>
  ),
  bulb: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M9 18h6M10 21h4M7 10a5 5 0 1 1 10 0c0 3-2 4-2 6H9c0-2-2-3-2-6z" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  logout: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  wifiOff: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M3 3l18 18M9 17a4 4 0 0 1 6 0M5 13a10 10 0 0 1 4-2.5M19 13a10 10 0 0 0-3-2M2 8.5A15 15 0 0 1 8 5.5M22 8.5a15 15 0 0 0-6-3M12 21h.01" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
    </Svg>
  ),
  refresh: ({ size = 22, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M23 4v6h-6M1 20v-6h6" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
      <Path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ),
  eye: ({ size = 20, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Circle
        cx="12"
        cy="12"
        r="3"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  ),
  eyeOff: ({ size = 20, color = 'currentColor', strokeWidth = 1.7 }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M1 1l22 22"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  ),
};

