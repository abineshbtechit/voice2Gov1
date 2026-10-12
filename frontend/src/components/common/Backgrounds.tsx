import React, { useEffect, useRef } from 'react';
import { View, StyleSheet, Animated, Easing, Platform } from 'react-native';
import Svg, { Defs, RadialGradient, Stop, Rect, Circle } from 'react-native-svg';

export const CloudBG: React.FC<{ isDark: boolean; opacity?: number }> = ({ isDark, opacity = 0.85 }) => {
  return (
    <View style={[StyleSheet.absoluteFill, { overflow: 'hidden', opacity, pointerEvents: 'none' }]}>
      <Svg height="100%" width="100%" style={StyleSheet.absoluteFill}>
        <Defs>
          <RadialGradient id="cloud1" cx="20%" cy="15%" rx="60%" ry="45%">
            <Stop offset="0%" stopColor={isDark ? 'rgba(70,84,140,0.35)' : 'rgba(200,214,255,0.60)'} stopOpacity="1" />
            <Stop offset="100%" stopColor="transparent" stopOpacity="0" />
          </RadialGradient>
          <RadialGradient id="cloud2" cx="85%" cy="25%" rx="55%" ry="45%">
            <Stop offset="0%" stopColor={isDark ? 'rgba(110,90,150,0.30)' : 'rgba(233,228,255,0.55)'} stopOpacity="1" />
            <Stop offset="100%" stopColor="transparent" stopOpacity="0" />
          </RadialGradient>
          <RadialGradient id="cloud3" cx="50%" cy="90%" rx="50%" ry="50%">
            <Stop offset="0%" stopColor={isDark ? 'rgba(40,90,130,0.35)' : 'rgba(217,240,255,0.70)'} stopOpacity="1" />
            <Stop offset="100%" stopColor="transparent" stopOpacity="0" />
          </RadialGradient>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#cloud1)" />
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#cloud2)" />
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#cloud3)" />
      </Svg>
    </View>
  );
};

export const MeshBG: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  return (
    <View style={[StyleSheet.absoluteFill, { overflow: 'hidden', pointerEvents: 'none' }]}>
      <Svg height="100%" width="100%" style={StyleSheet.absoluteFill}>
        <Defs>
          <RadialGradient id="mesh1" cx="30%" cy="30%" rx="40%" ry="40%">
            <Stop offset="0%" stopColor={isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'} stopOpacity="1" />
            <Stop offset="100%" stopColor="transparent" stopOpacity="0" />
          </RadialGradient>
          <RadialGradient id="mesh2" cx="80%" cy="70%" rx="40%" ry="40%">
            <Stop offset="0%" stopColor={isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'} stopOpacity="1" />
            <Stop offset="100%" stopColor="transparent" stopOpacity="0" />
          </RadialGradient>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#mesh1)" />
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#mesh2)" />
      </Svg>
    </View>
  );
};

export const AIOrb: React.FC<{ size?: number; spinning?: boolean; pulse?: boolean }> = ({
  size = 120,
  spinning = true,
  pulse = true,
}) => {
  const rotateAnim = useRef(new Animated.Value(0)).current;
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (spinning) {
      Animated.loop(
        Animated.timing(rotateAnim, {
          toValue: 1,
          duration: 8000,
          easing: Easing.linear,
          useNativeDriver: Platform.OS !== 'web',
        })
      ).start();
    }
  }, [spinning]);

  useEffect(() => {
    if (pulse) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.08,
            duration: 1800,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: Platform.OS !== 'web',
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 1800,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: Platform.OS !== 'web',
          }),
        ])
      ).start();
    }
  }, [pulse]);

  const spin = rotateAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });

  return (
    <Animated.View
      style={{
        width: size,
        height: size,
        alignItems: 'center',
        justifyContent: 'center',
        transform: [{ scale: pulseAnim }],
      }}
    >
      {/* Outer ambient glow */}
      <View
        style={[
          StyleSheet.absoluteFill,
          {
            borderRadius: size / 2,
            backgroundColor: 'rgba(200,214,255,0.35)',
            transform: [{ scale: 1.2 }],
          },
        ]}
      />

      {/* Spinning Conic/Radial Orb */}
      <Animated.View
        style={{
          width: size,
          height: size,
          borderRadius: size / 2,
          overflow: 'hidden',
          transform: [{ rotate: spin }],
          shadowColor: '#8C82BE',
          shadowOffset: { width: 0, height: 12 },
          shadowOpacity: 0.45,
          shadowRadius: 28,
          elevation: 12,
        }}
      >
        <Svg width={size} height={size}>
          <Defs>
            <RadialGradient id="orbGrad" cx="35%" cy="30%" rx="65%" ry="65%">
              <Stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.9" />
              <Stop offset="25%" stopColor="#E9E4FF" stopOpacity="0.9" />
              <Stop offset="50%" stopColor="#C8D6FF" stopOpacity="0.95" />
              <Stop offset="75%" stopColor="#D9F0FF" stopOpacity="0.9" />
              <Stop offset="100%" stopColor="#F5F1FF" stopOpacity="1" />
            </RadialGradient>
          </Defs>
          <Circle cx={size / 2} cy={size / 2} r={size / 2} fill="url(#orbGrad)" />
        </Svg>
      </Animated.View>
    </Animated.View>
  );
};
